---
name: ppt-builder
description: >
  生成原生可编辑 PowerPoint 幻灯片（流程图/递进阶梯/架构图/看板/通用版式）。
  触发分支：用户要"做一张/一组 PPT 图"、"画个流程图"、"搭个架构图"、
  "做个递进/阶梯示意"、或任何"把关系/结构变成幻灯片图面"的需求。
  agent 无视觉能力也能保证质量：确定性 SPEC → 编译校验 → 布局 → 渲染 →
  XML 物证断言 →（可选 COM 后处理）全链机器可证。
---

# PPT Builder — 确定性生成式幻灯片

## 定位与铁律

- **无视觉如何保证质量**：质量不靠"看"，靠确定性管道 + 断言链。
  SPEC YAML（声明式积木语言）→ spec_compile/validator（静态白名单）
  → ir_builder（布局求解）→ verify（G/T/D/S 四家族断言）→ render_pptx（纯消费 IR）
  → render_check_xml（解包 XML 物证）→ com_layer（可选 COM 后处理）。
- **铁律 1（铁证链）**：几何/锚点/z 只在布局层（ir_builder）定；
  渲染器与 COM **绝不重算或微调**任何几何——改布局 = 改 SPEC 重跑，
  verify 与 XML 物证会背书一致性。
- **铁律 2（层级）**：OOXML 层级 = spTree 文档序（越后越前）。
  z 由 ir_builder 唯一分配（声明序/z_override/容器内阶梯），渲染器按 z 稳定重排。
- **铁律 3（遮挡合法源仅两类）**：同容器归属（ownership 派生）或
  `relations.overlap` 显式声明。其余一律拦截。
- **铁律 4（COM 边界）**：COM 只做 renderer 表达不了的事——glue 连线绑定
  （BeginConnect/EndConnect 随动）、Group 组合、原生 Visio OLE 嵌入、PNG 预览、
  动画时间轴实时构造（安逸动画库 35 宏配方）、公式兜底（Word 批量引擎）、
  PDF 分发导出（--pdf → SaveAs 32）。任何 COM 结果都写回 com_out 供验收。
- **铁律 5（交付闭环）**：备注页 / 页面切换 / 元素级超链接 / 页码偏移 /
  PDF 导出的语义与展开公式在**渲染器与 XML 物证同规**——物证逐页核对
  （footer 页码展开、transition XML、hlinkClick rel 目标、notes part 文本），
  杜绝"看起来对了"。
- **铁律 6（默认排版规则）**：① 颜色一致性——文字同层一色，形状文字与
  所在填充对比 <3.0 自动反色（仅白/黑两族，渲染层对比度守卫）；② 居中优先
  ——无确定布局规则时文字/文字框默认居中于所属形状（表格单元格亦居中），
  左/右对齐文本块按实测宽成块居中；③ 自然排列时才用 justify 两端对齐 +
  首行缩进两字（align: justify + text_style.indent_chars: 2）。
- **铁律 7（母版与制图）**：seed 模式务必让母版背景透出——一般不用纯色全页
  卡遮挡母版（特例页用页级 framework.background）；示意图首选 tikz / 组合
  Office 形状（graph/stack 容器），不 Python 制图（布局与文字自适应不佳），
  需要数据图时才用 Python 出图落 image。

## 环境

