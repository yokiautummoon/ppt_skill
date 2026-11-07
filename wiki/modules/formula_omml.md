---
tags: [module]
module: formula_omml
depends_on: []
updated: 2026-09-10
---

# formula_omml — 公式 OMML 注入子集

UnicodeMath 子集解析 → OMML（mathPr 样式注入）。子集内直接注入（零 COM）；子集外走 formula_templates / omml_engine 兜底。语法边界见 references/formula-omml.md。

**承载形态**：公式是文本框内容，不是必须独立成形状（用户样例 公式示例.pptx）。
`omath_inline()` 产 `a14:m > m:oMath`（与文字同行的行内式）；
`omath_paragraph()` 产 `a14:m > m:oMathPara`（独占一段的显示式）。
`richtext.paragraphs()` 决定文本内 `{{…}}` 用哪种形态（同段有文字=行内，
独占一段=显示）；渲染与物证共用该判定。PowerPoint 16.0 实测两种形态均可
打开/回存（`_probe/probe_inline_formula.py`）。