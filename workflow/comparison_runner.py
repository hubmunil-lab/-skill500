"""Narrow comparison rework: structured provider -> semantic QC -> fixed renderer."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
from rendering.engine import ROOT, DEFAULT_FONT, font_data, MEASURE_JS, sha
from delivery.engine import finite_json
from customer_templates.engine import html, inspect, comparison, project
from customer_templates.prepare import configs, REGISTRY
from customer_templates.compare_revision import prepare as prepare_visual
from .core import task_input, save, digest
from .comparison_contract import business_qc, compile_copy, copy_qc, missing_comparison


class EvidenceComparisonProvider:
    """Deterministic, typed source adapter; never falls back to unrelated prose."""
    def __init__(self, packet): self.packet=packet

    def generate(self, task): return compile_copy(self.packet,task)

    def cache_key(self, task):
        return digest({'query':task['search_query'],'direction':task['direction'],
                       'original_query':task['original_query'],'packet':self.packet,'provider':'comparison-business-v2'})


def validate_assets(packet):
    errors=[]
    for side,subject in zip(('left','right'),packet['subjects']):
        asset=packet.get('assets',{}).get(side,{})
        try:
            path=(ROOT/asset['path']).resolve();license_path=(ROOT/asset['license_path']).resolve()
            if not path.is_relative_to(ROOT) or not license_path.is_relative_to(ROOT):raise ValueError('outside repository')
            if sha(path)!=asset['sha256'] or sha(license_path)!=asset['license_sha256']:raise ValueError('file/license hash mismatch')
            if asset.get('subject_id')!=subject['id'] or asset.get('sku')!=subject['sku']:raise ValueError('SKU/image mismatch')
            if packet['mode']=='synthetic_test':
                if asset.get('permitted_use')!='synthetic_test' or asset.get('license')!='CC0-1.0':raise ValueError('fixture rights missing')
            else:
                if asset.get('permitted_use')!='publication' or asset.get('license_status')!='authorized' or asset.get('kind')!='real_photo':raise ValueError('publication photo rights missing')
            with Image.open(path) as image:
                if list(image.size)!=asset['size'] or min(image.size)<1000:raise ValueError('size below minimum or metadata mismatch')
                if image.mode!='RGBA':raise ValueError('transparent channel missing')
        except (KeyError,OSError,ValueError) as error:
            errors.append({'code':'ASSET_OR_LICENSE_INVALID','side':side,'detail':str(error)})
    return errors


def resolved_layout(manifest, packet, revision, before=False):
    originals=sorted([c for c in configs() if c['category']=='compare'],key=lambda c:c['page_number'])
    components={'assets':{},'backgrounds':{}}
    old=json.loads((ROOT/REGISTRY).read_text())
    selected=[]
    for original in originals:
        if before:
            import copy
            config=copy.deepcopy(original)
            components['backgrounds'][config['id']]=old['backgrounds'][config['id']]
        else:
            entry=revision['templates'][original['id']]
            if sha(ROOT/entry['path'])!=entry['sha256']:raise ValueError('LOCKED_CONFIG_CHANGED')
            config=json.loads((ROOT/entry['path']).read_text())
            components['backgrounds'][config['id']]=revision['backgrounds'][config['id']]
        if any(a['box']!=b['box'] for a,b in zip(original['slots'],config['slots'])):raise ValueError('LOCKED_COORDINATES_CHANGED')
        if sha(ROOT/components['backgrounds'][config['id']]['path'])!=components['backgrounds'][config['id']]['sha256']:raise ValueError('LOCKED_BACKGROUND_CHANGED')
        config['item_order']=[s['id'] for s in packet['subjects']]
        for side,subject in zip(('left','right'),packet['subjects']):
            slot=next(s for s in config['slots'] if s['id']==side+'_photo')
            slot['subject']=subject['id']
            components['assets']['compare-'+side+'_photo']={**packet['assets'][side],'subject':subject['id']}
        selected.append(config)
    if len(manifest['pages'])!=3 or manifest['item_order']!=[s['id'] for s in packet['subjects']]:raise ValueError('PAGE_OR_SUBJECT_ORDER')
    for page,config in zip(manifest['pages'],selected):
        if page['template_id']!=config['id'] or page['item_ids']!=config['item_order']:raise ValueError('PAGE_OR_SUBJECT_ORDER')
        if set(page['values'])!={s['id'] for s in config['slots']}:raise ValueError('MISSING_SLOTS')
        for side,subject in zip(('left','right'),packet['subjects']):
            if page['values'][side+'_photo']!=side+'_photo' or page['values']['name_'+side]!=subject['name']:raise ValueError('CROSS_PAGE_IDENTITY')
    return selected,components


def render_fixed(copy, packet, revision, output, before=False):
    """Use original engine's HTML, geometry inspection and reference comparison."""
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    selected,components=resolved_layout(copy['manifest'],packet,revision,before)
    chars=''.join(str(v) for page in copy['manifest']['pages'] for v in page['values'].values())
    paths={'PosterCJK':DEFAULT_FONT,
           'PosterCJKSerif':Path('/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc'),
           'PosterCJKBold':Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'),
           'PosterCJKSerifBold':Path('/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc')}
    fonts={};fontmeta={}
    for name,path in paths.items():fonts[name],fontmeta[name]=font_data(path,chars)
    report={'status':'FAIL','scope':packet['mode'],'customer_approved':False,'delivery_ready':False,
            'visual_revision':'legacy-v5' if before else revision['revision'],'pages':[],'errors':[],'fonts':fontmeta,
            'warning':'Synthetic fixture data and original illustrations; not real product production' if packet['mode']=='synthetic_test' else 'Awaiting manual/customer acceptance'}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--font-render-hinting=none'])
        try:
            report['browser']=browser.version
            context=browser.new_context(viewport={'width':1242,'height':1656},device_scale_factor=1,locale='zh-CN',service_workers='block')
            context.route('**/*',lambda route:route.abort())
            for n,(config,page_input) in enumerate(zip(selected,copy['manifest']['pages']),1):
                page=context.new_page()
                try:
                    content=html(config,page_input['values'],components,fonts);(output/f'{n:02d}.html').write_text(content)
                    page.set_content(content,wait_until='load')
                    page.evaluate('async()=>{await Promise.all(["PosterCJK","PosterCJKSerif","PosterCJKBold","PosterCJKSerifBold"].map(f=>document.fonts.load(`28px ${f}`)));await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()))}')
                    measured=finite_json(page.evaluate(MEASURE_JS));errors=inspect(config,measured,n)
                    for name in paths:
                        if not page.evaluate('async f=>(await document.fonts.load(`28px ${f}`)).length',name):errors.append({'code':'FONT_MISSING','page':n,'element':name})
                    actual=page.locator('#locked-plate').bounding_box();scale,dx,dy=project(config)
                    if any(abs(actual[k]-v)>.5 for k,v in zip(('x','y','width','height'),(dx,dy,config['source_size'][0]*scale,config['source_size'][1]*scale))):errors.append({'code':'LOCKED_BACKGROUND','page':n})
                    entry={'page':n,'template_id':config['id'],'errors':errors,'elements':measured['elements']}
                    report['pages'].append(entry);report['errors'].extend(errors)
                    if not errors:
                        image_path=output/f'{n:02d}.png';page.screenshot(path=str(image_path))
                        with Image.open(image_path) as image:
                            if image.size!=(1242,1656):raise ValueError('CANVAS_SIZE')
                        entry['reference_diagnostics']=comparison(config,image_path,output,n)
                finally:page.close()
            context.close()
        finally:browser.close()
    if not report['errors']:
        preview=Image.new('RGB',(1242,592),'#eeeeee');d=ImageDraw.Draw(preview)
        d.text((8,5),'SYNTHETIC FIXTURE / NOT A REAL PRODUCT DELIVERY' if packet['mode']=='synthetic_test' else 'REVIEW / NOT CUSTOMER APPROVED',fill='black')
        pairs=Image.new('RGB',(828,582*3),'#eeeeee')
        for n in range(1,4):
            with Image.open(output/f'{n:02d}.png') as image:preview.paste(image.resize((414,552)),((n-1)*414,32))
            with Image.open(output/f'{n:02d}-comparison.png') as image:pairs.paste(image,(0,(n-1)*582))
        preview.save(output/'preview.png');pairs.save(output/'reference-comparison.png')
        report['status']='PASS_LAYOUT_ONLY'
    save(output/'qc_report.json',report)
    return report


