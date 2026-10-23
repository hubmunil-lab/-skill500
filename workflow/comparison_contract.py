"""Fixed comparison business contract; no substitute fields or reference-only bypass."""
import json
import math
import re
from .core import ROOT, digest

VERSION = 'compare-business-2'
PAGE_FIELDS = {1: ('appearance', 'taste', 'price'),
               2: ('energy', 'carbohydrate', 'sugars', 'vitamin_c', 'feature'),
               3: ('scene', 'selection')}
UNITS = {'energy': 'kcal', 'carbohydrate': 'g', 'sugars': 'g', 'vitamin_c': 'mg'}
FORBIDDEN = ('仅观察所提供的参考图', '参考图中的可见差异', '图片不能证明', '观察范围',
             '依据：参考图', '仅限参考图', '待核实', '内部审阅', '审核说明')
MATERIALS = {'appearance':'对应SKU的真实外观记录及授权照片', 'taste':'同一SKU的口感实测记录或可核实的厂家描述',
             'price':'带日期、渠道、币种及包装容量的价格记录',
             'energy':'热量及每100毫升计量基准', 'carbohydrate':'碳水及每100毫升计量基准',
             'sugars':'含糖量及每100毫升计量基准', 'vitamin_c':'维生素C及每100毫升计量基准',
             'feature':'适用特色成分的产品配料依据', 'scene':'有依据的实际食用场景', 'selection':'针对具体产品的选购依据'}


def missing_comparison(task):
    """No inference from an image to nutrition, taste, price or SKU."""
    missing = [{'code':'MISSING_FACT_EVIDENCE', 'page': page, 'side': side,
                'field': key, 'required_material': MATERIALS[key]}
               for page, keys in PAGE_FIELDS.items() for side in ('left','right') for key in keys]
    missing += [{'code':'MISSING_PRODUCT_IDENTITY', 'side':side, 'required_material':'品牌、SKU、规格、地区/版本、生熟或即饮状态'} for side in ('left','right')]
    missing += [{'code':'AUTHORIZED_MATCHING_ASSETS_REQUIRED', 'side':side, 'required_material':'匹配SKU的高清图片、授权凭据与允许用途'} for side in ('left','right')]
    return {'schema_version':2,'status':'BLOCKED','query':task['original_query'],
            'contract':VERSION,'render_allowed':False,'errors':missing}


def load_source(reference):
    import hashlib
    path = (ROOT/reference['path']).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file(): raise ValueError('source file outside repository or missing')
    if hashlib.sha256(path.read_bytes()).hexdigest() != reference['sha256']: raise ValueError('source hash mismatch')
    return json.loads(path.read_text())


def query_intent(task, subjects):
    if len(subjects)!=2:return None
    pattern=re.escape(subjects[0].get('name',''))+'与'+re.escape(subjects[1].get('name',''))+r'每100毫升(含糖量哪个更低|维生素C哪个更多)'
    match=re.fullmatch(pattern,task['search_query'])
    if not match:return None
    metric='sugars' if match.group(1)=='含糖量哪个更低' else 'vitamin_c'
    if any(word in task['direction'] for word in ('孕期','孕妇','治病','降血糖','减肥功效')):return None
    return {'metric':metric,'operation':'min' if metric=='sugars' else 'max','basis':{'amount':100,'unit':'ml'},'subjects':[s['id'] for s in subjects]}


