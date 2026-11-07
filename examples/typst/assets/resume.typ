// ============================================================
// 个人简历 · 复杂精美排版示范（自包含，零 @preview / 零外部资源）
//
// 设计语言移植自 typst 官网 CV 模板 impressive-impression
//（https://typst.app/universe/package/impressive-impression，
//  Forty Seconds 双栏侧栏风格）：
//   · 左侧深色侧栏：人像 + 联系 + 技能/语言点阵评级 + 获奖标签
//   · 右侧主栏：个人简介 + 工作经历时间线 + 项目经历 + 教育背景
//   · 主题色板：深海军蓝 ink + 项目蓝 accent + 金 gold（侧栏点缀）
//
// 页面尺寸显式声明 = 元素 rect（1in = 72pt）：自设页面 → 引擎信任不
// 自动围切（视图与目标框 1:1，渲染零重算）。数据红线示范：SPEC brief
// 为本页唯一数据源，正文数字/机构/年份全部溯源 brief。
// ============================================================

#set page(width: 7.8in, height: 10.3in, margin: 0pt)
#set text(font: ("Microsoft YaHei", "SimSun", "Times New Roman"), size: 10.5pt)
#set par(leading: 1.5em)

#let ink    = rgb("#1B2A4A")   // 深海军蓝：主文字 / 侧栏底
#let ink2   = rgb("#33415C")   // 正文次级
#let accent = rgb("#2D6CDF")   // 项目主蓝：主栏强调
#let gold   = rgb("#D9A441")   // 金：侧栏点缀
#let faint  = rgb("#6B7280")   // 弱文字
#let aw     = rgb("#EAF0FA")   // 侧栏主文字（近白）
#let am     = rgb("#93A5C4")   // 侧栏次要文字

// ---- 主栏小节标题：accent 竖条 + 深色标题 ----
#let sec(title) = block(
  grid(
    columns: (3.4pt, 1fr),
    column-gutter: 9pt,
    align: (left + horizon, left + horizon),
    box(width: 3.4pt, height: 14pt, fill: accent, radius: 1.8pt),
    text(size: 14.5pt, weight: "bold", fill: ink)[#title],
  ),
  below: 9pt,
)

// ---- 侧栏小节标题：金短线 + 标题 ----
#let asec(title) = block(
  grid(
    columns: (16pt, 1fr),
    column-gutter: 7pt,
    align: (left + horizon, left + horizon),
    box(width: 16pt, height: 2pt, fill: gold),
    text(size: 11pt, weight: "bold", fill: aw)[#title],
  ),
  above: 12pt,
  below: 7pt,
)

// ---- 点阵评级行（label + dots）----
#let rating(label, n, total: 5) = grid(
  columns: (1fr, auto),
  column-gutter: 8pt,
  align: (left + horizon, right + horizon),
  text(size: 9.5pt, fill: aw)[#label],
  grid(
    columns: total,
    column-gutter: 4pt,
    ..range(total).map(i => box(circle(radius: 2.5pt, fill: if i < n { gold } else { am.transparentize(55%) }))),
  ),
)