def cross_task_qc(results, output):
    errors=[];completed=[r for r in results if r.get('rendered')]
    for i,a in enumerate(completed):
        for b in completed[i+1:]:
            if a['query']==b['query'] or a['poster_content_hash']==b['poster_content_hash'] or a['body_hash']==b['body_hash']:
                errors.append({'code':'CROSS_QUERY_DUPLICATE_CONTENT','tasks':[a['task_id'],b['task_id']]})
    report={'status':'FAIL' if errors else 'PASS_DUPLICATE_CHECK','errors':errors,'review_required':True}
    save(Path(output)/'cross_task_qc.json',report)
    return report


def run_cases(output, case_file=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    from .comparison_fixtures import prepare
    cases=json.loads(Path(case_file).read_text()) if case_file else prepare()
    revision=prepare_visual();save(output/'visual_revision.json',revision)
    results=[]
    for raw in cases:
        task=task_input({k:v for k,v in raw.items() if k!='packet'})
        packet=json.loads((ROOT/raw['packet']).read_text());folder=output/task['task_id'];folder.mkdir()
        save(folder/'input.json',task);save(folder/'business_packet.json',packet)
        import shutil
        inputs=folder/'inputs';inputs.mkdir()
        for source_id,reference in packet['sources'].items():shutil.copyfile(ROOT/reference['path'],inputs/(source_id+'-source.json'))
        for side,asset in packet['assets'].items():
            shutil.copyfile(ROOT/asset['path'],inputs/(side+'-asset.png'))
            shutil.copyfile(ROOT/asset['license_path'],inputs/(side+'-LICENSE.txt'))
        qc=business_qc(packet,task);qc['errors']+=validate_assets(packet)
        if qc['errors']:
            qc['status']='FAIL'
            save(folder/'qc_report.json',qc);results.append({'task_id':task['task_id'],'rendered':False,'status':'BLOCKED'});continue
        provider=EvidenceComparisonProvider(packet);copy=provider.generate(task)
        content_report=copy_qc(copy,packet,task);save(folder/'content_qc.json',content_report)
        save(folder/'copy.json',copy);save(folder/'facts_and_sources.json',{'sources':packet['sources'],'pages':packet['pages']})
        (folder/'post.md').write_text('# '+copy['title']+'\n\n'+copy['body']+'\n')
        if content_report['errors']:raise ValueError('CONTENT_QC_FAILED')
        layout=render_fixed(copy,packet,revision,folder/'after')
        before=render_fixed(copy,packet,revision,folder/'before',before=True)
        # Two comparisons: same content isolates visual changes; historic samples show business correction.
        for n in range(1,4):
            if (folder/'after'/f'{n:02d}.png').exists():
                panels=[]
                legacy=ROOT/'artifacts/phase4-e2e'/('real-01' if raw['task_id']=='fixture-sugar' else 'real-02')/'attempt-003/render-0'/f'{n:02d}.png'
                for name,path in [('HISTORIC REJECTED',legacy),('BEFORE STYLE / NEW TEST CONTENT',folder/'before'/f'{n:02d}.png'),('AFTER / SYNTHETIC FIXTURE',folder/'after'/f'{n:02d}.png')]:
                    panel=Image.new('RGB',(414,582),'#eeeeee');ImageDraw.Draw(panel).text((5,5),name,fill='black')
                    if path.exists():
                        with Image.open(path) as im:panel.paste(im.convert('RGB').resize((414,552)),(0,30))
                    else:ImageDraw.Draw(panel).text((10,60),'BLOCKED BY LAYOUT QC',fill='red')
                    panels.append(panel)
                combined=Image.new('RGB',(1242,582),'white')
                for i,panel in enumerate(panels):combined.paste(panel,(i*414,0))
                combined.save(folder/f'{n:02d}-before-after.png')
        result={'task_id':task['task_id'],'query':task['original_query'],'status':'REVIEW_SYNTHETIC_TEST_ONLY',
                'rendered':not layout['errors'],'customer_approved':False,'delivery_ready':False,
                'cache_key':provider.cache_key(task),'poster_content_hash':digest(copy['manifest']['pages']),
                'body_hash':digest(copy['body']),'business_qc':qc,'layout_qc':layout['status'],
                'before_layout_qc':before['status'],'output':str(folder.relative_to(output))}
        save(folder/'qc_report.json',result);results.append(result)
    duplicate=cross_task_qc(results,output)
    if duplicate['errors']:
        for result in results:result['status']='BLOCKED_DUPLICATE';result['rendered']=False
    # Real queries remain blocked, even when --review-references was previously enabled.
    real_tasks=[task_input({'task_id':'real-01','query':'柠檬水和可乐外观有什么区别','direction':'只比较参考图可见差异'}),
                task_input({'task_id':'real-02','query':'柠檬水和可乐哪个颜色更深','direction':'颜色与包装'})]
    for task in real_tasks:
        save(output/task['task_id']/'input.json',task);save(output/task['task_id']/'qc_report.json',missing_comparison(task))
    report={'production_success':0,'real_queries_blocked':2,'synthetic_groups_rendered':sum(r['rendered'] for r in results),
            'customer_approved':False,'business_acceptance_passed':False,'cases':results,'cross_task_qc':duplicate}
    save(output/'report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','cross_task_qc')},ensure_ascii=False))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--cases',type=Path)
    args=parser.parse_args();run_cases(args.output,args.cases)
