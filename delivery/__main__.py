import argparse
import json
from pathlib import Path
from .engine import Blocked, render_review, export_delivery


def main():
    p=argparse.ArgumentParser(description='Business-01 fixed-template review and evidence-gated local export')
    sub=p.add_subparsers(dest='command',required=True)
    review=sub.add_parser('review');review.add_argument('--manifest',type=Path,required=True);review.add_argument('--output',type=Path,required=True)
    release=sub.add_parser('export');release.add_argument('--review',type=Path,required=True);release.add_argument('--approvals',type=Path,required=True);release.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=='review':
            report=render_review(json.loads(args.manifest.read_text()),args.output)
            print(json.dumps({'status':report['status'],'layout_errors':len(report['errors']),'delivery_blockers':len(report['delivery_blockers']),'report':str(args.output/'qc_report.json')},ensure_ascii=False))
            return 1 if report['errors'] else 0
        export_delivery(args.review,args.approvals,args.output);return 0
    except (Blocked,ValueError,OSError) as e:
        output=args.output
        # Never overwrite an existing directory to record a failed export.
        if not output.exists():
            output.mkdir(parents=True)
            (output/'qc_report.json').write_text(json.dumps({'status':'BLOCKED','errors':[e.detail if isinstance(e,Blocked) else {'code':'IO_OR_INPUT','message':str(e)}]},ensure_ascii=False,indent=2)+'\n')
        print(str(e));return 1


if __name__=='__main__':raise SystemExit(main())
