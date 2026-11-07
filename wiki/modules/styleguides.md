---
tags: [module]
module: styleguides
depends_on: []
updated: 2026-10-09
---

# styleguides — 规则集

flowchart / ladder / dashboard / deck 视觉规则（容器/配色/布局偏好）与新增图面类型步骤。查询/扩展入口，具体点位见 references/styleguide-rules.md。

- **scansci 内化可选键**（任意规则集可加，缺省不启用 = 零行为变化）：
  - `size_fs_floor: {threshold: <in>, fs: <pt>}` — 小尺寸字号下限：顶层元素
    rect 短边 < threshold → 字号须 ≥ fs（角色豁免 lab/caption/note/units/foot/
    hdr/ftr/meta 与带 owner 者）；verify S8 起拦，attribution advisory（人工/LLM）。
  - `labels_follow: true` — 标签组织：`.label` 后缀文本须与其目标同 owner 或同
    编辑单元（relations.edit_groups）；verify S9 起拦（默认关）。
- **flowchart.semantics 方法论契约**（流程图同质化治理，A/D 单一事实源）：
  `branch_min_nodes`（默认 5，复杂图阈值）+ `linear_escape`（`linear` 逃生键）+
  `guide`（LLM 生成指引原文）。机器侧 = spec_compile `_check_graph_semantics`
  （A：复杂图无分支 → exit 2）+ verify `check_graph_dedup`（C：跨页拓扑同构去
  重）；人读版 = references/flowchart-method.md；测试卡 guide 子串在文档在场。
- **QUANTITATIVE 量化规范表（A3 内化）**：推荐值可读副本——字号分层
  （body 14–18 / title 28–32 / hero 54–96 / caption 8–14）、线宽 0.5–1.5pt、
  行距 1.2–1.5、饱和填充面积 ≤25%、`max_emphasis` 4、`max_title_cjk` 16、
  `max_same_layout` 3、`min_layout_variety` 7、`pictures_per_page` 1。
  判定阈值仍走 `params.verify.typography` / `layout_variety`（数值接口单一
  事实源）；本表供风格卡/设计 DNA 比对与文档共用，人读版
  references/design-norms.md。