```bash
# 全部运行时走 win_py（Windows Python，装 python-pptx/pyyaml/win32com）
win_py scripts/build_ppt.py <spec.yaml> [--out DIR] [--com] [--pdf] [--report md|json|none]
                            [--strict-images] [--embed-fonts] [--com-strict]
# 配置栈临时调参（last-wins，值按 YAML 类型化，不改 SPEC）：
win_py scripts/build_ppt.py my.yaml --param framework.header_fs=14 --param table.pad=0.1
# 自优修订（校验失败 → 归因 → 机械/LLM 修订 → 回环；详见 wiki/runbooks/fix-loop.md）：
win_py scripts/build_ppt.py my.yaml --fix              # 机械收敛（零 LLM，确定性快路径）
win_py scripts/build_ppt.py my.yaml --fix --llm        # + 语义通道（content/advisory → exit 6 暂停）
win_py scripts/build_ppt.py my.yaml --revert           # 回滚最近确定性快照
# 交付闭环总演示（备注/切换/超链接/页码/PDF 五件套全场）：
win_py scripts/build_ppt.py examples/animation/chart.yaml --out out_anim --com  # 动画（--com 实时构造时间轴）
win_py scripts/build_ppt.py examples/method/cylinder.yaml --out out_method      # 圆柱/曲线积木（方法图）
win_py scripts/build_ppt.py examples/closure/closure.yaml --out out_closure --pdf
# 测试（可选，需 win_py）：
win_py tests/run_mutations.py        # 突变套件（无 Office）
win_py tests/regression.py           # examples 端到端回归（无 Office）
win_py tests/run_template.py         # meta.template 契约（无 Office）
win_py tests/run_analyzer.py         # 风格卡分析器契约（无 Office，含设计 DNA）
win_py tests/test_deck_rules.py      # 富文本/排版规范/版式多样性契约（无 Office）
win_py tests/test_images.py          # 图片占位/缺图清单/--strict-images 契约（无 Office）
win_py tests/test_font_embed.py      # 字体可移植/嵌入请求契约（无 Office；--embed-fonts 降级）
win_py tests/test_overflow_readback.py  # 文本溢出真实回读契约（桩单测 + --com 端到端）
win_py tests/com_office_check.py     # COM 自检（需 Office：glue/group/ole/pdf）
# 母版版式侧（无 Office）：
win_py scripts/template_analyzer.py <模板.pptx> [--out DIR]   # 风格卡（尺寸/主题色/字族/占位符）
win_py scripts/build_ppt.py examples/template/extract.yaml --out out_extract --com  # 提炼注入
win_py scripts/build_ppt.py examples/template/seed.yaml    --out out_seed    --com  # 版式打底
```

## Steps

