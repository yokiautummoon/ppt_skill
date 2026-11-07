# 示例：typst 复杂精美排版链路（type: typst）

`typst.yaml` 演示把 **typst 排版系统**作为一类积木接入确定性管线：一整页精美
个人简历（双栏侧栏 + 时间线 + 点阵评级 + 标签胶囊 + 页内配色）完全由 typst 排版，
编译产物以图块方式落版——聚焦「复杂排版」场景，示范 typst 相对 Office 原生
形状的排版能力上限（任意网格/渐变/圆角/矢量绘制）。

## 简历设计（设计语言移植自 typst 官网 CV 模板）

排版参考 typst 官网 universe 优质 CV 模板 **impressive-impression**
（Forty Seconds 双栏侧栏风格，packages.typst.org/preview/impressive-impression）：

- **左侧深色侧栏**（ink 深海军蓝）：人像（金渐变圆 + 姓氏单字）+ 姓名/职位 +
  联系行（单字角标块）+ 技能/语言**点阵评级**（金点满/灰点空）+ 获奖**标签胶囊**；
- **右侧主栏**：个人简介（两端对齐）+ 工作经历**时间线**（左时间 + 右标题/机构/
  要点，accent 左侧轨）+ 项目经历 + 教育背景；行尾 `1fr` 吸收尾白。
- **主题色板**：ink 深海军蓝 / accent 项目蓝 / gold 金（侧栏点缀）/ faint 弱文字。

源码 `assets/resume.typ` **自包含**（显式 `#set page(width: 7.8in, height: 10.3in,
margin: 0pt)`、零 `@preview` 依赖），`.typ` 体内同值页面设置供独立编译，SPEC
`preamble` 同值再注入 → `_explicit_page` 认账，引擎不自动围切（视图与目标框 1:1）。

**数据红线示范**：`meta.brief` 即本页唯一数据源（虚构演示人物林知夏，高级产品
设计师/设计系统方向，十年经验；「晓舟 UI」1200+ 组件 8 套主题提效 47%；三段
工作经历 × 数字：12 移动端项目/复用率 60%/+32%/40+ 组件/8 人组/3 业务线/900+
人日；教育同济 2012–2016），正文全部数字/机构/年份溯源 brief；后续 `--fix`
修订须仍能溯源（禁止编造）。

## 双通道语义

| 通道 | 结构 | 显示 | 依赖 |
|---|---|---|---|
| SVG（矢量） | `a:blip/@r:embed`→png，`a:extLst` 内 `asvg:svgBlip/@r:embed`→svg | PPT 2016+ 渲染矢量 | 无（typst 字形即轮廓 path，不引字体） |
| PNG（fallback） | 常规图片 | 旧版 PPT / svg 注入失败 | 无 |

svg 注入失败降级纯 PNG（组件银行记 `typst_png_fallback`，WARN 不阻断）。

## 运行

```bash
# 无 Office 确定性链（typst 编译在编译期完成，渲染零外部依赖）
win_py scripts/build_ppt.py examples/typst/typst.yaml --out examples/typst/out
# 打开 out/base.pptx 目视复核（矢量放大不糊；2016+ PPT 可右键"转换为形状"再编辑）
```

## 铁律与边界

- **整块为图（内容型积木）**：产物是 SVG/PNG 图，不可逐字编辑；要逐字改就回原生
  shape/text 积木。排版文字属内容 → 受数据红线约束（须溯源 brief 或标 `[占位]`）。
- **页面尺寸 = 元素 rect**（1in = 72pt）：typst 产物 viewBox 与目标框 1:1，渲染零
  重算（铁律 1 的排版块对应物）。用户 preamble 自带 `#set page(...)` 自控尺寸时，
  与 rect 不符 → stage1.5 WARN（渲染仍按 rect 落版，可能变形）。本例 preamble 与
  rect 精确一致（561.6×741.6pt），无此 WARN。
- **顶层元素**：排版块整块为图，不进容器 children（与 chart 同律）。
- **编译闸门**：typst 语法错误 = exit 2（错误含文件/行号/源码片段）；`typst.exe`
  缺失 = exit 2 提示（排版块是显式请求，不做静默降级）。

## 能力边界（typst 侧）

- 依赖 typst 0.15.x 语法；`@preview` 包（如 ceTZ `#import "@preview/cetz:0.3.1": *`）
  首次编译需联网拉取并缓存（离线环境请预缓存或避免 `@preview`）。本示例零依赖。
- 字体：默认 `Microsoft YaHei / SimSun / Times New Roman` 回退链；中文字形在 SVG 中
  转为轮廓 path，目标机无需装字体。

## 校验背书

- 单测：`win_py -X utf8 tests/test_typst_compile.py`（11 项：装配/双产物/错误/契约/
  注入/降级/最小边界盒围切 3 项；`_explicit_page` 认账 preamble 即不围切）。
- 物证：1 块 ×（存在 + PNG fallback + SVG 矢量）= 3 条 + 基础 4 条 = 7/7。
- 回归：`tests/regression.py` 收录本示例（物证 7 条）；突变 `tests/run_mutations.py`
  typst 契约段（编译期拦截 + IR 产物缺失守护）。
- 权威验证 = PowerPoint 打开 round-trip（矢量显示、另存后 svgBlip 保留）。