# 第五阶段：搜索意图驱动规划与模板适配报告

本阶段读取第四阶段业务验收准备报告后，修改了默认Batch入口，先计算问题所需事实，再选择已登记模板。未注册新模板、未自动批准客户模板。

## 实际结果

- 10例软件预期验证通过10/10，包含分类、模板选择/缺口、必要事实范围及实际渲染预期。这个比例不是业务成功率或通用语义准确率。
- 8条真实自然语言问题未提供完整真实产品资料，正式交付0/8；真实业务渲染0/8。
- 2条明确要求综合对比的合成软件案例实际渲染2/2，共6张1242×1656 PNG。数据/图片仅测试，不是实际产品信息，不计入真实业务成功。
- 新分支检出目录全量回归107项通过（70.238秒）；包含原93项及新增14项。未删除旧测试；1项旧断言按新规则由“外观索取20字段”更新为“只索取appearance、模板待确认”。
- 原workflow.pipeline也实际运行10条：2套合成图、8项未渲染，REVIEW 8 / BLOCKED 2 / DELIVERED 0；再次执行10/10恢复，无新渲染。

## 10条query及结果

以下保留完整原始query。每个任务的intent.json还列出搜索情境、核心focus/operation、必要事实、有用补充、不相关字段及解释。

| ID | 原始query | 内容类型/方向 | 需要的事实 | 模板与实际结果 |
|---|---|---|---|---|
| p5-appearance | 柠檬水和可乐哪个颜色更深（只看液体外观，不要营养） | 对比 / appearance | appearance | TEMPLATE_GAP_REVIEW_REQUIRED；未渲染 |
| p5-price | 250ml果汁和330ml果汁哪个更划算（统一容量比价） | 对比 / price | price | TEMPLATE_GAP_REVIEW_REQUIRED；未渲染 |
| p5-selection | 玻璃瓶和塑料瓶饮料通勤怎么选（选购对比，不看营养） | 对比 / selection | selection,packaging,portability,sealing | TEMPLATE_GAP_REVIEW_REQUIRED；未渲染 |
| p5-sugar | 示例甲和示例乙对比外观、口感、价格、营养、食用场景和选购，重点看每100毫升含糖量哪个更低 | 对比 / appearance,taste,price,nutrition,scene,selection | appearance,taste,price,sugars,energy,carbohydrate,vitamin_c,feature,scene,selection | customer-compare-v1；3张合成PNG，REVIEW |
| p5-vitamin | 示例丙和示例丁对比外观、口感、价格、营养、食用场景和选购，重点看每100毫升维生素C哪个更多 | 对比 / appearance,taste,price,nutrition,scene,selection | appearance,taste,price,vitamin_c,energy,carbohydrate,sugars,feature,scene,selection | customer-compare-v1；3张合成PNG，REVIEW |
| p5-intro | 青椒有什么营养特点 | 单一介绍 / ingredient_introduction | identity,nutrition_summary | TEMPLATE_GAP_REVIEW_REQUIRED；未渲染 |
| p5-procedure | 青椒炒肉怎么做，火候和步骤是什么 | 步骤操作 / cooking_steps | ingredients,steps,heat_control | TEMPLATE_GAP_REVIEW_REQUIRED；未渲染 |
| p5-recommend | 早餐水果推荐（方便携带） | 推荐 / scenario_recommendation | candidate_items,selection_reasons,constraints | CAPACITY_REVIEW_REQUIRED；未渲染 |
| p5-inventory | 常见苹果品种盘点（口感和用途） | 盘点 / item_inventory | item_list,distinguishing_features,usage | TEMPLATE_GAP_REVIEW_REQUIRED；未渲染 |
| p5-review | 三款无糖饮料实测体验（口感和价格） | 多品测评 / hands_on_review | product_identities,test_protocol,observations,limitations | TEMPLATE_GAP_REVIEW_REQUIRED；未渲染 |

## 与第四阶段的架构变化