1. **判断图面类型**：流程图/依赖图 → `graph` 容器；组织架构/树 → `graph` +
   `orientation: vertical`（见 examples/orgchart）；递进/阶梯/金字塔 →
   `ladder` + stack 梯形积木；架构组成图（已有外部图）→ `diagram` 逃生通道
   （mermaid→vsdx→OLE 嵌入）；通用版式/看板 → `deck`/`dashboard` + **先做 Step 2
   设计编排**（骨架/视觉主体/图标/强调）再按骨架写积木——不要默认退化成纯文本页；
   数据矩阵 → `table`（data 推导行列，原生表格）；数据变化/对比 →
   `chart`（column/bar/line/pie/area，数据驱动、零 COM）；数学公式/方程式 →
   `type: formula`（独立公式块；UnicodeMath 子集直接注入；子集外 `--com` 时
   Word 批量引擎兜底）——若公式要放进**既有文本框/标题/正文**，用任意 `text`
   里的 `{{表达式}}` 富文本标记（与文字同行 = 行内式，独占一行 = 显示式）；
   方法/机理/学科示意图（圆柱、自由曲线、虚线分区框）→ `shape.kind: cylinder`
   （复合圆柱：半透明侧壁 + 顶/底椭圆 + 等高弧）、`type: curve`（freeform 自由曲线）、
   `border_dash`/`line.dash`（虚线描边），examples/method，积木语法见
   references/spec-v2-language.md；
   复杂精美版式/多栏/精细排版/ceTZ 矢量示意图（Office 积木难表达）→
   `type: typst`（typst 全量排版 → SVG 矢量 + PNG 300ppi 双通道图块；页面尺寸
   = 元素 rect，编译期 exit 2 校验；整块为图不可逐字编辑、受数据红线约束，
   见 references/typst-chain.md 与 examples/typst）；
   精密矢量示意图（时间线/流程/雷达/环形循环/分层堆叠/注解示意——需**可缩放、
   可换色、可逐形状编辑**的图）→ `type: svg`（SVG → 原生 DrawingML custGeom
   形状；`src` 外链文件 xor 内联 `svg:`，支持 defs/use/<g transform>/y 翻转；
   遇 image/text/filter/clipPath/渐变 fail-closed exit 2；N 片 = N 个可动画/可挂
   链接形状）；再配 `rect_kind: ratio`（rect 写内容区 0–1 分数，版式随
   `meta.slide`/`margin` 自动重排——自适应布局的关节节点）；见
   references/svg-figures.md 与 examples/svg/{svg,ratio}.yaml；
   多页长序列（演示/课件/宣讲/汇报）→ `meta.slides`（每元素一页，examples/deck）；
   汇报/演示里的**封面/节标题/科研页/内容结构页** → 页型意图 `page_intent`
   （审定菜单：只写意图 token + 内容字段，引擎确定性展开破格版式——已落地 cover
   （examples/pageintent/cover.yaml：破格标题 + 强调条 + 落款）与 section
   （examples/pageintent/section.yaml：超大节序号 + 引导线 + 节名层级），
   科研三件套 problem（纵贯标记块 + 左对齐主问题）/ versus（双栏分色 +
   中缝对称）/ route（阶段链横向等距铺满，examples/research/sci.yaml 三页），
   以及**内容页结构生成五样板** panels（面板网格，examples/layouts/panels.yaml）/
   columns（分栏 + 箭头）/ kpis（指标卡行）/ cards（卡网格 + 顶饰）/
   figure_text（图文并置），语法与断言见 references/page-intents.md）；
   需要交付体验（演讲备注/页间切换/目录跳转/页码/PDF 分发）→ 五件套：
   `slides[i].notes`（演讲者备注）、`meta.transition`（页面切换，页级可覆盖）、
   元素 `link: {url|slide|email}`（超链接）、`params.framework.page_offset` +
   页级 footer 清空（封面不计页码）、`--pdf`（分发格式，需 Office）；
   总演示见 examples/closure；需要动效（时间轴语义）→ 元素级 `animation: {effect: 安逸宏}`
   （安逸动画库 35 宏参数化：进入/持续/强调/退出四族；`--com` 时 COM 实时构造
   时间轴，无 Office WARN 降级——动画缺省可预览、需 Office 播放复核；语法见
   references/animation.md，示例 examples/animation）；
   整页动画要确定性时间轴（顺序进/齐进/分组，不需要手排 TriggerDelay）→
   页级 `anim` 编排组（`mode: succession|aligned|group` + items，引擎展开绝对秒
   时间轴 → COM 链式锚定 + 回读比对；成员须是带 animation 的元素，容器/cylinder
   拒收；单页写顶层 `anim`、多页写 `slides[i].anim`；示例
   examples/animation/anim_group.yaml，语法见 references/animation.md「动画组」节）；
   页间平滑过渡（跨页同名对象补间变形）→ `transition: {effect: morph, dur?}`
   （dur 仅 morph 可声明，100~5000ms；`mc:AlternateContent` p159 兼容包）；
   书法/艺术字、需换机不丢字形或图片填充文字 → `type: brush`（字体字形 → 原生
   `a:custGeom` 矢量形状，三态填充 实色/渐变/图片；`font: kai|hei|song|fang|yahei`
   或 .ttf/.ttc 路径；字形按 ink 适配声明盒居中）；两者见 references/ink-brush.md
   与 examples/ink；
   需要矢量图标（流程图/看板/特性卡的图示符号，随主题着色、缩放不糊）→
   `type: icon`（Lucide 图标 → 原生 `a:custGeom` 描边形状；`icon` 名/中文关键词/
   英文标签，未命中回退 circle-dot；`style: {color, weight}` 描边色/磅值；正方适配
   声明盒居中）；见 references/icon-library.md 与 examples/icon；
   手头有品牌模板/成品 deck 要继承设计语言 →
   `meta.template`（extract 提炼样式注入 / seed 用模板版式 + 占位符打底，
   examples/template）。
