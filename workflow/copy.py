"""Grounded copy provider. Unsupported domains require an evidence-backed provider."""
import json
from .core import ROOT


class ReferenceVisualCopy:
    def supports(self, task, classification):
        query = task['search_query'] + ' ' + task['direction']
        return (classification['category'] == 'comparison' and '柠檬' in query and '可乐' in query
                and any(word in query for word in ['外观', '颜色'])
                and not any(word in query for word in ['营养', '健康', '热量', '糖', '孕', '减肥', '功效']))

    def generate(self, task):
        color_only = '颜色更深' in task['search_query']
        answer = ('现有参考图不足以判断哪种饮品液体颜色更深：左图可见淡黄色饮品，右图只展示不透明可乐罐。' if color_only else
                  '在所提供参考图中，左侧为透明杯中的淡黄色柠檬饮品，右侧为红色可乐罐；右图看不到罐内液体。')
        questions = ['图中两种饮品的颜色如何？', '图中可见什么容器和细节？', '结论适用范围是什么？']
        manifest = json.loads((ROOT / 'examples/customer_templates/compare.json').read_text())
        for page in manifest['pages']:
            page['values'].update(name_left='柠檬饮品', name_right='可乐')
        v = manifest['pages'][0]['values']
        v.update(title='柠檬饮品和可乐外观对比', subtitle='仅观察所提供的参考图',
                 tag_1='颜色', tag_2='可见细节', tag_3='观察范围',
                 field_1_left='淡黄色\n透明杯中可见饮品。', field_1_right='红色罐体\n罐内液体不可见。',
                 field_2_left='透明杯\n杯中可见柠檬片。', field_2_right='不透明罐\n只能观察包装。',
                 field_3_left='仅限参考图\n不推断配方与营养。', field_3_right='仅限参考图\n不推断口感与价格。')
        v = manifest['pages'][1]['values']
        v['title'] = '参考图中的可见差异'
        left = ['颜色：淡黄', '容器：透明杯', '可见：柠檬片', '依据：参考图', '范围：画面所见']
        right = ['液体：不可见', '包装：红色罐', '可见：罐体文字', '依据：参考图', '范围：画面所见']
        for i in range(1, 6):
            v[f'nutrient_{i}_left'], v[f'nutrient_{i}_right'] = left[i-1], right[i-1]
        manifest['pages'][2]['values'].update(title='看图辨认与结论边界',
            use_left='辨认\n看透明杯与柠檬片。', use_right='辨认\n看红色可乐罐体。',
            select_left='观察范围\n仅描述这张参考图。\n图片不能证明营养成分。',
            select_right='观察范围\n仅描述这张参考图。\n图片不能证明健康作用。')
        claims = [
            {'id': 'visual-left', 'kind': 'visual', 'text': '参考图左侧淡黄饮品、透明杯、柠檬片', 'source_ids': ['left']},
            {'id': 'visual-right', 'kind': 'visual', 'text': '参考图右侧只有红色罐体，罐内液体不可见', 'source_ids': ['right']}]
        return {'direct_answer': answer, 'title': '柠檬饮品和可乐，看图有什么不同？',
                'body': answer + '\n\n左侧看透明杯和柠檬片，右侧只能观察红色罐体，不能推断罐内液体颜色。'
                        '\n以上仅为参考图可见特征，不代表所有产品，也不提供营养或健康结论。'
                        '\n【内部审阅稿：模板与图片发布授权尚待确认】',
                'required_questions': questions, 'coverage': [
                    {'question': questions[0], 'answer': '左侧淡黄，右侧液体不可见。', 'claim_ids': ['visual-left', 'visual-right'], 'page': 1},
                    {'question': questions[1], 'answer': '透明杯、柠檬片；红色罐体。', 'claim_ids': ['visual-left', 'visual-right'], 'page': 2},
                    {'question': questions[2], 'answer': '仅限所提供参考图。', 'claim_ids': ['visual-left', 'visual-right'], 'page': 3}],
                'claims': claims, 'manifest': manifest, 'placeholders': [],
                'scope': 'internal_visual_reference_review', 'copy_provider': type(self).__name__}
