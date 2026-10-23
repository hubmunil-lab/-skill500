import argparse,json
from pathlib import Path
from .prepare import prepare
from .engine import render
from rendering.engine import ROOT


def main():
    parser=argparse.ArgumentParser(description='Rebuild four customer templates; no delivery or batch production')
    parser.add_argument('--category',choices=['compare','recommend','list','intro','all'],default='all')
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();prepare()
    categories=['compare','recommend','list','intro'] if args.category=='all' else [args.category]
    failed=False
    for category in categories:
        manifest=args.manifest or ROOT/f'examples/customer_templates/{category}.json'
        report=render(json.loads(manifest.read_text()),args.output/category)
        print(json.dumps({'category':category,'status':report['status'],'errors':report['errors']},ensure_ascii=False))
        failed|=bool(report['errors'])
    return 1 if failed else 0


if __name__=='__main__':raise SystemExit(main())
