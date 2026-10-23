"""Query-first grounded copy, before any template projection."""
import copy
import re
from .product_adapter import ProductAdapter, AdaptationError
from workflow.core import ROOT, digest
from workflow.comparison_contract import FORBIDDEN
import json

LABELS={'energy':'热量','carbohydrate':'碳水','sugars':'含糖量','vitamin_c':'维生素C','feature':'特色成分',
        'appearance':'外观','taste':'口感','price':'价格','scene':'食用场景','selection':'选购建议'}
NUMERIC={'energy','carbohydrate','sugars','vitamin_c'}


def basis_for(intent,packet,records):
    match=re.search(r'每\s*(\d+(?:\.\d+)?)\s*(毫升|ml|克|g|升|l)',intent['core_question'],re.I)
    configured=packet.get('normalization',{}).get('target_basis')
    states={r['fact'].get('basis',{}).get('state') for r in records}
    if len(states)!=1 or None in states:raise AdaptationError('STATE_OR_PREPARATION_MISMATCH')
    if match:
        unit={'毫升':'ml','克':'g','升':'l'}.get(match.group(2),match.group(2).lower())
        target={'amount':float(match.group(1)),'unit':unit,'state':next(iter(states))}
        if configured and target!=configured:raise AdaptationError('QUERY_BASIS_CONFIGURATION_CONFLICT')
        return target
    if configured:return copy.deepcopy(configured)
    bases=[r['fact'].get('basis') for r in records]
    if bases[0]!=bases[1]:raise AdaptationError('COMPARISON_BASIS_CONFIRMATION_REQUIRED')
    return copy.deepcopy(bases[0])