def business_qc(packet, task, production=False):
    errors=[]
    def fail(code, **where): errors.append({'code':code, **where})
    if packet.get('schema_version') != 2 or packet.get('contract') != VERSION: fail('BUSINESS_SCHEMA')
    if packet.get('mode') not in ('synthetic_test','production'): fail('EVIDENCE_MODE_REQUIRED')
    expected_binding = {'query':task['search_query'], 'direction':task['direction']}
    if packet.get('query_binding') != expected_binding: fail('QUERY_BINDING_MISMATCH')
    subjects=packet.get('subjects',[])
    if len(subjects)!=2 or len({x.get('id') for x in subjects})!=2: fail('SUBJECT_IDENTITY')
    if any(not s.get('sku') or not s.get('specification') or not s.get('name') for s in subjects):fail('PRODUCT_SPECIFICATION_MISSING')
    for s in subjects:
        if s.get('name','__absent__') not in task['search_query']: fail('QUERY_OBJECT_MISMATCH', subject=s.get('id'))
    sources={}
    for source_id, reference in packet.get('sources',{}).items():
        try:
            sources[source_id]=load_source(reference)
            if production and (sources[source_id].get('synthetic') or not reference.get('verified_for_production')):fail('NON_PRODUCTION_EVIDENCE',source=source_id)
        except (ValueError,KeyError,OSError,json.JSONDecodeError) as error:fail('EVIDENCE_SOURCE_INVALID',source=source_id,detail=str(error))
    pages=packet.get('pages',[])
    if len(pages)!=3:fail('BUSINESS_PAGE_COUNT')
    for n,keys in PAGE_FIELDS.items():
        if len(pages)<n:continue
        page=pages[n-1]
        if page.get('number')!=n or page.get('role')!={1:'appearance_taste_price',2:'nutrition',3:'scene_selection'}[n]:fail('BUSINESS_PAGE_ROLE',page=n)
        if page.get('subject_order')!=[s.get('id') for s in subjects]:fail('CROSS_PAGE_IDENTITY',page=n)
        for side,subject in zip(('left','right'),subjects):
            fields=page.get(side,{})
            if set(fields)!=set(keys):fail('BUSINESS_FIELDS',page=n,side=side,required=list(keys))
            for key in keys:
                ref=fields.get(key,{})
                fact=ref.get('fact',{})
                location={'page':n,'side':side,'field':key}
                source=sources.get(ref.get('source_id'),{})
                evidence=source.get('facts',{}).get(ref.get('fact_id'))
                if not evidence or fact != evidence:fail('FACT_EVIDENCE_VALUE_MISMATCH',**location)
                if fact.get('subject_id')!=subject.get('id') or fact.get('field')!=key:fail('FACT_TYPE_OR_SUBJECT_MISMATCH',**location)
                if not isinstance(fact.get('value'),(str,int,float)) or isinstance(fact.get('value'),bool) or fact.get('value')=='':fail('FACT_VALUE_MISSING',**location)
                if any(word in str(fact.get('value','')) for word in FORBIDDEN):fail('INTERNAL_NOTE_IN_CONTENT',**location)
                if key in UNITS:
                    value=fact.get('value')
                    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:fail('NUTRIENT_VALUE_INVALID',**location)
                    if fact.get('unit')!=UNITS[key]:fail('NUTRIENT_UNIT',**location)
                    if fact.get('basis')!={'amount':100,'unit':'ml','state':'ready_to_drink'}:fail('NUTRIENT_BASIS',**location)
                if key=='price' and (fact.get('unit')!='CNY' or not fact.get('date') or not fact.get('channel') or fact.get('volume_ml')!=500):fail('PRICE_CONTEXT',**location)
                if key=='feature' and not fact.get('ingredient_basis'):fail('FEATURE_INGREDIENT_BASIS',**location)
    # Numeric relationships are structural; exact source matching alone is not enough.
    if len(pages)>1:
        for side in ('left','right'):
            f=pages[1].get(side,{})
            sugar=f.get('sugars',{}).get('fact',{}).get('value')
            carb=f.get('carbohydrate',{}).get('fact',{}).get('value')
            if isinstance(sugar,(int,float)) and isinstance(carb,(int,float)) and sugar>carb:fail('SUGARS_EXCEED_CARBOHYDRATE',page=2,side=side)
    intent=query_intent(task,subjects)
    if intent is None:fail('QUERY_SEMANTICS_UNSUPPORTED')
    elif packet.get('focus')!=intent['metric']:fail('QUERY_FOCUS_MISMATCH')
    focus = packet.get('focus')
    if focus not in ('sugars','vitamin_c'):fail('UNSUPPORTED_QUERY_FOCUS')
    elif ('含糖量' if focus=='sugars' else '维生素C') not in task['search_query']:fail('QUERY_FOCUS_MISMATCH')
    return {'status':'FAIL' if errors else 'PASS_STRUCTURED_BUSINESS_CHECKS', 'errors':errors,
            'customer_approved':False, 'semantic_review_required':True,
            'human_checklist':['原始问题与直接答案是否一致','口感记录是否支持描述','产品身份与图片是否一致',
                              '事实来源是否权威且适用当前SKU','正文与每页信息是否一致','版面是否接近客户参考'],
            'limitation':'结构、类型、数值和精确证据映射可自动检查；来源真实性与业务语义需人工核查'}


