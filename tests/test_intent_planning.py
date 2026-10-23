import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from workflow.core import ROOT, task_input
from workflow.pipeline import Batch
from planning.intent import analyze
from planning.pipeline import plan_task, run_task
from planning.template_fit import match
from planning.product_adapter import ProductAdapter, AdaptationError
from planning.publish_copy import generate, project_existing_template
from planning.evidence import inspect_packet
from planning.fixtures import prepare


def task(query, direction=''):
    return task_input({'task_id':'query-test','query':query,'direction':direction})


class IntentPlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=prepare()

    def data(self,index=3):
        raw=self.cases[index];t=task_input({key:raw[key] for key in ('task_id','query','direction') if key in raw})
        return t,json.loads((ROOT/raw['packet']).read_text())

    def test_appearance_never_requires_nutrition_price_or_new_template(self):
        plan=plan_task(task('柠檬水和可乐哪个颜色更深（不要营养）'))
        self.assertEqual(plan['intent']['required_facts'],['appearance'])
        self.assertEqual(plan['template_match']['decision'],'TEMPLATE_GAP_REVIEW_REQUIRED')
        candidate=plan['template_match']['scores'][0]
        self.assertIn('IRRELEVANT_TEMPLATE_FIELDS',candidate['semantic_rejection_reasons'])
        self.assertIn('sugars',candidate['unrelated_required_fields'])
        self.assertEqual([f['field'] for f in plan['required_materials']['facts']],['appearance'])
        self.assertEqual(plan['intent']['original_query'],'柠檬水和可乐哪个颜色更深（不要营养）')

    def test_price_selection_and_nutrition_scopes(self):
        for query,expected in [('250ml饮料和330ml饮料哪个更划算',['price']),
                               ('A和B通勤怎么选（不看营养）',['selection','packaging','portability','sealing']),
                               ('A和B糖分谁更少',['sugars'])]:
            result=analyze(task(query));self.assertEqual(result['category'],'comparison');self.assertEqual(result['required_facts'],expected)

    def test_ten_cases_classify_without_template_forcing(self):
        for raw in self.cases:
            t=task_input({k:raw[k] for k in ('task_id','query','direction') if k in raw})
            packet=json.loads((ROOT/raw['packet']).read_text()) if raw.get('packet') else None
            plan=plan_task(t,packet)
            self.assertEqual(plan['intent']['category'],raw['expected_category'])
            self.assertEqual(plan['template_match']['selected_template_id'],raw['expected_template'])
        intro=plan_task(task('青椒有什么营养特点'))
        self.assertNotIn('recipes',intro['intent']['required_facts'])
        self.assertIn('recipes',intro['template_match']['scores'][0]['unrelated_required_fields'])

    def test_all_six_fit_scores_and_approval_are_separate(self):
        t,packet=self.data();plan=plan_task(t,packet);selected=plan['template_match']['scores'][0]
        self.assertEqual(set(selected['dimensions']),{'question_coverage','field_relevance','evidence','assets','approval','capacity'})
        self.assertTrue(selected['semantic_match']);self.assertEqual(selected['dimensions']['approval'],0)
        self.assertFalse(selected['customer_approved'])
        self.assertEqual(selected['text_capacity_status'],'not_measured')
        no_capacity=match(plan['intent'],object_count=3)
        self.assertIsNone(no_capacity['selected_template_id'])
        overflow=match(plan['intent'],object_count=2,content_fits=False)
        self.assertIn('TEXT_CAPACITY_EXCEEDED',overflow['scores'][0]['semantic_rejection_reasons'])
        with self.assertRaises(ValueError):analyze(task('A'),parser=type('Bad',(),{'parse':lambda self,t:{'original_query':'changed','required_facts':[]}})())

    def test_unregistered_profile_cannot_be_selected(self):
        intent=analyze(task('A和B外观有什么区别'))
        profile={'template_id':'invented-appearance','category':'comparison','required_fields':['appearance'],'themes':['appearance'],'pages':3}
        result=match(intent,profiles=[profile],object_count=2)
        self.assertEqual(result['scores'],[]);self.assertIsNone(result['selected_template_id'])

    def test_grounded_copy_uses_source_once_and_specific_selection(self):
        t,packet=self.data();plan=plan_task(t,packet);content=generate(plan['intent'],packet,plan['evidence'])
        self.assertTrue(content['body'].startswith(content['direct_answer']))
        self.assertNotIn('热量：热量：',content['body']);self.assertNotIn('特色成分：特色成分：',content['body'])
        self.assertIn('330ml',content['body']);self.assertIn('250ml',content['body']);self.assertIn('USD',content['body'])
        self.assertIn('本品更低',content['normalized_fields']['left']['selection']['display'])
        self.assertIn('另一款更低',content['normalized_fields']['right']['selection']['display'])
        projected=project_existing_template(content,packet,'customer-compare-v1')
        self.assertEqual(len(projected['slot_bindings']),20)
        self.assertNotEqual(projected['manifest']['pages'][2]['values']['select_left'],projected['manifest']['pages'][2]['values']['select_right'])

    def test_evidence_corruption_and_synthetic_promotion_blocked(self):
        t,packet=self.data();packet['pages'][1]['left']['sugars']['fact']['value']=999
        plan=plan_task(t,packet)
        self.assertTrue(plan['evidence']['errors'])
        with self.assertRaises(AdaptationError):generate(plan['intent'],packet,plan['evidence'])
        t,packet=self.data();packet['mode']='production'
        self.assertTrue(plan_task(t,packet)['evidence']['errors'])
        self.assertFalse(plan_task(t,packet)['evidence']['assets_ready'])

    def test_partial_evidence_answers_only_question_and_preserves_template_gap(self):
        t,packet=self.data();t=task('示例甲和示例乙糖分谁更少（每100ml）')
        plan=plan_task(t,packet)
        self.assertIsNone(plan['template_match']['selected_template_id'])
        self.assertEqual(plan['intent']['required_facts'],['sugars'])
        content=generate(plan['intent'],packet,plan['evidence'])
        self.assertIn('示例甲更低',content['direct_answer'])
        self.assertNotIn('热量',content['body']);self.assertNotIn('价格',content['body'])
        with self.assertRaisesRegex(ValueError,'IRRELEVANT_TEMPLATE_FIELD_VETO'):project_existing_template(content,packet,'customer-compare-v1')

    def test_missing_facts_and_no_approval_do_not_allow_png(self):
        with tempfile.TemporaryDirectory() as directory,patch('workflow.comparison_runner.render_fixed') as renderer:
            result=run_task(task('A和B外观有什么区别'),directory,render_review=True)
            self.assertFalse(result['generated']);self.assertFalse(result['customer_approved']);renderer.assert_not_called()

    def test_batch_resume_invalidates_when_actual_source_changes(self):
        t,packet=self.data()
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as directory:
            folder=Path(directory);source=folder/'source.json';source.write_bytes((ROOT/packet['sources']['fixture']['path']).read_bytes())
            packet['sources']['fixture']['path']=str(source.relative_to(ROOT))
            raw={k:t[k] for k in ('task_id','query','direction')}
            batch=Batch(folder/'batch',data_packets={t['task_id']:packet})
            first=batch.run(raw);self.assertTrue(first['content_generated'])
            self.assertTrue(batch.run(raw)['resumed'])
            source.write_text(source.read_text()+'\n')
            second=batch.run(raw);self.assertEqual(second['attempt'],2)
            self.assertFalse(second['content_generated']);self.assertFalse(second['generated'])
            self.assertIn('SOURCE_INVALID',{e['code'] for e in second['errors']})


