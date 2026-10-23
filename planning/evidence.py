"""Resolve exact typed facts; report only query-relevant missing information."""
import json
from workflow.core import ROOT
from workflow.comparison_contract import load_source
from workflow.comparison_runner import validate_assets


def inspect_packet(packet, intent):
    facts={};errors=[];sources={};products=packet.get('subjects',[])
    needed=set(intent['required_facts'])
    used={r.get('source_id') for page in packet.get('pages',[]) for side in ('left','right') for field,r in page.get(side,{}).items() if field in needed}
    for key,reference in packet.get('sources',{}).items():
        if key not in used:continue
        try:
            document=load_source(reference);sources[key]=document
            if packet.get('mode')!='synthetic_test' and (document.get('synthetic') or not reference.get('verified_for_production')):
                errors.append({'code':'PRODUCTION_SOURCE_REVIEW_REQUIRED','source_id':key})
        except (ValueError,OSError,KeyError,json.JSONDecodeError) as error:errors.append({'code':'SOURCE_INVALID','source_id':key,'detail':str(error)})
    for page in packet.get('pages',[]):
        for side,subject in zip(('left','right'),products):
            for field,reference in page.get(side,{}).items():
                if field not in needed:continue
                fact=reference.get('fact',{});document=sources.get(reference.get('source_id'),{})
                exact=document.get('facts',{}).get(reference.get('fact_id'))
                if not exact or exact!=fact or fact.get('subject_id')!=subject['id'] or fact.get('field')!=field:
                    errors.append({'code':'TYPED_FACT_EVIDENCE_MISMATCH','side':side,'field':field});continue
                if field in facts.setdefault(side,{}):errors.append({'code':'DUPLICATE_FACT','side':side,'field':field});continue
                facts[side][field]={'fact':fact,'source_id':reference['source_id'],'fact_id':reference['fact_id']}
    common=set.intersection(*(set(facts.get(side,{})) for side in ('left','right'))) if len(products)==2 else set()
    missing=[]
    for side in ('left','right'):
        for field in intent['required_facts']:
            if field not in facts.get(side,{}):missing.append({'side':side,'field':field,'code':'QUERY_FACT_MISSING'})
    identities_ok=len(products)==2 and len({s.get('id') for s in products})==2 and all(s.get('sku') and s.get('specification') and s.get('name') in intent['core_question'] for s in products)
    if not identities_ok:errors.append({'code':'PRODUCT_IDENTITY_UNRESOLVED'})
    asset_errors=validate_assets(packet) if len(products)==2 else [{'code':'ASSET_IDENTITY_MISSING'}]
    return {'facts':facts,'available_fields':sorted(common),'missing_query_facts':missing,'errors':errors,
            'assets_ready':not asset_errors,'asset_errors':asset_errors,'identity_ready':identities_ok,
            'source_mode':packet.get('mode'),'sources':packet.get('sources',{})}


def required_materials(intent):
    descriptions={
      'appearance':'被比较对象实物/液体外观记录及同条件照片；不可从罐体推断液体',
      'taste':'对应产品的口感实测记录或厂家描述，注明主观性和条件',
      'price':'价格、币种、实际容量/件数、渠道、采集日期、优惠条件和原始记录',
      'energy':'原标签能量、单位、基准、制备状态及对应来源',
      'carbohydrate':'原标签碳水、单位、基准及对应来源',
      'sugars':'糖值及定义、单位、原始基准和产品来源；未标示不是0',
      'vitamin_c':'维生素C值、单位、基准及产品来源；未标示不是0',
      'feature':'适用特色成分和配料/检测依据',
      'scene':'原问题场景的实际条件与适用依据，不自动填份量',
      'selection':'针对原问题的选择标准及支持记录，不附无关健康建议',
      'packaging':'两对象真实包装材质、规格及产品依据',
      'portability':'通勤携带所需实际重量、尺寸与携带条件记录',
      'sealing':'瓶盖/封口、能否重新封闭及对应说明或实际记录'}
    return {'identity':'原问题涉及的对象身份、真实规格与版本；食材可用可追溯身份，不编造SKU',
            'facts':[{'field':field,'needed_for':'direct_answer_or_explicit_useful_scope','material':descriptions.get(field,field+'的可核实资料')}
                     for field in intent['required_facts']],
            'assets':'只有生成图片时需要匹配授权素材，依用途选择实拍/步骤/产品图',
            'not_requested':intent['irrelevant_template_fields'],
            'template_confirmation':'无匹配模板时只申请对应方向的固定版式确认，不将其无关字段变成用户资料义务'}