// ---- 侧栏联系行：单字角标块 + 文本 ----
#let contact(ch, body) = grid(
  columns: (20pt, 1fr),
  column-gutter: 8pt,
  align: (center + horizon, left + horizon),
  box(width: 20pt, height: 20pt, fill: accent.transparentize(70%), radius: 5pt,
      align(center + horizon, text(size: 9pt, weight: "bold", fill: aw)[#ch])),
  text(size: 8.5pt, fill: aw)[#body],
)

// ---- 侧栏标签胶囊 ----
#let pill(label) = box(
  inset: (x: 6pt, y: 4pt),
  radius: 4pt,
  fill: aw.transparentize(88%),
  stroke: 0.6pt + am.transparentize(55%),
  align(center + horizon, text(size: 8.5pt, fill: aw)[#label]),
)

// ---- 主栏要点行：accent 方形标记 ----
#let li(x) = grid(
  columns: (8pt, 1fr),
  column-gutter: 6pt,
  align: (left + horizon, left + top),
  box(width: 4.5pt, height: 4.5pt, fill: accent, radius: 1.2pt),
  text(size: 9.5pt, fill: ink2)[#x],
)

// ---- 主栏经历条目：左时间 + 右标题/机构/要点（accent 左侧轨）----
#let entry(time, title, org, body) = grid(
  columns: (2.2cm, 1fr),
  column-gutter: 12pt,
  align: (left + top, left + top),
  text(size: 9pt, weight: "bold", fill: accent)[#time],
  block(
    stroke: (left: 2pt + accent.lighten(35%)),
    inset: (left: 10pt, top: 1pt, bottom: 1pt),
  )[
    #text(size: 11pt, weight: "bold", fill: ink)[#title]#h(6pt)#text(size: 8.5pt, fill: faint)[#org]
    #v(2.5pt)
    #body
  ],
)

// ============================================================
// 侧栏
// ============================================================
#let aside = block(
  width: 100%, height: 100%,
  fill: ink,
  radius: (top-left: 6pt, top-right: 0pt, bottom-left: 6pt, bottom-right: 0pt),
  inset: (x: 13pt, y: 18pt),
)[
  #align(center, box(width: 56pt, height: 56pt, radius: 50%,
      fill: gradient.linear(angle: 0deg, gold, gold.darken(14%)),
      align(center + horizon, text(size: 25pt, weight: "bold", fill: ink)[林])))
  #v(9pt)
  #align(center, text(size: 21pt, weight: "bold", fill: aw)[林知夏])
  #v(2pt)
  #align(center, text(size: 10pt, weight: "medium", fill: am)[高级产品设计师 · 设计系统])

  #asec[联系]
  #contact("邮", "hi@linzhixia.cn")
  #v(6pt)
  #contact("电", "+86 138-0000-0000")
  #v(6pt)
  #contact("址", "上海 · 徐汇")
  #v(6pt)
  #contact("网", "linzhixia.design")

  #asec[专业技能]
  #rating("设计系统", 5)
  #v(6pt)
  #rating("交互原型", 4)
  #v(6pt)
  #rating("用户研究", 4)
  #v(6pt)
  #rating("动效设计", 3)
  #v(6pt)
  #rating("前端协作", 3)
  #v(6pt)
  #rating("项目管理", 3)

  #asec[语言能力]
  #rating("中文", 5)
  #v(6pt)
  #rating("英语", 4)

  #asec[获奖与证书]
  #grid(
    columns: (1fr, 1fr),
    column-gutter: 6pt,
    row-gutter: 6pt,
    pill[红点提名], pill[年度设计奖],
    pill[专利 ×2],  pill[UX 认证],
  )
]

// ============================================================
// 主栏
// ============================================================
#let main = block(
  inset: (left: 18pt, right: 16pt, top: 16pt, bottom: 12pt),
)[
  #sec[个人简介]
  #block[
    #set par(justify: true)
    #text(size: 10pt, fill: ink2)[
      十年产品设计经验，专注 #text(fill: accent, weight: "bold")[设计系统] 与 B 端复杂工作台体验。
      主导从零搭建跨团队设计系统「晓舟 UI」，覆盖 5 条产品线、1200+ 组件、8 套主题，
      设计研发协作提效 #text(fill: accent, weight: "bold")[47%]。]
  ]
  #v(2pt)

  #sec[工作经历]
  #entry("2022 — 今", "设计系统负责人", "澜舟科技 · 上海")[
    #li[统筹 8 人设计平台组，推动设计系统 0→1 与多端落地]
    #v(3pt)
    #li[建立组件度量体系，接入 3 条业务线，年均节省 900+ 人日]
  ]
  #v(8pt)
  #entry("2019 — 2022", "资深产品设计师", "云帆科技 · 杭州")[
    #li[负责数据可视化平台改版，核心页任务完成率 +32%]
    #v(3pt)
    #li[沉淀 40+ 通用图表组件与栅格规范，获团队最佳实践奖]
  ]
  #v(8pt)
  #entry("2016 — 2019", "UI 设计师", "栖木互动 · 北京")[
    #li[参与 12 个移动端项目视觉与切图规范输出]
    #v(3pt)
    #li[建立组件库雏形，跨项目复用率达 60%]
  ]

  #sec[项目经历]
  #entry("2020 — 2022", "「晓舟 UI」设计系统 0→1", "澜舟科技")[
    #li[定义设计令牌 / 组件 / 文档三层体系，产出 1200+ 组件与 8 套主题]
  ]
  #v(8pt)
  #entry("2021 — 2022", "B 端数据沙盘改版", "澜舟科技")[
    #li[以任务驱动的信息架构重构，上线 6 个月留存 +28%]
  ]

  #sec[教育背景]
  #entry("2012 — 2016", "工业设计 · 本科", "同济大学 设计创意学院")[
    #li[主修用户研究与交互设计；毕业设计获学院优秀奖]
  ]

  #v(1fr)
  #align(right, text(size: 8pt, fill: faint)[林知夏 · 高级产品设计师 · 简历 2026])
]

// ============================================================
// 组装：双栏（侧栏 + 主栏）撑满整页；行高 1fr 吸收尾白
// ============================================================
#block(width: 100%, height: 100%)[
  #grid(
    columns: (5.6cm, 1fr),
    rows: (1fr,),
    column-gutter: 0pt,
    aside,
    main,
  )
]