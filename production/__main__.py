import argparse
import json
from .intent import analyze
from .planner import plan

def main():
    parser = argparse.ArgumentParser(description='Phase-one intent analysis and blocked production briefs')
    parser.add_argument('command', choices=['intent','plan','qc'])
    parser.add_argument('query', help='original query, or manifest path for qc')
    parser.add_argument('--category')
    parser.add_argument('--template')
    parser.add_argument('--items', nargs='+')
    parser.add_argument('--objects', nargs='+')
    args = parser.parse_args()
    try:
        if args.command == 'qc':
            from pathlib import Path
            from .qc import check
            output = check(json.loads(Path(args.query).read_text(encoding='utf-8')))
        elif args.command == 'intent':
            output = analyze(args.query,args.category)
        else:
            output = plan(args.query,args.category,args.template,args.items,args.objects)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(output,ensure_ascii=False,indent=2))
    return 1 if args.command == 'qc' and output['status'] != 'PASS' else 0

if __name__ == '__main__':
    raise SystemExit(main())
