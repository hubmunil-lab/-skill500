"""Score only registered fixed templates; semantic mismatch is a hard veto."""
import json
from pathlib import Path
from workflow.core import ROOT

DIRECTORY=Path(__file__).parent


def match(intent, available_fields=(), assets_ready=False, object_count=None, item_count=None,
          content_fits=None, catalog=None, profiles=None, policy=None):
    catalog=catalog or json.loads((ROOT/'template_catalog.yaml').read_text())
    profiles=profiles or json.loads((DIRECTORY/'template_profiles.json').read_text())['profiles']
    policy=policy or json.loads((DIRECTORY/'policy.json').read_text())
    registered={t['id']:t for t in catalog['templates']};needs=set(intent['required_facts']);scores=[]
    for profile in profiles:
        entry=registered.get(profile['template_id'])
        if not entry or intent['category'] not in entry['categories'] or profile['category']!=intent['category']:continue
        required=set(profile['required_fields']);coverage=len(needs&required)/len(needs) if needs else 0
        relevant=len(needs&required)/len(required) if required else 0
        evidence=len(required&set(available_fields))/len(required) if required else 0
        reasons=[]
        if not entry.get('editable') or not entry.get('layout_spec'):reasons.append('TEMPLATE_NOT_EDITABLE')
        if entry.get('page_sequence') and len(entry['page_sequence'])!=profile['pages']:reasons.append('REGISTERED_PAGE_COUNT_MISMATCH')
        if not set(intent['themes'])&set(profile['themes']):reasons.append('THEME_MISMATCH')
        if coverage<policy['minimum_question_coverage']:reasons.append('QUESTION_NOT_COVERED')
        if required-needs or relevant<policy['minimum_field_relevance']:reasons.append('IRRELEVANT_TEMPLATE_FIELDS')
        counts_ok=True
        for key,actual in [('object_count',object_count),('item_count',item_count)]:
            if key in profile and actual!=profile[key]:counts_ok=False;reasons.append('CAPACITY_UNKNOWN' if actual is None else 'CAPACITY_MISMATCH')
        capacity=1 if counts_ok and content_fits is not False and profile['pages']>=policy['minimum_pages'] else 0
        if content_fits is False:reasons.append('TEXT_CAPACITY_EXCEEDED')
        # Unknown is recorded; a length estimate is not a real overflow check.
        approval=entry.get('approval_status')=='approved' and entry.get('production_ready') is True
        dimensions={'question_coverage':coverage,'field_relevance':relevant,'evidence':evidence,
                    'assets':float(assets_ready),'approval':float(approval),'capacity':capacity}
        score=round(sum(dimensions[k]*policy['weights'][k] for k in dimensions),4)
        scores.append({'template_id':entry['id'],'dimensions':dimensions,'score':score,
                       'semantic_rejection_reasons':reasons,'semantic_match':not reasons,
                       'unrelated_required_fields':sorted(required-needs),
                       'template_data_missing':sorted(required-set(available_fields)),
                       'customer_approved':approval,'page_capacity':profile['pages'],
                       'text_capacity_status':'not_measured' if content_fits is None else ('fits' if content_fits else 'overflow'),
                       'profile':profile,'warnings':profile.get('warnings',[])})
    scores.sort(key=lambda s:s['score'],reverse=True)
    candidates=[s for s in scores if s['semantic_match']]
    selected=candidates[0] if candidates else None
    capacity_only=any(set(s['semantic_rejection_reasons'])=={'CAPACITY_UNKNOWN'} for s in scores)
    return {'decision':'MATCH_REVIEW_REQUIRED' if selected else ('CAPACITY_REVIEW_REQUIRED' if capacity_only else 'TEMPLATE_GAP_REVIEW_REQUIRED'),
            'selected_template_id':selected['template_id'] if selected else None,'scores':scores,
            'requested_content_directions':intent['themes'],
            'unregistered_directions_are_not_templates':True,'customer_approved':False,
            'policy_status':policy['status'],
            'reason':'已登记模板业务语义适配，审批/事实/素材/真实容量仍独立检查' if selected else '没有匹配的已登记固定模板；不改字段、不凑页数、不自动登记变体'}
