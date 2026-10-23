# 第二阶段：真实固定版式渲染测试

本模块已经通过本机 Chromium 调用真实生成PNG。当前仅支持**工程测试模式**，不是青椒五页成品、正式介绍类交付或已获客户审核的模板。

## 素材核查与备用模板

已核对 `references/library.json` 的全部56项素材及总览图，并逐张查看 `intro-4` 三张原图。仓库没有完整青椒五页参考、两张授权青椒食材照或三套真实步骤图。缺失项逐项列在 [素材审计](../references/phase2-asset-audit.json) 中；建议接收文件名只是新命名约定，不是声称存在的原始文件名。

按本阶段用户指定的备用方案，选取现有 `intro-4` 三页参考（封面、详情、禁忌）作为最小三页渲染测试。它在现有参考集合内完整，但不满足介绍生产所需的五页结构。原图疑似混用黄豆与鹰嘴豆，未将其照片作为已核实素材复用。测试只放自制透明图形，不冒充真实食材或实际操作照片。

## 安装与生成命令

本次实测工具：Python 3.12.14，Pillow 12.3.0，Playwright 1.62.0，fonttools 4.61.1，系统 Chromium 154.0.8037.57，Noto Sans CJK SC。使用系统浏览器，不需要另下载 Playwright 浏览器。本地需要 Chromium 与 Noto CJK 字体；字体许可证见 `FONT_LICENSE.txt`。

```bash
cd /workspace/-skill500
/workspace/.venvs/skill500/bin/python -m pip install -r rendering/requirements.txt
export PYTHONDONTWRITEBYTECODE=1
# 每次使用一个新的输出目录；存在的目录绝不覆盖。
/workspace/.venvs/skill500/bin/python -m rendering demo --output artifacts/my-render-run
# 自己准备的数据（本阶段仍仅允许test模式）：
/workspace/.venvs/skill500/bin/python -m rendering render \
  --manifest examples/rendering/intro4-test.json --output artifacts/my-other-run
# 全部既有与新增测试，包含真实浏览器测试：
/workspace/.venvs/skill500/bin/python -m unittest discover -s tests -v
/workspace/.venvs/skill500/bin/python scripts/validate_library.py
```

`demo` 额外创建可重复的透明测试图形，已存在且内容相同则复用，不同则拒绝覆盖。`render` 不生成或替换输入素材。生成成功退出0、布局或素材失败退出1、非法命令或现有输出目录退出2。

输出：`01.png`—`03.png`、每页可复查的自包含HTML、`qc_report.json`、`preview.png`（全部页面总图）、`reference-comparison.png`（原图与新图并排）。HTML内嵌字体和图片，不向网络请求素材。对比图左侧原始文字和数字仍未验证，只能用于版式参考。

## 固定版式与内容替换

`templates/*.json` 分别声明三张页面的像素坐标、框尺寸、字号、行高、颜色和图片适配方式。标题、摘要、特点、说明和表格是独立DOM元素，图片不包含正文。表格行列数量固定；文本自然换行，**不缩字、不移动元素、不截断溢出内容**。图像使用 `object-fit: contain`，保持比例、不裁断。

`template_registry.json` 保存模板及字体文件SHA-256。内容只可提供 `template_id` 和 `values`，不得注入CSS/坐标；DOM测量再次与注册模板比对。修改模板文件但不更新注册哈希会被阻断。新的可配置版式须另起版本及注册，并人工验收；修改注册表本身是受代码审阅的开发动作，哈希锁不是防御能编辑整个仓库的攻击者。

输入契约见 `examples/rendering/intro4-test.json`：

- `subject` 为词条食材标识；图片元数据subject必须相同。食材识别仍需人工检查，程序不会从文件名或模型输出假定图像正确。
- 图片路径仅允许仓库内已有文件，不支持远程URL或路径越界。真实食材照需 `kind=real_ingredient_photo`、`rights=owned/licensed`、`rights_evidence`、`reviewed=true`。这些是记录字段，不会自动证明版权。
- 已抠图的RGBA图片保持透明通道；`cutout=true` 却无透明像素会失败。不包含自动抠图算法，需上游先准备抠图素材。
- 封面与详情照片比较文件SHA-256，换ID但复用同一文件也会失败。EXIF方向统一后保持原比例。
- 图像读取器支持区分真实操作素材 `real_step_photo` 和成品图；操作素材需操作说明。当前没有已注册的食谱页面布局，也不具备真实步骤图，**没有生成食谱页**。
- 允许的测试占位素材为 `test_placeholder`；图片和页眉明确标注测试，不当作真实照片或事实。

第一阶段 `production` 仍是内容准备与交付预检入口，规则/模板审批状态保持原状；第二阶段 `rendering` 是独立原型，不绕过第一阶段的生产阻断。尚未将其接入自动生产队列。

## 真正执行的检测

渲染前：模板哈希和字段形状、图片主体标识和权限记录、透明通道、不同照片字节、固定字体文件和全部文字的cmap覆盖。抽取SC字形子集内嵌HTML，避免系统字体回退；字体源哈希不匹配或缺字即失败。粗体采用锁定字号下的浏览器合成，不声称等于参考图字体。

渲染后：等待字体与图片完成加载，读取真实DOM矩形、逐行Range矩形、scroll/client尺寸、计算后的字体和颜色；检测文字/表格溢出、图文框重叠、其他内容框重叠、元素越界、画布尺寸、字体加载及固定区域改变。装饰背景可合法承载文字；图片占位框不允许和文字框相交，采用保守矩形检查，透明空白也不作为遮字许可。最后检查实际PNG像素尺寸。

错误均写入 `qc_report.json`，包含 `page`、`element`、`code`、`message`；字体错误定位到各文字元素，进程级错误页码为空。失败页面不输出PNG；整套失败不输出成功预览。已成功的其他页可能保留，必须以整套报告状态判断，不能把局部PNG当作成功交付。

`PASS_TEST_ONLY` 仅表示工程布局测试通过，报告始终保持 `customer_approved=false`、`delivery_ready=false`。不证明语义、医学事实、授权或美观已通过。

## 与原图差异及后续

原图的纸纹、装饰、字体、图层坐标并未取得。现阶段是明确分区、避免遮挡的重建原型：纯色背景、新的固定坐标、不同表格边框、图片/文字分区、不含原装饰及不确定健康文字。所有差异见素材审计文件，并有实际并排对比图；需客户逐页人工验收，不能认定像素一致。

已有条件：可扩展独立固定版式、内容槽位、图像适配、字体检查和真实浏览器回归测试。扩展下一模板前需取得其完整参考/工程、授权真实素材、固定参数和验收；青椒五页必须先补齐三套真实操作照片与可靠营养资料。尚未实现可交付的食谱排版、自动抠图、自动语义识别、批量生产或发布。
