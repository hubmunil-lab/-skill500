"""Immutable business-template review rendering and evidence-bound local export."""
import base64
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageOps
from playwright.sync_api import sync_playwright
from rendering.engine import (ROOT, CANVAS, DEFAULT_FONT, sha, repository_path,
    font_data, build_html, MEASURE_JS, inspect_geometry, make_preview, make_comparison)


class Blocked(ValueError):
    def __init__(self,code,message,page=None,element=None):
        super().__init__(message);self.detail=dict(code=code,message=message,page=page,element=element,severity='blocking')


def finite_json(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value,list):return [finite_json(v) for v in value]
    return value


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def strict(value, keys, name):
    if not isinstance(value,dict) or set(value)!=set(keys):raise Blocked('INPUT_SCHEMA',name+' keys do not match contract')


def source_table(path):
    source=repository_path(path);meta=json.loads(source.read_text())
    if meta.get('source_id')!='USDA-SR28-09132':raise Blocked('FACT_SOURCE','Unsupported source record; new foods need reviewed source adapters')
    for file,expected in meta['extract_hashes'].items():
        if sha(source.parent/file)!=expected:raise Blocked('FACT_SOURCE','Source extract changed: '+file)
    rows={l.split('^')[1].strip('~'):l.split('^')[2] for l in (source.parent/'NUT_DATA-extract.txt').read_text().splitlines()}
    return [[label,rows[id]+' '+unit] for id,label,unit in [('208','能量','kcal'),('205','碳水化合物','g'),('269','总糖','g'),('291','膳食纤维','g'),('401','维生素C','mg')]]