1. 外观问题只索取外观、身份与同条件观察资料；热量、糖、价格等记为不相关模板字段。当前综合对比模板被拒绝，不把模板缺口包装成客户还欠营养资料。
2. 对比的外观/营养/价格/选购是内容方向，不能当作客户已批准模板。现有综合3页对比仅在query明确要求外观口感价格、营养、场景与选购时匹配；不改三页字段来凑图。
3. 模板评分覆盖问题、字段相关、事实、素材、审批、容量六维；policy权重为工程策略、非客户确认规则。语义不相关/问题未覆盖/容量不符等硬门控优先于总分。文字容量未测时明确标注，实际渲染仍检查溢出。
4. 数据适配保留raw_record，计算值和derivation另存。软件案例覆盖330/250/200/1000ml、USD/JPY、原始kJ、不同营养基准。原数据没有被改成500ml/CNY/每100ml；只做有依据的换算。
5. 删除重复标签的生成方式；正文以有依据的直接答案开头，选购建议根据本次比较结果和实际规格生成两侧差异，并保留推导来源。没有新的功效、人群或健康阈值结论。

## 证据与无资料时的行为

- 来源必须按source_id/fact_id精确绑定原值与对象，原始标签、单位和状态不能被改写。仅检查本问题需要的字段，不让无关模板事实变成需求。
- 有本问题证据但无匹配模板时，可生成与问题对应的待审文字，图片仍待模板确认；专项测试验证单独糖问题不附价格/热量，也不投影进综合模板。
- 无事实、规格、统一比较口径或授权素材时分别记录缺项；不同币种无汇率、质量/体积无密度、制备状态不同等均阻断，不猜测换算。
- 高层目前不自动导入密度/汇率资料；低层接口要求可解析的匹配来源，不能靠evidence_verified=true绕过。
- 目标受众、真实体验和健康条件不从词条擅自推断。方向与核心问题冲突需确认，方向不是事实来源。

## 合成样稿和来源

最新产物为artifacts/phase5-intent/run-004/。前几个run是保留的开发迭代，不合并计为更多生产套组。

- p5-sugar/render/01.png至03.png，preview.png、reference-comparison.png及逐元素QC。
- p5-vitamin/render/01.png至03.png，同上。
- 每任务input.json、intent.json、template_match.json、required_materials.json、missing_materials.json、planning_brief.json、copy.json、post.md、qc_report.json。
- 两套生成任务另有source_packet.json、inputs/完整源JSON/原始插画/许可证；copy.json逐槽包含原始记录、换算与推导映射。
- 综合query是为验证既有综合版式而明确构造的全维度软件问题，不代表常见搜索词分布；不将其伪装成真实搜索日志或真实商品成功案例。

## 仍不支持与待客户判断

- 没有已登记的外观专用、价格专用、营养专用、选购专用固定模板；不擅自新增或改综合版式。
- 默认规则解析器有范围限制，复杂省略、否定冲突、多对象关系等需要人工/可插拔解析器复核，不承诺通用语义准确率。
- 新内容提供器主要支持有类型证据的双对象数值比较及有限外观描述；多品评测、步骤、介绍、推荐、盘点及通勤选购的完整文案/渲染适配仍未完成。
- 配置支持多个单位/币种，不代表任何单位或货币都已支持；跨状态/跨质量体积/跨币种遇到缺依据时停审。展示舍入与价格有效窗口还没有客户确认规范。
- 2套插画不是真实实拍，不能证明SKU、液体透明度或真实口感；合成营养值可追溯但不是可靠科学证据。
- 第四阶段记录的字体、色彩强调、密度与原图差异保留，仍需客户视觉验收。107项技术通过不构成内容、素材授权或客户审批通过。
- 当前真实业务成功为0。没有自动发布或DELIVERED放行，不创建PR，不改main。

## 代码、回归与复现

新增planning/意图、证据、评分、单位与发布文案模块，以及样例和14项针对性测试；workflow.pipeline默认调用新层并保留SQLite状态、重试和恢复，缓存依赖增加数据文件实际哈希。历史v2对比协议/渲染器及旧成果保留。

本次独立review/phase5-intent分支同时补齐此前仅存在工作区的前四阶段运行源码/配置/测试依赖，以便实际检出后复跑；不代表本阶段新增数百个功能或模板。未上传venv、缓存或凭据。该检出目录使用当前已安装依赖实际运行107项回归通过。

```bash
python -m planning.fixtures
python -m planning examples/planning/ten_queries.json --output artifacts/phase5-intent/new-run --render-review
python -m workflow.pipeline examples/planning/batch_inputs.json --data examples/planning/packet_index.json --output artifacts/phase5-intent/new-batch --review-references
python -m unittest discover -s tests -v
```

环境依赖、接口与边界见planning/README.md。实际渲染输出须新建目录，避免覆盖已有产物。技术状态与真实业务统计分别见report.json和test_report.json。
