import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from .core import ROOT, TEMPLATES, classifier, configured_model, digest, match_assets, save, task_input, verify_claims, safe_rework
from .copy import ReferenceVisualCopy
from production.intent import analyze
from production.planner import plan
from .comparison_contract import missing_comparison


def fingerprint():
    files = [* (ROOT/'workflow').glob('*.py'), ROOT/'template_catalog.yaml',
             * (ROOT/'customer_templates').glob('*.py'), * (ROOT/'customer_templates/configs').glob('*.json'),
             ROOT/'customer_templates/registry.json', ROOT/'customer_templates/component_registry_v5.json']
    files += list((ROOT/'planning').glob('*.py')) + list((ROOT/'planning').glob('*.json'))
    files += list((ROOT/'production').glob('*.py')) + [ROOT/'production_rules.yaml', ROOT/'qc_rules.yaml', ROOT/'rendering/engine.py']
    files += list((ROOT/'customer_templates/components-v5').glob('*.png')) + list((ROOT/'assets/customer_reference').rglob('*.png'))
    return digest({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)})


def packet_file_hashes(packet):
    result={}
    if not packet:return result
    entries=list(packet.get('sources',{}).values())+list(packet.get('assets',{}).values())
    for entry in entries:
        for key in ('path','license_path'):
            if key not in entry:continue
            path=(ROOT/entry[key]).resolve()
            result[entry[key]]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_relative_to(ROOT) and path.is_file() else 'MISSING_OR_FORBIDDEN'
    return result


def content_qc(copy, sources):
    errors = verify_claims(copy['claims'], sources)
    if copy.get('manifest', {}).get('category') == 'compare':
        errors.append({'code': 'COMPARISON_BUSINESS_PACKET_REQUIRED', 'detail': 'Use typed comparison fields and exact source bindings; visual-only text is not business content'})
    if not copy['direct_answer'] or not copy['body'].startswith(copy['direct_answer']):
        errors.append({'code': 'DIRECT_ANSWER_MISSING'})
    if copy['placeholders']:
        errors.append({'code': 'PLACEHOLDER_CONTENT'})
    if len(copy['coverage']) != len(copy['required_questions']):
        errors.append({'code': 'QUESTION_COVERAGE'})
    claims = {c['id'] for c in copy['claims']}
    for index, item in enumerate(copy['coverage']):
        if item['question'] != copy['required_questions'][index] or not item['answer'] or not set(item['claim_ids']) <= claims:
            errors.append({'code': 'QUESTION_COVERAGE', 'element': index})
    signatures = [digest(p['values']) for p in copy['manifest']['pages']]
    if len(set(signatures)) != len(signatures):
        errors.append({'code': 'DUPLICATE_PAGE'})
    return {'errors': errors, 'semantic_review_required': True,
            'checks': ['direct_answer_first', 'evidence_hash_and_kind', 'question_mapping', 'duplicate_pages'],
            'limitation': '规则校验不能替代语义、图片身份与视觉人工验收'}


