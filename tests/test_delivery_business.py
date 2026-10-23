import copy
import json
from pathlib import Path
import tempfile
import unittest
from delivery.engine import Blocked, digest, validate, render_review, export_delivery
from rendering.engine import ROOT


def sample():return json.loads((ROOT/'examples/delivery/grapes-comparison.json').read_text())


class BusinessContractTests(unittest.TestCase):
    def test_real_content_and_blocking_obligations(self):
        registry,layouts,images,bindings,blockers=validate(sample())
        self.assertEqual(registry['family'],'business-01')
        self.assertEqual([x['role'] for x in layouts],['cover','nutrition','selection'])
        self.assertEqual(len(images),2)
        self.assertTrue({'SOURCE_RESOLUTION','IMAGE_RIGHTS_REQUIRED','TEMPLATE_APPROVAL_REQUIRED','FACT_EDITOR_REQUIRED'}<={b['code'] for b in blockers})
        self.assertEqual(len(bindings['assets']),2)

    def test_missing_photo_cannot_render(self):
        data=sample();data['assets'].pop('red')
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'blocked';report=render_review(data,folder)
            self.assertEqual(report['status'],'BLOCKED')
            self.assertEqual(report['errors'][0]['code'],'ASSET_MISSING')
            self.assertFalse(list(folder.glob('*.png')))
            self.assertTrue((folder/'qc_report.json').exists())

    def test_changed_nutrition_is_blocked(self):
        data=sample();data['pages'][1]['values']['table_left'][0][1]='5 kcal'
        with self.assertRaises(Blocked) as caught:validate(data)
        self.assertEqual(caught.exception.detail['code'],'NUTRITION_MISMATCH')

    def test_source_cannot_be_applied_to_another_food(self):
        data=sample();data['subject']='apple'
        with self.assertRaises(Blocked) as caught:validate(data)
        self.assertEqual(caught.exception.detail['code'],'FACT_SCOPE')

    def test_page_order_and_image_identity(self):
        for change,expected in [('order','PAGE_ORDER'),('image','OBJECT_ORDER')]:
            data=sample()
            if change=='order':data['pages'][0],data['pages'][1]=data['pages'][1],data['pages'][0]
            else:data['pages'][2]['values']['photo_left']='red'
            with self.assertRaises(Blocked) as caught:validate(data)
            self.assertEqual(caught.exception.detail['code'],expected)

    def test_style_override_cannot_be_passed_in_content(self):
        data=sample();data['pages'][0]['css']='font-size:8px'
        with self.assertRaises(Blocked) as caught:validate(data)
        self.assertEqual(caught.exception.detail['code'],'INPUT_SCHEMA')

    def test_placeholder_and_false_clinical_claim_blocked(self):
        for text,code in [('测试占位','PLACEHOLDER_FORBIDDEN'),('这种葡萄可以抗癌','HEALTH_CLAIM')]:
            data=sample();data['pages'][0]['values']['detail_1_left']=text
            with self.assertRaises(Blocked) as caught:validate(data)
            self.assertEqual(caught.exception.detail['code'],code)

    def test_title_limit_and_image_hash(self):
        data=sample();data['title']='字'*20
        with self.assertRaises(Blocked) as caught:validate(data)
        self.assertEqual(caught.exception.detail['code'],'TITLE_LENGTH')
        data=sample();data['assets']['red']['sha256']='0'*64
        with self.assertRaises(Blocked) as caught:validate(data)
        self.assertEqual(caught.exception.detail['code'],'ASSET_CHANGED')


class BusinessBrowserTests(unittest.TestCase):
    def test_repeated_terms_preserve_locked_geometry_and_fail_closed_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=render_review(sample(),Path(tmp)/'a')
            data=sample();data['title']='葡萄颜色能看出糖分吗';data['query']='葡萄颜色能判断含糖量吗？';data['pages'][0]['values']['title']=data['title']
            b=render_review(data,Path(tmp)/'b')
            self.assertEqual(a['status'],'REVIEW_NOT_DELIVERABLE',a['errors'])
            self.assertEqual(b['status'],'REVIEW_NOT_DELIVERABLE',b['errors'])
            fingerprint=lambda d:[[(e['id'],e['rect'],e['font_size'],e['line_height']) for e in p['elements']] for p in d['pages']]
            self.assertEqual(fingerprint(a),fingerprint(b))
            self.assertFalse(a['delivery_ready']);self.assertFalse(a['content_placeholders'])
            json.loads((Path(tmp)/'a/qc_report.json').read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            self.assertIn('| 营养字段 |',(Path(tmp)/'a/body.md').read_text())
            self.assertIn('body_sha256',a['bindings'])
            with self.assertRaises(Blocked) as caught:export_delivery(Path(tmp)/'a',Path(tmp)/'fake-approvals.json',Path(tmp)/'release')
            self.assertEqual(caught.exception.detail['code'],'DELIVERY_BLOCKED')
            self.assertFalse((Path(tmp)/'release').exists())
            changed=json.loads((Path(tmp)/'a/manifest.json').read_text());changed['query']='changed query'
            (Path(tmp)/'a/manifest.json').write_text(json.dumps(changed))
            with self.assertRaises(Blocked) as caught:export_delivery(Path(tmp)/'a',Path(tmp)/'none',Path(tmp)/'stale')
            self.assertEqual(caught.exception.detail['code'],'REVIEW_STALE')

    def test_long_text_does_not_shrink_or_export(self):
        data=sample();data['pages'][2]['values']['why_1_left']='这是故意过长的业务正文。'*100
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'overflow';report=render_review(data,folder)
            self.assertTrue(any(e['code']=='TEXT_OVERFLOW' and e['page']==3 and e['element']=='why_1_left' for e in report['errors']))
            self.assertFalse((folder/'03.png').exists())
            self.assertFalse((folder/'preview.png').exists())


if __name__=='__main__':unittest.main()
