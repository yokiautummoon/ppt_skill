---
tags: [module]
module: template_analyzer
depends_on: []
updated: 2026-09-10
---

# template_analyzer — 模板风格卡

分析模板/成品 pptx → 风格卡（尺寸/主题色/字族/母版版式占位符 idx）。extract（提炼样式注入 spec）/ seed（用模板版式 + 占位符打底）；占位符 idx 继承语义见 references/ooxml-notes.md §12。spec_compile 在 meta.template 校验时依赖它。

**设计 DNA（B2 内化）**：`design_dna` 逐页统计 DrawingML 事实——run 数/加粗
run/字号分布（a:rPr@sz）/文字色（solidFill srgbClr）/latin+ea 字族/形状构成
（p:sp 的 a:prstGeom@prst）/图片/表格/图表数；另出全局聚合（sizes/colors/
fonts/shape_mix 前 N）与 `pages_with_picture`。纯 zip 解析（lxml），不依赖
python-pptx（模板无页时返回空统计）；stylecard.md 增加「设计 DNA」段，
供 agent 模仿既有 deck 观感（字体/字号层级/用色/形状语汇）。