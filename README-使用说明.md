# food-template-posters v3 | 使用说明

本包以您上传的原版 Skill 增量更新，保留原有模板和案例素材。已经把两轮客户反馈变成验收规则，新增 `references/acceptance-v3.md`；在 `SKILL.md` 追加 v3 强制流程，新增 `scripts/validate_delivery.py` 和两项自动测试。

## 在 Codex 中使用

将整个 `food-template-posters` 文件夹放入 Codex 可读取的项目或技能目录。开启会话并说：

> 请先读取 `food-template-posters/SKILL.md` 和 `references/acceptance-v3.md`，严格按照这里的规则开展工作。先审计当前成图模块和模板实际可编辑性，再选择一条真实 query，输出搜索意图分析、直接回答、页面计划、待核实事实和素材需求。未经审核和授权，不要虚构食谱素材、模板已经过审或自动生产已完成。每组至少3页，介绍类按5页，使用独立中文文字层，并逐页检查。

## 校验命令

在 Skill 文件夹运行：

```
python scripts/validate_library.py
python -m unittest discover -s tests -v
python scripts/validate_delivery.py /你的任务目录/delivery-manifest.json
```

最后一条对实际交付运行，必须在图片旁准备 manifest（字段示例在 `examples/delivery-manifest.example.json`）。依赖 Pillow。若未审核，程序会返回 `REVIEW`；它不会把未完成的审核当成通过。

## 未完成/不得夸大

本次更新为**可读取的业务 Skill + 机器校验工具**。原项目仅含模板图、培训规则和静态校验脚本，本更新并未凭空变出可靠的模板像素坐标或完整海报排版/渲染器，也未自动取得网络实拍食谱图片授权。达到“每天500组自动制作”的目标还需要建立可编辑模板坐标、实际生成引擎、素材管线、页面图文视觉检查、事实审核和客户模板验收。