class ProductAdaptationTests(unittest.TestCase):
    def test_non_500ml_non_cny_original_records_unchanged(self):
        adapter=ProductAdapter();fact={'value':2,'unit':'USD','quantity':{'amount':.33,'unit':'l','count':1},'date':'2026-10-23','channel':'synthetic test'}
        original=copy.deepcopy(fact);normalized=adapter.price(fact,{'amount':100,'unit':'ml'})
        self.assertAlmostEqual(normalized['value'],2/3.3);self.assertEqual(normalized['currency'],'USD')
        self.assertEqual(normalized['raw_record'],original);self.assertEqual(fact,original)
        jpy={**fact,'unit':'JPY'};self.assertEqual(adapter.price(jpy)['currency'],'JPY')

    def test_basis_units_and_raw_kj_preserved(self):
        adapter=ProductAdapter();fact={'value':418.4,'unit':'kJ','basis':{'amount':250,'unit':'mL','state':'ready_to_drink'}}
        out=adapter.nutrient(fact,{'amount':100,'unit':'ml','state':'ready_to_drink'},'kcal')
        self.assertAlmostEqual(out['value'],40);self.assertEqual(out['raw_record'],fact)
        self.assertTrue(out['derivation']['formula'])
        mass={'value':5,'unit':'g','basis':{'amount':.1,'unit':'kg','state':'raw'}}
        self.assertAlmostEqual(adapter.nutrient(mass,{'amount':100,'unit':'g','state':'raw'},'mg')['value'],5000)

    def test_density_and_fx_need_resolved_source_not_just_true_flag(self):
        fact={'value':10,'unit':'g','basis':{'amount':100,'unit':'g','state':'raw'}}
        target={'amount':100,'unit':'ml','state':'raw'};density={'source_id':'lab','g_per_ml':2,'evidence_verified':True}
        with self.assertRaisesRegex(AdaptationError,'DENSITY_EVIDENCE_REQUIRED'):ProductAdapter().nutrient(fact,target,'g',density)
        adapter=ProductAdapter(evidence_resolver=lambda key:{'g_per_ml':2} if key=='lab' else None)
        self.assertEqual(adapter.nutrient(fact,target,'g',density)['value'],20)
        price={'value':2,'unit':'USD','quantity':{'amount':330,'unit':'ml'},'date':'2026-10-23','channel':'synthetic'}
        fx={'source_id':'fx','date':'2026-10-23','from':'USD','to':'CNY','rate':7,'evidence_verified':True}
        with self.assertRaisesRegex(AdaptationError,'FX_EVIDENCE_REQUIRED'):ProductAdapter().price(price,target_currency='CNY',fx=fx)
        evidence={k:v for k,v in fx.items() if k not in ('source_id','evidence_verified')}
        self.assertEqual(ProductAdapter(evidence_resolver=lambda key:evidence).price(price,target_currency='CNY',fx=fx)['value'],14)

    def test_state_and_unsupported_units_block(self):
        adapter=ProductAdapter();fact={'value':2,'unit':'g','basis':{'amount':100,'unit':'ml','state':'concentrate'}}
        with self.assertRaisesRegex(AdaptationError,'STATE_OR_PREPARATION_MISMATCH'):adapter.nutrient(fact,{'amount':100,'unit':'ml','state':'ready_to_drink'},'g')
        with self.assertRaises(AdaptationError):adapter.quantity(1,'unknown','ml')
        with self.assertRaises(AdaptationError):adapter.quantity(float('nan'),'ml','l')
