import copy
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from rendering.engine import ROOT,sha
from customer_templates.prepare import configs,prepare,REGISTRY
from customer_templates.engine import validate,project,render


def manifest(category):return json.loads((ROOT/f'examples/customer_templates/{category}.json').read_text())


class CustomerTemplateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.components=prepare();cls.configurations=configs()

    def test_complete_fifteen_file_inventory(self):
        expected={'compare':3,'recommend':3,'list':4,'intro':5}
        self.assertEqual(len(self.configurations),15)
        for category,n in expected.items():
            paths=list((ROOT/'assets/customer_reference'/category).iterdir())
            self.assertEqual(len(paths),n)
            self.assertTrue(all(p.suffix=='.png' for p in paths))
            for config in [c for c in self.configurations if c['category']==category]:
                self.assertEqual(sha(ROOT/config['reference']),config['reference_sha256'])

    def test_catalog_mapping_and_no_false_approval(self):
        catalog=json.loads((ROOT/'template_catalog.yaml').read_text())
        sets=[t for t in catalog['templates'] if t['id'].startswith('customer-')]
        self.assertEqual(len(sets),4)
        self.assertEqual(sum(len(t['assets']) for t in sets),15)
        for t in sets:
            self.assertTrue(t['editable']);self.assertFalse(t['production_ready'])
            self.assertEqual(t['approval_status'],'not_verified')
            self.assertEqual(len(t['page_sequence']),len(t['assets']))

    def test_uniform_projection_and_immutable_component_hashes(self):
        for c in self.configurations:
            scale,dx,dy=project(c);w,h=c['source_size']
            self.assertLessEqual(w*scale,1242.001);self.assertLessEqual(h*scale,1656.001)
            self.assertAlmostEqual(dx*2+w*scale,1242);self.assertAlmostEqual(dy*2+h*scale,1656)
        for section in ['assets','backgrounds']:
            for a in self.components[section].values():self.assertEqual(sha(ROOT/a['path']),a['sha256'])

    def test_all_four_valid_content_contracts(self):
        for category in ['compare','recommend','list','intro']:
            self.assertEqual(len(validate(manifest(category),self.components)),{'compare':3,'recommend':3,'list':4,'intro':5}[category])

    def test_wrong_page_order_and_missing_content_blocked(self):
        for category in ['compare','recommend','list','intro']:
            data=manifest(category);data['pages'].reverse()
            with self.assertRaisesRegex(ValueError,'PAGE_ORDER'):validate(data,self.components)
            data=manifest(category);data['pages'][0]['values'].pop(next(iter(data['pages'][0]['values'])))
            with self.assertRaisesRegex(ValueError,'CONTENT_MISSING'):validate(data,self.components)

    def test_compare_identity_and_list_cross_page_order(self):
        data=manifest('compare');data['pages'][2]['values']['name_left']='另一个饮品'
        with self.assertRaisesRegex(ValueError,'CROSS_PAGE_LABEL'):validate(data,self.components)
        data=manifest('list');data['item_order'].reverse()
        with self.assertRaisesRegex(ValueError,'CROSS_PAGE_ORDER'):validate(data,self.components)
        data=manifest('recommend');data['item_order'][0]=data['item_order'][1]
        with self.assertRaisesRegex(ValueError,'CROSS_PAGE_ORDER'):validate(data,self.components)

        data=manifest('recommend');data['pages'][1]['values']['title']='不一致的标题'
        with self.assertRaisesRegex(ValueError,'CROSS_PAGE_LABEL'):validate(data,self.components)
        data=manifest('recommend');data['pages'][0]['values']['number_dragonfruit']='99'
        with self.assertRaisesRegex(ValueError,'VISIBLE_ORDER'):validate(data,self.components)

    def test_intro_feature_consistency_and_three_distinct_recipes(self):
        data=manifest('intro');data['pages'][1]['values']['benefit_2']='不同的亮点'
        with self.assertRaisesRegex(ValueError,'CROSS_PAGE_LABEL'):validate(data,self.components)
        data=manifest('intro');data['pages'][3]['values']['recipe_title']=data['pages'][2]['values']['recipe_title']
        with self.assertRaisesRegex(ValueError,'RECIPE_COMPLETENESS'):validate(data,self.components)

    def test_no_missing_or_swapped_images_or_asset_corruption(self):
        data=manifest('compare');data['pages'][0]['values']['left_photo']='right_photo'
        with self.assertRaisesRegex(ValueError,'ASSET_IDENTITY'):validate(data,self.components)
        components=copy.deepcopy(self.components);components['assets']['compare-left_photo']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'ASSET_CHANGED'):validate(manifest('compare'),components)

    def test_no_style_override_or_production_bypass(self):
        data=manifest('list');data['pages'][0]['css']='font-size:1px'
        with self.assertRaisesRegex(ValueError,'PAGE_ORDER'):validate(data,self.components)
        data=manifest('intro');data['mode']='production'
        with self.assertRaisesRegex(ValueError,'TEST_ONLY'):validate(data,self.components)

    def test_only_observed_recipe_overlays_registered(self):
        for c in self.configurations:
            if c['role']!='recipe':self.assertEqual(c['allowed_overlaps'],[])
            else:
                self.assertTrue(c['allowed_overlaps'])
                for a,b in c['allowed_overlaps']:
                    self.assertTrue('recipe_title' in (a,b) or any(x.startswith('step_caption_') for x in (a,b)))


class CustomerTemplateBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):prepare()

    def test_all_fifteen_pages_really_render_and_have_comparison_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            total=0
            for category in ['compare','recommend','list','intro']:
                out=Path(tmp)/category;result=render(manifest(category),out)
                self.assertEqual(result['status'],'PASS_RECONSTRUCTION_TEST_ONLY',result['errors'])
                self.assertFalse(result['customer_approved']);self.assertFalse(result['delivery_ready'])
                for n,entry in enumerate(result['pages'],1):
                    with Image.open(out/f'{n:02d}.png') as image:self.assertEqual(image.size,(1242,1656))
                    self.assertTrue(entry['elements']);self.assertEqual(entry['errors'],[])
                    self.assertTrue((out/f'{n:02d}-comparison.png').exists())
                    self.assertTrue((out/f'{n:02d}-difference.png').exists())
                    self.assertGreaterEqual(entry['pixel_diagnostics']['fixed_region_mean_absolute_rgb_error'],0)
                self.assertTrue((out/'preview.png').exists());total+=len(result['pages'])
                json.loads((out/'qc_report.json').read_text(),parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            self.assertEqual(total,15)

    def test_real_long_text_is_blocked_without_font_shrink(self):
        data=manifest('recommend');data['pages'][0]['values']['serving_dragonfruit']='过长文字溢出。'*80
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'long';report=render(data,out)
            self.assertEqual(report['status'],'FAIL')
            self.assertTrue(any(e['code']=='TEXT_OVERFLOW' and e['element']=='serving_dragonfruit' and e['page']==1 for e in report['errors']))
            self.assertFalse((out/'01.png').exists());self.assertFalse((out/'preview.png').exists())


if __name__=='__main__':unittest.main()
