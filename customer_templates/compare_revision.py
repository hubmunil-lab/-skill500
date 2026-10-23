"""Visual corrections to existing compare templates; coordinates never move.

Do not register a fifth template. Keep v5 plates/configs and their tests intact.
"""
import copy
import json
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw
from rendering.engine import ROOT, sha
from .prepare import configs, keep

REVISION = 'compare-visual-rework-1'


def corrected_config(config):
    result=copy.deepcopy(config)
    for slot in result['slots']:
        if slot['kind']!='text':continue
        if slot['id']=='title':
            slot.update(font_size=48, line_height=62.4, weight=700, outline=3)
        elif slot['id']=='subtitle':
            slot.update(font_size=30, line_height=39, weight=700, outline=1.5)
        elif slot['id'].startswith(('name_','tag_')):
            slot.update(font_size=27 if slot['id'].startswith('name_') else 22,
                        line_height=35.1 if slot['id'].startswith('name_') else 28.6, weight=700)
        else:
            slot.update(font_size=20.5, line_height=27, weight=400)
    result['visual_revision']=REVISION
    return result


def corrected_plate(config):
    """Clear only interior panels; original border rings never get painted over."""
    with Image.open(ROOT/config['reference']) as source:
        image=source.convert('RGB')
    d=ImageDraw.Draw(image);w,h=image.size;cover=config['role']=='cover'
    d.rectangle((12,6,w-12,132),fill=config['background_samples']['header'])
    if cover:
        # Single full-width frame; no rectangle touches its border.
        d.rectangle((40,209,w-40,472),fill='white')
        for box in [(40,472,345,925),(397,472,w-34,925)]:
            d.rounded_rectangle(box,radius=25,fill='#f8f6f7')
        with Image.open(ROOT/config['reference']) as source:
            image.paste(source.crop((286,280,433,386)),(286,280))
        d=ImageDraw.Draw(image)
        d.rounded_rectangle((150,135,568,206),radius=35,fill='#ffc56f')
        for y in (676,834):
            for start,end in ((44,341),(410,685)):
                for x in range(start,end,4):d.line((x,y,x+1,y),fill='#777777')
        for key,box in [('tag_1',(282,605,408,655)),('tag_2',(282,722,408,771)),('tag_3',(282,856,408,903))]:
            # Fully replace old tag glyphs; preserve tag anchor and palette.
            d.rounded_rectangle(box,radius=7,fill='#ed5f0b')
    else:
        # Inner border is near x=34/344 and 386/694; clear strictly inside.
        for box in [(38,170,340,929),(390,170,w-37,929)]:
            d.rounded_rectangle(box,radius=20,fill='white')
        for box in [(38,568,340,929),(390,568,w-37,929)]:
            d.rounded_rectangle(box,radius=25,fill='#f8f6f7' if config['role']=='nutrition' else '#ffffff')
        if config['role']=='nutrition':
            for start,end in ((49,326),(400,680)):
                for x in range(start,end,4):d.line((x,839,x+1,839),fill='#777777')
    for slot in config['slots']:
        if slot['id'].startswith('name_'):
            d.rounded_rectangle(slot['box'],radius=20,fill=slot['erase_color'])
    return image


def prepare():
    selected=sorted([c for c in configs() if c['category']=='compare'],key=lambda c:c['page_number'])
    result={'revision':REVISION,'templates':{},'backgrounds':{},'changes':[],'customer_approved':False}
    for original in selected:
        revised=corrected_config(original)
        # Fixed source-coordinate boxes, photos and palette are immutable.
        for before,after in zip(original['slots'],revised['slots']):
            assert before['box']==after['box'] and before['kind']==after['kind'] and before.get('color')==after.get('color')
        data=(json.dumps(revised,ensure_ascii=False,indent=2)+'\n').encode()
        import hashlib
        config_digest=hashlib.sha256(data).hexdigest()
        base=ROOT/'customer_templates/compare-rework'/config_digest[:12]
        config_path=base/(revised['id']+'.json');keep(config_path,data)
        image=corrected_plate(original); buffer=BytesIO();image.save(buffer,format='PNG')
        path=base/(revised['id']+'-background.png');keep(path,buffer.getvalue())
        result['templates'][revised['id']]={'path':str(config_path.relative_to(ROOT)),'sha256':sha(config_path)}
        result['backgrounds'][revised['id']]={'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
        result['changes'].append({'template_id':original['id'],'coordinate_changes':0,
            'font_changes':[{'element':a['id'],'before':{k:a[k] for k in ('font_size','weight','outline')},
                            'after':{k:b[k] for k in ('font_size','weight','outline')}}
                           for a,b in zip(original['slots'],revised['slots']) if a['kind']=='text'],
            'background_method':'Clear inside border rings, not across them; no inpainting on photo regions',
            'original_font_unavailable':True})
    return result


if __name__=='__main__':
    from workflow.core import save
    save(ROOT/'artifacts/phase4-rework/visual_revision.json',prepare())
