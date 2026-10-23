import json
import subprocess
import sys
import unittest
from production.classifier import classify
from production.config import ROOT, categories, load, normalize_category
from production.intent import analyze
from production.planner import plan
from production.qc import check


class ConfigurationTests(unittest.TestCase):
    def test_six_categories_and_aliases(self):
        self.assertEqual(len(categories()),6)
        self.assertEqual(normalize_category('介绍'),'intro')
        self.assertEqual(normalize_category('固定搭配'),'procedure')
        with self.assertRaises(ValueError): normalize_category('七类')

    def test_catalog_preserves_all_assets_and_roles(self):
        catalog=load('template_catalog.yaml')
        library=load('references/library.json')
        listed=[a for t in catalog['templates'] for a in t['assets']]+catalog['unassigned_assets']
        self.assertEqual(len(catalog['templates']),17)
        self.assertEqual(len(listed),71)
        self.assertEqual({a['path']:a['sha256'] for a in listed},{a['path']:a['sha256'] for a in library['assets']})
        for t in catalog['templates']:
            self.assertEqual(t['editable'], t['id'].startswith('customer-'))
            self.assertFalse(t['production_ready'])
            for a in t['assets']: self.assertTrue((ROOT/a['path']).is_file())
        self.assertEqual({a['role'] for a in catalog['unassigned_assets']},{'rules','procedure','negative-example','positive-example'})

    def test_sources_exist(self):
        for name in ['production_rules.yaml','qc_rules.yaml']:
            for source in load(name)['sources']: self.assertTrue((ROOT/source).is_file())


class ClassificationTests(unittest.TestCase):
    def test_six_types(self):
        cases={'青椒营养价值':'intro','青椒炒蛋怎么做':'procedure','减肥期间食材推荐':'recommendation','苹果品种图鉴':'inventory','火龙果和葡萄哪个含糖低':'comparison','三款饮品实测':'review'}
        for query,key in cases.items():
            with self.subTest(query=query): self.assertEqual(classify(query)['category'],key)

    def test_ambiguous_and_unknown(self):
        for query in ['苹果','适合孕期的食物有哪些','三款饮品对比测评']:
            self.assertIsNone(classify(query)['category'])
        self.assertEqual(classify('苹果','单一介绍')['status'],'explicit')
        for query in ['',None,'  ']:
            with self.assertRaises(ValueError): classify(query)


class IntentTests(unittest.TestCase):
    def test_constraints_and_no_invented_answer(self):
        result=analyze('怀孕14周能吃花甲吗','介绍',direction_hint='水果大全')
        self.assertEqual(result['explicit_constraints'],['怀孕14周'])
        self.assertIn('花甲',result['query'])
        self.assertIsNone(result['direct_answer'])
        self.assertFalse(result['direction_hint_is_evidence'])
        self.assertEqual(len(result['required_answers']),3)
        self.assertTrue(all(a['query']==result['query'] for a in result['required_answers']))


class PlanningTests(unittest.TestCase):
    def test_intro_five_pages(self):
        result=plan('青椒营养价值',template_id='intro-1')
        self.assertEqual([p['role'] for p in result['pages']],['cover','detail','recipe','recipe','recipe'])
        self.assertFalse(result['render_ready'])
        self.assertIn('TEMPLATE_NOT_EDITABLE_OR_APPROVED',result['blockers'])
        self.assertEqual(set(x for p in result['pages'] for x in p['answer_ids']),{'A1','A2','A3'})

    def test_order_and_fixed_capacity(self):
        ids=list('abcdef')
        result=plan('苹果品种图鉴',template_id='list-1',items=ids)
        self.assertEqual([p['item_ids'] for p in result['pages']],[ids,['a','b'],['c','d'],['e','f']])
        self.assertIn('FIXED_COVER_SLOT_COUNT_MISMATCH',plan('苹果品种图鉴',template_id='list-1',items=list('abcde'))['blockers'])
        with self.assertRaises(ValueError): plan('苹果品种图鉴',template_id='list-1',items=['a',' A '])
        with self.assertRaises(ValueError): plan('苹果品种图鉴',template_id='list-1')

    def test_comparison(self):
        result=plan('红石榴和白石榴对比',template_id='compare-1',objects=['red','white'])
        self.assertEqual(len(result['pages']),3)
        self.assertTrue(all(p['object_ids']==['red','white'] for p in result['pages']))
        for objects in [None,['a'],['a','b','c'],['a','A']]:
            with self.assertRaises(ValueError): plan('石榴对比',objects=objects)

    def test_template_exclusion_and_mismatch(self):
        with self.assertRaises(ValueError): plan('青椒营养价值',template_id='intro-2')
        with self.assertRaises(ValueError): plan('青椒营养价值',template_id='compare-1')
        with self.assertRaises(ValueError): plan('青椒营养价值',template_id='unknown')

    def test_incomplete_categories_and_ambiguity(self):
        for query,template in [('青椒怎么做','recipe-1'),('三款饮品测评','review-1')]:
            result=plan(query,template_id=template)
            self.assertEqual(result['pages'],[])
            self.assertIn('CATEGORY_RULES_INCOMPLETE',result['blockers'])
        self.assertIn('CATEGORY_UNRESOLVED',plan('苹果')['blockers'])


