# 正式模板1号候选：生产输入与阻断规范 v1

候选为 `business-01`，源自仓库 `compare-1` 双列对比模板。它不是 `intro-4` 演示模板。定义三页：外观/三营养亮点封面、营养数据、选择场景。第三页为同一固定版式的新增延展，客户未批准前只输出审阅样稿。

## 模板配置规范

- `template_registry.json`：schema_version、family、category、page_roles、font_sha256、templates及policy。模板ID与内容SHA-256绑定；改版必须使用新ID及新哈希，重新验收。
- 每页 `templates/*.json`：固定width=1242、height=1656、background、font_family、role、reference和elements。
- 元素：唯一id，kind为text/image/table/decoration，固定x/y/width/height。text/table还需固定font_size/line_height/weight/color；table固定rows/columns；image只允许contain适配。
- 标题、答案、左右照片/标签、正文、营养表和备注全部独立固定坐标。正文不得注入HTML/CSS、替换坐标、字号或页序。装饰可作为底板，照片框不得遮挡文字框。
- 当前三页均使用同一双列网格，图像位置与左右身份跨页不变。新版不承诺与原位图像素一致。

## 输入数据结构规范

可运行实例为 `examples/delivery/grapes-comparison.json`。根对象字段必须精确包含：

| 字段 | 类型/规则 |
| --- | --- |
| schema_version | 整数1 |
| template_family | business-01 |
| query | 非空原搜索问题 |
| subject | 食材对象域；当前数据适配器仅支持grapes，其他食材须增加独立证据适配器 |
| title | 非空、少于20字 |
| direct_answer | 非空、直接回答query，语义需事实编辑审核 |
| highlights | 恰好三个非空亮点，不强填未经证实的医疗功效 |
| objects | 恰好两个不同id的对象，各有id、label、asset |
| assets | 按asset ID索引真实照片记录，禁止占位/生成食材图替代 |
| nutrition_source | 仓库内证据记录路径，当前为USDA SR28 09132；不是该颜色/品种分别实测 |
| pages | 恰好三页，严格按cover/nutrition/selection；每页仅有template_id和values |

`values`的键必须完全匹配该页非装饰槽位（status由程序提供）。文字为非空字符串，图片为已存在asset ID，营养表必须逐格匹配可复算的来源数据。`label_left/right`匹配objects顺序，`photo_left/right`在所有页维持同一对象照片。

资产记录至少含path、sha256、subject（对象id）、kind=real_ingredient_photo、cutout=true、rights_status、rights_evidence。抠图PNG须有透明像素，原图保持不变。path只能指向仓库内已有文件；不在渲染阶段请求网络或临时补图。`rights_status=owned/licensed`还须有rights_evidence对象，包含仓库内证据path和sha256。当前样例照片来源于用户参考图，记录为unverified_user_reference，不能当作已获外部发布许可。

事实证据包含原始记录摘录、营养字段定义、文档摘要、镜像commit、完整源文件及摘录SHA-256。每100克、生鲜、可食部及通用记录范围必须明确。来源为2015年SR28第三方镜像，实时USDA原站当前被网络策略拒绝；不宣称已核对最新官方数据。

## 过长、缺图与失败策略

**文字过长只报错。** 不裁掉正文、不用省略号隐瞒缺字、不缩小字号、不移动框。编辑须在框容量内改写，重新生成并重新审核。营养数值和计量基准不得为了排版改写。图片只等比contain，不拉伸、不截断主体；不能用放大低清图解决高清源素材缺失。

缺图片、图片解码失败、对象错配、图片hash变化、缺透明通道、表格与来源不一致、乱页序、未知槽位或注入样式：**硬阻断渲染**，不输出完整预览。若渲染中后页失败，已生成的前页只是诊断残留，整套不可交付。

