# 第四阶段：证据门控的端到端流程

## 运行

从仓库根目录执行（依赖沿用 customer_templates/requirements.txt、Chromium 和 Noto CJK 字体）：

```bash
/workspace/.venvs/skill500/bin/python -m workflow.pipeline examples/workflow/ten_queries.json --output artifacts/phase4-e2e --review-references
/workspace/.venvs/skill500/bin/python -m unittest discover -s tests -v
```

相同命令校验输入、依赖及全部产物 SHA256 后跳过已完成任务。`--retry` 创建新的 attempt 目录，保留旧输出。依赖变化或产物丢失/篡改也创建新 attempt。恢复粒度为单任务，不是单页。SQLite 保存状态、尝试次数和事件；READY 表示队列/处理中，REVIEW 表示需人工材料或审核，BLOCKED 表示无模板、输入错误或执行失败，DELIVERED 保留给通过外部审批后的交付。**当前不提供自动转 DELIVERED 的路径**，不存在已批准模板与发布授权时不可能交付。

## 输入与模块接口

JSON 数组，每项为 `{"task_id":"unique-id","query":"原始词条（选题方向）","direction":"可选显式方向"}`。原始 query 不变，末尾括号方向另存；方向不是证据，健康限制不能被方向冲淡。task_id 不允许路径字符，绑定唯一输入，禁止同 ID 换词条。

`ClassificationProvider.classify(query)` 返回 category（intro/procedure/recommendation/inventory/comparison/review）、confidence（0..1）、reason。可通过 Batch(provider=...) 注入。HTTPS OpenAI 兼容适配器使用 WORKFLOW_MODEL_ENDPOINT（完整 chat/completions 地址）、WORKFLOW_MODEL_NAME、WORKFLOW_MODEL_API_KEY；未配置或服务异常明确回退规则，记录原因和置信度。低置信度、模型/规则分歧必须复核。模型高置信度也不构成发布授权。本次未调用线上模型。

`CopyProvider.supports(task, classification)` / `generate(task)` 可注入 Batch(copy_provider=...)。返回 direct_answer、title、body、required_questions、coverage、claims、manifest、placeholders、scope。正文必须以直接答案开头。当前内置提供器**仅支持指定客户参考图的柠檬饮品/可乐外观问题**，其余类型先产意图与规划简报并停审，不声称已实现任意词条自动写作。沿用第一阶段 analyze/plan，缺少有序对象/条目时保留规划阻断，绝不捏造名单。渲染 manifest 使用第三阶段严格槽位协议，不能绕过固定布局或换图校验。

证据：每项 claim 带 id、kind（visual/nutrition/health/population）、text、source_ids；每个 source 带 kind、仓库内 path、sha256、locator。必须逐项校验文件哈希、类型和定位。科学/营养来源需要另行人工确认权威性、适用范围和版本；本阶段内置只有视觉观察，**照片不能支持营养、健康、特殊人群建议**。缺证据时不生成占位健康结论。

素材：match_assets 接口按 subject、purpose、最小尺寸、license_status、文件哈希过滤；默认仅 authorized。无联网抓取。--review-references 是用户提供参考图片的内部测试开关，保留 unknown 授权、customer_approved=false，不能作为发布许可。照片精度较低，不自动称为高清实拍。

## 阻断、质检与返工

默认缺授权素材不渲染。内部参考图模式允许输出审阅 PNG，但 REVIEW 永不自动变更为 DELIVERED。缺科学证据、缺客户审批、缺授权不能通过重试/改写消除。每个任务 qc_report.json 汇总内容与渲染 QC；渲染 QC 逐页逐元素保留尺寸、字体、溢出、遮挡、位置、越界、锁区与顺序检测。

内容 QC 检查直接回答在首位、问题/答案/证据映射、重复页、证据类型和哈希。语义一致性与照片真实身份仍须人工核查，规则通过不等于客户认可。安全返工最多3次，只支持去除首尾空白，**不截断、不缩字、不自动生成新事实**；无可安全修复方案直接阻断。每次渲染单独目录。

常见错误：TEMPLATE_UNAVAILABLE（缺模板）、EVIDENCE_AND_GROUNDED_COPY_REQUIRED（缺证据和文案提供器）、AUTHORIZED_MATCHING_ASSETS_REQUIRED、CUSTOMER_APPROVAL_REQUIRED、REFERENCE_LICENSE_UNKNOWN、HUMAN_SEMANTIC_REVIEW_REQUIRED、PIPELINE_FAILURE。错误保存每任务 JSON 与 SQLite events。批次输入错误隔离保存在 batch_report.json，不影响其他任务；无有效 ID 的输入不能写入 tasks 主表。

## 实测范围

10条是人工挑选的真实自然语言词条，不是声称从搜索平台获取的数据。覆盖六大类；预计2套3页外观对比审阅稿、6项内容/材料待审、2项缺模板阻断。两套使用同一模板和图片，测试不同问题；这不等于已验证不同食材替图生产。缺乏证据的8项不生成 PNG，也不冒充完整套组。
