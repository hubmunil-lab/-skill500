# 客户参考模板重建：差异及未解决问题

本轮已同步远端main至 `3a6e45345aed82b9c60e25b90e53c40f03973bb1`，保留此前本地开发文件。全部15张原图逐张查看；原图未改写。

**结论：四套可编辑固定模板的技术重建与实际PNG测试已完成；尚未达到字体/像素完全一致或正式交付批准。** 输出不是将原海报作为整张不可编辑背景直接截图：文字、食材图片、食谱照片块和固定装饰分别处理。

## 数量与页面对应关系

| 分类 | 要求/实际 | 页面结构 | 对应旧目录 |
| --- | --- | --- | --- |
| compare | 3/3 | 双品封面→营养字段→场景及选购 | compare-1的同类双列样式；新饮品三页集独立注册 |
| recommend | 3/3 | 三页各两项详情，01—06 | 旧目录没有这一场景照片推荐样式，独立新建 |
| list | 4/4 | 六项封面→三页各两项详情 | 与list-1/2相关但字段/边框有差异，不冒充同版 |
| intro | 5/5 | 青椒封面→三特点详情→三张不同步骤食谱 | intro-3纸纹/紫色笔刷系列的完整五页新参考 |

数量完整不等于生产结构已经客户确认：recommend没有独立总览封面，不能擅自把三张详情改成封面或加第四张。intro现在已有五页参考及操作画面；此前“青椒五页参考缺失”已由这次提交解决，但独立原始照片、文字图层及许可仍缺。

## 全部15页映射与坐标依据

完整坐标、字号、颜色、照片框及锁定区域见 `customer_templates/configs/*.json`；图片哈希及映射见 `customer_templates/reference_audit.json`。UUID不是页码，以下顺序依据页面内容建立。

| 类别/页 | 源图 | 原尺寸 | 页面角色 | 配置ID |
| --- | --- | --- | --- | --- |
| compare/1 | [1167c9fe-9822-419f-8d82-f6d1ad23b2cc.png](assets/customer_reference/compare/1167c9fe-9822-419f-8d82-f6d1ad23b2cc.png) | 720×967 | cover | customer-compare-01-v1 |
| compare/2 | [ea68826f-81e5-4816-90cb-ecf7193fcd00.png](assets/customer_reference/compare/ea68826f-81e5-4816-90cb-ecf7193fcd00.png) | 726×976 | nutrition | customer-compare-02-v1 |
| compare/3 | [0d9ac319-df9b-4bd6-a2ca-3d6bf10a18ee.png](assets/customer_reference/compare/0d9ac319-df9b-4bd6-a2ca-3d6bf10a18ee.png) | 723×973 | selection | customer-compare-03-v1 |
| recommend/1 | [6c44d1cc-a954-4774-9433-798b36144bcb.png](assets/customer_reference/recommend/6c44d1cc-a954-4774-9433-798b36144bcb.png) | 730×973 | detail | customer-recommend-01-v1 |
| recommend/2 | [da26d06f-4a2b-4326-a3f9-b1e46855f954.png](assets/customer_reference/recommend/da26d06f-4a2b-4326-a3f9-b1e46855f954.png) | 730×973 | detail | customer-recommend-02-v1 |
| recommend/3 | [fd0fe681-4f9c-4451-9bb8-f361445d4b99.png](assets/customer_reference/recommend/fd0fe681-4f9c-4451-9bb8-f361445d4b99.png) | 727×976 | detail | customer-recommend-03-v1 |
| list/1 | [bd73bcf0-f931-429f-9bf8-6c7810fffe19.png](assets/customer_reference/list/bd73bcf0-f931-429f-9bf8-6c7810fffe19.png) | 730×976 | cover | customer-list-01-v1 |
| list/2 | [2e0b94bb-f421-4239-ad1b-f6e5fc88d360.png](assets/customer_reference/list/2e0b94bb-f421-4239-ad1b-f6e5fc88d360.png) | 727×976 | detail | customer-list-02-v1 |
| list/3 | [bab805d8-ff7a-417e-97aa-84f784283b42.png](assets/customer_reference/list/bab805d8-ff7a-417e-97aa-84f784283b42.png) | 721×957 | detail | customer-list-03-v1 |
| list/4 | [0f9f4bf7-ed77-4249-89b7-65fe797ccb18.png](assets/customer_reference/list/0f9f4bf7-ed77-4249-89b7-65fe797ccb18.png) | 732×969 | detail | customer-list-04-v1 |
| intro/1 | [a0c2303f-2b0e-4890-b2ae-ac6a1bd5ca0e.png](assets/customer_reference/intro/a0c2303f-2b0e-4890-b2ae-ac6a1bd5ca0e.png) | 729×972 | cover | customer-intro-01-v1 |
| intro/2 | [410daa43-47e6-41ee-bf7b-fbc360c1ce3d.png](assets/customer_reference/intro/410daa43-47e6-41ee-bf7b-fbc360c1ce3d.png) | 724×966 | detail | customer-intro-02-v1 |
| intro/3 | [6a1521cf-936d-40c6-8099-b4b7260acd06.png](assets/customer_reference/intro/6a1521cf-936d-40c6-8099-b4b7260acd06.png) | 727×973 | recipe | customer-intro-03-v1 |
| intro/4 | [c7367b78-0e75-479a-9181-2f71bff2d9ad.png](assets/customer_reference/intro/c7367b78-0e75-479a-9181-2f71bff2d9ad.png) | 727×976 | recipe | customer-intro-04-v1 |
| intro/5 | [e392d62e-3fdb-44a3-839e-c05f985c832a.png](assets/customer_reference/intro/e392d62e-3fdb-44a3-839e-c05f985c832a.png) | 730×978 | recipe | customer-intro-05-v1 |