2. **设计编排（写 SPEC 前必做——决定画面是否与旧版同质）**：
   全绿但骨架单一 = 看起来跟以前一样。先排页序与版式骨架，再动手写元素。
   - **页序节奏**：封面 → 节标题 → 内容页（≥2 种骨架）→ 结尾。封面/节页用
     页型意图 `page_intent`（cover/section），不要用 text+shape 硬拼；
     **同 intent 多页缺省自动轮换变体**（cover: left/band/split、
     section: num_left/num_giant/band），要锁定某页形态才写 `variant:`——
     同变体重复会被 A1 版式多样性判同质（见 references/page-intents.md §9）。
   - **内容页骨架菜单**（相邻页不得同骨架；同骨架全篇 ≤2 页）：
     ① 三/四卡图标行（shape 卡 + `type: icon` + 短文案）
     ② 左右分栏（左文右图 / 右文左图——chart、typst、图标阵列）
     ③ 图标+要点竖列（左 icon 列 + 右正文）
     ④ 数据页（`chart` + 右侧结论条）
     ⑤ 机制/多栏精细排版（`type: typst` 整块）
     ⑥ 流程/阶段（`graph` 或页型 `route`）
     ⑦ 引语/大字页（单句 + 强调 + 落款）
     ⑧ 对照页（页型 `versus`）
   - **视觉主体**：每个内容页至少 1 个 chart/image/diagram/typst/icon/svg/graph/table；
     纯文字页不得连续出现。
   - **图标默认用**：并行要点 / 卡片 / 流程节点 / 特性介绍 → 配 `type: icon`
     （中文关键词即可，见 references/icon-library.md）。
   - **强调**：关键数字/术语用 `[[…]]`（每页 ≤4），层级用 `**…**`；不要整段加粗。
   - **制图选型**：机制/多栏/精细排版 → `type: typst`；数据 → `chart`；
     精密矢量示意图（时间线/雷达/循环/分层/注解）→ `type: svg`（原生不可逐形状
     编辑的示意图优先，见 references/svg-figures.md）；方法机理 → `cylinder`/
     `curve`；不要用文字堆叠模拟图表。
   - **避开 AI 感痕迹**（源官方 pptx skill §Avoid）：内容页**禁止**三类填充式装饰
     ——① 标题下细横条（"hallmark of AI-generated slides"）；② 跨页宽装饰色条
     （头/脚色条）；③ 卡片单边强调条（贴边竖条）。用留白/底色/阴影/图标区分层级。
     另：配色须**支配而非平分**（一个主色占 60–70% + 1–2 辅色 + 1 锐利点缀，最大色
     占比 <55% 报警）；配色须**针对主题定制**（换到别的 deck 仍成立即不够具体 →
     声明 `meta.theme`）。`[design]` 行与 report.md「设计体检」机器检出（advisory）。
   - **内容处理转换律**：3+ 数字 → 指标卡/图（`kpis`/`chart`）；A vs B → 对照栏
     （`versus`）；重复字段 → 表格（`table`）；有序步骤 → 流程（`graph`/`route`）；
     长段 → 短句要点。`[design·转换律]` 逐条提示（advisory）。见 design-norms.md
     §内容处理转换律。
   - **跨页序列**（三步流程展开/对比演化）→ 同名对象 + `transition: morph`。
   - 阈值人读版 = references/design-norms.md（标题 ≤16 字、正文 ≤220 字、
     版式 distinct ≥ max(3, ⌈内容页×0.5⌉)、视觉主体页占比 ≥34%、密度峰值 ≤85%、
     字号档 ≥3）；管线跑完会打印 `[design]` 设计体检
     （视觉主体/图标/强调计数 + 密度峰值 + 建议），未达节奏就回去改 SPEC。
   - **活样板**：examples/showcase/showcase.yaml——6 页零重复骨架（cover/section/
     图标卡行/图表+KPI 结论条/versus/route），`[design] 视觉主体 6/6 页 · 图标 3 ·
     强调 4`。新 deck 照着它排页序与骨架，不要退回"标题 + 若干文本框"。
     变体家族样板：examples/pageintent/variants.yaml——cover split + 三 section
     自动轮换（num_left→num_giant→band）+ 内容对照页。
