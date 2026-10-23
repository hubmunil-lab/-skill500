# 第五阶段审阅

真实业务交付0/8；两组合成软件测试渲染2/2，不能当作真实商品或客户验收通过。

- [完整报告](../../phase5_intent_report.md)
- [10条任务的意图、分类、模板与结果](run-004/report.json)
- [一键下载本次PNG、文案、来源和QC](phase5-intent-review-bundle.zip)
- [默认Batch运行结果](batch-final/batch_report.json)
- [完整回归记录](regression_tests.txt)

| 合成测试 | 预览 | PNG与逐页QC |
|---|---|---|
| 示例甲/乙：含糖量 | [查看](run-004/p5-sugar/render/preview.png) | [目录](run-004/p5-sugar/render/) |
| 示例丙/丁：维生素C | [查看](run-004/p5-vitamin/render/preview.png) | [目录](run-004/p5-vitamin/render/) |

每任务有intent/template_match/required_materials/missing_materials/planning_brief；生成任务另有copy、post、source_packet和inputs。没有匹配模板不生成PNG，不要求补交无关营养事实。

源码与接口：[planning/README](../../planning/README.md)。本分支补齐此前未推送的运行依赖；main不变，不创建PR，不自动批准模板。
