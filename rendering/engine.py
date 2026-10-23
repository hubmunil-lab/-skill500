"""Local-only HTML/CSS rendering with browser geometry and font QC.

All templates are immutable draft prototypes. Production mode fails closed.
No JavaScript, HTML, CSS, or URLs are accepted from content inputs.
"""
import base64
from datetime import datetime, timezone
import hashlib
from html import escape
from io import BytesIO
import json
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from PIL import Image, ImageColor, ImageDraw, ImageOps
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FONT = Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
CANVAS = (1242, 1656)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def issue(page, element, code, message):
    return dict(page=page, element=element, code=code, message=message, severity='error')


def repository_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError('Missing or non-repository file: ' + str(value))
    return path


def load_template(template_id):
    registry = json.loads((ROOT/'rendering/template_registry.json').read_text())
    entry = registry['templates'].get(template_id)
    if entry is None:
        raise ValueError('Template not registered: ' + str(template_id))
    path = repository_path(entry['path'])
    if sha(path) != entry['sha256']:
        raise ValueError('Locked template hash mismatch: ' + template_id)
    return json.loads(path.read_text())


def font_data(font_path, chars):
    """Pin the actual local face and reject missing glyphs before subsetting."""
    path = Path(font_path)
    if not path.is_file():
        raise ValueError('Font file missing: ' + str(path))
    face = 0
    if path.suffix.lower() in ('.ttc', '.otc'):
        # Noto CJK collection index varies: find SC rather than assuming index.
        from fontTools.ttLib import TTCollection
        collection = TTCollection(path, lazy=True)
        try:
            for i, candidate in enumerate(collection.fonts):
                names = ' '.join(n.toUnicode() for n in candidate['name'].names if n.nameID in (1,16))
                if 'CJK SC' in names:
                    face = i
                    break
        finally:
            collection.close()
    font = TTFont(path, fontNumber=face)
    try:
        cmap = font.getBestCmap()
        missing = sorted({c for c in chars if not c.isspace() and ord(c) not in cmap})
        if missing:
            raise ValueError('Missing glyphs: ' + ' '.join(f'U+{ord(c):04X}' for c in missing))
        options = subset.Options()
        options.recalc_timestamp = False
        worker = subset.Subsetter(options=options)
        worker.populate(text=chars)
        worker.subset(font)
        data = BytesIO()
        font.save(data)
        return data.getvalue(), {'source_sha256':sha(path), 'face_index':face, 'font_path':str(path)}
    finally:
        font.close()


def prepare_asset(record, subject, mode, expected_kind='real_ingredient_photo'):
    if not isinstance(record, dict):
        raise ValueError('Asset metadata must be an object')
    if record.get('subject') != subject:
        raise ValueError('Asset subject differs from task subject')
    if record.get('kind') == 'test_placeholder':
        if mode != 'test':
            raise ValueError('Test placeholders cannot be production photographs')
    elif record.get('kind') not in ('real_ingredient_photo','real_step_photo'):
        raise ValueError('Unknown image type; finished dishes do not substitute for steps')
    elif record.get('reviewed') is not True or not record.get('rights_evidence') or record.get('rights') not in ('owned','licensed'):
        raise ValueError('Real photo needs rights evidence and subject review')
    if record.get('kind') != 'test_placeholder' and record.get('kind') != expected_kind:
        raise ValueError('Photo kind does not match this image slot')
    if expected_kind == 'real_step_photo' and record.get('kind') != 'test_placeholder' and not record.get('operation_description'):
        raise ValueError('Real step photo requires actual operation description')
    path = repository_path(record.get('path',''))
    with Image.open(path) as original:
        im = ImageOps.exif_transpose(original).convert('RGBA')
        if record.get('cutout') and im.getextrema()[3][0] == 255:
            raise ValueError('Cutout image has no transparent pixels')
        # Keep original aspect and RGBA. Browser uses contain; no cropping/stretching.
        data = BytesIO()
        im.save(data,format='PNG')
        return 'data:image/png;base64,'+base64.b64encode(data.getvalue()).decode(), {
            'sha256':sha(path),'original_size':list(im.size),'alpha_preserved':True,
            'has_transparency':im.getextrema()[3][0]<255,'kind':record['kind']}


