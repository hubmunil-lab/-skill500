import argparse
import json
from pathlib import Path
from .engine import DEFAULT_FONT, ROOT, render
from .fixtures import create_fixtures


def main():
    parser=argparse.ArgumentParser(description='Render locked 1242x1656 test prototypes; not customer delivery')
    parser.add_argument('command',choices=['demo','render'])
    parser.add_argument('--manifest',type=Path,default=ROOT/'examples/rendering/intro4-test.json')
    parser.add_argument('--output',type=Path,required=True,help='New empty output directory; existing paths are never overwritten')
    parser.add_argument('--font',type=Path,default=DEFAULT_FONT)
    parser.add_argument('--chromium',default='/usr/bin/chromium')
    args=parser.parse_args()
    try:
        if args.command=='demo':create_fixtures()
        report=render(json.loads(args.manifest.read_text()),args.output,args.font,args.chromium)
    except (OSError,ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({'status':report['status'],'pages':len(report['pages']),'errors':len(report['errors']),
                      'report':str(args.output/'qc_report.json'),'customer_approved':False},ensure_ascii=False))
    return 1 if report['errors'] else 0


if __name__=='__main__':raise SystemExit(main())