## 保留与拆分策略

- 固定：原生页结构、双列/两条目/六宫格、图片占位、背景色系、相对字体层级、边框、横线、图标、纸纹与紫色笔刷位置。原位图尺寸略偏离3:4，等比居中映射1242×1656，保留窄边，不用横纵不同倍率拉伸。
- 可编辑：标题、名称、编号、说明、营养字段、备注/摘要、食谱标题与步骤caption。每个字段是独立HTML文字层，照片是独立图片元素。默认使用明确的排版测试文字，未复用健康数据。
- 组件修补：变量区域须先清掉原文字；平色块按源图区域清理，纸纹/笔刷及食谱嵌字局部用图像修补估计隐藏像素。这个估计不能恢复真正的源图层。照片主体位置不因输入文字长短移动。
- 字体：仓库没有原字库和字体名称。用锁定的Noto Sans/Serif CJK Regular/Bold保持无衬线/衬线与粗细层级，固定字号/基线/行高。它们是度量近似，不宣称原字体完全一致；无法仅靠位图确认准确字号、字重和字距。
- 食谱：保留原拼图网格和已观察到的文字叠图关系；只有逐对登记的标题/图片、caption/图片重叠允许，未关闭通用遮挡检查。步骤测试编号是画面定位与排版编号，不是已核实的食谱操作说明。

## 分套差异与未解决项

| 模板 | 已实现 | 尚有差异/必须确认 |
| --- | --- | --- |
| compare | 三页双列、对象跨页同图同侧、胶囊名称、橙色分类标签、营养字段和场景框 | 原标题字体未知；胶囊与标签局部重建边缘可能不同； 源图图案清理处有局部细缝/白边；价格、糖量、商品规格、功效和场景文案均未核实 |
| recommend | 三页两项、固定大号6与顶端装饰、场景照片、衬线标题、01—06编号和三条字段 | 无独立封面；原字库未知；栏目内修补边缘/行距近似；带背景照片只作为这套新参考的特定样式，不扩大为所有推荐模板的例外 |
| list | 六项总览、三张两项详情、同序/无重复、绿色边框、橙色原因标签与勾选标记 | 原品名字体/描边未知；局部修补仍可能留下极细照片边缘；孕期禁忌、每次份量和频次不得从图中直接沿用 |
| intro | 完整五页、两张不同青椒图、前三亮点一致、三道独立步骤拼图、可编辑caption | 纸纹/笔刷内部及原食谱标题/步骤字底下会有修补模糊或色块；需要无字原照片/分层文件消除这些误差；真实步骤文字、菜名及用量仍须审核 |

所有15张源图约720×970像素。输出1242×1656 PNG不等于获得了原生高清照片。素材真实性和授权也不能由参考位图或文件名证明。

## 程序质检与真实输出

已执行：槽位缺失、图片身份/哈希、配置和固定背景锁、画布尺寸、文字溢出、图片越界、图文遮挡、可见字形交叠、字号/颜色/坐标改变、字体缺失、页序、条目顺序/重复、名称一致性、推荐可见编号、介绍三特点与三食谱完整性。超长文本直接报错，不缩字、不挪框。

文字框与中间分类标签的边界可能按原布局相交，因此文字之间检查实际字形位置；食物图片仍用保守框检查。静态位图内的极小字形残留、错别字、食物真伪和语义正确性不能由DOM自动证明，仍需逐图人工复核。

所有套组均真实调用Chromium渲染。每套包含逐页PNG/HTML、qc_report.json、preview.png、reference-comparison.png，以及每页对照和像素差异图。

