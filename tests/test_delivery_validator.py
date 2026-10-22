import sys, tempfile, json, unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from validate_delivery import run
class ValidatorTests(unittest.TestCase):
    def test_valid_simple_three_page(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            for i in range(1,4):Image.new('RGB',(1242,1656)).save(base/f'{i:02}.png')
            payload={'query':'测试','type':'推荐','title':'适合的食物','direct_answer':'回答','body':'图文正文', 'template_id':'approved-1','template_approved':True,'sources_verified':True,'asset_rights_verified':True,'ingredient_order':['a','b'], 'pages':[{'file':'01.png','role':'cover','layout_reviewed':True,'content_reviewed':True},{'file':'02.png','role':'detail','new_ingredient_ids':['a'],'layout_reviewed':True,'content_reviewed':True},{'file':'03.png','role':'detail','new_ingredient_ids':['b'],'layout_reviewed':True,'content_reviewed':True}]}
            p=base/'manifest.json';p.write_text(json.dumps(payload,ensure_ascii=False));self.assertEqual(run(p),[])
            payload['pages'][2]['new_ingredient_ids']=['a'];p.write_text(json.dumps(payload,ensure_ascii=False));self.assertIn('REPEATED_INGREDIENT',[x['code'] for x in run(p)])
    def test_intro_recipe_gate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'manifest.json';p.write_text(json.dumps({'query':'青椒怎么吃','type':'介绍','title':'青椒吃法','direct_answer':'适量','body':'内容','pages':[]},ensure_ascii=False));self.assertIn('RECIPE_PAGE_COUNT',[x['code'] for x in run(p)])
if __name__=='__main__':unittest.main()
