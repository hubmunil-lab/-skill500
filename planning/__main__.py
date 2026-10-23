import argparse
import json
from pathlib import Path
from workflow.core import ROOT, task_input, save
from .pipeline import run_task


def run(input_file,output,render_review=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);results=[]
    for raw in json.loads(Path(input_file).read_text()):
        task=task_input({key:raw[key] for key in ('task_id','query','direction') if key in raw})
        packet=json.loads((ROOT/raw['packet']).read_text()) if raw.get('packet') else None
        result=run_task(task,output/task['task_id'],packet,render_review)
        intent=json.loads((output/task['task_id']/'intent.json').read_text())
        result['software_expectations_passed']=(set(intent['required_facts'])==set(raw.get('expected_required_facts',intent['required_facts'])) and result['category']==raw.get('expected_category') and result['template_id']==raw.get('expected_template') and result['generated']==raw.get('expect_render'))
        results.append(result);save(output/task['task_id']/'result.json',result)
    synthetic=[r for r in results if r['data_kind']=='synthetic_test'];real=[r for r in results if r['data_kind']!='synthetic_test']
    duplicates=[]
    rendered=[r for r in results if r['generated']]
    for i,a in enumerate(rendered):
        for b in rendered[i+1:]:
            if a['poster_content_hash']==b['poster_content_hash'] or a['body_hash']==b['body_hash']:duplicates.append([a['task_id'],b['task_id']])
    report={'tasks':results,'software_expectations':{'passed':sum(r['software_expectations_passed'] for r in results),'total':len(results)},
            'synthetic_software_rendering':{'success':sum(r['generated'] for r in synthetic),'total':len(synthetic)},
            'real_business':{'delivered':0,'rendered':sum(r['generated'] for r in real),'total':len(real)},
            'duplicates':duplicates,'customer_approved':False,'business_acceptance_passed':False}
    save(output/'report.json',report);print(json.dumps({k:v for k,v in report.items() if k!='tasks'},ensure_ascii=False))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path);parser.add_argument('--output',required=True,type=Path);parser.add_argument('--render-review',action='store_true')
    args=parser.parse_args();run(args.input,args.output,args.render_review)