| 模板 | 预览 | 对照 | QC |
| --- | --- | --- | --- |
| compare | [总图](artifacts/customer-template-reconstruction/compare/preview.png) | [逐页对照](artifacts/customer-template-reconstruction/compare/reference-comparison.png) | [JSON](artifacts/customer-template-reconstruction/compare/qc_report.json) |
| recommend | [总图](artifacts/customer-template-reconstruction/recommend/preview.png) | [逐页对照](artifacts/customer-template-reconstruction/recommend/reference-comparison.png) | [JSON](artifacts/customer-template-reconstruction/recommend/qc_report.json) |
| list | [总图](artifacts/customer-template-reconstruction/list/preview.png) | [逐页对照](artifacts/customer-template-reconstruction/list/reference-comparison.png) | [JSON](artifacts/customer-template-reconstruction/list/qc_report.json) |
| intro | [总图](artifacts/customer-template-reconstruction/intro/preview.png) | [逐页对照](artifacts/customer-template-reconstruction/intro/reference-comparison.png) | [JSON](artifacts/customer-template-reconstruction/intro/qc_report.json) |

## 像素差诊断

以下RGB平均绝对误差范围0—255，非客户验收评分。测试文案不同且变量区域经过拆分，整体差异不应接近零；固定区域指标还受重采样影响。固定区域不足5%时标记不可靠，尤其满版食谱几乎都是可替换图片区，不能用窄缝/边缘的均值推断整页一致。

| 分类/页 | 整体MAE | 固定区域MAE | 固定区域占比 | 该固定指标可解释性 |
| --- | --- | --- | --- | --- |
| compare/1 | 19.52 | 2.10 | 37.6% | 诊断用，仍须人审 |
| compare/2 | 16.51 | 1.47 | 51.8% | 诊断用，仍须人审 |
| compare/3 | 22.66 | 1.88 | 46.4% | 诊断用，仍须人审 |
| recommend/1 | 10.30 | 1.15 | 51.7% | 诊断用，仍须人审 |
| recommend/2 | 10.10 | 1.56 | 51.7% | 诊断用，仍须人审 |
| recommend/3 | 9.42 | 0.63 | 51.9% | 诊断用，仍须人审 |
| list/1 | 7.56 | 1.05 | 35.5% | 诊断用，仍须人审 |
| list/2 | 26.79 | 1.99 | 36.3% | 诊断用，仍须人审 |
| list/3 | 26.14 | 2.54 | 35.2% | 诊断用，仍须人审 |
| list/4 | 25.46 | 2.33 | 36.3% | 诊断用，仍须人审 |
| intro/1 | 12.56 | 0.97 | 57.7% | 诊断用，仍须人审 |
| intro/2 | 12.98 | 0.85 | 62.8% | 诊断用，仍须人审 |
| intro/3 | 7.79 | 0.16 | 0.6% | 区域太少，不作一致性结论 |
| intro/4 | 8.50 | 0.12 | 0.9% | 区域太少，不作一致性结论 |
| intro/5 | 6.85 | 0.07 | 0.8% | 区域太少，不作一致性结论 |

## 当前可交付边界与下一步

本轮成果可用于审阅固定模板重建和测试，不是客户已批准的正式内容。四套均保持customer_approved=false、delivery_ready=false，production模式被拒绝。没有开发或启动500组批量生产。

需补充/确认：原字体文件及许可、可编辑源工程/坐标；无字原始高清食材/步骤照片及使用权；推荐类是否需要另补总览封面；三道食谱的正式展示顺序和逐步说明；健康、孕期、份量、商品营养/价格等事实证据；客户对逐页视觉差异的实物签审。

已有图片现在足以测试五页结构，不能继续称“缺三张步骤参考图”；仍然缺的是可无损替换的原始分层素材和事实/授权记录。

## 文件与运行

新增customer_templates模块（15页配置、字体/组件锁、派生图形和模板级QC）、四份测试manifest、参考审计和模板测试。更新template_catalog.yaml添加四套独立重建版本；references/library.json仅追加15项，原56项不变；相应测试计数/可编辑状态检查更新。运行命令和输入约束见 [customer_templates/README.md](customer_templates/README.md)。

## 最终验证

- 全量66项测试通过，包含全部15页的真实Chromium渲染及超长文字失败测试；详见 `artifacts/customer-template-reconstruction/test_report.json` 与 `tests.txt`。
- 15张正式测试PNG均为1242×1656，四套QC均为PASS_RECONSTRUCTION_TEST_ONLY，布局错误数0；不代表像素一致或客户已审核。
- 71项素材与培训源文件哈希通过。原56项索引内容不变，新追加15项；原客户图片未修改。
- 每页额外输出 `NN-regions.png`：蓝框为文字、红框为图片；其余为冻结装饰区域。图中的区域框用于核对坐标，不属于成品设计。