3. **搭 SPEC（声明式积木）**：`meta`（title/style_guide/slide/margin/brief/params/theme）
   + `palette`（token 库）+ `elements`（平铺）+ `relations`。
   - `meta.brief`：用户原始需求（自然语言；全局打底，页级 `slides[i].brief` 覆盖）
     ——`--fix` 修订器的意图依据源；数据字段（data/categories/series）改动须
     溯源 brief 原文或标 `[占位]`（数据红线）。
   - **设计语言 / 艺术指导层**：`meta.theme: <预设名>` 或 `{primary, style?, mode?,
     overrides?, geometry?, structure?, motif?, font_pair?}`——deck 级统一设计语言，
     一次声明全篇贯穿。
     ① 命名预设（**跨色相，防"默认蓝"**）：NNSFC 系 `nsfc_blue`/`nsfc_navy`/`nsfc_red`/
     `nsfc_green`/`nsfc_purple` + `modern_light` + 官方 10 套跨色相命名主题
     `midnight_executive`/`forest_moss`/`coral_energy`/`warm_terracotta`/`ocean_gradient`/
     `charcoal_minimal`/`teal_trust`/`berry_cream`/`sage_calm`/`cherry_bold`；
     ② 派生生成器：只给 `primary` 即自动派生全套色彩角色（deep/pale/panel/panel_line/
     emph/text/muted/line/bg/surface/accent，tint→白/shade→黑 HSL 内插，亮度单调
     pale>primary>deep）；`secondary` 作支撑色（描边/浅面板）；③ 色彩角色可作 palette
     token（`style.fill: panel`、expander `accent: primary`）；④ 类型尺度
     `hero/title/subtitle/body/caption` 经 `text_style.scale` 取缺省字号；⑤ 主题几何
     （`geometry: {margin, card_radius}`）作最低层参数；作者 `meta.params` 仍顶盖
     （配置栈：主题 < meta.params < 页级 < CLI）；⑥ 未知名/色值/子键 fail-closed
     （编译期 ValueError）；⑦ 缺省注入 clrScheme 槽（品牌色进原生 UI）。
     **防刻板三键**（官方 anthropics/skills pptx §Design Ideas 内化）：
     ⑧ `structure: uniform|sandwich|dark`——**背景节奏**：`sandwich` 封面/节页深底
     （主题 `deep` 色全幅背景 + 浅字反色）、内容页浅底；`dark` 全篇深底（须配
     `mode: dark`，否则内容页文字落深底不可见 → 编译期 fail-closed）；⑨ `motif:
     none|circle_icon`——**视觉母题**：每个图标加 accent 系圆形背衬（全篇重复的特征
     元素，官方 "icons in colored circles"）；⑩ `font_pair: sans_sans|serif_sans|
     serif_serif`——**衬线标题×无衬线正文**配对（安全字体 Cambria/Calibri，反差而不
     让 QA 溢出检查失准）。三键缺省 uniform/none/sans_sans = 零行为变化。
     见 scripts/themes.py、references/design-norms.md、examples/pageintent/theme_deep.yaml。
   - **类型尺度**：`text_style.scale: hero|title|subtitle|body|caption`——经主题
     `text.scale` 取缺省字号（显式 `fs` 优先）；`title/hero` 档置 `role:title`、
     余档 `role:body`，渲染层按 role 定字体族（标题/正文字族分离）。无 `scale`
     的元素零行为变化。
   - **多页序列**：`meta.slides: [每元素一页]`——顶层 elements/relations 须移入
     各页（编译期拦截）；palette 全局共享、元素 id 作用域 = 页内、遮挡/安全区
     校验按页隔离（任一页违规 → exit 3）；页级可选 margin/framework 覆盖（键级
     dict 合并）；页级可选 `params` 覆盖（配置栈页级层：该页字号硬底/表格 pad
     等参数旋钮逐页可调）；footer `{page}` 逐页编号。
   - **配置栈**：`meta.params` 全局打底 → `slides[i].params` 页级覆盖 →
     CLI `--param key=value` 顶覆盖（last-wins，值 YAML 类型化）。
     页级 params 贯穿布局/校验/渲染/物证全链路（见 wiki/modules/params.md）。
   - **页型意图**（多页专属）：`slides[i].page_intent: cover` + 同页
     `cover: {title, subtitle?, meta?, accent?, variant?}`——agent 只声明意图与
     内容，版式（大标题/强调条/落款）由引擎展开、verify 破格断言背书；
     `variant` 缺省按同 intent 出现次序在家族内轮换（确定性），显式值锁定该页；
     页面意图不进顶层 meta（编译期拦）；意图枚举/字段白名单/保留 id/变体族见
     references/page-intents.md。
   - 顶层元素写绝对 `rect: [x, y, w, h]`；容器内 children 只写相对尺寸或数值。
   - 积木：`shape`（基本形 + `kind: cylinder` 复合圆柱 + style/text_style +
     `border_dash` 虚线描边；cylinder 专属 `slice` 剖视 / `opacity` 侧壁透明度 /
     `face_opacity` 端面区目标不透明度——叠区自动反解保真，缺省 1.0 实色，
     约束 `face_opacity > opacity`）、`curve`（freeform 自由曲线，归一化点列）、
     `stack`/`dock`（自动布局）、
     `graph`（nodes/edges/groups 全自动流式布局；`orientation: vertical` 即组织树）、
     `table`（data 矩阵 → 原生 a:tbl）、`chart`（categories+series → 原生图表，
     零 COM）、`formula`（expr + 可选 fs/color；
     子集与兜底语法见 references/formula-omml.md，求和用 `∑_(i=1)^n` 字符式，
     离线模板直接命中 → 免 --com）、`typst`（typst 全量排版 → SVG 矢量 + PNG
     300ppi 双通道图块，页面尺寸 = 元素 rect 1:1；整块为图不可逐字编辑、受数据
     红线约束、须顶层声明；`design` 字段走 LLM 设计作业协议，见
     references/typst-chain.md）。
   - **行内富文本**：任意 `text`（元素/表格单元格/graph 节点/边标签）支持
     `**加粗**`、`[[强调]]`（强调色 = `params.style.emphasis`，默认 #C00000）
     与 `{{公式}}`（UnicodeMath → 原生 OMML，写进**当前文本框**：与文字同行 =
     行内式 `m:oMath`，独占一行/一段 = 显示式 `m:oMathPara`）；可嵌套
     `**[[…]]**`，不可交叉/空标记/未闭合（编译期 exit 2）；`{{…}}` 不得嵌在
     `**`/`[[ ]]` 内。IR 存 plain（测量/断言）+ runs（渲染），渲染与物证同规。
   - **图片占位（缺图不静默）**：`image` 可省 `src`，改 `placeholder: true` 或
     `placeholder: "<提示词>"`（可配 `caption`）；渲染落虚线占位框并写
     `out/img_prompts.md`（逐条 id/目标尺寸/提示词/期望路径）。`src` 文件缺失
     同样降级占位框，不阻断。交付前用 `--strict-images` 要求"图必须齐"（exit 2）。
   - **字体可移植**：`meta.params.font.portable: true`（或 CLI `--embed-fonts`）
     请求 Office 端嵌入字体，另用 `portable_list` 记录交付前需人工确认在目标机
     可用的字族。实测自动化保存路径不产嵌入字体 part → WARN 诚实降级（不阻断，
     见 references/ooxml-notes.md §15）；跨机可移植的等效手法 = 通用字族（latin/ea
     取目标机必有字体）。
   - 尺寸/间距尽量交给求解器；确需手工微调用 `meta.params` 覆盖数值接口。
   - 全文法表见 references/spec-v2-language.md；量化排版/版式规范见
     references/design-norms.md（标题字数/正文密度/强调密度/版式多样性阈值）。