def validate(manifest):
    strict(manifest,['schema_version','template_family','query','subject','title','direct_answer','objects','assets','nutrition_source','highlights','pages'],'manifest')
    if manifest['schema_version']!=1 or manifest['template_family']!='business-01':raise Blocked('INPUT_SCHEMA','Unsupported business template')
    for key in ['query','subject','title','direct_answer']:
        if not isinstance(manifest[key],str) or not manifest[key].strip():raise Blocked('CONTENT_MISSING',key+' required')
    if len(manifest['title'])>=20:raise Blocked('TITLE_LENGTH','Title must be shorter than 20 characters')
    if not isinstance(manifest['highlights'],list) or len(manifest['highlights'])!=3 or any(not isinstance(x,str) or not x.strip() for x in manifest['highlights']):raise Blocked('CONTENT_MISSING','Exactly three real highlights required')
    objects=manifest['objects']
    if not isinstance(objects,list) or len(objects)!=2:raise Blocked('OBJECT_COUNT','Exactly two objects required')
    for obj in objects:
        strict(obj,['id','label','asset'],'object')
        if any(not isinstance(x,str) or not x.strip() for x in obj.values()):raise Blocked('INPUT_SCHEMA','Invalid object values')
    if objects[0]['id']==objects[1]['id']:raise Blocked('OBJECT_COUNT','Objects must differ')
    registry=json.loads((ROOT/'delivery/template_registry.json').read_text())
    if not isinstance(manifest['pages'],list) or len(manifest['pages'])!=3:raise Blocked('PAGE_COUNT','Business-01 requires exactly three pages')
    expected_table=source_table(manifest['nutrition_source'])
    if manifest['subject']!='grapes':raise Blocked('FACT_SCOPE','Current source adapter is for raw grapes only; other terms need their own evidence adapter')
    phrases=json.loads((ROOT/'qc_rules.yaml').read_text())['banned_health_phrases']
    if any(phrase in json.dumps(manifest['pages'],ensure_ascii=False) for phrase in phrases):raise Blocked('HEALTH_CLAIM','Banned medical-effect wording in output content')
    if not isinstance(manifest['assets'],dict):raise Blocked('ASSET_MISSING','Assets map required')
    prepared={};layouts=[];bindings={'manifest':digest(manifest),'layouts':{},'assets':{},'source':sha(repository_path(manifest['nutrition_source'])),'extracts':json.loads(repository_path(manifest['nutrition_source']).read_text())['extract_hashes']}
    blockers=[dict(code='TEMPLATE_APPROVAL_REQUIRED',message='Customer approval of reconstructed template and third page required'),dict(code='FACT_EDITOR_REQUIRED',message='Review historical mirrored source and generic-record scope'),dict(code='VISUAL_REVIEW_REQUIRED',message='Human review of final PNGs required')]
    for n,(page,role) in enumerate(zip(manifest['pages'],registry['page_roles']),1):
        strict(page,['template_id','values'],'page')
        entry=registry['templates'].get(page['template_id'])
        if not entry:raise Blocked('TEMPLATE_UNKNOWN','Unregistered template',n,'template')
        path=repository_path(entry['path'])
        if sha(path)!=entry['sha256']:raise Blocked('LAYOUT_CHANGED','Registered template hash changed',n,'template')
        layout=json.loads(path.read_text());layouts.append(layout);bindings['layouts'][layout['id']]=sha(path)
        if layout['role']!=role:raise Blocked('PAGE_ORDER','Template role/order mismatch',n,'template')
        required={e['id'] for e in layout['elements'] if e['kind']!='decoration'}-{'status'}
        values=page['values']
        if not isinstance(values,dict) or set(values)!=required:raise Blocked('INPUT_SCHEMA','Slots do not match locked template',n,'values')
        for element in layout['elements']:
            id=element['id'];kind=element['kind']
            if kind=='decoration' or id=='status':continue
            value=values[id]
            if kind in ('text','image') and (not isinstance(value,str) or not value.strip()):raise Blocked('CONTENT_MISSING','Non-empty slot required',n,id)
            if kind=='text' and any(s in value for s in ['测试占位','待核实','待填写','测试素材']):raise Blocked('PLACEHOLDER_FORBIDDEN','Business sample cannot use placeholder content',n,id)
            if kind=='table' and value!=expected_table:raise Blocked('NUTRITION_MISMATCH','Nutrition table differs from pinned source extract',n,id)
            if kind!='image':continue
            side=0 if id=='photo_left' else 1;obj=objects[side]
            if value!=obj['asset']:raise Blocked('OBJECT_ORDER','Image identity changed across pages',n,id)
            record=manifest['assets'].get(value)
            if not isinstance(record,dict):raise Blocked('ASSET_MISSING','Required real photo is missing',n,id)
            if record.get('kind')!='real_ingredient_photo' or record.get('subject')!=obj['id']:raise Blocked('ASSET_SUBJECT','Real photo/object identity mismatch',n,id)
            path=repository_path(record.get('path',''))
            if sha(path)!=record.get('sha256'):raise Blocked('ASSET_CHANGED','Image bytes differ from recorded hash',n,id)
            bindings['assets'][value]=sha(path)
            with Image.open(path) as raw:
                image=ImageOps.exif_transpose(raw).convert('RGBA')
                if record.get('cutout') is not True or image.getextrema()[3][0]==255:raise Blocked('ASSET_ALPHA','Transparent foreground required',n,id)
                target_scale=min(element['width']/image.width,element['height']/image.height)
                if target_scale>registry['policy']['delivery_max_upscale']:
                    blockers.append(dict(code='SOURCE_RESOLUTION',page=n,element=id,message=f'Native {image.width}x{image.height}; display scale {target_scale:.3f} > 1.0'))
                data=BytesIO();image.save(data,format='PNG')
                prepared[value]=('data:image/png;base64,'+base64.b64encode(data.getvalue()).decode(),{})
            if record.get('rights_status') not in ('licensed','owned') or not record.get('rights_evidence'):
                blockers.append(dict(code='IMAGE_RIGHTS_REQUIRED',page=n,element=id,message='Real repository photo exists, but delivery license not established'))
            else:
                evidence=record['rights_evidence']
                if not isinstance(evidence,dict) or sha(repository_path(evidence.get('path','')))!=evidence.get('sha256'):raise Blocked('RIGHTS_EVIDENCE','Invalid rights evidence file',n,id)
        if values['label_left']!=objects[0]['label'] or values['label_right']!=objects[1]['label']:raise Blocked('OBJECT_ORDER','Object labels must retain identity',n,'label')
    return registry,layouts,prepared,bindings,blockers


