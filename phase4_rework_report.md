# 第四阶段返工：内容与业务QC缺陷报告

**本次结果：已修复对比类业务门控，并生成两套各3张、实际可人工检查的合成测试PNG；真实生产成功0套、原真实词条阻断2条。业务验收未通过，客户审批未设置为true。**

旧6张PNG已被人工退回。旧报告的“PASS_LAYOUT”仅代表历史几何检查，不能作为内容合格、可交付或客户接受的依据。所有旧图、模板、代码接口与原有测试保留。

## 逐项根因与修正

| 缺陷 | 根因 | 实际修改及证据 |
|---|---|---|
| 第二页不是营养、第三页不是场景与选购 | 旧manifest的nutrient/use/select只是无类型文本槽位；提供器可任意改语义 | 新增comparison_contract：第1页appearance/taste/price；第2页energy/carbohydrate/sugars/vitamin_c/feature；第3页scene/selection。左右共20个字段，类型、页角色和对象顺序全部固定 |
| 内部说明填满海报 | ReferenceVisualCopy被当成有效业务提供器，review开关绕过事实要求 | 旧类保留为回归反例；Batch对比路径和content_qc拒绝视觉观察稿。审核说明只留QC，海报缺资料时无PNG。缺少营养/价格/口感时逐字段报错，不补无关说明 |
| real-01/02图文重复 | 两个query走同一硬编码manifest；未校验query→意图→具体答案；只有单页重复检查。不是缓存撞键导致 | 新提供器用完整受限语法解析对象、每100ml基准、指标与min/max运算；封面与正文直接回答。cache_key含原始query、query、方向、完整packet及来源哈希；正文与逐页内容跨任务检查，换ID或换路径不能成为独立成功 |
| 来源有哈希就能为任意文案背书 | 旧verify_claims只验证文件存在、哈希与宽泛kind，不检查源记录的实际值 | 新字段绑定source_id+fact_id+完整fact，逐值比对源JSON，同时检查对象、指标、单位、计量基准、价格上下文、配料依据。图片不能作为营养/口感/价格证据 |
| 字体偏粗偏大 | 旧所有正文slot字重700，标题52px、描边5px，未分别校准 | 原slot坐标/配色保留，标题48px/700/描边3px；正文20.5px/27px行高/400。标签与名称分别固定字号，不按文案动态缩字。原客户字体未知，仍待客户目视确认 |
| 边框白色断裂 | prepare.plate的白矩形x=40..345和x=375..等跨过内框，清掉固定像素 | 新compare_revision只在框内清理变量内容。第2/3页两侧被测框条与参考图像素误差修正后均为0；这不表示整页像素一致，见visual_border_metrics.json |
| 清理修补痕迹 | 低清客户裁图、粗暴覆盖VS边缘，与背景清除互相污染 | 测试使用原创透明高分辨率程序插画，独立于模板背景，不使用有擦除痕迹的饮品裁图；背景保留框环。真实客户饮品照片仍需补授权高清原图，代码没有“恢复”不存在的像素 |
| 信息密度低 | 缺资料时填短审核语句，未完成实际业务信息 | 测试第1页外观3行、口感4行、价格2行；第2页5项营养/成分；第3页场景2行、选购7行。均为字段本身信息，溢出时失败，不靠缩字或移动版式 |

## 两套实际生成案例：明确不是生产食品

现有资料没有两套真实商品的完整、可核查数据与发布授权；因此没有声称“已找到足够资料”。按本次任务允许的降级测试方式，使用作者自行编写、明确标识的合成软件测试数据和原创程序插画（CC0-1.0），验证完整内容流程。数值、价格、口感、配料、场景都属合成fixture，不是检测、官方数据或真实食品营养结论。

| 案例 | 原始query | 生成的直接答案 | 页数/状态 |
|---|---|---|---|
| fixture-sugar | 测试配方A与测试配方B每100毫升含糖量哪个更低 | 每100毫升A含糖2g、B含糖6g，A更低 | 3页，REVIEW_SYNTHETIC_TEST_ONLY |
| fixture-vitamin | 测试配方C与测试配方D每100毫升维生素C哪个更多 | 每100毫升C维生素C为12mg、D为45mg，D更多 | 3页，REVIEW_SYNTHETIC_TEST_ONLY |

两套完整海报正文、颜色、数值、名称和比较结论不同，6张PNG的SHA256均不同。封面直接显示各自结论，第二页完成营养对比，第三页完成场景与选购。海报没有用内部审核说明替代业务内容；“虚构配方”是测试内容身份的必要标识，不是营养或价格字段的占位文案。预览顶部另标注SYNTHETIC，独立的审核报告不混进海报。

## 最新PNG、来源和对照

以 `artifacts/phase4-rework/run-004/` 为本次最终审阅产物；run-001至003是保留的视觉/文案迭代，不作为最终稿。

