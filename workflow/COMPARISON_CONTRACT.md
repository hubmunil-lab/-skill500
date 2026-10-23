# 对比类返工协议（仅修复现有模板）

运行固定入口：

```bash
/workspace/.venvs/skill500/bin/python -m workflow.comparison_runner --output artifacts/phase4-rework/new-run
/workspace/.venvs/skill500/bin/python -m unittest tests.test_comparison_rework -v
```

输出目录必须不存在，避免覆盖既有图片。默认创建两个**合成软件验收案例**，不是实际食品、实测价格或真实营养数据。数据与原创程序插画为 CC0-1.0；不能冒充真实商品，也不能作为营养事实来源。客户参考版式与字体不在该授权范围。

## 固定业务语义

| 页码 | 业务角色 | 左右两侧各自必填 | 额外校验 |
|---|---|---|---|
| 1 | 外观、口感、价格 | appearance / taste / price | 价格币种CNY、500ml容量、日期、渠道；不能用图片观察替代口感与价格 |
| 2 | 营养 | energy / carbohydrate / sugars / vitamin_c / feature | kcal/g/g/mg；同为每100ml即饮状态；特色成分须配料依据；糖不得大于碳水 |
| 3 | 实际食用场景、选购建议 | scene / selection | 绑定同一SKU、记录和来源；不得填图片证据局限性说明 |

根字段：schema_version=2、contract=compare-business-2、mode=synthetic_test或production、query_binding、focus、subjects、sources、pages、assets。完整输入示例见 examples/workflow/comparison_rework/*-packet.json。

- query_binding 保留去除括号方向后的 query 和 direction；原标题另存在 input.json。
- subjects 必须有两项且ID不同，包含name、sku、specification。每页 subject_order 固定。
- 每个业务字段是 {source_id, fact_id, fact}。来源JSON必须有 facts[fact_id]，其完整值须与 fact 精确一致，不能拿一张照片哈希为任意健康文案背书。
- 来源包含仓库内路径及SHA256，`fact_id` 同时是可人工查看的定位标识；数字、单位、基准、产品身份和字段类型一起绑定。
- 真实生产证据必须经过编辑确认 verified_for_production，且源文件不能标记synthetic。该标记属于人工输入，不会由程序自动写true；哈希和结构通过仍不等于来源内容正确。
- assets 绑定两侧ID及SKU、像素尺寸、文件与授权文件SHA256；真实资料要求授权实拍与publication用途。默认合成案例只允许synthetic_test用途插画；改mode为production不能洗白。

## 内容生成及语义质检

EvidenceComparisonProvider 是确定性的资料适配器，不是通用AI。当前明确支持：`对象A与对象B每100毫升含糖量哪个更低`、`对象A与对象B每100毫升维生素C哪个更多`。使用完整语法解析、具体对象与min/max运算生成直接答案，不是数关键词；问“更高”却提供“更低”意图会阻断。其他问题需要新增经确认的意图协议，不能擅自转成已支持的问题。

海报槽位与正文从同一份已验证业务字段编译；slot_bindings逐槽保存来源定位、字段、对象及最终显示文本。copy_qc重新编译并精确比对正文、直接答案、意图、标题和海报，拒绝文案或数值改动。仅靠类型校验仍不能评估来源真假和描述好坏，保留人工语义清单。

旧 ReferenceVisualCopy 保留作历史回归输入；旧通用 content_qc 会拒绝其对比输出，Batch 对比路径也会输出20项事实缺口并阻断。--review-references 不能再绕过业务证据。历史通过结果只说明旧布局测试，不是业务合格样稿。

对两条不同任务，查询、方向、原始query、完整packet与来源哈希共同构成cache_key；任务ID不充当内容差异。跨任务检查不同query同正文或同页内容，同query换任务ID也报重复。生成器根据具体比较目标计算答案，封面直接给出结论，正文首句相同结论；其余两页仍须完成模板规定任务。

## 视觉修正与人工复核

compare_revision 对原三张对比模板作版本化修正，**未新增模板家族**。全部原slot坐标、照片区域和文字颜色保留；正文固定20.5px/27px常规字重，标题固定48px、字重700、白描边3px。禁止动态缩字与改布局。

背景只清理内框之内的变量区域，保留已知边框环像素；不再以跨过边框的白色大矩形遮挡。测试图片独立透明PNG，完全不使用原有被粗暴擦除VS边缘的饮品裁图。原客户字体/分层源文件仍缺失，这只是可人工比较的修正，不声称像素复原。

每页输出参考对照与差异图；before/使用同一份新内容和插画、旧字体与旧背景，after/使用新字体与修复背景。NN-before-after.png另含历史退回图，避免把内容变化误当作视觉精度提升。所有比较图与审核说明保存在独立产物，不写进海报业务字段。

逐页几何检查仍复用原引擎HTML/inspect/字体加载、文字溢出、遮挡、越界、固定坐标、锁定背景、尺寸检查；跨页身份和业务顺序在渲染前验证。缺资料或授权时，无关文案、占位数字、扩大review开关均不能解锁渲染。

有完整真实资料时，可用相同case列表结构调用 --cases 自定义JSON。每项包含task_id/query/direction/packet；packet必须符合上述协议。当前始终delivery_ready=false/customer_approved=false，不提供自动客户审批。
