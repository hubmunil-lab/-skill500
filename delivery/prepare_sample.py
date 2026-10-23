"""Reproduce the real-content review sample from preserved repository inputs."""
from collections import deque
from io import BytesIO
import json
from pathlib import Path
from PIL import Image
from rendering.engine import ROOT, sha


def write_new_or_identical(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=data:
        raise ValueError('Refusing to overwrite different existing file: '+str(path))
    if not path.exists():path.write_bytes(data)


def prepare():
    original=ROOT/'assets/compare-1-detail.jpg'
    crops={'dark':(105,190,342,581),'red':(464,185,733,582)}
    records={}
    with Image.open(original) as source:
        for subject,box in crops.items():
            im=source.crop(box).convert('RGBA');pix=im.load();w,h=im.size
            queue=deque([(x,0) for x in range(w)]+[(x,h-1) for x in range(w)]+[(0,y) for y in range(h)]+[(w-1,y) for y in range(h)])
            seen=set()
            # Remove only the connected near-white surround; keep interior fruit highlights.
            while queue:
                x,y=queue.popleft()
                if (x,y) in seen or not (0<=x<w and 0<=y<h):continue
                seen.add((x,y));r,g,b,a=pix[x,y]
                if min(r,g,b)>228 and max(r,g,b)-min(r,g,b)<24:
                    pix[x,y]=(r,g,b,0)
                    queue.extend([(x-1,y),(x+1,y),(x,y-1),(x,y+1)])
            data=BytesIO();im.save(data,format='PNG')
            path=ROOT/f'delivery/sample_assets/{subject}-grapes.png'
            write_new_or_identical(path,data.getvalue())
            records[subject]={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'subject':subject,'kind':'real_ingredient_photo','cutout':True,
                'rights_status':'unverified_user_reference','rights_evidence':None,'subject_review':'visually grape cluster; exact cultivar not verified',
                'source_path':'assets/compare-1-detail.jpg','source_sha256':sha(original),'crop_box':list(box),'source_native_size':[w,h]}
    target=ROOT/'delivery/evidence/photo_provenance.json'
    write_new_or_identical(target,(json.dumps(records,ensure_ascii=False,indent=2)+'\n').encode())
    return records


if __name__=='__main__':prepare()