4. **跑管线**：`win_py scripts/build_ppt.py my.yaml --out out`。
   退出码契约：0 全过；1 IO/内部；2 编译静态失败；3 校验 FAIL；4 渲染/物证失败；
   5 COM 失败（仅 `--com-strict`）；6 需 LLM 修订（**稳态暂停，非错误**）。
   `--com`（需 Office）追加 COM 后处理；`--pdf` 导出 base.pdf（隐含进 COM，
   无 Office 降级 WARN）；`--com-strict` 才让 COM 失败阻断。
5. **看 report**：`out/report.md` 给每次失败的家族与原因
   （G 几何 / T 文本 / D 容器 / S 规范）。**迭代闭环 = 改 SPEC → 重跑**，
   绝不手改产出的 pptx 或 XML。校验失败可交 `--fix` 自优修订链：违规归因三类
   （internal 停机 exit 4 报 bug / fixable 机械默认动作收敛 / content·advisory
   走 LLM 作业模式），每轮快照 `.snap.N` + fix.diff 审计、回环强制过 verify；
   `--llm` 时遇语义需求 **exit 6 稳态暂停** → 读 out/llm_job.json、按菜单/依据
   回填 out/llm_out.json（数据须溯源 brief 或 `[占位]`）→ **重跑同命令**；
   `--revert` 回滚最近快照。全程见 wiki/runbooks/fix-loop.md。
   失败或返工对照 references/copyediting.md 逐类自查
   （示意图优先 / 文字框间隙 / 字号分层 / 符号标注三档）。
6. **供人目视审阅**：`--com` 会导出 `out/preview.png`；把 base.pptx/preview.png
   交给用户"过目"。agent 不读图——目视判断属用户。交付前过一遍
   copyediting.md §㈤ 自查；用户反馈回来 = 改 SPEC 重跑，并对照清单消除
   **同类**问题（同批反馈常命中同一类，如"伪符号"往往多处残留——全量扫再改）。
