"""Extract query constraints without inventing health answers or user biography."""
import re
from .classifier import classify

QUESTIONS = {
    'intro': ['该食材对原问题的直接答案是什么？', '有哪些可核实的营养或作用及其边界？', '怎样食用及哪些情况不适合？'],
    'procedure': ['需要哪些材料和准备？', '实际操作步骤是什么？', '有哪些与原问题相关的注意事项？'],
    'recommendation': ['在原场景下有哪些可选食材？', '选择理由及限制是什么？', '如何食用或搭配？'],
    'inventory': ['原问题范围内有哪些品种或食材？', '各项有什么区别？', '各项如何使用或选择？'],
    'comparison': ['原问题涉及的两对象核心差异是什么？', '同一计量基准下证据是什么？', '在原场景下如何选择？'],
    'review': ['测评对象和维度是什么？', '真实记录支持哪些结论？', '适用场景及测评限制是什么？'],
}

def analyze(query, category=None, direction_hint=None):
    result = classify(query, category)
    key = result['category']
    constraints = [m.group() for m in re.finditer(r'怀孕\d*周?|孕期|减肥期间|增重|增肥|肠胃|脾胃虚弱|低脂|低糖|高蛋白|易消化|儿童|老人|过敏', query)]
    return {'query': query, 'classification': result,
            'search_motivation': '希望获得针对「' + query + '」的可用答案；此为词面分析，需编辑复核',
            'explicit_constraints': list(dict.fromkeys(constraints)),
            'unknowns': ['未提供的病史、个体耐受、对象规格和实际体验不得推断'],
            'direction_hint': direction_hint, 'direction_hint_is_evidence': False,
            'direct_answer': None, 'answer_status': 'pending_verification',
            'required_answers': [{'id': f'A{i}', 'question': q, 'query': query}
                                 for i, q in enumerate(QUESTIONS.get(key, ['原问题的直接答案是什么？', '支持证据是什么？', '适用条件和限制是什么？']), 1)],
            'facts_to_verify': ['任何健康功效、营养数值及其生熟/干鲜/可食部/产品规格基准'],
            'review_required': True}
