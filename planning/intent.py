"""Explainable, replaceable query parser; no template fields are consulted."""
import re
from typing import Protocol
from workflow.core import classifier

NUTRIENTS=('energy','carbohydrate','sugars','vitamin_c','feature')
ALL_COMPARISON=('appearance','taste','price',*NUTRIENTS,'scene','selection')

class IntentParser(Protocol):
    def parse(self, task: dict) -> dict: ...


class RuleIntentParser:
    """Bounded rules: uncertainty stays explicit, no inferred biography."""
    def __init__(self, classifier_provider=None):
        self.classifier_provider=classifier_provider

    def parse(self, task):
        query=task['search_query'];direction=task['direction'];text=query+'；'+direction
        # Negative scope must not be treated as a positive request.
        exclusions=[]
        patterns={'nutrition':r'(?:不要|不看|不比较|无需|不涉及)(?:任何)?(?:营养|热量|营养数据)',
                  'price':r'(?:不要|不看|不比较|无需|不涉及)价格'}
        active=text
        for key,pattern in patterns.items():
            if re.search(pattern,text):exclusions.append(key);active=re.sub(pattern,'',active)
        classification=classifier(query,self.classifier_provider)
        if re.search(r'测评|实测|试喝|评测',query):category='review'
        elif re.search(r'对比|相比|区别|哪个|哪种|比.{0,8}(?:高|低|便宜|贵)|vs',query,re.I) or (re.search(r'和|与',query) and re.search(r'怎么选|如何选|选购|谁|比一比',query)):category='comparison'
        else:category=classification['category']
        if category!=classification['category']:
            classification={**classification,'baseline_category':classification['category'],'category':category,
                            'intent_override_reason':'原问题的实测或明确两对象选择语义，保留人工复核','review_required':True}
        themes=[];required=[];supporting=[];focus=None;conflicts=[]
        if 'nutrition' in exclusions and re.search(r'含糖|糖分|维生素|热量|碳水',query):conflicts.append('核心营养问题与排除营养的方向冲突')
        def add(theme,*fields):
            if theme not in themes:themes.append(theme)
            for field in fields:
                if field not in required:required.append(field)
        if category=='comparison':
            if re.search(r'外观|颜色|色泽|透明',active):add('appearance','appearance')
            if re.search(r'口感|味道|酸甜',active):add('taste','taste')
            if 'price' not in exclusions and re.search(r'价格|便宜|划算|贵|比价',active):add('price','price')
            metric_patterns=[('sugars',r'含糖|糖含量|糖分|总糖'),('vitamin_c',r'维生素\s*C|维C'),('energy',r'热量|能量'),('carbohydrate',r'碳水')]
            if 'nutrition' not in exclusions or conflicts:
                for metric,pattern in metric_patterns:
                    if re.search(pattern,active,re.I):add('nutrition',metric);focus=focus or metric
                if re.search(r'营养',active):add('nutrition',*NUTRIENTS)
            if re.search(r'食用场景|饮用场景|使用场景',active):add('scene','scene')
            if re.search(r'选购|怎么选|如何选|通勤',active):add('selection','selection');supporting.append('具体使用条件与限制')
            if not required:themes=['unresolved'];supporting.append('确认比较对象和比较维度')
            if 'appearance' in required:supporting+=['同光照与容器条件','照片中是否真正可见被比较液体']
            if 'price' in required:supporting+=['容量与件数','渠道、日期与优惠条件','是否需要统一币种和容量']
            if any(k in required for k in NUTRIENTS):supporting+=['原始标签与计量基准','产品状态及换算依据']
            if 'selection' in required:
                supporting+=['目标场景的选择标准及依据']
                if '通勤' in active:
                    for field in ('packaging','portability','sealing'):
                        if field not in required:required.append(field)
        else:
            mapping={'intro':('ingredient_introduction',['identity','nutrition_summary']),
                     'procedure':('cooking_steps',['ingredients','steps','heat_control']),
                     'recommendation':('scenario_recommendation',['candidate_items','selection_reasons','constraints']),
                     'inventory':('item_inventory',['item_list','distinguishing_features','usage']),
                     'review':('hands_on_review',['product_identities','test_protocol','observations','limitations'])}
            theme,fields=mapping.get(category,('unresolved',[]));themes=[theme];required=fields
            if category=='inventory' and re.search(r'孕|禁忌',text):themes=['pregnancy_inventory'];required+=['population_evidence']
            if category=='intro' and re.search(r'做法|食谱',active):required+=['recipes','real_step_photos']
            if re.search(r'孕期|孕妇|过敏|糖尿病',query):required+=['population_evidence']
        contexts=list(dict.fromkeys(re.findall(r'通勤|早餐|孕期|孕妇|儿童|减肥期间|方便携带|每\s*\d+(?:\.\d+)?\s*(?:毫升|ml|克|g)|每瓶|每份',text,re.I)))
        operation='min' if re.search(r'更低|更少|低一点|含糖低|便宜|划算',query) else ('max' if re.search(r'更多|更高|更深|更贵|高一点',query) else 'describe')
        if category=='comparison' and focus is None:
            focus='price' if 'price' in required else ('appearance' if 'appearance' in required else ('selection' if 'selection' in required else None))
        unrelated=[field for field in ALL_COMPARISON if field not in required] if category=='comparison' else []
        return {'schema_version':1,'original_query':task['original_query'],'core_question':query,
                'direction':direction,'direction_is_evidence':False,'category':category,
                'classification':classification,'themes':themes,'focus':focus,'operation':operation,
                'search_context':contexts,'required_facts':required,'useful_supplement':list(dict.fromkeys(supporting)),
                'irrelevant_template_fields':unrelated,'explicit_exclusions':exclusions,'scope_conflicts':conflicts,
                'parser':'RuleIntentParser','confidence':.8 if required else .2,'human_review_required':True,
                'unknowns':['未提供的产品版本、受众健康条件、真实体验不得推断']}


def analyze(task, parser=None):
    result=(parser or RuleIntentParser()).parse(task)
    if result.get('original_query')!=task['original_query'] or not isinstance(result.get('required_facts'),list):
        raise ValueError('INTENT_PROVIDER_SCHEMA')
    return result
