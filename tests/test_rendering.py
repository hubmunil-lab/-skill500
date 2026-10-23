"""Real Chromium tests; no mocked browser geometry or screenshot success."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from playwright.sync_api import sync_playwright
from rendering.engine import (ROOT, CANVAS, DEFAULT_FONT, MEASURE_JS, build_html,
    font_data, inspect_geometry, load_template, prepare_asset, render, validate_values)
from rendering.fixtures import create_fixtures


def manifest():
    return json.loads((ROOT/'examples/rendering/intro4-test.json').read_text())


class AssetAndLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):create_fixtures()

    def test_subject_and_license_gate(self):
        data=manifest();asset=data['assets']['placeholder-1']
        with self.assertRaisesRegex(ValueError,'subject'): prepare_asset(asset,'青椒','test')
        asset=copy.deepcopy(asset);asset.update(kind='real_ingredient_photo',rights='unknown')
        with self.assertRaisesRegex(ValueError,'rights'):prepare_asset(asset,'黄豆','test')
        with self.assertRaisesRegex(ValueError,'placeholders'):prepare_asset(manifest()['assets']['placeholder-1'],'黄豆','production')

    def test_locked_file_tampering_rejected(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'tampered.json';file.write_text('{}')
            with patch('rendering.engine.repository_path',return_value=file):
                with self.assertRaisesRegex(ValueError,'hash mismatch'):
                    load_template('intro4-cover-prototype-v1')

    def test_recipe_finished_dish_not_accepted_as_steps(self):
        record=copy.deepcopy(manifest()['assets']['placeholder-1'])
        record.update(kind='finished_dish',rights='owned',reviewed=True,rights_evidence='synthetic test fixture, not actual permission')
        with self.assertRaisesRegex(ValueError,'finished dishes'):
            prepare_asset(record,'黄豆','test',expected_kind='real_step_photo')

    def test_transparent_channel_and_original_aspect_retained(self):
        import base64
        from io import BytesIO
        url,info=prepare_asset(manifest()['assets']['placeholder-1'],'黄豆','test')
        with Image.open(BytesIO(base64.b64decode(url.split(',')[1]))) as image:
            self.assertEqual(image.mode,'RGBA')
            self.assertEqual(image.size,(640,480))
            self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertTrue(info['has_transparency'])

    def test_override_and_table_shape_rejected(self):
        page=manifest()['pages'][0];layout=load_template(page['template_id'])
        page['style']={'font_size':8}
        self.assertIn('LOCKED_REGION',{e['code'] for e in validate_values(layout,page,1)})
        page.pop('style');page['values']['nutrition']=[['bad']]
        self.assertIn('SCHEMA',{e['code'] for e in validate_values(layout,page,1)})

    def test_all_registered_hashes_match(self):
        registry=json.loads((ROOT/'rendering/template_registry.json').read_text())
        for id,entry in registry['templates'].items():
            self.assertEqual(hashlib.sha256((ROOT/entry['path']).read_bytes()).hexdigest(),entry['sha256'])
            self.assertEqual(load_template(id)['width'],1242)
        with self.assertRaises(ValueError):load_template('not-approved')


class BrowserGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        create_fixtures()
        cls.data=manifest();cls.layout=load_template(cls.data['pages'][0]['template_id'])
        font,_=font_data(DEFAULT_FONT,''.join(str(v) for v in cls.data['pages'][0]['values'].values()))
        assets={k:prepare_asset(v,'黄豆','test') for k,v in cls.data['assets'].items()}
        cls.html=build_html(cls.layout,cls.data['pages'][0]['values'],assets,font)
        cls.playwright=sync_playwright().start()
        cls.browser=cls.playwright.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.playwright.stop()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':1242,'height':1656},device_scale_factor=1)
        self.page=self.context.new_page();self.page.set_content(self.html)
        self.page.evaluate('async()=>{await document.fonts.ready;await Promise.all([...document.images].map(i=>i.decode()))}')

    def tearDown(self):self.context.close()

    def codes(self):return {e['code'] for e in inspect_geometry(self.layout,self.page.evaluate(MEASURE_JS),1)}

    def test_clean_browser_layout(self):self.assertEqual(self.codes(),set())

    def test_actual_text_overflow(self):
        self.page.locator('#summary').evaluate("e=>e.textContent='长中文溢出测试'.repeat(200)")
        self.assertIn('TEXT_OVERFLOW',self.codes())
        self.assertEqual(self.page.locator('#summary').evaluate('e=>getComputedStyle(e).fontSize'),'27px')

    def test_table_cell_overflow(self):
        self.page.locator('.cell').first.evaluate("e=>e.textContent='长表格文字'.repeat(200)")
        self.assertIn('TEXT_OVERFLOW',self.codes())

    def test_actual_image_text_overlap(self):
        self.page.locator('#food').evaluate("e=>{e.style.left='64px';e.style.top='98px'}")
        codes=self.codes();self.assertIn('IMAGE_TEXT_OVERLAP',codes);self.assertIn('LOCKED_REGION',codes)

    def test_actual_image_bounds(self):
        self.page.locator('#food').evaluate("e=>e.style.left='1200px'")
        self.assertIn('IMAGE_OUT_OF_BOUNDS',self.codes())

    def test_locked_font_and_geometry(self):
        self.page.locator('#title').evaluate("e=>{e.style.fontSize='12px';e.style.width='1000px'}")
        self.assertIn('LOCKED_REGION',self.codes())

    def test_locked_color(self):
        self.page.locator('#title').evaluate("e=>e.style.color='red'")
        self.assertIn('LOCKED_REGION',self.codes())

    def test_actual_viewport_dimensions(self):
        self.page.set_viewport_size({'width':1000,'height':1656})
        self.assertIn('PAGE_SIZE',self.codes())


class RendererIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):create_fixtures()

    def test_three_real_pngs_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'run'
            report=render(manifest(),output)
            self.assertEqual(report['status'],'PASS_TEST_ONLY',report['errors'])
            self.assertFalse(report['customer_approved'])
            for n in range(1,4):
                with Image.open(output/f'{n:02d}.png') as im:
                    self.assertEqual(im.size,CANVAS)
                    self.assertGreater(len(im.getcolors(maxcolors=1000000)),100)
                self.assertTrue(report['pages'][n-1]['elements'])
                self.assertEqual(report['pages'][n-1]['errors'],[])
            self.assertTrue((output/'preview.png').exists())
            self.assertTrue((output/'reference-comparison.png').exists())
            self.assertEqual(json.loads((output/'qc_report.json').read_text())['errors'],[])
            with self.assertRaises(FileExistsError):render(manifest(),output)

    def test_font_file_and_missing_glyph_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=render(manifest(),Path(tmp)/'missing',font_path='/missing-font.ttf')
            self.assertEqual(report['status'],'FAIL')
            self.assertTrue(all(e['code']=='FONT_MISSING' for e in report['errors']))
            self.assertTrue(all(e['page'] and e['element'] for e in report['errors']))
            data=manifest();data['pages'][0]['values']['title']='字\U0010ffff'
            report=render(data,Path(tmp)/'glyph')
            self.assertEqual(report['status'],'FAIL')
            self.assertIn('U+10FFFF',report['errors'][0]['message'])

    def test_same_image_bytes_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=manifest();data['pages'][1]['values']['food']='placeholder-1'
            report=render(data,Path(tmp)/'repeat')
            self.assertIn('REPEATED_PHOTO',{e['code'] for e in report['errors']})

    def test_no_production_bypass_or_style_injection(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=manifest();data['mode']='production'
            self.assertEqual(render(data,Path(tmp)/'production')['status'],'FAIL')
            data=manifest();data['pages'][0]['css']='img {display:none}'
            report=render(data,Path(tmp)/'injection')
            self.assertIn('LOCKED_REGION',{e['code'] for e in report['errors']})
            self.assertTrue((Path(tmp)/'injection/qc_report.json').exists())

    def test_overflow_reports_page_and_element_without_silent_shrinking(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=manifest();data['pages'][1]['values']['description_1']='长中文'.join(['内容']*1000)
            out=Path(tmp)/'overflow';report=render(data,out)
            errors=[e for e in report['errors'] if e['code']=='TEXT_OVERFLOW']
            self.assertTrue(any(e['page']==2 and e['element']=='description_1' for e in errors),report)
            self.assertFalse((out/'02.png').exists())
            self.assertFalse((out/'preview.png').exists())


if __name__=='__main__':unittest.main()