class Batch:
    def __init__(self, output, review_references=False, provider=None, copy_provider=None, data_packets=None):
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.output/'tasks.sqlite3')
        self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, input_hash TEXT, dependency_hash TEXT, status TEXT, result TEXT, attempts INTEGER)')
        self.db.execute('CREATE TABLE IF NOT EXISTS events (id TEXT, status TEXT, detail TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP)')
        self.provider = provider
        self.review_references = review_references
        self.copy_provider = copy_provider or ReferenceVisualCopy()
        self.data_packets = data_packets or {}

    def run(self, raw, retry=False):
        task = task_input(raw)
        identity = task['task_id']
        input_hash = digest(task)
        dependency_hash = digest({'code': fingerprint(), 'review_references': self.review_references,
                                  'model': getattr(self.provider, 'model', type(self.provider).__name__),
                                  'copy_provider': type(self.copy_provider).__name__, 'packet': self.data_packets.get(identity),
                                  'packet_files': packet_file_hashes(self.data_packets.get(identity))})
        previous = self.db.execute('SELECT input_hash,dependency_hash,status,result,attempts FROM tasks WHERE id=?', (identity,)).fetchone()
        if previous and previous[0] != input_hash:
            raise ValueError('TASK_ID_COLLISION: task ID already bound to another input')
        if previous and previous[1] == dependency_hash and previous[2] != 'READY' and not retry:
            result = json.loads(previous[3])
            folder = self.output/result['artifact_directory']
            if all((folder/path).is_file() and hashlib.sha256((folder/path).read_bytes()).hexdigest() == value for path,value in result.get('artifact_hashes', {}).items()):
                return {**result, 'resumed': True}
        attempt = previous[4]+1 if previous else 1
        folder = self.output/identity/f'attempt-{attempt:03d}'
        folder.mkdir(parents=True, exist_ok=False)
        self.db.execute('INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?)', (identity,input_hash,dependency_hash,'READY','{}',attempt))
        self.db.execute('INSERT INTO events(id,status,detail) VALUES (?,?,?)', (identity,'READY','queued'))
        self.db.commit()
        result = {'task_id': identity, 'status': 'READY', 'generated': False, 'errors': [],
                  'artifact_directory': str(folder.relative_to(self.output)), 'attempt': attempt,
                  'customer_approved': False, 'delivery_ready': False, 'reworks': 0}
        try:
            from planning.pipeline import run_task
            from planning.intent import RuleIntentParser
            planned = run_task(task, folder, self.data_packets.get(identity), render_review=self.review_references, parser=RuleIntentParser(self.provider))
            result.update(planned)
            result['artifact_directory'] = str(folder.relative_to(self.output))
            result['attempt'] = attempt

        except Exception as error:
            result.update(status='BLOCKED')
            result['errors'].append({'code': 'PIPELINE_FAILURE', 'type': type(error).__name__, 'detail': str(error)[:500]})
        if result['status'] == 'READY': result['status'] = 'REVIEW'
        save(folder/'qc_report.json', {'status': result['status'], 'generated': result['generated'],
             'customer_approved': False, 'delivery_ready': False, 'errors': result['errors'],
             'content_report': 'content_qc.json' if (folder/'content_qc.json').exists() else None,
             'layout_report': result.get('render_directory','') + '/qc_report.json' if result['generated'] else None})
        save(folder/'result.json', result)
        result['artifact_hashes'] = {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
        self.db.execute('UPDATE tasks SET status=?,result=? WHERE id=?', (result['status'],json.dumps(result,ensure_ascii=False),identity))
        self.db.execute('INSERT INTO events(id,status,detail) VALUES (?,?,?)', (identity,result['status'],json.dumps(result['errors'],ensure_ascii=False)))
        self.db.commit()
        return result

    def render_review(self, task, selection, provider, folder, result):
        from customer_templates.engine import render
        if selection.get('category') == 'comparison':
            raise ValueError('COMPARISON_BUSINESS_PACKET_REQUIRED: visual-only provider retired')
        component_data = json.loads((ROOT/'customer_templates/component_registry_v5.json').read_text())
        registry = {key: {**value, 'purposes': ['comparison'], 'license_status': 'unknown'}
                    for key,value in component_data['assets'].items()}
        assets = []
        sources = {}
        for source_id, subject in [('left', 'lemon_drink'), ('right', 'cola')]:
            matches = match_assets(registry, subject, 'comparison', minimum=(150,200), authorized=False)
            if not matches: raise ValueError('MATCHING_REFERENCE_ASSET_MISSING: '+subject)
            asset = matches[0]
            assets.append(asset)
            sources[source_id] = {'kind': 'visual', 'path': asset['path'], 'sha256': asset['sha256'],
                                  'locator': '完整裁切图；仅支持画面观察', 'reference': asset.get('reference'),
                                  'scientific_evidence': False}
        copy = provider.generate(task)
        save(folder/'copy.json', copy)
        save(folder/'intent.json', {'original_query': task['original_query'], 'direction': task['direction'],
             'direct_answer': copy['direct_answer'], 'must_answer': copy['required_questions'],
             'coverage': copy['coverage'], 'scope': copy['scope']})
        save(folder/'evidence.json', {'claims': copy['claims'], 'sources': sources})
        save(folder/'assets.json', assets)
        (folder/'post.md').write_text('# '+copy['title']+'\n\n'+copy['body']+'\n', encoding='utf-8')
        qc = content_qc(copy, sources)
        save(folder/'content_qc.json', qc)
        if qc['errors']: raise ValueError('CONTENT_QC_FAILED')
        manifest = copy['manifest']
        for attempt in range(4):
            render_folder = folder/f'render-{attempt}'
            render(manifest, render_folder)
            report = json.loads((render_folder/'qc_report.json').read_text())
            if not report['errors']:
                result.update(generated=True, render_directory=str(render_folder.relative_to(folder)))
                break
            repaired = safe_rework(manifest, attempt)
            if repaired is None: raise ValueError('LAYOUT_QC_FAILED: '+json.dumps(report['errors'],ensure_ascii=False)[:300])
            manifest = repaired
            result['reworks'] += 1
        else: raise ValueError('REWORK_LIMIT_EXCEEDED')
        save(folder/'render_manifest.json', manifest)
        result.update(status='REVIEW', page_count=3)
        result['errors'].append({'code': 'REFERENCE_LICENSE_UNKNOWN', 'detail': '仅客户参考图内部审阅，非发布授权'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review-references', action='store_true')
    parser.add_argument('--retry', action='store_true')
    parser.add_argument('--data', type=Path, help='JSON mapping task ID to repository packet path')
    args = parser.parse_args()
    packets = {}
    if args.data:
        for identity, value in json.loads(args.data.read_text()).items():
            path=(ROOT/value).resolve()
            if not path.is_relative_to(ROOT):raise ValueError('PACKET_PATH_OUTSIDE_REPOSITORY')
            packets[identity]=json.loads(path.read_text())
    batch = Batch(args.output, args.review_references, configured_model(), data_packets=packets)
    results = []
    for raw in json.loads(args.input.read_text()):
        try: results.append(batch.run(raw, args.retry))
        except Exception as error: results.append({'task_id': raw.get('task_id'), 'status':'BLOCKED','generated':False,'errors':[{'code':'INPUT_OR_RESUME_ERROR','detail':str(error)}]})
    report = {'tasks': results, 'generated_groups': sum(r['generated'] for r in results),
              'not_rendered': sum(not r['generated'] for r in results),
              'states': {state: sum(r['status']==state for r in results) for state in ['READY','REVIEW','BLOCKED','DELIVERED']}}
    save(args.output/'batch_report.json', report)
    print(json.dumps({key:value for key,value in report.items() if key != 'tasks'}, ensure_ascii=False))


if __name__ == '__main__': main()