def compile_copy(packet, task):
    qc=business_qc(packet,task,production=packet.get('mode')=='production')
    if qc['errors']: raise ValueError('BUSINESS_QC_FAILED: '+json.dumps(qc['errors'],ensure_ascii=False))
    subjects=packet['subjects'];left,right=subjects
    pages=packet['pages'];focus=packet['focus']; label={'sugars':'含糖量','vitamin_c':'维生素C'}[focus]
    values=[pages[1][side][focus]['fact']['value'] for side in ('left','right')]
    unit=UNITS[focus]
    if values[0]==values[1]: conclusion='两者相同'
    else:
        winner=subjects[(values[1]<values[0]) if focus=='sugars' else (values[1]>values[0])]['name']
        conclusion=winner+('更低' if focus=='sugars' else '更多')
    answer=f'每100毫升{label}：{left["name"]}{values[0]:g}{unit}，{right["name"]}{values[1]:g}{unit}，{conclusion}。'
    manifest=json.loads((ROOT/'examples/customer_templates/compare.json').read_text())
    manifest['item_order']=[s['id'] for s in subjects]
    slot_bindings={}; paragraphs=[]
    for n,page in enumerate(manifest['pages'],1):
        page['item_ids']=manifest['item_order'][:]
        for side,subject in zip(('left','right'),subjects):page['values']['name_'+side]=subject['name']
        paragraphs.append(f'第{n}页')
        for side in ('left','right'):
            for key,ref in pages[n-1][side].items():
                fact=ref['fact']; value=fact['value']
                if key in UNITS: text={'energy':'热量','carbohydrate':'碳水','sugars':'含糖量','vitamin_c':'维生素C'}[key]+f'：{value:g}{fact["unit"]}'
                elif key=='price':text=f'{value:g}元／500毫升\n'+fact['date'][5:].replace('-', '月')+'日测试渠道' if packet['mode']=='synthetic_test' else f'{value:g}元／500毫升\n'+fact['date']
                elif key=='feature':text='特色成分：'+str(value)
                else:text=str(value)
                slot={1:{'appearance':'field_1','taste':'field_2','price':'field_3'},
                      2:{'energy':'nutrient_1','carbohydrate':'nutrient_2','sugars':'nutrient_3','vitamin_c':'nutrient_4','feature':'nutrient_5'},
                      3:{'scene':'use','selection':'select'}}[n][key]+'_'+side
                page['values'][slot]=text
                slot_bindings[f'{n}.{slot}']={'source_id':ref['source_id'],'fact_id':ref['fact_id'],'field':key,'subject_id':fact['subject_id'],'text':text}
                field_label={'appearance':'外观','taste':'口感','price':'价格','energy':'热量','carbohydrate':'碳水','sugars':'含糖量','vitamin_c':'维生素C','feature':'特色成分','scene':'食用场景','selection':'选购建议'}[key]
                paragraphs.append(subjects[0 if side=='left' else 1]['name']+'｜'+field_label+'：'+text.replace('\n','；'))
    p=manifest['pages'][0]['values']
    cover_answer=('两者'+label+'相同') if values[0]==values[1] else winner+label+('更低' if focus=='sugars' else '更多')
    p.update(title=cover_answer,subtitle='虚构配方｜每100毫升' if packet['mode']=='synthetic_test' else '每100毫升，同规格比较',
             tag_1='外观特点',tag_2='口感区别',tag_3='价格差异')
    manifest['pages'][1]['values']['title']='每100毫升营养对比'
    manifest['pages'][2]['values']['title']='食用场景与选购'
    body=answer+'\n\n'+'\n'.join(paragraphs)
    return {'original_query':task['original_query'],'query_binding':packet['query_binding'],'direct_answer':answer,
            'title':task['search_query'],'body':body,'manifest':manifest,'slot_bindings':slot_bindings,
            'intent':query_intent(task,subjects),'focus':focus,'evidence_mode':packet['mode'],'business_qc':qc,'content_hash':digest({'body':body,'pages':manifest['pages']})}


def copy_qc(copy, packet, task):
    expected=compile_copy(packet,task)
    errors=[]
    for field in ('query_binding','direct_answer','title','body','manifest','slot_bindings','intent','focus','evidence_mode'):
        if copy.get(field)!=expected[field]:errors.append({'code':'COPY_FACT_OR_QUERY_MISMATCH','element':field})
    for page in copy.get('manifest',{}).get('pages',[]):
        for slot,text in page['values'].items():
            if any(word in text for word in FORBIDDEN):errors.append({'code':'INTERNAL_NOTE_IN_CONTENT','element':slot})
    return {'errors':errors,'status':'FAIL' if errors else 'PASS_CONTENT_BINDINGS',
            'semantic_review_required':True,'checks':['exact_typed_fact_bindings','query_focus_computation','article_poster_same_source','cross_page_identity']}