def generate(intent,packet,evidence,adapter=None):
    adapter=adapter or ProductAdapter();subjects=packet['subjects'];facts=evidence['facts'];normalized={side:{} for side in ('left','right')}
    if evidence['errors'] or evidence['missing_query_facts']:raise AdaptationError('QUERY_EVIDENCE_REQUIRED')
    if any(word in str(facts) for word in FORBIDDEN):raise AdaptationError('INTERNAL_QC_IN_BUSINESS_FIELDS')
    for field in intent['required_facts']:
        records=[facts[side][field] for side in ('left','right')]
        for side,record in zip(('left','right'),records):
            fact=record['fact'];value=fact['value']
            if field in NUMERIC:
                basis=basis_for(intent,packet,records)
                preferred=packet.get('normalization',{}).get('metric_units',{}).get(field)
                target_unit=preferred or records[0]['fact']['unit']
                adapted=adapter.nutrient(fact,basis,target_unit)
                text=f'{value:g}{fact["unit"]}' if isinstance(value,(int,float)) else str(value)
                display=f'{adapted["value"]:g}{target_unit}'
            elif field=='price':
                quantity=packet.get('normalization',{}).get('price_quantity')
                if re.search(r'划算|比价',intent['core_question']) and not quantity:raise AdaptationError('PRICE_COMPARISON_QUANTITY_REQUIRED')
                target_currency=packet.get('normalization',{}).get('currency') or records[0]['fact']['unit']
                adapted=adapter.price(fact,quantity,target_currency)
                pack=adapted['comparison_quantity'];amount=pack['amount'];unit=pack['unit']
                display=f'{adapted["currency"]} {adapted["value"]:g}/{amount:g}{unit}'
                text=display
            else:
                if not isinstance(value,str) or not value.strip():raise AdaptationError('BUSINESS_TEXT_MISSING')
                if field=='feature' and not fact.get('ingredient_basis'):raise AdaptationError('INGREDIENT_BASIS_REQUIRED')
                adapted={'raw_record':copy.deepcopy(fact),'value':value,'derivation':[]};display=value;text=value
            normalized[side][field]={'display':display,'adaptation':adapted,'binding':copy.deepcopy(record)}
    for side in ('left','right'):
        if {'sugars','carbohydrate'}<=set(normalized[side]):
            sugar=normalized[side]['sugars']['adaptation'];carb=normalized[side]['carbohydrate']['adaptation']
            amount,_=adapter.quantity(sugar['value'],sugar['unit'],carb['unit'])
            if sugar['basis']!=carb['basis'] or float(amount)>carb['value']+1e-9:raise AdaptationError('SUGARS_EXCEED_CARBOHYDRATE')
    focus=intent.get('focus');answer=None;winner=None
    if focus in NUMERIC or focus=='price':
        if focus not in normalized['left'] or focus not in normalized['right']:raise AdaptationError('FOCUS_FACT_MISSING')
        left,right=[normalized[side][focus]['adaptation'] for side in ('left','right')]
        if focus=='price':
            if left['currency']!=right['currency'] or left['comparison_quantity']!=right['comparison_quantity']:
                raise AdaptationError('PRICE_COMPARISON_BASIS_REQUIRED')
            prefix=f'按{left["comparison_quantity"]["amount"]:g}{left["comparison_quantity"]["unit"]}比较价格'
        else:
            if left['basis']!=right['basis'] or left['unit']!=right['unit']:raise AdaptationError('COMPARISON_BASIS_MISMATCH')
            prefix=f'每{left["basis"]["amount"]:g}{left["basis"]["unit"]}的{LABELS[focus]}'
        if intent['operation'] not in ('min','max'):raise AdaptationError('COMPARISON_OPERATOR_CONFIRMATION_REQUIRED')
        values=[left['value'],right['value']]
        if values[0]==values[1]:conclusion='两者相同'
        else:
            index=(values[1]<values[0]) if intent['operation']=='min' else (values[1]>values[0]);winner=subjects[index]['name']
            conclusion=winner+(('更便宜' if intent['operation']=='min' else '更贵') if focus=='price' else ('更低' if intent['operation']=='min' else '更多'))
        answer=f'{prefix}：{subjects[0]["name"]}为{normalized["left"][focus]["display"]}，{subjects[1]["name"]}为{normalized["right"][focus]["display"]}，{conclusion}。'
    elif focus=='appearance':
        answer='；'.join(subject['name']+'：'+normalized[side]['appearance']['display'].replace('\n','，') for side,subject in zip(('left','right'),subjects))+'。'
        # Describing two photos does not establish which is darker without a scoped observation.
        if intent['operation'] in ('min','max'):raise AdaptationError('COMPARATIVE_APPEARANCE_JUDGEMENT_REQUIRED')
    else:raise AdaptationError('CONTENT_PROVIDER_SCOPE_REVIEW_REQUIRED')
    if focus in NUMERIC and 'selection' in intent['required_facts']:
        for side,subject in zip(('left','right'),subjects):
            record=normalized[side]['selection'];choice='两者相同' if winner is None else ('本品更低' if intent['operation']=='min' else '本品更多') if winner==subject['name'] else ('另一款更低' if intent['operation']=='min' else '另一款更多')
            lines=[('糖值' if focus=='sugars' else LABELS[focus])+'优先：'+choice,
                   LABELS[focus]+'：'+normalized[side][focus]['display']]
            if 'price' in normalized[side]:lines.append(normalized[side]['price']['display'])
            lines+=['口感可结合上页记录','核对实际版本与标签']
            record['display']='\n'.join(lines)
            record['adaptation']['derivation']={'method':'query_metric_and_pack_context',
                'source_bindings':[normalized[s][focus]['binding'] for s in ('left','right')],
                'price_binding':normalized[side].get('price',{}).get('binding'),
                'note':'比较建议来自可追溯数值与规格，不是新的营养功效或人群建议'}
    paragraphs=[answer]
    if focus in NUMERIC:
        paragraphs.append('比较时先对齐计量基准，再看标签数值；整瓶含量和每单位含量不要混着比。')
    for fields in [('appearance','taste'),('price',),('energy','carbohydrate','sugars','vitamin_c','feature'),('scene','selection')]:
        lines=[]
        for side,subject in zip(('left','right'),subjects):
            parts=[]
            for field in fields:
                if field not in normalized[side]:continue
                text=normalized[side][field]['display'].replace('\n','，')
                if field=='price':
                    raw_price=normalized[side][field]['adaptation']['raw_record']
                    text+='（'+raw_price['date']+'，'+raw_price['channel']+'）'
                # Prefix once; source text may already begin with a label.
                text=re.sub(r'^'+re.escape(LABELS[field])+r'[：:，,\s]*','',text)
                parts.append(LABELS[field]+'：'+text)
            if parts:lines.append(subject['name']+'，'+'；'.join(parts)+'。')
        if lines:paragraphs.append('\n'.join(lines))
    if focus in NUMERIC:
        title=f'{subjects[0]["name"]}和{subjects[1]["name"]}怎么选？先看'+('糖' if focus=='sugars' else LABELS[focus])
    else:title=f'{subjects[0]["name"]}和{subjects[1]["name"]}，外观差在哪？'
    return {'original_query':intent['original_query'],'intent':copy.deepcopy(intent),'direct_answer':answer,'title':title,
            'body':'\n\n'.join(paragraphs),'normalized_fields':normalized,'winner':winner,
            'data_kind':packet['mode'],'customer_approved':False,'delivery_ready':False,
            'publisher_review_required':True,'provider':'IntentGroundedCopyV1'}


