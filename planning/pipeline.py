"""Shared runtime entry for old Batch and the phase-five case runner."""
import json
from pathlib import Path
from workflow.core import ROOT, save, digest
from .intent import analyze
from .evidence import inspect_packet, required_materials
from .template_fit import match
from .publish_copy import generate, project_existing_template
from .product_adapter import AdaptationError


def plan_task(task, packet=None, parser=None):
    intent=analyze(task,parser)
    evidence=inspect_packet(packet,intent) if packet else {'available_fields':[],'facts':{},'missing_query_facts':[{'field':k,'code':'QUERY_FACT_MISSING'} for k in intent['required_facts']],
                                                        'errors':[],'assets_ready':False,'asset_errors':[{'code':'AUTHORIZED_MATCHING_ASSETS_REQUIRED'}],'identity_ready':False}
    count=len(packet.get('subjects',[])) if packet else (2 if intent['category']=='comparison' and any(x in intent['core_question'] for x in ('和','与','对比')) else (1 if intent['category']=='intro' else None))
    fit=match(intent,evidence['available_fields'],evidence['assets_ready'],object_count=count,
              item_count=len(packet.get('items',[])) if packet and 'items' in packet else None)
    return {'schema_version':1,'intent':intent,'evidence':evidence,'template_match':fit,
            'required_materials':required_materials(intent),'data_kind':packet.get('mode') if packet else 'real_query_no_product_data',
            'customer_approved':False,'delivery_ready':False}


def run_task(task, output, packet=None, render_review=False, parser=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);plan=plan_task(task,packet,parser)
    intent,evidence,fit=plan['intent'],plan['evidence'],plan['template_match'];errors=[]
    result={'task_id':task['task_id'],'original_query':task['original_query'],'status':'REVIEW','generated':False,
            'content_generated':False,'category':intent['category'],'template_id':fit['selected_template_id'],
            'template_decision':fit['decision'],'data_kind':plan['data_kind'],'customer_approved':False,'delivery_ready':False,
            'errors':errors,'reworks':0,'cache_key':digest({'query':task['original_query'],'direction':task['direction'],'packet':packet,'planning_version':'intent-first-1'})}
    save(output/'input.json',task);save(output/'intent.json',intent);save(output/'classification.json',intent['classification'])
    save(output/'planning_brief.json',plan);save(output/'template_match.json',fit);save(output/'required_materials.json',plan['required_materials'])
    save(output/'missing_materials.json',{'status':fit['decision'],'query':task['original_query'],
          'errors':evidence['missing_query_facts']+evidence['errors']+evidence['asset_errors'],
          'required_for_original_question':plan['required_materials'],'not_a_demand_for_all_template_fields':True})
    if fit['selected_template_id'] is None:errors.append({'code':fit['decision'],'detail':fit['reason']})
    if evidence['missing_query_facts']:errors.append({'code':'QUERY_EVIDENCE_REQUIRED','fields':[m['field'] for m in evidence['missing_query_facts']]})
    errors.extend(evidence['errors']);errors.extend(evidence['asset_errors'])
    copy=None
    if intent.get('scope_conflicts'):errors.append({'code':'QUERY_SCOPE_CONFIRMATION_REQUIRED','details':intent['scope_conflicts']})
    if packet and intent['category']=='comparison' and not evidence['errors'] and not evidence['missing_query_facts'] and not intent.get('scope_conflicts'):
        try:
            copy=generate(intent,packet,evidence);result['content_generated']=True
            save(output/'copy.json',copy);(output/'post.md').write_text('# '+copy['title']+'\n\n'+copy['body']+'\n')
        except (AdaptationError,KeyError,ValueError) as error:errors.append({'code':'CONTENT_ADAPTATION_REVIEW_REQUIRED','detail':str(error)})
    if fit['selected_template_id'] and copy and evidence['assets_ready']:
        selected=next(s for s in fit['scores'] if s['template_id']==fit['selected_template_id'])
        if render_review and selected['profile'].get('renderer')=='compare_revision':
            try:
                from customer_templates.compare_revision import prepare
                from workflow.comparison_runner import render_fixed
                projected=project_existing_template(copy,packet,fit['selected_template_id'])
                # Regenerate from the verified facts to prevent edited poster/body divergence.
                expected=project_existing_template(generate(intent,packet,evidence),packet,fit['selected_template_id'])
                if projected!=expected:raise ValueError('CONTENT_BINDING_MISMATCH')
                save(output/'copy.json',projected);save(output/'source_packet.json',packet)
                save(output/'content_qc.json',{'status':'PASS_BINDINGS_NOT_CUSTOMER_APPROVAL','errors':[],
                     'checks':['exact_source_facts','preserved_raw_values','query_before_template','derived_answer','body_poster_binding'],
                     'semantic_review_required':True,'data_kind':packet['mode']})
                report=render_fixed(projected,packet,prepare(),output/'render')
                if report['errors']:
                    result['status']='BLOCKED';errors.append({'code':'LAYOUT_QC_FAILED','details':report['errors']})
                else:
                    result.update(generated=True,page_count=3,render_directory='render')
                    result['poster_content_hash']=digest(projected['manifest']['pages']);result['body_hash']=digest(projected['body'])
            except (ValueError,KeyError,OSError) as error:
                result['status']='BLOCKED';errors.append({'code':'TEMPLATE_ADAPTER_REVIEW_REQUIRED','detail':str(error)})
        else:errors.append({'code':'RENDER_REVIEW_NOT_REQUESTED_OR_ADAPTER_UNAVAILABLE'})
        errors.append({'code':'CUSTOMER_APPROVAL_REQUIRED'})
    if not copy and fit['selected_template_id']:result['status']='BLOCKED'
    if not fit['scores'] and intent['category'] in ('procedure','review'):result['status']='BLOCKED'
    if packet and packet.get('mode')=='synthetic_test':errors.append({'code':'SYNTHETIC_SOFTWARE_TEST_ONLY'})
    save(output/'qc_report.json',{'status':result['status'],'generated':result['generated'],
         'customer_approved':False,'delivery_ready':False,'errors':errors,'intent_required_facts':intent['required_facts'],
         'layout_report':'render/qc_report.json' if result['generated'] else None})
    return result
