"""Separate synthetic fixtures for product-unit adaptation; no real product data."""
import copy
import hashlib
import json
from pathlib import Path
from workflow.core import ROOT, save

DIRECTORY=ROOT/'examples/planning'


def prepare():
    DIRECTORY.mkdir(parents=True,exist_ok=True);synthetic=[]
    definitions=[('sugar',['示例甲','示例乙'],[330,250],'USD',[6.6,12.5],[26.4,15],[100,125],'sugars'),
                 ('vitamin',['示例丙','示例丁'],[200,1000],'JPY',[8,50],[24,450],[200,1000],'vitamin_c')]
    for key,names,specs,currency,sugars,vitamins,bases,focus in definitions:
        original=ROOT/'artifacts/phase4-rework/run-004'/('fixture-sugar' if key=='sugar' else 'fixture-vitamin')
        packet=json.loads((original/'business_packet.json').read_text());packet['schema_version']=3;packet['contract']='intent-first-evidence-1'
        query=f'{names[0]}和{names[1]}对比外观、口感、价格、营养、食用场景和选购，重点看每100毫升'+('含糖量哪个更低' if focus=='sugars' else '维生素C哪个更多')
        packet['query_binding']={'query':query,'direction':'合成软件测试，不是真实产品'};packet['focus']=focus
        packet['normalization']={'target_basis':{'amount':100.0,'unit':'ml','state':'ready_to_drink'},
                                 'metric_units':{'energy':'kcal','carbohydrate':'g','sugars':'g','vitamin_c':'mg'}}
        subjects=packet['subjects']
        facts={}
        for i,subject in enumerate(subjects):
            subject.update(id='p5_'+key+'_'+str(i),name=names[i],sku='SYNTHETIC-P5-'+key+'-'+str(i),
                           specification=f'{specs[i]}ml/瓶；合成即饮配方')
        for page in packet['pages']:
            page['subject_order']=[s['id'] for s in subjects]
            for side,i in [('left',0),('right',1)]:
                for field,reference in page[side].items():
                    fact=reference['fact'];fact['subject_id']=subjects[i]['id']
                    if field in ('energy','carbohydrate','sugars','vitamin_c'):
                        fact['basis']['amount']=bases[i]
                        if field=='sugars':fact['value']=sugars[i]
                        elif field=='vitamin_c':fact['value']=vitamins[i]
                        elif field=='carbohydrate':fact['value']=sugars[i]+2
                        else:
                            fact['value']=(sugars[i]+2)*4*4.184;fact['unit']='kJ'
                    if field=='price':
                        fact.pop('volume_ml',None);fact.update(value=(1.2+i*.3) if key=='sugar' else (120+i*280),unit=currency,
                                                             quantity={'amount':specs[i],'unit':'ml','count':1},
                                                             date='2026-10-23',channel='合成测试渠道')
                    if field=='scene':fact['value']='随餐搭配\n先看实际包装容量' if i==0 else '外出携带\n留意瓶盖密封状态'
                    if field=='selection':
                        fact['value']=f'核对{specs[i]}ml实际规格\n保留标签原始口径\n对齐每100ml再比较\n'+('重点看糖值与定义' if focus=='sugars' else '重点看维C数值单位')+'\n查看配料和储存条件'
                    fact_id=subjects[i]['id']+'_'+field;reference.update(source_id='fixture',fact_id=fact_id);facts[fact_id]=copy.deepcopy(fact)
        source=DIRECTORY/(key+'-source.json')
        save(source,{'synthetic':True,'license':'CC0-1.0','not_real_product_information':True,
                     'purpose':'unit_currency_and_query_software_testing','subjects':subjects,'facts':facts})
        packet['sources']={'fixture':{'path':str(source.relative_to(ROOT)),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'verified_for_production':False}}
        for side,i in [('left',0),('right',1)]:
            image=original/'inputs'/(side+'-asset.png');license_path=original/'inputs'/(side+'-LICENSE.txt')
            packet['assets'][side].update(path=str(image.relative_to(ROOT)),sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                                         license_path=str(license_path.relative_to(ROOT)),license_sha256=hashlib.sha256(license_path.read_bytes()).hexdigest(),
                                         subject_id=subjects[i]['id'],sku=subjects[i]['sku'])
        path=DIRECTORY/(key+'-packet.json');save(path,packet)
        synthetic.append({'task_id':'p5-'+key,'query':query,'direction':packet['query_binding']['direction'],'packet':str(path.relative_to(ROOT)),
                          'expected_category':'comparison','expected_template':'customer-compare-v1','data_kind':'synthetic_test','expect_render':True})
    cases=[
      {'task_id':'p5-appearance','query':'柠檬水和可乐哪个颜色更深（只看液体外观，不要营养）','expected_category':'comparison','expected_template':None,'data_kind':'real_query_no_product_data','expect_render':False},
      {'task_id':'p5-price','query':'250ml果汁和330ml果汁哪个更划算（统一容量比价）','expected_category':'comparison','expected_template':None,'data_kind':'real_query_no_product_data','expect_render':False},
      {'task_id':'p5-selection','query':'玻璃瓶和塑料瓶饮料通勤怎么选（选购对比，不看营养）','expected_category':'comparison','expected_template':None,'data_kind':'real_query_no_product_data','expect_render':False},
      *synthetic,
      {'task_id':'p5-intro','query':'青椒有什么营养特点','expected_category':'intro','expected_template':None,'data_kind':'real_query_no_product_data','expect_render':False},
      {'task_id':'p5-procedure','query':'青椒炒肉怎么做，火候和步骤是什么','expected_category':'procedure','expected_template':None,'data_kind':'real_query_no_product_data','expect_render':False},
      {'task_id':'p5-recommend','query':'早餐水果推荐（方便携带）','expected_category':'recommendation','expected_template':None,'data_kind':'real_query_no_product_data','expect_render':False},
      {'task_id':'p5-inventory','query':'常见苹果品种盘点（口感和用途）','expected_category':'inventory','expected_template':None,'data_kind':'real_query_no_product_data','expect_render':False},
      {'task_id':'p5-review','query':'三款无糖饮料实测体验（口感和价格）','expected_category':'review','expected_template':None,'data_kind':'real_query_no_product_data','expect_render':False}]
    required=[['appearance'],['price'],['selection','packaging','portability','sealing'],
              ['appearance','taste','price','sugars','energy','carbohydrate','vitamin_c','feature','scene','selection'],
              ['appearance','taste','price','vitamin_c','energy','carbohydrate','sugars','feature','scene','selection'],
              ['identity','nutrition_summary'],['ingredients','steps','heat_control'],
              ['candidate_items','selection_reasons','constraints'],['item_list','distinguishing_features','usage'],
              ['product_identities','test_protocol','observations','limitations']]
    for case,fields in zip(cases,required):case['expected_required_facts']=fields
    save(DIRECTORY/'ten_queries.json',cases)
    return cases


if __name__=='__main__':prepare()
