from pathlib import Path
import json, hashlib, sys
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'references/library.json').read_text(encoding='utf-8'))
errors=[]
seen=set()
for item in data['assets']:
    rel=item['path']; p=(root/rel).resolve()
    if not p.is_relative_to(root): errors.append('Path outside skill: '+rel); continue
    if rel in seen: errors.append('Duplicate path: '+rel)
    seen.add(rel)
    if not p.is_file(): errors.append('Missing: '+rel); continue
    if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']: errors.append('Changed asset: '+rel)
    if item['role'] not in {'template-page','rules','procedure','positive-example','negative-example'}: errors.append('Unknown role: '+rel)
actual={p.relative_to(root).as_posix() for p in (root/'assets').rglob('*') if p.is_file() and p.suffix.lower() in {'.png','.jpg','.jpeg'}}
errors.extend('Unindexed: '+p for p in sorted(actual-seen))
print('\n'.join(errors) if errors else f'PASS: {len(seen)} assets; paths and SHA-256 verified')
if errors:
    sys.exit(1)

for item in data.get('training_transcripts',[]):
    p=(root/item['path']).resolve()
    if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
        raise SystemExit('FAIL: training source '+item['path'])
print('PASS: training source hashes verified')
