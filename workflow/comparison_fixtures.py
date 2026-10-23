"""Reproducible synthetic fixtures, not nutrition facts about real products.

Original vector-like PNG artwork and authored data are dedicated under CC0-1.0.
No network image or customer beverage photo is used as a fixture asset.
"""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw
from .core import ROOT, save
from .comparison_contract import VERSION, PAGE_FIELDS, UNITS

DIRECTORY = ROOT/'examples/workflow/comparison_rework'
LICENSE = '''SPDX-License-Identifier: CC0-1.0
The original programmatic product illustrations and fictional test dataset in this
folder are dedicated to the public domain under CC0 1.0 Universal:
https://creativecommons.org/publicdomain/zero/1.0/
They were authored for software testing, not downloaded from the web.
All prices, nutrition, ingredients and sensory descriptions are SYNTHETIC TEST
DATA, not measurements or claims about actual foods or commercial products.
Customer template reference images, fonts and other repository assets are NOT
covered by this dedication. No customer approval is implied.
'''


def artwork(path, color, shape):
    im=Image.new('RGBA',(2400,2800),(0,0,0,0))
    base=ImageDraw.Draw(im)
    class ScaledDraw:
        def __getattr__(self, name):
            def draw(box, **kwargs):
                for key in ('radius','width'):
                    if key in kwargs:kwargs[key]*=2
                return getattr(base,name)(tuple(v*2 for v in box),**kwargs)
            return draw
    d=ScaledDraw()
    if shape=='bottle':
        d.rounded_rectangle((400,120,800,260),radius=30,fill='#d5d9d9',outline='#858585',width=8)
        d.rounded_rectangle((300,250,900,1260),radius=110,fill=color,outline='#777777',width=10)
        d.rounded_rectangle((340,570,860,920),radius=24,fill='#fff8e5',outline='#d8cbb4',width=5)
        d.ellipse((475,665,725,815),fill=color,outline='#777777',width=5)
        d.rectangle((355,330,385,520),fill='#ffffff99')
    else:
        d.rounded_rectangle((220,220,980,1280),radius=65,fill='#f0f6f8',outline='#777777',width=12)
        d.rounded_rectangle((245,520,955,1245),radius=45,fill=color)
        d.ellipse((220,185,980,330),fill='#e5f4f8',outline='#777777',width=10)
        d.ellipse((250,215,950,300),fill=color)
        d.rectangle((290,400,320,1130),fill='#ffffffbb')
        d.ellipse((405,680,785,1050),fill='#ffffff66',outline='#ffffff',width=12)
    bounds=im.getbbox();padding=30
    im=im.crop((max(0,bounds[0]-padding),max(0,bounds[1]-padding),min(im.width,bounds[2]+padding),min(im.height,bounds[3]+padding)))
    im.save(path)


