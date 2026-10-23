"""Produce content briefs; missing editable templates always block rendering."""
from math import ceil
from .config import categories, template
from .intent import analyze

def plan(query, category=None, template_id=None, items=None, objects=None, direction_hint=None):
    intent = analyze(query, category, direction_hint)
    key = intent['classification']['category']
    blockers = ['DIRECT_ANSWER_UNVERIFIED', 'FACTS_AND_RIGHTS_UNVERIFIED', 'EDITORIAL_REVIEW_REQUIRED']
    result = {'schema_version': 1, 'intent': intent, 'category': key, 'template_id': template_id,
              'status': 'blocked', 'render_ready': False, 'pages': [], 'blockers': blockers}
    if not key:
        blockers.append('CATEGORY_UNRESOLVED')
        return result
    rule = categories()[key]
    result['required_fields'] = rule['required_fields']
    selected = template(template_id) if template_id else None
    if selected:
        if key not in selected['categories']:
            raise ValueError('Template/category mismatch')
        if any(topic in query for topic in selected['excluded_topics']):
            raise ValueError('Template excluded for this topic')
        if not (selected['editable'] and selected['editable_source'] and selected['layout_spec'] and selected['approval_status'] == 'approved'):
            blockers.append('TEMPLATE_NOT_EDITABLE_OR_APPROVED')
    else:
        blockers.append('TEMPLATE_REQUIRED')
    if rule['rule_status'] == 'partial':
        blockers.append('CATEGORY_RULES_INCOMPLETE')
        return result
    roles = list(rule['default_roles'])
    groups = None
    if key in ('recommendation', 'inventory'):
        if not isinstance(items, list) or not items or any(not isinstance(x, str) or not x.strip() for x in items):
            raise ValueError('Ordered non-empty ingredient IDs required')
        clean = [x.strip().casefold() for x in items]
        if len(set(clean)) != len(clean):
            raise ValueError('Duplicate ingredient IDs')
        if not selected or not selected['detail_slots']:
            blockers.append('DETAIL_CAPACITY_UNKNOWN')
            return result
        if len(items) != selected['cover_slots']:
            blockers.append('FIXED_COVER_SLOT_COUNT_MISMATCH')
            return result
        n = selected['detail_slots']
        groups = [items[i:i+n] for i in range(0,len(items),n)]
        roles = ['cover'] + ['detail'] * max(2,ceil(len(items)/n))
    if key == 'comparison':
        if not isinstance(objects,list) or len(objects)!=2 or any(not isinstance(x,str) or not x.strip() for x in objects) or objects[0].strip().casefold()==objects[1].strip().casefold():
            raise ValueError('Exactly two distinct object IDs required')
        result['object_order'] = objects
        blockers.append('OBJECT_KIND_AND_MEASUREMENT_REVIEW_REQUIRED')
    for i, role in enumerate(roles):
        page = {'number': i+1, 'role': role, 'answer_ids': ['A1'] if i==0 else ['A2','A3'],
                'layout_id': None, 'layout_status': 'awaiting_approved_spec', 'content_status': 'brief_only'}
        if groups is not None:
            page['item_ids'] = items if i==0 else groups[i-1]
        if key=='comparison':
            page['object_ids'] = objects
            page['photo_policy'] = 'same_photo_and_left_right_identity_across_pages'
        if role=='recipe':
            page.update(recipe_id=None, recipe_title=None, steps=[], asset_kind='licensed_or_owned_real_step_photos', must_include_subject=True, query_match_required=True)
        result['pages'].append(page)
    return result
