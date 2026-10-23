# 第一阶段：分类、意图、内容规划与质检

保留全部原文件与素材，新增 `production/` 实现可执行的内容准备流程。本阶段不渲染海报、不抓取网络图片、不推断健康答案，也不发布内容。

## 运行

Python 3.10+；原有图片验证器与测试依赖 Pillow。当前云环境使用 `/workspace/.venvs/skill500/bin/python`，亦可使用已安装 Pillow 的 Python。

```bash
cd /workspace/-skill500
export PYTHONDONTWRITEBYTECODE=1
/workspace/.venvs/skill500/bin/python -m production intent '怀孕14周能吃花甲吗' --category 单一介绍
/workspace/.venvs/skill500/bin/python -m production plan '青椒营养价值' --template intro-1
/workspace/.venvs/skill500/bin/python -m production plan '苹果品种图鉴' --template list-1 --items a b c d e f
/workspace/.venvs/skill500/bin/python -m production plan '红石榴和白石榴哪个营养价值高' --template compare-1 --objects red white
/workspace/.venvs/skill500/bin/python -m production qc examples/production-brief.example.json
/workspace/.venvs/skill500/bin/python -m unittest discover -s tests -v
/workspace/.venvs/skill500/bin/python scripts/validate_library.py
```

`intent`、`plan` 正常返回草案时退出0，输入非法退出2。`qc` 读取结构化交付草稿；FAIL或REVIEW退出1，只有预检PASS退出0。示例是未完成草稿，故QC预期退出1。旧 `scripts/validate_delivery.py` 的 REVIEW 仍退出0，保持兼容；勿将它用于自动放行。

## 文件与契约

- `production_rules.yaml`：六类稳定英文ID、中文名称/兼容别名、来源、页序、字段、素材和通用约束。步骤/测评字段是规划接口建议，不冒充完整客户验收规则。
- `template_catalog.yaml`：13家族、全部56项资产及角色、哈希、容量和模板专属约束。规则图、正反例、操作截图和页面参考分别标记，所有家族的工程、坐标和审批状态均未知。
- `qc_rules.yaml`：QC规则目录和已知医疗表述词表。三个配置使用 **YAML 1.2 的 JSON 子集**，可由标准库json或YAML解析器读取，避免为静态配置新增依赖；请维持此格式。
- `production/classifier.py`：透明词面基线；未知/多意图不强行分六类之一，显式分类可覆盖建议但不取消语义审查。
- `production/intent.py`：保存原query、显式人群/场景限制、搜索动机假设、至少三个问题及待核实项。直接答案空值，不能把模板问题当成已经回答。
- `production/planner.py`：介绍默认五页，推荐盘点按固定容量分组且顺序不变，对比恰好两对象。每页关联必答点；缺少两类正式规则则返回无页序的阻塞草案。不自动重建缺页或改字体/图片槽位。
- `production/qc.py`：独立于旧校验器的结构化预检，检查页数、标题、必答覆盖、顺序、重复、食谱、对比、版式声明、健康/营养证据和审查记录。交付manifest的 `content` 对象必须包含对应类目 `required_fields` 声明的非空字段，语义由人工审核。调用方通过 `claims` 显式声明主张（无则空数组），营养主张需source/verified/basis/food_state/edible_portion_or_product_spec。人工审查记录需要approved/reviewer/evidence。

现有模板全部不可直接渲染，因此当前任何已有模板的交付草稿都会被模板关卡阻断。`plan.status=blocked` 是成功生成了缺口明确的计划，不是生产成功；不能自动把它提交渲染队列。

语义相关性、正文实际覆盖、事实真实性、素材权利、真实体验和最终像素合规不能由manifest自报证明。新增QC的PASS也仅指结构化预检通过。健康关键词有否定句误报和词表漏检风险，需人工复核。近似字数、每行行数及占图四分之一等仅记录为参考约束，未获得坐标/字体前不假装有像素检查能力。

## 后续开发顺序

1. 按 `references/phase1-confirmations.md` 补齐可编辑工程、模板验收、两类培训与事实/素材证据标准；先验证6项推荐盘点和五页介绍的完整固定模板。
2. 接入版本化坐标/字体/文本槽位渲染器，测试长中文、溢出和遮挡，建立真实失败样本与人工签审流程。
3. 接入真实词条标注集和授权素材/事实来源，验证分类准确度、语义覆盖及小批量交付。
4. 质量稳定后再做批任务、幂等重试、审查队列和产能压测；500组/日仍需基于端到端实测。
