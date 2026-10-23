# 客户参考图固定模板重建

本模块复用现有 `rendering.engine` 的字体处理、真实DOM测量、固定坐标及PNG导出能力，另加四套参考模板的页面/条目/步骤一致性检查。仅用于模板重建测试，不接入正式交付或500组生产。

## 运行

```bash
cd /workspace/-skill500
/workspace/.venvs/skill500/bin/python -m pip install -r customer_templates/requirements.txt
export PYTHONDONTWRITEBYTECODE=1
/workspace/.venvs/skill500/bin/python -m customer_templates \
  --output artifacts/customer-new-run
# 单套及自定义测试文字（保持输入schema与slot ID）：
/workspace/.venvs/skill500/bin/python -m customer_templates --category intro \
  --manifest examples/customer_templates/intro.json --output artifacts/customer-intro-run
/workspace/.venvs/skill500/bin/python -m unittest discover -s tests -v
/workspace/.venvs/skill500/bin/python scripts/validate_library.py
```

需要当前系统 Chromium、Noto Sans/Serif CJK Regular/Bold，字体文件SHA-256已锁定。新增OpenCV仅用于去除参考位图嵌字后的局部像素修补，不做事实判断或图像生成。

每次使用全新的输出路径。已存在且不同的派生组件会拒绝覆盖；相同组件复用。源参考图从不改写。

## 输入和模板约定

- `registry.json` 锁定15页配置与四个字体文件；`configs/*.json` 包含原生尺寸、源图SHA-256、页序、对象/步骤ID、固定文字框、照片框、字体层级、配色、描边、对齐和已观察到的叠字例外。
- 坐标均在对应原图像素空间声明，整页以同一倍率等比放入1242×1656画布并居中。不同原图略偏离3:4，留下窄边而不拉伸图像或任意移动元素。
- `components-v5/`、`component_registry_v5.json` 分别保存固定背景/装饰与独立照片块；字段文字由HTML独立绘制。背景不是直接盖整张成品图的伪可编辑接口：变量文字已清除，照片也按独立槽位重新渲染。
- 背景包括本来就不可随意更改的纸纹、框线、手绘数字、图标、装饰和固定栏目标签。图内文字清理采用局部修补，不能恢复真正被文字遮住的像素。
- `examples/customer_templates/*.json` 的根字段必须为schema_version、category、mode、item_order、pages；mode只能是reconstruction_test。
- 每页仅接受template_id、item_ids、values；values须完整包含配置的全部槽位。文字非空，照片必须映射到已登记、同身份、hash相符的素材，禁止CSS/坐标覆盖。
- 文字过长报错，不裁切、不省略、不缩小字号、不挪动框。更换测试文字后重新运行检查。
- Compare保持左右对象及名称；recommend保持01—06编号及无重复顺序；list保持封面横向顺序与详情一致；intro保持前三特点名称一致、三道不同食谱与步骤caption序号一致。

## 页面结构

| 集合 | 页数 | 页序 |
| --- | --- | --- |
| compare | 3 | 双品封面→营养字段→食用场景/选购 |
| recommend | 3 | 条目01/02→03/04→05/06，三页都是两项详情 |
| list | 4 | 六项封面→花甲/山楂→薏米/荔枝→螃蟹/木瓜 |
| intro | 5 | 青椒封面→三特点详情→馅饼→虎皮青椒→炒肉丝 |

UUID不是页码；映射来自逐张观察。三道食谱的展示顺序为本轮测试约定，不宣称客户另行指定了固定先后。推荐类没有独立总览封面，不能擅自补页，也不能自动宣布符合旧生产规则。

## 真正执行的检查和产物

检查字体文件、字形覆盖、实际字体加载、数据schema、页面数量/顺序、对象身份、可见编号、跨页名称、内容完整性及背景/配置/素材hash。浏览器阶段检查scroll/client和逐行Range的文字溢出、文字遮挡、图文框相交、元素越界、字体字号/颜色/坐标改变、固定背景位置及PNG尺寸。

源食谱把标题和步骤字叠在图片上，因此只有配置中明确登记的“该标题/该图”“该caption/该图”例外允许重叠；不是关闭全局遮挡检查。文字之间仍检查真实字形区域交叠。装饰底板不当成食物图片参与遮挡判断。

每套输出连续编号PNG、自包含HTML、`qc_report.json`、`preview.png`、`reference-comparison.png`，以及每页`NN-comparison.png`和4倍增强的`NN-difference.png`。

像素差记录整体MAE、固定区域MAE和固定区域占比。测试文案本就不同，整体像素差不能当相似度验收分数；固定区域不足5%时标记该项不可靠。字体替代、修补和位图重采样仍须人看对照图，不能用技术PASS代替客户视觉批准。

成功状态为PASS_RECONSTRUCTION_TEST_ONLY，customer_approved/delivery_ready始终为false；失败状态FAIL，错误包括页码、元素、代码与原因。预检错误页码可能为空。失败页不输出PNG，整套失败不输出成功预览。

## 尚未解决

原字体和源图层未提供；目前使用固定的Noto字体、相应粗细和基线覆盖参数，不声称与原字体相同。纸纹/笔刷与食谱嵌字位置的修补会产生局部模糊、色块或极小字形残留风险。参考图片尺寸约720×970，没有原始高清照片/分层工程。健康数据、食用份量、孕期禁忌、价格、口感和素材授权均未审核，测试字段不作为正式事实输出。详见根目录差异报告。
