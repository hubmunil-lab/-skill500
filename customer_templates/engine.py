"""Source-coordinate fixed layouts built on the existing Playwright QC engine."""
import base64
from io import BytesIO
import json
from pathlib import Path
from html import escape
from PIL import Image, ImageChops, ImageDraw, ImageStat
from playwright.sync_api import sync_playwright
from rendering.engine import ROOT, sha, font_data, DEFAULT_FONT, MEASURE_JS, inspect_geometry, intersects
from delivery.engine import finite_json
from .prepare import configs, REGISTRY

SERIF=Path('/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc')
EXPECTED_COUNTS={'compare':3,'recommend':3,'list':4,'intro':5}


def project(config):
    w,h=config['source_size'];scale=min(1242/w,1656/h);dx=(1242-w*scale)/2;dy=(1656-h*scale)/2
    return scale,dx,dy


def metric_layout(config):
    scale,dx,dy=project(config);elements=[]
    for slot in config['slots']:
        x1,y1,x2,y2=slot['box'];element={'id':slot['id'],'kind':slot['kind'],'x':dx+x1*scale,'y':dy+y1*scale,'width':(x2-x1)*scale,'height':(y2-y1)*scale}
        if slot['kind']=='text':element.update(font_size=slot['font_size']*scale,line_height=slot['line_height']*scale,weight=slot['weight'],color=slot['color'])
        elements.append(element)
    return {'elements':elements}


def data_uri(path):
    return 'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()


def validate(manifest,components):
    if not isinstance(manifest,dict) or set(manifest)!={'schema_version','category','mode','item_order','pages'}:raise ValueError('MANIFEST_SCHEMA: unknown/missing root keys')
    category=manifest['category']
    if manifest['schema_version']!=1 or manifest['mode']!='reconstruction_test' or category not in EXPECTED_COUNTS:raise ValueError('TEST_ONLY: no production mode or unsupported category')
    selected=sorted([c for c in configs() if c['category']==category],key=lambda c:c['page_number'])
    if len(manifest['pages'])!=EXPECTED_COUNTS[category]:raise ValueError('PAGE_COUNT: wrong number of pages')
    root_order=manifest['item_order']
    for page,config in zip(manifest['pages'],selected):
        if set(page)!={'template_id','item_ids','values'} or page['template_id']!=config['id']:raise ValueError('PAGE_ORDER: page/template mismatch')
        if page['item_ids']!=config['item_order']:raise ValueError('ITEM_ORDER: changed objects/steps')
        values=page['values']
        if not isinstance(values,dict) or set(values)!={s['id'] for s in config['slots']}:raise ValueError('CONTENT_MISSING: exact slot set required')
        for slot in config['slots']:
            value=values[slot['id']]
            if not isinstance(value,str) or not value.strip():raise ValueError('CONTENT_MISSING: '+config['id']+'/'+slot['id'])
            if slot['kind']=='image':
                asset_id=asset_key(config,value)
                if value!=slot['id'] or asset_id not in components['assets']:raise ValueError('ASSET_IDENTITY: missing/swapped photo '+slot['id'])
                asset=components['assets'][asset_id]
                if asset['subject']!=slot['subject'] or sha(ROOT/asset['path'])!=asset['sha256']:raise ValueError('ASSET_CHANGED: '+asset_id)
        plate=components['backgrounds'][config['id']]
        if sha(ROOT/plate['path'])!=plate['sha256']:raise ValueError('LOCKED_BACKGROUND: '+config['id'])
    if category=='compare':
        if root_order!=['lemon_drink','cola'] or any(p['item_ids']!=root_order for p in manifest['pages']):raise ValueError('CROSS_PAGE_ORDER: comparison identity')
        for side in ['left','right']:
            if len({p['values']['name_'+side] for p in manifest['pages']})!=1:raise ValueError('CROSS_PAGE_LABEL: comparison label')
    elif category=='recommend':
        if len({p['values']['title'] for p in manifest['pages']})!=1:raise ValueError('CROSS_PAGE_LABEL: recommendation header')
        if [x for p in manifest['pages'] for x in p['item_ids']]!=root_order or len(set(root_order))!=len(root_order):raise ValueError('CROSS_PAGE_ORDER: recommendation duplicates/order')
        for i,item in enumerate(root_order,1):
            page=next((p for p in manifest['pages'] if item in p['item_ids']),None)
            if page is None or page['values'].get('number_'+item)!=f'{i:02d}':raise ValueError('VISIBLE_ORDER: recommendation item number')
    elif category=='list':
        if manifest['pages'][0]['item_ids']!=root_order or [x for p in manifest['pages'][1:] for x in p['item_ids']]!=root_order or len(set(root_order))!=len(root_order):raise ValueError('CROSS_PAGE_ORDER: list cover/detail order')
        for item in root_order:
            names=[p['values']['name_'+item] for p in manifest['pages'] if 'name_'+item in p['values']]
            if len(set(names))!=1:raise ValueError('CROSS_PAGE_LABEL: list name inconsistency')
    elif category=='intro':
        if root_order!=['pepper','pie','tiger_pepper','pepper_pork']:raise ValueError('CROSS_PAGE_ORDER: intro role/recipe order')
        for i in range(1,4):
            if manifest['pages'][0]['values'][f'benefit_{i}']!=manifest['pages'][1]['values'][f'benefit_{i}']:raise ValueError('CROSS_PAGE_LABEL: intro feature mismatch')
        for page in manifest['pages'][2:]:
            for key,value in page['values'].items():
                if key.startswith('step_caption_') and not value.startswith('步骤'+key.split('_')[-1]+'｜'):raise ValueError('VISIBLE_ORDER: recipe caption sequence')
        if len({p['values']['recipe_title'] for p in manifest['pages'][2:]})!=3:raise ValueError('RECIPE_COMPLETENESS: distinct recipe titles required')
    return selected


