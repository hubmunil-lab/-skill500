"""Structured preflight QC, complementary to legacy image-file validation.

Evidence records are required but not independently verified here. Human review
remains mandatory; PASS only means this structured preflight found no issues.
"""
import re
from .config import load, normalize_category, template


def check(data):
    issues = []
    def add(code, message, severity='blocking'):
        issues.append({'code': code, 'message': message, 'severity': severity})
    if not isinstance(data, dict):
        return {'status':'FAIL','scope':'structured_preflight','issues':[{'code':'SCHEMA','message':'manifest must be an object','severity':'blocking'}]}
    try:
        category = normalize_category(data.get('category',data.get('type')))
    except ValueError:
        category = None
        add('CATEGORY', '未知分类')
    rules = load('production_rules.yaml')
    qc = load('qc_rules.yaml')
    for field in rules['global']['required_fields']:
        if field == 'required_answers':
            continue
        if not isinstance(data.get(field),str) or not data[field].strip():
            add('TEXT','缺少非空字段: '+field)
    title = data.get('title','')
    if isinstance(title,str) and len(title)>=rules['global']['title_max_exclusive']:
        add('TEXT','标题须少于20字')
    pages = data.get('pages',[])
    if not isinstance(pages,list) or any(not isinstance(p,dict) for p in pages):
        add('SCHEMA','pages须为对象数组')
        pages = []
    if len(pages)<rules['global']['min_pages']:
        add('PAGE_COUNT','至少3页')
    answers = data.get('required_answers',[])
    if not isinstance(answers,list) or len(answers)<rules['global']['min_information_points'] or any(not isinstance(a,dict) or not isinstance(a.get('id'),str) or not a['id'].strip() or not isinstance(a.get('question'),str) or not a['question'].strip() for a in answers):
        add('COMPLETENESS','至少3个具有id/question的必答点')
        answer_ids = []
    else:
        answer_ids = [a['id'] for a in answers]
        if len(set(answer_ids))!=len(answer_ids):
            add('COMPLETENESS','必答点ID重复')
    covered = set()
    for p in pages:
        ids = p.get('answer_ids',[])
        if not isinstance(ids,list) or any(not isinstance(x,str) for x in ids):
            add('COMPLETENESS','页面answer_ids格式错误')
            ids=[]
        if not ids or not set(ids)<=set(answer_ids):
            add('COMPLETENESS','每页须对应已声明必答点')
        covered.update(ids)
        if p.get('size') != rules['global']['canvas']:
            add('LAYOUT','页面尺寸须1242×1656')
    if not set(answer_ids)<=covered:
        add('COMPLETENESS','有必答点未分配页面')
    # The body-order assertion is structural; human review checks actual prose.
    if data.get('body_answer_ids') != answer_ids:
        add('COMPLETENESS','正文必答点覆盖及顺序缺失')
    selected = None
    try:
        selected = template(data.get('template_id'))
        if category not in selected['categories']:
            add('TEMPLATE','模板分类不匹配')
        if any(topic in data.get('query','') for topic in selected['excluded_topics']):
            add('TEMPLATE','该模板不适用此主题')
        if not (selected['editable'] and selected['editable_source'] and selected['layout_spec'] and selected['approval_status']=='approved'):
            add('TEMPLATE','目录未登记已验收可编辑工程，不能以manifest自行批准')
    except (ValueError,TypeError):
        add('TEMPLATE','模板未注册')
    if category:
        content = data.get('content', {})
        for field in rules['categories'][category]['required_fields']:
            if not isinstance(content, dict) or not isinstance(content.get(field), (str, list, dict)) or not content[field]:
                add('COMPLETENESS', '缺少类目内容字段: ' + field)
    if category and rules['categories'][category]['rule_status']=='partial':
        add('CATEGORY','类目培训规则待确认','review')
    if category=='intro':
        roles=[p.get('role') for p in pages]
        if roles[:2]!=['cover','detail'] or roles.count('recipe')!=3:
            add('RECIPE','介绍须封面、详情及三道真实步骤食谱')
        recipe_ids=[]
        for p in pages:
            if p.get('role')!='recipe':
                continue
            recipe_ids.append(p.get('recipe_id'))
            steps=p.get('steps',[])
            # Existing legacy validator's 2-step minimum, not a newly inferred client rule.
            if not isinstance(steps,list) or len(steps)<rules['global']['legacy_recipe_min_steps'] or any(not isinstance(s,str) or not s.strip() for s in steps) or not p.get('recipe_title'):
                add('RECIPE','菜名及至少两步操作缺失（沿用旧校验器）')
            if p.get('asset_kind') not in ['licensed_real_step_photos','owned_real_step_photos']:
                add('RIGHTS','食谱须真实步骤照片')
            if not p.get('subject_ingredient_id') or p.get('subject_ingredient_id')!=data.get('subject_ingredient_id') or p.get('query_match_reviewed') is not True:
                add('RECIPE','食谱食材及query匹配未确认','review')
        if any(not isinstance(x,str) or not x.strip() for x in recipe_ids) or len(set(str(x) for x in recipe_ids))!=3:
            add('RECIPE','须三道不同且有ID的食谱')
        if len(pages)>=2 and (not pages[0].get('photo_id') or not pages[1].get('photo_id') or pages[0].get('photo_id')==pages[1].get('photo_id')):
            add('LAYOUT','介绍前两页须不同照片')
    if category in ['recommendation','inventory']:
        order=data.get('ingredient_order')
        details=[]
        for p in pages[1:]:
            ids=p.get('item_ids',[])
            if not isinstance(ids,list) or any(not isinstance(x,str) or not x.strip() for x in ids):
                add('ORDER','详情item_ids格式错误')
            else:
                details.extend(x.strip().casefold() for x in ids)
            if p.get('item_kind')!='ingredient':
                add('COMPLETENESS','推荐盘点只展示食材')
        if len(details)!=len(set(details)):
            add('DUPLICATE','详情食材重复')
        if not isinstance(order,list) or not order or any(not isinstance(x,str) or not x.strip() for x in order):
            add('ORDER','缺少有效ingredient_order')
        elif not pages or pages[0].get('item_ids')!=order or data.get('body_item_ids')!=order or details!=[x.strip().casefold() for x in order]:
            add('ORDER','封面详情正文顺序不一致')
        if selected and isinstance(order,list) and len(order)!=selected['cover_slots']:
            add('LAYOUT','固定封面槽位数量不匹配')
        for p in pages[1:]:
            if selected and selected['detail_slots'] and (not isinstance(p.get('item_ids'),list) or len(p['item_ids'])!=selected['detail_slots']):
                add('LAYOUT','固定详情槽位数量不匹配')
        if not pages or pages[0].get('role')!='cover' or any(p.get('role')!='detail' for p in pages[1:]):
            add('PAGE_COUNT','须封面及至少两张详情')
    if category=='comparison':
        objects=data.get('object_order',[])
        if not isinstance(objects,list) or len(objects)!=2 or any(not isinstance(x,str) or not x.strip() for x in objects) or len(set(objects))!=2:
            add('COMPARISON','须恰好两个不同对象')
            objects=[]
        kinds=data.get('object_kinds',[])
        if kinds not in [['ingredient','ingredient'],['commercial','commercial']]:
            add('COMPARISON','对象须同类，不混比自制与商品饮品')
        for p in pages:
            photos=p.get('object_photo_ids')
            if p.get('object_ids')!=objects or not isinstance(photos,list) or len(photos)!=2 or not all(isinstance(x,str) and x.strip() for x in photos) or photos!=pages[0].get('object_photo_ids'):
                add('COMPARISON','对象身份、照片及左右顺序不一致')
    # Only publishable fields are scanned: an original query may itself ask about a banned claim.
    text=json_text({'title':data.get('title'), 'body':data.get('body'), 'direct_answer':data.get('direct_answer'), 'pages':pages})
    for phrase in qc['banned_health_phrases']:
        if phrase in text:
            add('HEALTH','需复核禁用表述: '+phrase)
    claims=data.get('claims')
    if not isinstance(claims,list):
        add('HEALTH','须显式提供claims数组，无主张时为空数组','review')
    else:
        for claim in claims:
            if not isinstance(claim,dict) or not claim.get('text') or not claim.get('source') or claim.get('verified') is not True:
                add('HEALTH','主张缺核实记录')
            elif claim.get('kind')=='nutrition' and not all(claim.get(k) for k in ['basis','food_state','edible_portion_or_product_spec']):
                add('HEALTH','营养数据缺计量及食物状态基准')
    for field, code in [('fact_review','HEALTH'),('rights_review','RIGHTS'),('visual_review','LAYOUT'),('semantic_review','COMPLETENESS')]:
        record=data.get(field)
        if not isinstance(record,dict) or record.get('approved') is not True or not all(isinstance(record.get(k),str) and record[k].strip() for k in ['reviewer','evidence']):
            add(code,'缺人工审查及证据: '+field,'review')
    for p in pages:
        if p.get('layout_overrides'):
            add('LAYOUT','不得擅自改变版式')
        if not p.get('layout_id'):
            add('LAYOUT','未绑定已验收版式')
    return {'status':'FAIL' if any(i['severity']=='blocking' for i in issues) else 'REVIEW' if issues else 'PASS',
            'scope':'structured_preflight_only_not_pixel_or_fact_verification','issues':issues}


def json_text(value):
    import json
    return json.dumps(value,ensure_ascii=False)
