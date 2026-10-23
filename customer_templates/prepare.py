"""Independent texture, decorations and photos; preserve all customer originals."""
from io import BytesIO
import json
import cv2
import numpy as np
from PIL import Image, ImageDraw
from rendering.engine import ROOT, sha

COMPONENTS='customer_templates/components-v5'
REGISTRY='customer_templates/component_registry_v5.json'


def keep(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=data:raise ValueError('Refusing to overwrite different generated component '+str(path))
    if not path.exists():path.write_bytes(data)


def configs():
    registry=json.loads((ROOT/'customer_templates/registry.json').read_text());result=[]
    for id,entry in registry['templates'].items():
        path=ROOT/entry['path']
        if sha(path)!=entry['sha256']:raise ValueError('Configuration hash changed: '+id)
        config=json.loads(path.read_text())
        if sha(ROOT/config['reference'])!=config['reference_sha256']:raise ValueError('Reference hash changed: '+config['reference'])
        result.append(config)
    return result


def repair_text(image,boxes,white=False):
    """Repair only glyph-coloured pixels within explicit source regions.

    Inpainting estimates hidden pixels. It is not recovery of the original
    source layer; generated backgrounds/photos require visual approval.
    """
    array=np.asarray(image.convert('RGB')).copy();mask=np.zeros(array.shape[:2],dtype=np.uint8)
    for raw in boxes:
        x1,y1,x2,y2=[int(v) for v in raw];x1=max(0,x1);y1=max(0,y1);x2=min(array.shape[1],x2);y2=min(array.shape[0],y2)
        pixels=array[y1:y2,x1:x2].astype(int)
        if not pixels.size:continue
        lo=pixels.min(axis=2);hi=pixels.max(axis=2)
        selected=((hi-lo)<55)&((lo>195)|(hi<100)) if white else hi<195
        mask[y1:y2,x1:x2] |= selected.astype(np.uint8)*255
    mask=cv2.dilate(mask,np.ones((3,3),np.uint8))
    return Image.fromarray(cv2.inpaint(array,mask,3,cv2.INPAINT_TELEA))


def plate(config,source):
    image=source.copy();draw=ImageDraw.Draw(image);w,h=image.size;cat=config['category']
    if cat=='compare':
        draw.rectangle((20,6,w-20,132),fill=config['background_samples']['header'])
        cover=config['role']=='cover'
        for x1,x2 in [(40,345),(375,w-35)]:
            draw.rectangle((x1,210,x2,477),fill='white')
            draw.rounded_rectangle((x1,476 if cover else 535,x2,928),radius=22,fill='#f8f6f7' if config['role']!='selection' else '#ffffff')
        if cover:
            image.paste(source.crop((286,280,433,386)),(286,280));draw=ImageDraw.Draw(image)
            draw.rounded_rectangle((150,135,568,206),radius=35,fill='#ffc56f')
            for y in [676,834]:
                for x in range(44,341,4):draw.line((x,y,x+1,y),fill='#777777')
                for x in range(410,685,4):draw.line((x,y,x+1,y),fill='#777777')
        for s in config['slots']:
            if s['id'].startswith('name_') or s['id'].startswith('tag_'):
                draw.rounded_rectangle(s['box'],radius=20 if s['id'].startswith('name_') else 7,fill=s['erase_color'])
    elif cat=='recommend':
        draw.rectangle((215,100,w-10,282),fill='#f8f7f3')
        for top in [386,680]:
            draw.rectangle((360,top-6,w-14,top+112),fill='#f8f7f3')
            for y in [503,552,600]:draw.rectangle((488,y+top-386-4,w-18,y+top-386+50),fill='#f1f1e6')
    elif cat=='list':
        if config['role']=='cover':
            draw.rectangle((5,24,w-5,119),fill=config['background_samples']['header'])
            for s in config['slots']:
                if s['kind']=='image':draw.rectangle(s['box'],fill='white')
                elif s['id'].startswith('name_'):draw.rounded_rectangle(s['box'],radius=18,fill=s['erase_color'])
        else:
            for item in config['item_order']:
                named=next(s for s in config['slots'] if s['id']=='name_'+item);y=named['box'][1]
                draw.rounded_rectangle((34,y,366,y+71),radius=22,fill='#e9ebdc')
                draw.rectangle((40,y+76,407,y+183),fill='white')
                draw.rectangle((113,y+198,w-25,y+278),fill='#fffbed')
                draw.rectangle((70,y+299,w-25,min(y+440,h-15)),fill='white')
                photo=next(s for s in config['slots'] if s['id']=='photo_'+item);draw.rectangle((408,y-12,w-24,y+196),fill='white')
    elif cat=='intro' and config['role']!='recipe':
        black=[];white=[]
        for slot in config['slots']:
            if slot['kind']!='text':continue
            x1,y1,x2,y2=slot['box'];box=[x1-8,y1-8,x2+8,y2+8]
            (white if slot['id'].startswith('benefit_') else black).append(box)
        if config['role']=='cover':black.append([42,605,w-38,739])
        image=repair_text(source,black);image=repair_text(image,white,white=True)
    else:
        # All recipe pixels come from independent clean tiles, not a full poster overlay.
        regions=[slot['box'] for slot in config['slots'] if slot['kind']=='text']
        image=repair_text(source,regions,white=True);draw=ImageDraw.Draw(image)
        for slot in config['slots']:
            if slot['kind']=='image':draw.rectangle(slot['box'],fill='#d0c5ad')
    return image


def prepare():
    result={'schema_version':2,'backgrounds':{},'assets':{}}
    for config in configs():
        source=Image.open(ROOT/config['reference']).convert('RGB');clean=source
        if config['role']=='recipe':
            regions=[(130,445,source.width-90,522)]
            for slot in config['slots']:
                if slot['id'].startswith('step_caption_'):
                    x1,y1,x2,y2=slot['box'];regions.append((x1,y1-25,x2,y2))
            clean=repair_text(source,regions,white=True)
        background=plate(config,source)
        for s in config['slots']:
            if s['kind']!='image':continue
            id=f"{config['category']}-{s['id']}"
            if config['category']=='intro':id=config['id']+'-'+s['id']
            if id in result['assets']:continue
            crop=clean.crop(tuple(s['crop'])).convert('RGBA')
            if config['category']=='compare' and s['id']=='left_photo':
                # The reference VS label protrudes into the crop's empty right margin.
                d=ImageDraw.Draw(crop);d.rectangle((238,0,crop.width,174),fill='white')
            data=BytesIO();crop.save(data,format='PNG');path=ROOT/COMPONENTS/f'{id}.png';keep(path,data.getvalue())
            result['assets'][id]={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'subject':s['subject'],'reference':config['reference'],'crop':s['crop'],'size':list(crop.size),'rights':'reference_reconstruction_only_not_confirmed_for_delivery','embedded_text_status':'Recipe captions repaired by local inpainting; exact hidden pixels cannot be recovered'}
        data=BytesIO();background.save(data,format='PNG');path=ROOT/COMPONENTS/f"{config['id']}-background.png";keep(path,data.getvalue())
        result['backgrounds'][config['id']]={'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'method':'Reference decoration pixels retained; variable regions cleaned with source-coordinate masks and explicit paper/brush inpainting. Hidden source layers remain unknown.'}
    keep(ROOT/REGISTRY,(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());return result


if __name__=='__main__':prepare()
