# 第五阶段：搜索意图优先

顺序固定为：原始query → 核心问题/情境/必要事实 → 已登记模板评分 → 证据与原值适配 → 先回答问题的文案 → 固定槽位投影 → Playwright几何检查 → 人工审阅。没有模板或事实时分别记录缺口，不把无关模板字段追加为用户资料义务。

## 复跑

项目需要Python、customer_templates/requirements.txt所列包、Chromium及Noto CJK字体。字体许可证保留在rendering/FONT_LICENSE.txt。当前环境使用 /workspace/.venvs/skill500/bin/python；其他环境使用自身Python/venv。

```bash
python -m planning.fixtures
python -m planning examples/planning/ten_queries.json --output artifacts/phase5-intent/new-run --render-review
python -m workflow.pipeline examples/planning/batch_inputs.json --data examples/planning/packet_index.json --output artifacts/phase5-intent/new-batch --review-references
python -m unittest discover -s tests -v
```

两个渲染命令均实际调用原HTML/CSS+Playwright。前者输出10例软件预期/真实业务统计；后者沿用SQLite任务状态与恢复。相同Batch命令检查依赖与产物后恢复，--retry保留旧attempt。--review-references现仅表示请求内部审阅渲染，不再准许未知授权素材；源文件、授权与数据类型仍需校验。无匹配模板的任务不渲染。

## 意图接口

IntentParser.parse(task)返回original_query、core_question、category、themes、focus、operation、search_context、required_facts、useful_supplement、irrelevant_template_fields、scope_conflicts。RuleIntentParser可替换；原分类器的规则/可选模型结果保留，增加明确双对象选择和实测语义的解释。它是有边界的规则解析器，不宣称通用中文语义理解。

六大生产类型不变。appearance/nutrition/price/selection仅为内容方向，不向template_catalog.yaml注册新模板。例：外观问题只需外观/同条件观测和身份，通勤选择需包装、携带条件、封口与选择依据；营养介绍不会自动索取3个食谱。括号方向不是证据，不能悄悄覆盖核心问题；冲突需复核。

## 模板评分及门控

policy.json是可配置工程策略，不是客户新规则。权重：问题覆盖0.30、字段相关0.25、事实0.15、素材0.10、审批0.10、容量0.10。评分仅用于解释与排序，不能冲掉硬阻断。

只评估catalog已有的可编辑模板。未覆盖问题、必填字段与问题无关、主题不同、对象/条目容量不符、已知溢出，均禁止投影。不凭高总分放行。容量未知返回待确认；文本容量在实际浏览器渲染前只标记not_measured，不冒充已通过。审批未知的语义匹配模板仅可做有证据/授权的审阅稿，customer_approved和delivery_ready保持false。

现有综合对比模板仍固定三页：外观口感价格/营养/食用选购。只有query明确要求这些信息才适配；单独外观/价格/营养/选购缺少专门登记变体，返回模板缺口，不重设计。现有介绍模板的3张食谱也不能反向要求不问食谱的介绍query补食谱。

## 产品与单位接口

ProductAdapter(configuration=..., evidence_resolver=...)支持可配置单位、别名、币种、营养基准和真实包装数量。nutrient/price返回raw_record、标准化值和derivation；不改源值。配置示例与合成packet见examples/planning/。

- 实际容量不固定500ml，支持330/250/200/1000ml等；价格保留真实容量、件数、日期、渠道。
- 币种不固定CNY，默认配置CNY/USD/EUR/JPY/HKD/GBP，可扩展；不同币种无可核查汇率时阻断，不当成同一种钱。
- 营养保留原始单位、基准和状态。只在有合法单位关系、统一基准和同一制备状态时换算。能量kJ↔kcal采用明确工程常数，展示值为一般数值格式，原精度/换算过程保留；客户法规舍入规范尚待确认。
- 质量↔体积需要密度资料；跨币种需要有日期/方向的汇率资料。只传evidence_verified=true不能放行，低层接口需经来源解析器返回完全匹配记录。当前高层生成器不自动接入密度/汇率文档，遇到这种情况停审，不能自行猜测。
- 问题/配置基准冲突、产品状态不同、未标示数值、单位不支持均停审。没有统一比较口径时不比较。

## 发布文案与来源

原始事实由带哈希的源JSON按fact_id精确匹配，并核对对象和字段类型；只校验本问题所需字段。合成来源不能通过改mode或verified标记伪装成真实来源。照片身份/授权与科学事实分别处理。

正文先给出有依据的答案，再按query提供相关细节；单指标问题不会自动附上价格、热量和食用建议。有已核查的事实但无匹配模板时可输出待审文本，图片仍待确认。

标签只格式化一次，清除重复前缀。“怎么选”在数据足够时依据同口径比较结果、具体包装与价格生成两侧不同建议；derivation保留跨对象事实映射，不新增功效、健康阈值或特殊人群建议。文案仍需编辑润色和受众审核，不宣称已达到小红书营销效果。

## 版本与限制

workflow.pipeline.Batch默认接入本规划层，不是旁路演示。第四阶段comparison_contract/comparison_runner保留为历史v2协议与回归接口，其固定500ml/CNY/问句不是当前通用入口。一个旧回归断言按新需求更新为“外观只需appearance、返回模板待确认”，保留该测试及其他全部测试。

当前通用新内容提供器主要覆盖有类型证据的双对象数值比较与有限外观描述；通勤选择、推荐、盘点、介绍和实测可以规划/列资料，但没有新的完整文案/渲染适配器。现有4模板的字体/配色强调差异仍待客户验收，本阶段不修版式、不注册变体、不自动签批。

8条人为选定的真实自然语言问题没有完整真实商品资料；另2条显式要求全维度比较的合成query仅用于复用现有综合模板验证。这不是10条真实商品生产成功，也不是证明通用解析效果。10例预期通过率、合成渲染率和真实交付率分别报告。