def project_existing_template(content,packet,template_id):
    if template_id!='customer-compare-v1':raise ValueError('RENDER_ADAPTER_UNAVAILABLE')
    manifest=json.loads((ROOT/'examples/customer_templates/compare.json').read_text())
    subjects=packet['subjects'];manifest['item_order']=[s['id'] for s in subjects];bindings={}
    field_to_slot={'appearance':'field_1','taste':'field_2','price':'field_3',
                   'energy':'nutrient_1','carbohydrate':'nutrient_2','sugars':'nutrient_3','vitamin_c':'nutrient_4','feature':'nutrient_5',
                   'scene':'use','selection':'select'}
    for n,page in enumerate(manifest['pages'],1):
        page['item_ids']=manifest['item_order'][:]
        keys={1:('appearance','taste','price'),2:('energy','carbohydrate','sugars','vitamin_c','feature'),3:('scene','selection')}[n]
        for side,subject in zip(('left','right'),subjects):
            page['values']['name_'+side]=subject['name']
            for field in keys:
                if field not in content['intent']['required_facts']:raise ValueError('IRRELEVANT_TEMPLATE_FIELD_VETO: '+field)
                record=content['normalized_fields'][side][field];text=record['display']
                if field in NUMERIC or field=='feature':text=LABELS[field]+'：'+text
                if field=='price':text+='\n'+record['adaptation']['raw_record']['date']
                slot=field_to_slot[field]+'_'+side;page['values'][slot]=text
                bindings[f'{n}.{slot}']={'field':field,'subject_id':subject['id'],**record}
    focus=content['intent']['focus'];metric=LABELS.get(focus,'差异')
    cover=content['winner']+metric+('更低' if content['intent']['operation']=='min' else '更多') if content['winner'] else '同口径比较，结果相同'
    numeric=content['normalized_fields']['left'][focus]['adaptation'];basis=numeric.get('basis')
    if not basis:raise ValueError('COMPREHENSIVE_RENDER_METRIC_REQUIRED')
    scope=f'每{basis["amount"]:g}{basis["unit"]}'
    manifest['pages'][0]['values'].update(title=cover,subtitle=('虚构配方｜' if packet['mode']=='synthetic_test' else '')+scope,
                                          tag_1='外观特点',tag_2='口感区别',tag_3='价格差异')
    manifest['pages'][1]['values']['title']=scope+'营养对比'
    manifest['pages'][2]['values']['title']='食用场景与选购'
    result=copy.deepcopy(content);result.update(manifest=manifest,slot_bindings=bindings)
    result['content_hash']=digest({'query':content['intent']['core_question'],'pages':manifest['pages'],'body':content['body']})
    return result