def build_html(layout, values, assets, font_bytes):
    elements = []
    for e in layout['elements']:
        style = f"left:{e['x']}px;top:{e['y']}px;width:{e['width']}px;height:{e['height']}px;"
        kind = e['kind']
        if kind == 'decoration':
            elements.append(f'<div class="element decoration" id="{escape(e["id"])}" style="{style}background:{e["background"]}"></div>')
            continue
        style += f"color:{e.get('color','#462312')};"
        attr = f'id="{escape(e["id"])}" data-kind="{kind}"'
        if kind == 'image':
            elements.append(f'<img class="element" {attr} style="{style}object-fit:contain;object-position:center" src="{assets[values[e["id"]]][0]}"/>')
            continue
        style += f"font-size:{e['font_size']}px;line-height:{e['line_height']}px;font-weight:{e.get('weight',400)};"
        if kind == 'table':
            rows = values[e['id']]
            cells = ''.join('<div class="cell">'+escape(cell)+'</div>' for row in rows for cell in row)
            style += f"display:grid;grid-template-columns:repeat({e['columns']},1fr);grid-template-rows:repeat({e['rows']},1fr);"
            elements.append(f'<div class="element" {attr} style="{style}">{cells}</div>')
        else:
            elements.append(f'<div class="element" {attr} style="{style}">{escape(values[e["id"]])}</div>')
    encoded=base64.b64encode(font_bytes).decode()
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<style>@font-face{{font-family:PosterCJK;src:url(data:font/ttf;base64,{encoded});font-weight:100 900;font-display:block}}
*{{box-sizing:border-box}}html,body{{margin:0;width:{layout['width']}px;height:{layout['height']}px;background:{layout['background']}}}
body{{font-family:PosterCJK}}.element{{position:absolute;white-space:pre-wrap;overflow:visible;overflow-wrap:anywhere;word-break:normal}}
.cell{{min-width:0;min-height:0;display:flex;align-items:center;justify-content:center;border:1px solid #9e8159;padding:10px;white-space:pre-wrap;overflow-wrap:anywhere}}
</style><body>{''.join(elements)}</body></html>'''


MEASURE_JS = r'''() => {
 const box = r => ({x:r.x,y:r.y,width:r.width,height:r.height});
 return {width:document.documentElement.clientWidth,height:document.documentElement.clientHeight,
 font_loaded:document.fonts.check('28px PosterCJK'),
 elements:[...document.querySelectorAll('.element')].map(el=>{
 const r=el.getBoundingClientRect(),s=getComputedStyle(el);
 const texts=[]; const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
 while(walker.nextNode()) {const range=document.createRange();range.selectNodeContents(walker.currentNode);for(const b of range.getClientRects())texts.push(box(b));}
 return {id:el.id,kind:el.dataset.kind||'decoration',rect:box(r),text_rects:texts,
 scroll_width:el.scrollWidth,scroll_height:el.scrollHeight,client_width:el.clientWidth,client_height:el.clientHeight,
 font_size:parseFloat(s.fontSize),line_height:parseFloat(s.lineHeight),font_family:s.fontFamily,font_weight:parseInt(s.fontWeight),
 color:s.color,background:s.backgroundColor,object_fit:s.objectFit,loaded:el.tagName!=='IMG'||(el.complete&&el.naturalWidth>0),natural_width:el.naturalWidth||null,natural_height:el.naturalHeight||null};})};}'''


def intersects(a,b):
    return min(a['x']+a['width'],b['x']+b['width'])>max(a['x'],b['x'])+0.5 and min(a['y']+a['height'],b['y']+b['height'])>max(a['y'],b['y'])+0.5


def inspect_geometry(layout, measured, page):
    errors=[]
    if (measured['width'],measured['height']) != CANVAS:
        errors.append(issue(page,'canvas','PAGE_SIZE','Browser canvas is not 1242x1656'))
    if not measured['font_loaded']:
        errors.append(issue(page,'font','FONT_MISSING','Pinned face did not load'))
    actual={e['id']:e for e in measured['elements']}
    for spec in layout['elements']:
        e=actual.get(spec['id'])
        if e is None:
            errors.append(issue(page,spec['id'],'LOCKED_REGION','Missing locked element'));continue
        rect=e['rect']
        if any(abs(rect[k]-spec[k])>0.5 for k in ('x','y','width','height')):
            errors.append(issue(page,e['id'],'LOCKED_REGION','DOM geometry changed from registered layout'))
        if rect['x']<0 or rect['y']<0 or rect['x']+rect['width']>CANVAS[0]+0.5 or rect['y']+rect['height']>CANVAS[1]+0.5:
            errors.append(issue(page,e['id'],'IMAGE_OUT_OF_BOUNDS' if e['kind']=='image' else 'ELEMENT_OUT_OF_BOUNDS','Element extends beyond canvas'))
        expected_color=spec.get('background') if e['kind']=='decoration' else spec.get('color')
        if expected_color:
            expected_rgb='rgb(%d, %d, %d)' % ImageColor.getrgb(expected_color)
            actual_color=e['background'] if e['kind']=='decoration' else e['color']
            if actual_color!=expected_rgb:
                errors.append(issue(page,e['id'],'LOCKED_REGION','Locked color changed'))
        if e['kind'] in ('text','table'):
            if abs(e['font_size']-spec['font_size'])>0.1 or abs(e['line_height']-spec['line_height'])>0.1 or e['font_weight']!=spec.get('weight',400) or 'PosterCJK' not in e['font_family']:
                errors.append(issue(page,e['id'],'LOCKED_REGION','Font metrics/style changed'))
            out=e['scroll_width']>e['client_width']+1 or e['scroll_height']>e['client_height']+1
            for r in e['text_rects']:
                out |= r['x']<rect['x']-1 or r['y']<rect['y']-1 or r['x']+r['width']>rect['x']+rect['width']+1 or r['y']+r['height']>rect['y']+rect['height']+1
            if out:errors.append(issue(page,e['id'],'TEXT_OVERFLOW','Rendered text exceeds fixed box; shorten content, never shrink font'))
        if e['kind']=='image':
            if not e['loaded']:errors.append(issue(page,e['id'],'IMAGE_DECODE','Image failed to decode'))
            if e['object_fit']!='contain':errors.append(issue(page,e['id'],'LOCKED_REGION','Image fit changed'))
    foreground=[e for e in measured['elements'] if e['kind']!='decoration']
    for i,a in enumerate(foreground):
        for b in foreground[i+1:]:
            if intersects(a['rect'],b['rect']):
                code='IMAGE_TEXT_OVERLAP' if 'image' in (a['kind'],b['kind']) else 'CONTENT_OVERLAP'
                errors.append(issue(page,a['id'],code,'Overlaps '+b['id']))
    return errors


def validate_values(layout, page, number):
    errors=[]
    if set(page)-{'template_id','values'}:
        errors.append(issue(number,'page','LOCKED_REGION','Content may not supply style, geometry, HTML or layout overrides'))
    values=page.get('values',{})
    if not isinstance(values,dict):
        return [issue(number,'values','SCHEMA','values must be an object')]
    required={e['id'] for e in layout['elements'] if e['kind']!='decoration'}
    if set(values)!=required:
        errors.append(issue(number,'values','SCHEMA','Content slots differ: '+str(sorted(set(values)^required))))
    for e in layout['elements']:
        v=values.get(e['id'])
        if e['kind'] in ('text','image') and (not isinstance(v,str) or not v.strip()):
            errors.append(issue(number,e['id'],'SCHEMA','Nonempty text or asset ID required'))
        if e['kind']=='table' and (not isinstance(v,list) or len(v)!=e['rows'] or any(not isinstance(row,list) or len(row)!=e['columns'] or any(not isinstance(cell,str) or not cell.strip() for cell in row) for row in v)):
            errors.append(issue(number,e['id'],'SCHEMA','Table must match fixed rows/columns with nonempty strings'))
        if e['id']=='test_label' and (not isinstance(v,str) or '非客户交付' not in v):
            errors.append(issue(number,e['id'],'TEST_LABEL','Test output must visibly state 非客户交付'))
    return errors


def render(manifest, output, font_path=DEFAULT_FONT, chromium='/usr/bin/chromium'):
    output=Path(output)
    # Never overwrite another run or accidentally leave stale passing PNGs.
    output.mkdir(parents=True,exist_ok=False)
    report={'schema_version':1,'created_at':datetime.now(timezone.utc).isoformat(),'scope':'test_render_only',
            'customer_approved':False,'delivery_ready':False,'pages':[],'errors':[],
            'reference_audit':'references/phase2-asset-audit.json',
            'visual_approval':'pending_human_review',
            'visual_differences':['Solid background replaces paper texture; no original ornaments or exact font metrics','Image placeholders replace unverified source photos; rectangular panels are separated to prevent overlap','Cover labels/table and detail/caution panels use explicit new coordinates, not measured original layers'],
            'checks':['text_overflow','image_text_overlap','font_file_and_glyph_coverage','font_browser_load','page_size','image_bounds','locked_regions'],
            'limitations':['Prototype geometry differs from raster reference; human visual approval required','Asset subject/rights metadata requires human evidence verification','No automatic food recognition, medical fact checking or foreground segmentation']}
    def finish():
        for entry in report['pages']:
            entry['errors']=[e for e in report['errors'] if e['page'] in (entry['page'], None)]
            entry['status']='FAIL' if entry['errors'] else 'PASS_LAYOUT_ONLY'
        report['status']='FAIL' if report['errors'] else 'PASS_TEST_ONLY'
        (output/'qc_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        return report
    try:
        if not isinstance(manifest,dict) or manifest.get('schema_version')!=1:
            raise ValueError('Unsupported manifest schema')
        if manifest.get('mode')!='test' or manifest.get('test_only') is not True:
            raise ValueError('Production disabled: template approval and real assets missing')
        if not isinstance(manifest.get('subject'),str) or not manifest['subject'].strip():
            raise ValueError('Subject required')
        if not isinstance(manifest.get('pages'),list) or len(manifest['pages'])<3:
            raise ValueError('At least three pages required')
        if set(manifest)-{'schema_version','mode','test_only','subject','source_family','pages','assets'}:
            raise ValueError('Unknown manifest keys; layout overrides forbidden')
        layouts=[]
        font_chars=''
        prepared={}
        for number,page in enumerate(manifest['pages'],1):
            record={'page':number,'template_id':page.get('template_id'),'elements':[], 'errors':[]}
            report['pages'].append(record)
            try:
                layout=load_template(page.get('template_id'))
                layouts.append(layout)
                record['reference']=layout['reference']
                record['layout_sha256']=sha(repository_path(json.loads((ROOT/'rendering/template_registry.json').read_text())['templates'][layout['id']]['path']))
                errs=validate_values(layout,page,number)
                if errs:
                    report['errors'].extend(errs);continue
                font_chars+=''.join(str(v) for k,v in page['values'].items())
                for e in layout['elements']:
                    if e['kind']!='image':continue
                    asset_id=page['values'][e['id']]
                    try:
                        prepared[asset_id]=prepare_asset(manifest.get('assets',{}).get(asset_id),manifest['subject'],'test')
                    except (ValueError,OSError) as exc:
                        report['errors'].append(issue(number,e['id'],'ASSET_INVALID',str(exc)))
            except (ValueError,TypeError,KeyError) as exc:
                report['errors'].append(issue(number,'template','LOCKED_REGION',str(exc)))
        if report['errors']:return finish()
        # Introduction cover/detail must contain different image bytes, not just IDs.
        roles={l['role']:i for i,l in enumerate(layouts)}
        if 'cover' in roles and 'detail' in roles:
            ci,di=roles['cover'],roles['detail']
            ca=manifest['pages'][ci]['values'].get('food'); da=manifest['pages'][di]['values'].get('food')
            if ca and da and prepared[ca][1]['sha256']==prepared[da][1]['sha256']:
                report['errors'].append(issue(di+1,'food','REPEATED_PHOTO','Cover/detail require different image bytes'))
        try:
            fonts,report['font']=font_data(font_path,font_chars)
            font_lock=json.loads((ROOT/'rendering/template_registry.json').read_text())['font_source_sha256']
            if report['font']['source_sha256']!=font_lock:
                raise ValueError('Font file hash differs from pinned template family')
        except (ValueError,OSError) as exc:
            for n,layout in enumerate(layouts,1):
                for e in layout['elements']:
                    if e['kind'] in ('text','table'):report['errors'].append(issue(n,e['id'],'FONT_MISSING',str(exc)))
            return finish()
        if report['errors']:return finish()
        report['assets']={k:v[1] for k,v in prepared.items()}
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=chromium,headless=True,args=['--no-sandbox','--font-render-hinting=none'])
            try:
                report['browser']=browser.version
                context=browser.new_context(viewport={'width':CANVAS[0],'height':CANVAS[1]},device_scale_factor=1,locale='zh-CN',service_workers='block')
                context.route('**/*',lambda route:route.abort())
                for n,(layout,page_input) in enumerate(zip(layouts,manifest['pages']),1):
                    page=context.new_page()
                    try:
                        html=build_html(layout,page_input['values'],prepared,fonts)
                        (output/f'{n:02d}.html').write_text(html)
                        page.set_content(html,wait_until='load')
                        page.evaluate('async () => { await document.fonts.ready; await Promise.all([...document.images].map(i=>i.decode())); }')
                        measurement=page.evaluate(MEASURE_JS)
                        errors=inspect_geometry(layout,measurement,n)
                        report['pages'][n-1]['elements']=measurement['elements']
                        # FontFaceSet.load must actually resolve our embedded face, not just a fallback.
                        loaded=page.evaluate("async () => (await document.fonts.load('28px PosterCJK')).map(f=>({family:f.family,status:f.status}))")
                        if not loaded or any(f['status']!='loaded' for f in loaded):errors.append(issue(n,'font','FONT_MISSING','Embedded face not loaded'))
                        report['pages'][n-1]['font_faces']=loaded
                        report['errors'].extend(errors)
                        if not errors:
                            target=output/f'{n:02d}.png'
                            page.screenshot(path=str(target),type='png',full_page=False,animations='disabled')
                            with Image.open(target) as png:
                                if png.size!=CANVAS:report['errors'].append(issue(n,'canvas','PAGE_SIZE','Exported PNG dimensions incorrect'))
                            report['pages'][n-1]['png']=target.name
                    finally:page.close()
                context.close()
            finally:browser.close()
        for entry in report['pages']:
            entry['errors']=[e for e in report['errors'] if e['page']==entry['page']]
            entry['status']='FAIL' if entry['errors'] else 'PASS_LAYOUT_ONLY'
        if not report['errors']:
            make_preview(output, len(layouts))
            make_comparison(output,layouts)
            report['preview']='preview.png';report['visual_comparison']='reference-comparison.png'
    except Exception as exc:
        report['errors'].append(issue(None,'render','RENDER_ERROR',type(exc).__name__+': '+str(exc)))
    return finish()


def make_preview(output,count):
    canvas=Image.new('RGB',(414*count,552),'#e4e2dc')
    for n in range(1,count+1):
        with Image.open(output/f'{n:02d}.png') as im:
            canvas.paste(im.convert('RGB').resize((414,552),Image.Resampling.LANCZOS),((n-1)*414,0))
    canvas.save(output/'preview.png')


def make_comparison(output,layouts):
    """Side-by-side, never claim numeric pixel similarity equals customer approval."""
    canvas=Image.new('RGB',(828,590*len(layouts)),'#dad7cd')
    draw=ImageDraw.Draw(canvas)
    for i,l in enumerate(layouts):
        draw.text((12,i*590+8),'REFERENCE (original text unverified)',fill='black')
        draw.text((426,i*590+8),'RENDER PROTOTYPE / NOT APPROVED',fill='black')
        for x,path in [(0,ROOT/l['reference']),(414,output/f'{i+1:02d}.png')]:
            with Image.open(path) as im:
                thumb=ImageOps.contain(im.convert('RGB'),(414,552))
                canvas.paste(thumb,(x,i*590+35))
    canvas.save(output/'reference-comparison.png')