def asset_key(config,id):return (config['id']+'-'+id) if config['category']=='intro' else config['category']+'-'+id


def html(config,values,components,fonts):
    scale,dx,dy=project(config);layout=metric_layout(config)
    faces=''.join(f"@font-face{{font-family:{name};src:url(data:font/ttf;base64,{base64.b64encode(data).decode()});font-weight:100 900;ascent-override:88%;descent-override:12%;line-gap-override:0%}}" for name,data in fonts.items())
    image=components['backgrounds'][config['id']]
    parts=[f'<img id="locked-plate" src="{data_uri(ROOT/image["path"])}" style="position:absolute;left:{dx}px;top:{dy}px;width:{config["source_size"][0]*scale}px;height:{config["source_size"][1]*scale}px"/>']
    for slot,element in zip(config['slots'],layout['elements']):
        style='position:absolute;'+''.join(f'{key}:{element[key]}px;' for key in ['width','height'])+f'left:{element["x"]}px;top:{element["y"]}px;'
        if slot['kind']=='image':
            asset=components['assets'][asset_key(config,values[slot['id']])]
            parts.append(f'<img class="element" data-kind="image" id="{slot["id"]}" src="{data_uri(ROOT/asset["path"])}" style="{style}object-fit:contain"/>')
        else:
            font=('PosterCJKSerif' if slot['font']=='serif' else 'PosterCJK')+('Bold' if slot['weight']>=700 else '')
            style+=f"font-family:{font};font-size:{element['font_size']}px;line-height:{element['line_height']}px;font-weight:{slot['weight']};color:{slot['color']};text-align:{slot['align']};"
            if slot.get('vertical_align')=='center':style+=f"padding-top:{max(0,(element['height']-element['line_height'])/2)}px;"
            if slot['outline']:style+=f"-webkit-text-stroke:{slot['outline']*scale}px {slot['outline_color']};paint-order:stroke fill;"
            parts.append(f'<div class="element" data-kind="text" id="{slot["id"]}" style="{style}">{escape(values[slot["id"]])}</div>')
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>'+faces+'*{box-sizing:border-box}html,body{margin:0;width:1242px;height:1656px;background:#ffffff}.element{white-space:pre-wrap;overflow:visible;overflow-wrap:anywhere}</style><body>'+''.join(parts)+'</body></html>'


def inspect(config,measurement,number):
    errors=inspect_geometry(metric_layout(config),measurement,number)
    allowed={frozenset(pair) for pair in config['allowed_overlaps']}
    def permitted(e):
        return e['message'].startswith('Overlaps ') and frozenset([e['element'],e['message'][9:]]) in allowed
    # Text boxes may intersect reference centre-label boxes; visible glyphs may not.
    errors=[e for e in errors if e['code']!='CONTENT_OVERLAP' and not (e['code']=='IMAGE_TEXT_OVERLAP' and permitted(e))]
    texts=[e for e in measurement['elements'] if e['kind']=='text']
    for i,a in enumerate(texts):
        for b in texts[i+1:]:
            if frozenset([a['id'],b['id']]) in allowed:continue
            if any(intersects(x,y) for x in a['text_rects'] for y in b['text_rects']):errors.append({'code':'TEXT_OCCLUSION','page':number,'element':a['id'],'message':'Rendered glyphs overlap '+b['id'],'severity':'error'})
    return errors


def comparison(config,png,output,number):
    w,h=config['source_size'];scale,dx,dy=project(config)
    with Image.open(ROOT/config['reference']) as source:
        fitted=Image.new('RGB',(1242,1656),'white');fitted.paste(source.convert('RGB').resize((round(w*scale),round(h*scale)),Image.Resampling.BILINEAR),(round(dx),round(dy)))
    with Image.open(png) as image:
        actual=image.convert('RGB');diff=ImageChops.difference(fitted,actual)
        mask=Image.new('L',(1242,1656),255);d=ImageDraw.Draw(mask)
        for s in config['slots']:
            x1,y1,x2,y2=s['box'];d.rectangle((dx+x1*scale-3,dy+y1*scale-3,dx+x2*scale+3,dy+y2*scale+3),fill=0)
        pair=Image.new('RGB',(828,582),'#eeeeee');draw=ImageDraw.Draw(pair)
        draw.text((8,8),'REFERENCE / UNVERIFIED TEXT',fill='black');draw.text((422,8),'EDITABLE TEST / NOT APPROVED',fill='black')
        pair.paste(fitted.resize((414,552)),(0,30));pair.paste(actual.resize((414,552)),(414,30));pair.save(output/f'{number:02d}-comparison.png')
        diff.point(lambda v:min(255,v*4)).save(output/f'{number:02d}-difference.png')
        return {'fixed_region_pixel_fraction':mask.histogram()[255]/(1242*1656),'fixed_region_metric_reliable':mask.histogram()[255]/(1242*1656)>=0.05,'overall_mean_absolute_rgb_error':sum(ImageStat.Stat(diff).mean)/3,'fixed_region_mean_absolute_rgb_error':sum(ImageStat.Stat(diff,mask).mean)/3,'meaning':'Test text deliberately differs; pixel metrics are diagnostic, not customer approval.'}


def render(manifest,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    report={'schema_version':1,'category':manifest.get('category'),'status':'FAIL','customer_approved':False,'delivery_ready':False,'scope':'customer_reference_reconstruction_test','pages':[],'errors':[],'warnings':['Original font files and source layers unavailable; metric replacements need manual approval','Background repair, image-caption separation and native-to-canvas margins are documented approximations','Test field text is not a health/nutrition claim; source screenshot claims are not independently verified']}
    def finish():
        (output/'qc_report.json').write_text(json.dumps(finite_json(report),ensure_ascii=False,indent=2,allow_nan=False)+'\n');return report
    try:
        registry=json.loads((ROOT/'customer_templates/registry.json').read_text())
        for path,expected in registry['font_files'].items():
            if sha(Path(path))!=expected:raise ValueError('FONT_CHANGED: '+path)
        components=json.loads((ROOT/REGISTRY).read_text())
        selected=validate(manifest,components)
        if manifest['category']=='recommend':report['warnings'].append('Three detail pages supplied; standalone cover is absent. Production structure requires customer clarification.')
        chars=''.join(str(v) for p in manifest['pages'] for v in p['values'].values())
        sans,sansmeta=font_data(DEFAULT_FONT,chars);serif,serifmeta=font_data(SERIF,chars)
        bold,boldmeta=font_data(Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'),chars)
        serifbold,serifboldmeta=font_data(Path('/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'),chars)
        fonts={'PosterCJK':sans,'PosterCJKSerif':serif,'PosterCJKBold':bold,'PosterCJKSerifBold':serifbold};report['fonts']={'sans':sansmeta,'serif':serifmeta}
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--font-render-hinting=none'])
            try:
                report['browser']=browser.version
                context=browser.new_context(viewport={'width':1242,'height':1656},device_scale_factor=1,locale='zh-CN',service_workers='block');context.route('**/*',lambda r:r.abort())
                for n,(config,page_input) in enumerate(zip(selected,manifest['pages']),1):
                    page=context.new_page()
                    try:
                        content=html(config,page_input['values'],components,fonts);(output/f'{n:02d}.html').write_text(content)
                        page.set_content(content,wait_until='load');page.evaluate('async()=>{await Promise.all(["PosterCJK","PosterCJKSerif","PosterCJKBold","PosterCJKSerifBold"].map(f=>document.fonts.load(`28px ${f}`)));await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()))}')
                        measured=finite_json(page.evaluate(MEASURE_JS));errors=inspect(config,measured,n)
                        for family in {('PosterCJKSerif' if s.get('font')=='serif' else 'PosterCJK')+('Bold' if s.get('weight',400)>=700 else '') for s in config['slots'] if s['kind']=='text'}:
                            if not page.evaluate('async family=>(await document.fonts.load(`28px ${family}`)).length',family):errors.append({'code':'FONT_MISSING','page':n,'element':'font','message':'Font face not loaded: '+family})
                        plate=page.locator('#locked-plate').bounding_box();scale,dx,dy=project(config)
                        expected=[dx,dy,config['source_size'][0]*scale,config['source_size'][1]*scale]
                        if any(abs(plate[k]-v)>0.5 for k,v in zip(['x','y','width','height'],expected)):errors.append({'code':'LOCKED_BACKGROUND','page':n,'element':'locked-plate','message':'Fixed decoration plate moved'})
                        entry={'page':n,'template_id':config['id'],'reference':config['reference'],'reference_sha256':config['reference_sha256'],'elements':measured['elements'],'errors':errors,'registered_overlays':config['allowed_overlaps'],'status':'FAIL' if errors else 'PASS_LAYOUT'}
                        report['pages'].append(entry);report['errors'].extend(errors)
                        if not errors:
                            path=output/f'{n:02d}.png';page.screenshot(path=str(path),full_page=False)
                            with Image.open(path) as im:
                                if im.size!=(1242,1656):raise ValueError('PNG_SIZE: invalid export')
                            entry['pixel_diagnostics']=comparison(config,path,output,n)
                    finally:page.close()
                context.close()
            finally:browser.close()
        if not report['errors']:
            count=len(selected);preview=Image.new('RGB',(414*count,576),'#eeeeee');draw=ImageDraw.Draw(preview);draw.text((8,5),'CUSTOMER TEMPLATE RECONSTRUCTION TEST / NOT APPROVED',fill='black')
            pair=Image.new('RGB',(828,582*count),'#eeeeee')
            for n in range(1,count+1):
                with Image.open(output/f'{n:02d}.png') as im:preview.paste(im.resize((414,552)),((n-1)*414,24))
                with Image.open(output/f'{n:02d}-comparison.png') as im:pair.paste(im,(0,(n-1)*582))
            preview.save(output/'preview.png');pair.save(output/'reference-comparison.png');report['status']='PASS_RECONSTRUCTION_TEST_ONLY'
    except Exception as e:
        code=str(e).split(':')[0] if ':' in str(e) else 'RENDER_ERROR'
        if code in ['Font file missing','Missing glyphs']:code='FONT_MISSING'
        report['errors'].append({'code':code,'page':None,'element':None,'message':str(e)})
    return finish()
