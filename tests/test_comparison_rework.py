import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageChops
from workflow.core import ROOT, task_input
from workflow.copy import ReferenceVisualCopy
from workflow.pipeline import Batch, content_qc
from workflow.comparison_contract import business_qc, compile_copy, copy_qc, missing_comparison, PAGE_FIELDS
from workflow.comparison_runner import EvidenceComparisonProvider, validate_assets, resolved_layout, cross_task_qc, render_fixed
from workflow.comparison_fixtures import prepare
from customer_templates.compare_revision import prepare as prepare_visual
from customer_templates.prepare import configs


class ComparisonBusinessRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=prepare();cls.revision=prepare_visual()

    def data(self, index=0):
        raw=self.cases[index]
        return (task_input({k:v for k,v in raw.items() if k!='packet'}),json.loads((ROOT/raw['packet']).read_text()))

    def codes(self, packet, task):return {e['code'] for e in business_qc(packet,task)['errors']}

    def test_complete_typed_three_page_contract(self):
        for i in range(2):
            task,packet=self.data(i)
            self.assertEqual(business_qc(packet,task)['errors'],[])
            self.assertEqual(validate_assets(packet),[])
            for page in packet['pages']:
                for side in ('left','right'):self.assertEqual(set(page[side]),set(PAGE_FIELDS[page['number']]))
            result=compile_copy(packet,task)
            self.assertFalse(copy_qc(result,packet,task)['errors'])
            self.assertEqual(len(result['slot_bindings']),20)
            self.assertTrue(result['body'].startswith(result['direct_answer']))

    def test_legacy_visual_only_content_rejected(self):
        task=task_input({'task_id':'old','query':'柠檬水和可乐外观区别'})
        legacy=ReferenceVisualCopy().generate(task)
        qc=content_qc(legacy,{})
        self.assertIn('COMPARISON_BUSINESS_PACKET_REQUIRED',{e['code'] for e in qc['errors']})

    def test_no_reference_switch_bypass_or_renderer_call(self):
        for flag in (False,True):
            with tempfile.TemporaryDirectory() as directory, patch('customer_templates.engine.render') as renderer:
                result=Batch(directory,review_references=flag).run({'task_id':'original','query':'柠檬水和可乐哪个颜色更深'})
                self.assertEqual(result['status'],'REVIEW');self.assertFalse(result['generated'])
                self.assertEqual(result['template_decision'],'TEMPLATE_GAP_REVIEW_REQUIRED')
                renderer.assert_not_called()
                missing=json.loads((Path(directory)/result['artifact_directory']/'missing_materials.json').read_text())
                # Phase 5: appearance query needs appearance facts, not all 20 legacy template fields.
                self.assertEqual({e['field'] for e in missing['errors'] if 'field' in e},{'appearance'})
                self.assertNotIn('sugars',[f['field'] for f in missing['required_for_original_question']['facts']])

    def test_no_business_field_substitution_even_with_source(self):
        task,packet=self.data()
        packet['pages'][1]['left']['energy']=packet['pages'][0]['left']['appearance']
        self.assertIn('FACT_TYPE_OR_SUBJECT_MISMATCH',self.codes(packet,task))
        packet['pages'][2]['left'].pop('scene')
        self.assertIn('BUSINESS_FIELDS',self.codes(packet,task))

    def test_nutrients_require_exact_values_units_basis_and_kind(self):
        for key,value,code in [('value',999,'FACT_EVIDENCE_VALUE_MISMATCH'),('unit','mg','NUTRIENT_UNIT'),
                               ('basis',{'amount':1,'unit':'bottle'},'NUTRIENT_BASIS'),('value',float('nan'),'NUTRIENT_VALUE_INVALID')]:
            task,packet=self.data();packet['pages'][1]['left']['energy']['fact'][key]=value
            self.assertIn(code,self.codes(packet,task))
        task,packet=self.data();packet['sources']['fixture']['sha256']='0'*64
        self.assertIn('EVIDENCE_SOURCE_INVALID',self.codes(packet,task))

    def test_synthetic_source_and_illustrations_cannot_be_production(self):
        task,packet=self.data();packet['mode']='production'
        self.assertTrue(business_qc(packet,task,production=True)['errors'])
        self.assertTrue(validate_assets(packet))
        packet['sources']['fixture']['verified_for_production']=True
        self.assertIn('NON_PRODUCTION_EVIDENCE',{e['code'] for e in business_qc(packet,task,production=True)['errors']})

    def test_internal_notes_blocked_and_poster_body_cannot_diverge(self):
        task,packet=self.data();packet['pages'][0]['left']['appearance']['fact']['value']='依据：参考图'
        self.assertIn('INTERNAL_NOTE_IN_CONTENT',self.codes(packet,task))
        task,packet=self.data();compiled=compile_copy(packet,task)
        compiled['manifest']['pages'][1]['values']['nutrient_1_left']='依据：参考图'
        self.assertIn('INTERNAL_NOTE_IN_CONTENT',{e['code'] for e in copy_qc(compiled,packet,task)['errors']})
        task,packet=self.data();compiled=compile_copy(packet,task);compiled['body']='无糖，适合所有人'
        self.assertIn('COPY_FACT_OR_QUERY_MISMATCH',{e['code'] for e in copy_qc(compiled,packet,task)['errors']})

    def test_cross_page_identity_query_and_focus(self):
        task,packet=self.data();packet['pages'][2]['subject_order'].reverse()
        self.assertIn('CROSS_PAGE_IDENTITY',self.codes(packet,task))
        task,packet=self.data();packet['focus']='vitamin_c'
        self.assertIn('QUERY_FOCUS_MISMATCH',self.codes(packet,task))
        task,packet=self.data();task['direction']='改成孕期功效'
        self.assertIn('QUERY_BINDING_MISMATCH',self.codes(packet,task))
        task,packet=self.data();packet['subjects'][1]['name']='另一个产品'
        self.assertIn('QUERY_OBJECT_MISMATCH',self.codes(packet,task))

    def test_reversed_question_cannot_reuse_lower_sugar_answer(self):
        task,packet=self.data();task['search_query']=task['search_query'].replace('哪个更低','哪个更高')
        packet['query_binding']['query']=task['search_query']
        self.assertIn('QUERY_SEMANTICS_UNSUPPORTED',self.codes(packet,task))

    def test_missing_price_context_and_invalid_sugar(self):
        task,packet=self.data();packet['pages'][0]['left']['price']['fact'].pop('date')
        self.assertIn('PRICE_CONTEXT',self.codes(packet,task))
        task,packet=self.data();packet['pages'][1]['left']['sugars']['fact']['value']=100
        self.assertIn('SUGARS_EXCEED_CARBOHYDRATE',self.codes(packet,task))

    def test_two_queries_generate_distinct_answers_pages_and_keys(self):
        one,p1=self.data();two,p2=self.data(1)
        a=EvidenceComparisonProvider(p1);b=EvidenceComparisonProvider(p2)
        self.assertNotEqual(a.cache_key(one),b.cache_key(two))
        ca,cb=a.generate(one),b.generate(two)
        self.assertIn('测试配方A更低',ca['direct_answer'])
        self.assertIn('测试配方D更多',cb['direct_answer'])
        self.assertNotEqual(ca['body'],cb['body']);self.assertNotEqual(ca['manifest'],cb['manifest'])
        with self.assertRaisesRegex(ValueError,'BUSINESS_QC_FAILED'):a.generate(two)
        with tempfile.TemporaryDirectory() as directory:
            duplicate=cross_task_qc([{'rendered':True,'task_id':'a','query':'q1','poster_content_hash':'same','body_hash':'a'},
                                    {'rendered':True,'task_id':'b','query':'q2','poster_content_hash':'same','body_hash':'b'}],directory)
            self.assertEqual(duplicate['errors'][0]['code'],'CROSS_QUERY_DUPLICATE_CONTENT')

    def test_assets_identity_authorization_and_hash_checks(self):
        task,packet=self.data();packet['assets']['left']['subject_id']='another'
        self.assertTrue(validate_assets(packet))
        task,packet=self.data();packet['assets']['left']['license_sha256']='bad'
        self.assertTrue(validate_assets(packet))
        task,packet=self.data();packet['assets'].pop('right')
        self.assertTrue(validate_assets(packet))

    def test_original_coordinates_unchanged_and_borders_preserved(self):
        for original in [c for c in configs() if c['category']=='compare']:
            new=json.loads((ROOT/self.revision['templates'][original['id']]['path']).read_text())
            self.assertEqual([s['box'] for s in original['slots']],[s['box'] for s in new['slots']])
            for a,b in zip(original['slots'],new['slots']):
                if a['id'].startswith(('nutrient_','field_','use_','select_')):self.assertEqual(b['weight'],400);self.assertLess(b['font_size'],a['font_size'])
            if original['role']!='cover':
                with Image.open(ROOT/original['reference']) as reference, Image.open(ROOT/self.revision['backgrounds'][original['id']]['path']) as plate:
                    # v5 rectangles erased this vertical frame; new plate retains its exact pixels.
                    for box in [(342,180,355,480),(370,180,388,480)]:
                        self.assertIsNone(ImageChops.difference(reference.convert('RGB').crop(box),plate.convert('RGB').crop(box)).getbbox())


class ComparisonActualRenderingTests(unittest.TestCase):
    def test_render_and_real_overflow_with_fixed_font(self):
        cases=prepare();raw=cases[0];task=task_input({k:v for k,v in raw.items() if k!='packet'})
        packet=json.loads((ROOT/raw['packet']).read_text());compiled=compile_copy(packet,task);revision=prepare_visual()
        with tempfile.TemporaryDirectory() as directory:
            report=render_fixed(compiled,packet,revision,Path(directory)/'good')
            self.assertEqual(report['errors'],[])
            for n in range(1,4):
                with Image.open(Path(directory)/'good'/f'{n:02d}.png') as image:self.assertEqual(image.size,(1242,1656))
            compiled['manifest']['pages'][0]['values']['field_1_left']='真实溢出测试'*100
            report=render_fixed(compiled,packet,revision,Path(directory)/'bad')
            self.assertTrue(any(e['code']=='TEXT_OVERFLOW' and e['element']=='field_1_left' for e in report['errors']))
            self.assertFalse((Path(directory)/'bad/01.png').exists())