- `fixture-sugar/after/01.png`、`02.png`、`03.png`。
- `fixture-vitamin/after/01.png`、`02.png`、`03.png`。
- 两组各有 `after/preview.png`、`after/reference-comparison.png`、逐页reference comparison/difference、逐页元素级 `after/qc_report.json`。
- `NN-before-after.png`：左为历史退回样稿，中为相同新内容+旧字体/旧背景，右为本次修正。中/右对照可以单独评估视觉修复；不同案例内容不能作为像素级还原证明。第3页旧字号容纳不了完整7行选购内容，before的溢出QC正确阻断，三栏图中明确显示BLOCKED，未伪造旧版第3页PNG。
- `input.json`保留query与方向；`business_packet.json`为每页结构化业务字段；`copy.json`为正文/海报/意图/逐槽来源绑定；`facts_and_sources.json`为来源定位。
- `inputs/fixture-source.json`、左右插画PNG、左右LICENSE文本是随产物保存的可独立检查源文件。其数据用途明确为软件测试，不能作为真实健康证据。
- `report.json`、`content_qc.json`、`cross_task_qc.json`、`visual_revision.json`与`visual_border_metrics.json`为程序及视觉检查记录。

## 原真实词条：正确阻断

`artifacts/phase4-rework/original-query-block-test/` 用第一版真实输入的原始query（含括号方向）重新执行了原Batch入口，且故意开启旧 --review-references 开关。结果2/2 BLOCKED、生成0套、无PNG；证明旧开关不能绕过业务规则或复用历史成功缓存。

| 词条 | 具体缺项 |
|---|---|
| 柠檬水和可乐外观有什么区别（只比较参考图可见差异） | 两侧各自appearance、taste、price、energy、carbohydrate、sugars、vitamin_c、feature、scene、selection的事实来源；两侧品牌/SKU/规格/版本，以及匹配授权实拍 |
| 柠檬水和可乐哪个颜色更深（颜色与包装） | 同上；且右图只有不透明罐体，不能推断液体颜色。无法识别精确产品配方，不用参考截图数字填补 |

每个字段在missing_materials.json中分别列明页码、左右侧、字段名及所需资料。所谓“外观问题”不能使既定三页模板的其他必填任务消失；若客户希望仅回答外观，需要先确认其他内容产品，本次没有新增模板或擅自改变规则。

## 验收条件逐项说明

| 条件 | 本次证据与判定 |
|---|---|
| 模板没有明显错位 | 6页真实浏览器固定坐标、遮挡、越界、字体、锁区和尺寸检查通过；已查看预览，仍需客户确认字体、密度和整体可读性 |
| 实际回答原始问题 | 两个受限合成问题已解析并计算，正文与封面直接回答；不能外推为任意query语义能力 |
| 三页完成指定任务 | 合成案例20个必填业务字段齐全且逐项映射，程序通过 |
| 没有审核说明填充正文 | 新业务通路无此填充；旧稿回归输入必须拒绝 |
| 两套不重复 | 正文/页内容/缓存键均不同；6张PNG哈希不同 |
| 健康数据可追溯 | 合成数据可追溯到fixture，**真实健康数据尚缺，不满足真实食品交付验收** |
| 缺资料正确阻断 | 原Batch两个真实query、开启旧review开关，均阻断且没有PNG |

因此：**软件缺陷修复和合成流程测试通过，不宣布客户业务验收通过。** 原字体/可编辑源图、授权高清实拍、产品规格、价格记录、口感依据和可靠营养来源仍需人工补充；代码不能伪造这些资料。

## 代码及测试

修改 `workflow/pipeline.py`，新增 `workflow/comparison_contract.py`、`workflow/comparison_runner.py`、`workflow/comparison_fixtures.py`、`workflow/COMPARISON_CONTRACT.md`、`customer_templates/compare_revision.py`、`tests/test_comparison_rework.py`，并新增测试资料与版本化背景/config快照。原四套模板的registry、v5组件、配置、源图与旧测试保留，不注册第五套模板。

全量回归93项通过（79项既有+14项新增，73.078秒）；最终封面答案及密度调整后专项14项通过（10.687秒）。包含实际Playwright PNG渲染与超长文字失败回归。71项素材/培训源哈希校验通过。

```bash
/workspace/.venvs/skill500/bin/python -m workflow.comparison_runner --output artifacts/phase4-rework/new-run
/workspace/.venvs/skill500/bin/python -m workflow.pipeline examples/workflow/comparison_rework/original_queries.json --output artifacts/phase4-rework/new-block-run --review-references
/workspace/.venvs/skill500/bin/python -m unittest discover -s tests -v
```

命令在包含前四阶段代码和venv的当前Codex工作区运行；本次GitHub审阅分支上传的是审阅产物与报告，不声称已推送全部阶段源码。输出目录须为新目录，防止覆盖已有文件。第三方数据完整后可使用同一协议的 --cases JSON 验证，不需要开发通用AI文案生成器。
