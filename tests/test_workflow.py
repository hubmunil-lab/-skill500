import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from workflow.core import task_input, classifier, ModelClassifier, match_assets, verify_claims, safe_rework, ROOT
from workflow.copy import ReferenceVisualCopy
from workflow.pipeline import Batch, content_qc


class WorkflowTests(unittest.TestCase):
    def test_input_preserves_original_and_hint(self):
        value = task_input({'task_id':'a','query':'青椒怎么做（步骤）'})
        self.assertEqual(value['search_query'], '青椒怎么做')
        self.assertEqual(value['direction'], '步骤')
        self.assertEqual(value['original_query'], '青椒怎么做（步骤）')
        for bad in ['../x', '', '/tmp/a']:
            with self.assertRaises(ValueError): task_input({'task_id':bad,'query':'x'})
        with self.assertRaises(ValueError): task_input({'task_id':'a','query':'x','customer_approved':True})

    def test_six_categories(self):
        for query, expected in [('青椒营养介绍','intro'),('青椒怎么做','procedure'),
             ('有哪些水果推荐','recommendation'),('苹果品种有哪些','inventory'),
             ('柠檬水和可乐区别','comparison'),('三款饮料测评','review')]:
            result = classifier(query)
            self.assertEqual(result['category'], expected)
            self.assertTrue(result['review_required'])
            self.assertEqual(result['provider'], 'rules_fallback')

    def test_model_validation_and_disagreement(self):
        class Provider:
            def classify(self, query): return {'category':'intro','confidence':.99,'reason':'nutrition'}
        result = classifier('青椒营养介绍', Provider())
        self.assertFalse(result['review_required'])
        self.assertTrue(classifier('两款饮品区别', Provider())['review_required'])
        class Bad:
            def classify(self, query): return {'category':'intro','confidence':float('nan'),'reason':'bad'}
        self.assertEqual(classifier('青椒营养介绍', Bad())['provider'], 'rules_fallback')
        with self.assertRaises(ValueError): ModelClassifier('http://example.com','m','k')

    def test_source_kind_cannot_promote_visual_to_health(self):
        path = ROOT/'examples/customer_templates/compare.json'
        source = {'photo':{'kind':'visual','path':str(path.relative_to(ROOT)),
                    'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'locator':'cover'}}
        self.assertFalse(verify_claims([{'id':'v','kind':'visual','source_ids':['photo']}], source))
        self.assertTrue(verify_claims([{'id':'h','kind':'health','source_ids':['photo']}], source))
        source['photo']['sha256'] = 'wrong'
        self.assertTrue(verify_claims([{'id':'v','kind':'visual','source_ids':['photo']}], source))

    def test_license_identity_size_filter(self):
        data = json.loads((ROOT/'customer_templates/component_registry_v5.json').read_text())['assets']
        registry = {k:{**v,'purposes':['comparison'],'license_status':'unknown'} for k,v in data.items()}
        self.assertFalse(match_assets(registry,'cola','comparison'))
        self.assertTrue(match_assets(registry,'cola','comparison',authorized=False))
        self.assertFalse(match_assets(registry,'cola','recipe_step',authorized=False))
        self.assertFalse(match_assets(registry,'cola','comparison',(9000,9000),False))

    def test_copy_rejects_ungrounded_health_query(self):
        provider = ReferenceVisualCopy()
        self.assertFalse(provider.supports(task_input({'task_id':'x','query':'柠檬水和可乐外观哪个更健康'}),{'category':'comparison'}))
        self.assertFalse(provider.supports(task_input({'task_id':'x','query':'青椒功效'}),{'category':'intro'}))

    def test_direction_cannot_hide_health_request(self):
        task = task_input({'task_id':'x','query':'柠檬水和可乐外观区别（哪个更健康）'})
        self.assertFalse(ReferenceVisualCopy().supports(task, {'category':'comparison'}))

    def test_model_http_adapter_contract(self):
        from io import BytesIO
        payload = {'choices':[{'message':{'content':json.dumps({'category':'comparison','confidence':.9,'reason':'two objects'})}}]}
        with patch('workflow.core.urllib.request.urlopen', return_value=BytesIO(json.dumps(payload).encode())) as request:
            prediction = ModelClassifier('https://example.invalid/chat/completions','test-model','not-a-real-key').classify('两款对比')
        self.assertEqual(prediction['category'],'comparison')
        self.assertEqual(request.call_args.kwargs['timeout'],30)

    def test_current_visual_copy_does_not_infer_hidden_liquid(self):
        task = task_input({'task_id':'x','query':'柠檬水和可乐哪个颜色更深'})
        copy = ReferenceVisualCopy().generate(task)
        self.assertIn('不足以判断', copy['direct_answer'])
        self.assertIn('液体不可见', copy['manifest']['pages'][0]['values']['field_1_right'])
        self.assertFalse(copy['placeholders'])

    def test_safe_rework_never_shrinks_or_invents(self):
        document = {'pages':[{'values':{'text':'  每100克  \n  原文  '}}]}
        repaired = safe_rework(document, 0)
        self.assertEqual(repaired['pages'][0]['values']['text'], '每100克\n原文')
        self.assertIsNone(safe_rework(document, 3))
        self.assertIsNone(safe_rework(repaired, 1))

    def test_blocked_resume_retry_collision_and_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = Batch(directory)
            raw = {'task_id':'a','query':'青椒炒肉怎么做'}
            first = batch.run(raw)
            self.assertEqual(first['status'],'BLOCKED')
            self.assertFalse(first['generated'])
            self.assertTrue(batch.run(raw)['resumed'])
            self.assertEqual(batch.run(raw, retry=True)['attempt'],2)
            with self.assertRaises(ValueError): batch.run({'task_id':'a','query':'营养介绍'})
            second = batch.run({'task_id':'b','query':'小米营养介绍'})
            self.assertEqual(second['status'],'REVIEW')
            self.assertFalse(second['customer_approved'])
            self.assertFalse(list(Path(directory).rglob('*.png')))

    def test_default_never_uses_unlicensed_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Batch(directory).run({'task_id':'a','query':'柠檬水和可乐外观区别'})
            self.assertFalse(result['generated'])
            self.assertIn('AUTHORIZED_MATCHING_ASSETS_REQUIRED', [e['code'] for e in result['errors']])

    def test_actual_run_artifacts_if_present(self):
        path = ROOT/'artifacts/phase4-e2e/batch_report.json'
        if not path.exists(): self.skipTest('Run documented E2E command first')
        report = json.loads(path.read_text())
        self.assertEqual(len(report['tasks']),10)
        self.assertEqual(report['generated_groups'],2)
        from PIL import Image
        for result in report['tasks']:
            self.assertNotEqual(result['status'],'DELIVERED')
            self.assertFalse(result['customer_approved'])
            if result['generated']:
                folder = path.parent/result['artifact_directory']/result['render_directory']
                for i in range(1,4):
                    with Image.open(folder/f'{i:02d}.png') as image: self.assertEqual(image.size,(1242,1656))
                self.assertFalse(json.loads((folder/'qc_report.json').read_text())['errors'])
