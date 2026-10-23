"""Conservative, explainable baseline. Ambiguous queries require review."""
import re
from .config import normalize_category

PATTERNS = {
    'intro': r'营养|功效|作用|好处|介绍|能吃|可以吃|能不能吃',
    'procedure': r'怎么做|如何做|做法|步骤|教程|食谱',
    'recommendation': r'推荐|适合|吃什么|喝什么|选什么|选择|怎么搭配|如何搭配',
    'inventory': r'盘点|种类|品种|图鉴|有哪些',
    'comparison': r'对比|相比|比较|区别|哪个|哪种|\bvs\b',
    'review': r'测评|评测|试喝|体验|实测',
}

def classify(query, category=None):
    if not isinstance(query, str) or not query.strip():
        raise ValueError('query must be non-empty text')
    hits = [key for key, pattern in PATTERNS.items() if re.search(pattern, query, re.I)]
    if category is not None:
        selected = normalize_category(category)
        return {'category': selected, 'candidates': hits, 'status': 'explicit',
                'reason': '调用方明确指定；原问题仍须语义复核'}
    # Comparing a nutrient is still comparison; instructional nutrient recipes are procedures.
    if 'comparison' in hits and 'review' not in hits:
        hits = ['comparison']
    elif 'procedure' in hits and set(hits) <= {'procedure', 'intro'}:
        hits = ['procedure']
    selected = hits[0] if len(hits) == 1 else None
    return {'category': selected, 'candidates': hits,
            'status': 'suggested' if selected else 'needs_confirmation',
            'reason': '词面启发式，非已验证的语义判断' if selected else '多意图或信息不足，不自动选类'}