def render_review(manifest, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={'schema_version':1,'status':'BLOCKED','delivery_ready':False,'customer_approved':False,'errors':[],'delivery_blockers':[],'pages':[],'content_placeholders':False,'review_only':True}
    def finish():
        (output/'qc_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n');return report
    try:
        registry,layouts,assets,bindings,blockers=validate(manifest)
        report['delivery_blockers']=blockers
        chars=''.join(str(v) for p in manifest['pages'] for v in p['values'].values())+'食材选择｜双品对比'
        font,info=font_data(DEFAULT_FONT,chars)
        if info['source_sha256']!=registry['font_sha256']:raise Blocked('FONT_CHANGED','Font differs from locked family')
        report['font']=info
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--font-render-hinting=none'])
            try:
                report['browser']=browser.version
                context=browser.new_context(viewport={'width':1242,'height':1656},device_scale_factor=1,locale='zh-CN',service_workers='block')
                context.route('**/*',lambda route:route.abort())
                for n,(layout,page_input) in enumerate(zip(layouts,manifest['pages']),1):
                    page=context.new_page()
                    try:
                        values=dict(page_input['values'],status='食材选择｜双品对比')
                        html=build_html(layout,values,assets,font);(output/f'{n:02d}.html').write_text(html)
                        page.set_content(html,wait_until='load');page.evaluate('async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()))}')
                        geometry=finite_json(page.evaluate(MEASURE_JS))
                        errors=inspect_geometry(layout,geometry,n)
                        loaded=page.evaluate("async()=> (await document.fonts.load('28px PosterCJK')).length")
                        if not loaded:errors.append(dict(code='FONT_MISSING',page=n,element='font',message='Embedded font did not load'))
                        report['pages'].append(dict(page=n,template_id=layout['id'],elements=geometry['elements'],errors=errors,status='FAIL' if errors else 'PASS_LAYOUT'))
                        report['errors'].extend(errors)
                        if not errors:
                            page.screenshot(path=str(output/f'{n:02d}.png'),full_page=False)
                            with Image.open(output/f'{n:02d}.png') as image:
                                if image.size!=CANVAS:raise Blocked('PAGE_SIZE','Wrong exported dimensions',n,'canvas')
                    finally:page.close()
                context.close()
            finally:browser.close()
        if report['errors']:return finish()
        make_preview(output,3);make_comparison(output,layouts)
        with Image.open(output/'preview.png') as preview:
            draw=ImageDraw.Draw(preview);draw.rectangle((0,0,preview.width,26),fill='#ffffff')
            draw.text((12,2),'待客户验收样稿｜真实内容与照片，尚未获准交付',font=ImageFont.truetype(str(DEFAULT_FONT),18,index=2),fill='#64263f')
            preview.save(output/'preview.png')
        # Exact rendered inputs and bytes bind any later human signoffs.
        bindings['pngs']={f'{n:02d}.png':sha(output/f'{n:02d}.png') for n in range(1,4)}
        (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        (output/'body.md').write_text(compose_body(manifest))
        bindings['body_sha256']=sha(output/'body.md')
        report['bindings']=bindings;report['review_digest']=digest(bindings)
        report['status']='REVIEW_NOT_DELIVERABLE'
    except Blocked as exc:report['errors'].append(exc.detail)
    except Exception as exc:report['errors'].append(dict(code='RENDER_ERROR',page=None,element=None,message=str(exc)))
    return finish()


def compose_body(manifest):
    """Readable caption, deduplicating shared comparison data without omitting it."""
    cover,nutrition,selection=[p['values'] for p in manifest['pages']]
    parts=[manifest['title'],manifest['direct_answer'],
           '对比对象：'+manifest['objects'][0]['label']+'与'+manifest['objects'][1]['label']+'。']
    parts += ['三个营养亮点（通用生鲜葡萄记录）']+manifest['highlights']
    for i in range(1,4):
        parts += [cover[f'point_{i}_left'],
                  manifest['objects'][0]['label']+'：'+cover[f'detail_{i}_left'],
                  manifest['objects'][1]['label']+'：'+cover[f'detail_{i}_right']]
    parts += [nutrition['title'],nutrition['answer'],nutrition['table_heading_left']]
    rows=nutrition['table_left']
    parts.append('| 营养字段 | 每100克可食部 |\n| --- | --- |\n'+'\n'.join('| '+a+' | '+b+' |' for a,b in rows))
    parts += [nutrition['table_scope_left'],selection['title'],selection['answer']]
    for i in range(1,4):
        for side in ['left','right']:
            heading=selection[f'use_{i}_{side}'];text=selection[f'why_{i}_{side}']
            paragraph=heading+'：'+text
            if paragraph not in parts:parts.append(paragraph)
    parts.append(cover['note'])
    return '\n\n'.join(parts)+'\n'


def export_delivery(review, approvals, output):
    """Local export only; never publishes. No fabricated approvals are shipped."""
    review=Path(review);output=Path(output)
    report=json.loads((review/'qc_report.json').read_text())
    if report.get('errors') or report.get('status')!='REVIEW_NOT_DELIVERABLE':raise Blocked('LAYOUT_FAILED','Review rendering must pass first')
    manifest=json.loads((review/'manifest.json').read_text())
    _,_,_,current,blockers=validate(manifest)
    current['pngs']={f'{n:02d}.png':sha(review/f'{n:02d}.png') for n in range(1,4)}
    current['body_sha256']=sha(review/'body.md')
    if digest(current)!=report.get('review_digest'):raise Blocked('REVIEW_STALE','Reviewed input, sources or output changed')
    hard=[b for b in blockers if b['code'] in ('SOURCE_RESOLUTION','IMAGE_RIGHTS_REQUIRED')]
    if hard:raise Blocked('DELIVERY_BLOCKED','Unresolved image resolution or rights; see QC delivery_blockers')
    packet=json.loads(Path(approvals).read_text())
    if packet.get('review_digest')!=report['review_digest']:raise Blocked('APPROVAL_STALE','Signoffs do not bind exact reviewed version')
    for role in ['customer_template','fact_editor','rights_holder','visual_editor']:
        record=packet.get('signoffs',{}).get(role,{})
        if record.get('approved') is not True or not all(isinstance(record.get(k),str) and record[k].strip() for k in ['reviewer','date','evidence_path','evidence_sha256']):raise Blocked('APPROVAL_REQUIRED','Missing signoff: '+role)
        if sha(repository_path(record['evidence_path']))!=record['evidence_sha256']:raise Blocked('APPROVAL_EVIDENCE','Evidence changed: '+role)
    output.mkdir(parents=True,exist_ok=False)
    # Preserve exactly the pixels approved by reviewers; preview-only mark is not exported.
    for name in ['01.png','02.png','03.png','body.md']:shutil.copyfile(review/name,output/name)
    final_report=dict(report,status='DELIVERY_APPROVED',delivery_ready=True,customer_approved=True,review_only=False,delivery_blockers=[],approval_packet='approval_packet.json')
    (output/'qc_report.json').write_text(json.dumps(final_report,ensure_ascii=False,indent=2)+'\n')
    shutil.copyfile(approvals,output/'approval_packet.json')
    (output/'release_receipt.json').write_text(json.dumps({'status':'DELIVERY_APPROVED','review_digest':report['review_digest'],'files':current['pngs'],'note':'Exact signed pixels preserved. Local export only; no publishing.'},indent=2)+'\n')