class QualityTests(unittest.TestCase):
    def manifest(self):
        p=plan('苹果品种图鉴',template_id='list-1',items=list('abcdef'))
        return {'category':'inventory','query':'苹果品种图鉴','direct_answer':'区分这些品种的特点后再按用途选择。',
                'title':'苹果品种与用途','body':'待审稿正文','template_id':'list-1',
                'required_answers':p['intent']['required_answers'],'body_answer_ids':['A1','A2','A3'],
                'ingredient_order':list('abcdef'),'body_item_ids':list('abcdef'),
                'claims':[], 'pages':[dict(page,size=[1242,1656],item_kind='ingredient') for page in p['pages']]}

    def codes(self,data): return {i['code'] for i in check(data)['issues']}

    def test_cannot_self_approve_bitmap(self):
        data=self.manifest()
        data['template_approved']=True
        self.assertIn('TEMPLATE',self.codes(data))
        self.assertEqual(check(data)['status'],'FAIL')

    def test_order_duplicate_and_completeness(self):
        data=self.manifest()
        self.assertNotIn('ORDER',self.codes(data))
        self.assertNotIn('DUPLICATE',self.codes(data))
        data['pages'][-1]['item_ids']=['a','f']
        self.assertTrue({'ORDER','DUPLICATE'}<=self.codes(data))
        data['pages'][0]['answer_ids']=['unknown']
        self.assertIn('COMPLETENESS',self.codes(data))

    def test_health_and_nutrition(self):
        data=self.manifest()
        data['direct_answer']='这些食材可以抗癌'
        self.assertIn('HEALTH',self.codes(data))
        data=self.manifest()
        data['claims']=[{'text':'每100克1克蛋白质','kind':'nutrition','verified':True,'source':'数据库记录'}]
        self.assertTrue(any(i['code']=='HEALTH' and i['severity']=='blocking' for i in check(data)['issues']))
        data['claims'][0].update(basis='每100克',food_state='生鲜',edible_portion_or_product_spec='可食部')
        self.assertFalse(any(i['code']=='HEALTH' and i['severity']=='blocking' for i in check(data)['issues']))

    def test_title_layout_pages_and_review(self):
        data=self.manifest()
        data['title']='字'*20
        data['pages'][0]['layout_overrides']={'font_size':12}
        data['pages'][0]['size']=[1,1]
        data['pages']=data['pages'][:2]
        self.assertTrue({'TEXT','LAYOUT','PAGE_COUNT'}<=self.codes(data))
        self.assertTrue(any(i['severity']=='review' for i in check(data)['issues']))

    def test_intro_and_comparison_gates(self):
        data=self.manifest()
        data['category']='intro'
        self.assertIn('RECIPE',self.codes(data))
        data['category']='comparison'
        data['object_order']=['a','b']
        data['object_kinds']=['homemade','commercial']
        self.assertIn('COMPARISON',self.codes(data))

    def test_bad_manifest_is_not_pass(self):
        for data in [[],{}, {'pages':[1]}, {'category':'推荐','pages':[{'item_ids':None}]}]:
            with self.subTest(data=data): self.assertEqual(check(data)['status'],'FAIL')


class CliTests(unittest.TestCase):
    def test_plan_cli(self):
        result=subprocess.run([sys.executable,'-B','-m','production','plan','青椒营养价值','--template','intro-1'],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(json.loads(result.stdout)['pages']),5)

    def test_invalid_input_cli(self):
        result=subprocess.run([sys.executable,'-B','-m','production','plan','苹果','--category','错误'],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,2)


class AdditionalQualityTests(unittest.TestCase):
    def test_intro_recipe_validation(self):
        data={'category':'intro','query':'青椒营养价值','subject_ingredient_id':'pepper',
              'pages':[{'role':'cover','photo_id':'a'},{'role':'detail','photo_id':'b'}]+[
                  {'role':'recipe','recipe_id':str(i),'recipe_title':'青椒食谱'+str(i),
                   'steps':['清洗食材','烹调至熟'],'asset_kind':'owned_real_step_photos',
                   'subject_ingredient_id':'pepper','query_match_reviewed':True} for i in range(3)]}
        self.assertFalse(any(i['code']=='RECIPE' for i in check(data)['issues']))
        data['pages'][-1]['recipe_id']='0'
        self.assertTrue(any(i['code']=='RECIPE' for i in check(data)['issues']))
        data['pages'][-1]['asset_kind']='generated_finished_dish'
        self.assertTrue(any(i['code']=='RIGHTS' and i['severity']=='blocking' for i in check(data)['issues']))

    def test_comparison_identity_and_photo_reuse(self):
        data={'category':'comparison','object_order':['a','b'],'object_kinds':['commercial','commercial'],
              'pages':[{'object_ids':['a','b'],'object_photo_ids':['photo-a','photo-b']} for _ in range(3)]}
        self.assertFalse(any(i['code']=='COMPARISON' for i in check(data)['issues']))
        data['pages'][2]['object_photo_ids']=['photo-b','photo-a']
        self.assertTrue(any(i['code']=='COMPARISON' for i in check(data)['issues']))

    def test_structurally_complete_fixture_passes_only_preflight(self):
        from unittest.mock import patch
        data=QualityTests().manifest()
        data['content']={'items':list('abcdef'),'distinguishing_features':'待审品种特点','usage':'待审用途'}
        for p in data['pages']: p['layout_id']='fixture-layout'
        for field in ['fact_review','rights_review','visual_review','semantic_review']:
            data[field]={'approved':True,'reviewer':'test fixture reviewer','evidence':'fixture record'}
        approved={'categories':['inventory'],'excluded_topics':[], 'editable':True,
                  'editable_source':'fixture-only','layout_spec':{'id':'fixture-layout'},
                  'approval_status':'approved','cover_slots':6,'detail_slots':2}
        with patch('production.qc.template', return_value=approved):
            result=check(data)
        self.assertEqual(result['status'],'PASS',result)
        self.assertIn('preflight_only',result['scope'])

    def test_qc_cli_rejects_unfinished_brief(self):
        result=subprocess.run([sys.executable,'-B','-m','production','qc','examples/production-brief.example.json'],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'FAIL')

if __name__=='__main__': unittest.main()