照片不足高清标准或权利未确认：允许明确标为“待客户验收”的本地审阅包，**阻断正式导出**。本样例照片仅237×391和269×397，小幅上采样也超出本候选的正式交付策略（display scale<=1.0）。不能把生成1242×1656文件说成原素材已经高清。

## 报错规范

`qc_report.json`记录status、errors、delivery_blockers、pages、bindings和review_digest。错误包含code、message、page、element；根结构错误page/element为空。根结构/证据错误优先停止，修复后再运行；浏览器布局错误按页汇总。

- INPUT_SCHEMA / CONTENT_MISSING / TITLE_LENGTH：输入缺失或不合法。
- PAGE_COUNT / PAGE_ORDER / TEMPLATE_UNKNOWN / LAYOUT_CHANGED：模板身份或锁定范围不合法。
- ASSET_MISSING / ASSET_SUBJECT / ASSET_CHANGED / ASSET_ALPHA / RIGHTS_EVIDENCE：照片缺失、错配或证据不一致。
- FACT_SOURCE / FACT_SCOPE / NUTRITION_MISMATCH / HEALTH_CLAIM / PLACEHOLDER_FORBIDDEN：数据域、数值或表述不合规。
- TEXT_OVERFLOW / IMAGE_TEXT_OVERLAP / CONTENT_OVERLAP / IMAGE_OUT_OF_BOUNDS / LOCKED_REGION / FONT_MISSING / FONT_CHANGED / PAGE_SIZE：真实浏览器排版失败。
- SOURCE_RESOLUTION / IMAGE_RIGHTS_REQUIRED / TEMPLATE_APPROVAL_REQUIRED / FACT_EDITOR_REQUIRED / VISUAL_REVIEW_REQUIRED：存在真实内容，但不能正式交付。
- REVIEW_STALE / APPROVAL_STALE / APPROVAL_REQUIRED / APPROVAL_EVIDENCE / DELIVERY_BLOCKED：正式导出阻断。

review命令退出0仅表示审阅包排版成功，其状态为REVIEW_NOT_DELIVERABLE，不代表交付成功。硬错误退出1；已有输出目录不覆盖。所有导出失败也写qc_report（不会覆盖已存在目录）。

## 生产阻断与审批绑定

当前客户未批准任何business-01页面，没有附送伪造审批包。正式导出先重新校验当前源文件与输入，再比较实际PNG的SHA-256；任一变更使原审批失效。硬性素材缺口必须先修复，不能用true覆盖。

审批包需review_digest及signoffs，角色为customer_template、fact_editor、rights_holder、visual_editor。各角色需approved=true、reviewer、date、evidence_path和evidence_sha256；证据文件必须存在且hash匹配。review_digest绑定输入、模板、照片、事实摘录、配套正文及最终PNG；审批文件是可追溯的人工记录，不是自动生成的授权或密码学身份认证。

导出只复制经批准的原始像素和正文，并生成DELIVERY_APPROVED回执；不再渲染、不改字体、不移动元素。预览总图的“待客户验收”标记不进入独立候选PNG，独立PNG是否能用由QC和真实审批决定。当前示例因清晰度和授权缺口不能进入此分支；未宣称已在客户批准素材上验证正式交付。

## 命令

```bash
cd /workspace/-skill500
export PYTHONDONTWRITEBYTECODE=1
/workspace/.venvs/skill500/bin/python -m delivery.prepare_sample
/workspace/.venvs/skill500/bin/python -m delivery review \
  --manifest examples/delivery/grapes-comparison.json --output artifacts/new-review-run
# 仅在素材缺口解决且取得真实审批文件后使用：
/workspace/.venvs/skill500/bin/python -m delivery export \
  --review artifacts/new-review-run --approvals /path/to/real-approval-packet.json \
  --output artifacts/new-approved-delivery
```

本轮不开发调度系统、其他五类模板、素材搜索平台或发布功能。第一阶段分类和第二阶段引擎保持原状，由新增delivery模块复用其真实浏览器测量能力。