7. **架构图逃生通道**（用户外部已绘制的图）：mermaid → Visio 导出 .vsdx →
   SPEC 里 `type: diagram, src: x.vsdx` → 渲染层跳过 → COM `AddOLEObject` 原生嵌入
   （双击进 Visio 可编辑）。PNG 类预渲染图直接 `type: diagram, src: x.png` 按图片落版。
   详见 references/agent-playbook.md 与 references/pipeline.md。

## 完成判据（全绿才算完）

- [ ] 管线 exit 0，`out/report.md` 无违规；产物 `out/base.pptx` 存在。
- [ ] `out/` 有 ir.json（调试/复现用）。
- [ ] **设计体检通过**：`[design]` 行无警告 / report.md「设计体检」无提示——
      内容页均有视觉主体、版式骨架无 >2 页重复、关键内容用了 `[[强调]]`；
      多页 deck 至少用过 2 种骨架（封面/节页用 page_intent 而非硬拼）。
- [ ] 有 `--com` 时 `com_out.json` 的 glue/groups/ole 项 ok（没有则不要求）。
- [ ] 给用户看过 preview.png（或说明了产物路径让其自看）。
- [ ] 若曾踩坑调整布局：改的是 SPEC 而非渲染层/产物；重跑仍 exit 0。
- [ ] 故意让用户复核的点已标注（如 vsdx 源路径、外部字体、OLE 双击行为）。
- [ ] 校对自查（copyediting.md）：正文/卡片字号 ≥16（verify S1b 背书）；
      非公式文本无 ASCII 下划线伪符号（Unicode 假公式或文字化）；
      文字框与图形区间隙 ≥0.2in。

## References（按需推进度披露）

- spec-v2-language.md — SPEC v2 全语法 schema 表（字段/单位/引用/params 键）
- page-intents.md — 页型意图：审定菜单 + 引擎破格展开（每原型 = 布局代码 + 断言）
- animation.md — 动画支持：35 宏配方/常量实测表/作业协议/降级语义/动画编排组（anim）
- alpha-blend.md — 半透明层叠加反解：merge/apart 闭式 + cylinder 叠区保真（S7 断言）
- formula-omml.md — 公式支持：文本框内联 `{{…}}`/OMML 注入子集/兜底边界/
  Word 批量引擎/实测语法
- typst-chain.md — typst 复杂精美排版链路：type:typst 语法/双通道 svgBlip/编译闸门/LLM 设计作业协议
- ink-brush.md — 书法矢量字（type:brush：字形→custGeom/三态填充/图片填充文字）+ Morph 平滑切换（mc:AlternateContent 兼容包/跨页同名补间）
- icon-library.md — 矢量图标库（type:icon：Lucide→custGeom 描边形状/名称关键词解析/正方适配；assets/icons/lucide.json）
- svg-figures.md — 矢量图内化 + 相对坐标层（type:svg：SVG→原生 DrawingML custGeom/图式目录/何时用哪条通道；rect_kind:ratio 相对坐标自适应定位；assets/figures/radar.svg）
- pipeline.md — 命令、gates、退出码、产物、COM 作业契约
- styleguide-rules.md — 规则集（flowchart/ladder/dashboard/deck）+ 新增图面类型步骤
- text-measurement.md — 文本测量与 autofit 原理
- ooxml-notes.md — OOXML/COM 实证陷阱表（shdw 无 a:clr、ZOrder 反向、lxml 空元素…）
- stylecard.md — 模板风格卡：分析模板/成品 pptx → 尺寸/主题色/字族/母版版式占位符
  + 设计 DNA（逐页字号/字族/文字色/形状构成统计）
- design-norms.md — 量化设计规范：字号分层/标题字数/正文密度/强调密度/版式多样性阈值
  + AI 感规避（三类填充式装饰 + 配色支配度 + 配色具体性）+ 视觉丰度 + 内容处理转换律
- agent-playbook.md — 绝对+自动混合策略、迭代闭环、人机协作分工
- copyediting.md — 人工校对经验清单（示意图优先/几何间隙/字号分层/符号三档/交付自查）
- wiki/runbooks/fix-loop.md — `--fix` 自优修订循环：归因/机械 R1–R4/LLM 作业模式/exit 6 回填协议/--revert