def prepare():
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    (DIRECTORY/'LICENSE.txt').write_text(LICENSE,encoding='utf-8')
    datasets=[('sugar','sugars',[12,28],[3,7],[2,6],[8,6],['柠檬酸','苹果酸'],['#f7da5c','#df9654']),
              ('vitamin','vitamin_c',[20,24],[5,6],[4,5],[12,45],['抗坏血酸','柠檬酸'],['#eea36e','#a6c571'])]
    cases=[]
    for index,(case,focus,energy,carb,sugar,vitamin,features,colors) in enumerate(datasets):
        letters=('A','B') if index==0 else ('C','D')
        subjects=[{'id':'fixture_'+letter.lower(),'name':'测试配方'+letter,'sku':'SYNTHETIC-'+letter+'-500',
                   'specification':'500ml/瓶；虚构即饮配方'} for letter in letters]
        query=(subjects[0]['name']+'与'+subjects[1]['name']+'每100毫升'+('含糖量哪个更低' if focus=='sugars' else '维生素C哪个更多'))
        facts={};pages=[]
        for number,keys in PAGE_FIELDS.items():
            page={'number':number,'role':{1:'appearance_taste_price',2:'nutrition',3:'scene_selection'}[number],
                  'subject_order':[s['id'] for s in subjects]}
            for side,subject in zip(('left','right'),subjects):
                i=0 if side=='left' else 1
                page[side]={}
                for field in keys:
                    values={'appearance': ('浅黄透明液体\n杯中可见清澈光泽\n颜色均匀无沉淀' if i==0 else '琥珀色透明液体\n瓶身可见均匀色泽\n外观澄清无颗粒') if index==0 else ('浅橙色透明液体\n杯中呈均匀色泽\n外观清澈无颗粒' if i==0 else '浅绿色透明液体\n瓶中颜色均匀\n可见清澈光泽'),
                            'taste': ('酸味清晰入口轻甜\n柠檬香气较轻\n无气泡口感平顺\n回味偏清淡' if i==0 else '甜味较明显\n酸味柔和果香浓\n无气泡口感平顺\n回味偏浓郁') if index==0 else ('酸甜均衡果香轻\n无气泡入口平顺\n橙香回味较短\n口感偏清淡' if i==0 else '酸味较明显\n无气泡入口平顺\n苹果香气较清晰\n回味偏酸爽'),
                            'price': (4+i+index), 'energy':energy[i], 'carbohydrate':carb[i], 'sugars':sugar[i],
                            'vitamin_c':vitamin[i], 'feature':features[i],
                            'scene':('餐间搭配\n按250毫升分装' if i==0 else '外出随餐\n按200毫升分装'),
                            'selection': ('选购建议\n核对500毫升规格\n比价时换算同容量\n关注每100毫升含糖\n确认密封与保质期\n查看配料与过敏原\n按瓶身条件储存' if focus=='sugars' else
                                          '选购建议\n核对500毫升规格\n查看维生素C标示\n按100毫升统一比较\n确认密封与保质期\n查看配料与过敏原\n按瓶身条件储存')}
                    fact={'subject_id':subject['id'],'field':field,'value':values[field]}
                    if field in UNITS:fact.update(unit=UNITS[field],basis={'amount':100,'unit':'ml','state':'ready_to_drink'})
                    if field=='price':fact.update(unit='CNY',volume_ml=500,date='2026-10-23',channel='虚构测试渠道')
                    if field=='feature':fact['ingredient_basis']='虚构配料记录：水、'+features[i]
                    fact_id=subject['id']+'_'+field;facts[fact_id]=fact
                    page[side][field]={'source_id':'fixture','fact_id':fact_id,'fact':fact}
            pages.append(page)
        source_path=DIRECTORY/(case+'-source.json')
        save(source_path,{'synthetic':True,'license':'CC0-1.0','purpose':'synthetic_software_acceptance_only',
                          'not_real_food_evidence':True,'subjects':subjects,'facts':facts})
        packet={'schema_version':2,'contract':VERSION,'mode':'synthetic_test','focus':focus,
                'query_binding':{'query':query,'direction':'合成数据验收，不用于真实食品交付'},
                'subjects':subjects,'sources':{'fixture':{'path':str(source_path.relative_to(ROOT)),
                    'sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'verified_for_production':False}},
                'pages':pages,'assets':{}}
        for side,subject,color,shape in zip(('left','right'),subjects,colors,('cup','bottle')):
            path=DIRECTORY/(subject['id']+'.png');artwork(path,color,shape)
            packet['assets'][side]={'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'subject_id':subject['id'],'sku':subject['sku'],'license':'CC0-1.0','license_path':str((DIRECTORY/'LICENSE.txt').relative_to(ROOT)),
                'license_sha256':hashlib.sha256((DIRECTORY/'LICENSE.txt').read_bytes()).hexdigest(),
                'permitted_use':'synthetic_test','kind':'original_programmatic_illustration','size':list(Image.open(path).size)}
        packet_path=DIRECTORY/(case+'-packet.json');save(packet_path,packet)
        cases.append({'task_id':'fixture-'+case,'query':query,'direction':packet['query_binding']['direction'],
                      'packet':str(packet_path.relative_to(ROOT))})
    save(DIRECTORY/'cases.json',cases)
    return cases


if __name__=='__main__':prepare()
