---
tags: [module]
module: spec_fixer
parent: build_ppt
depends_on:
  - attribution
  - params
updated: 2026-09-14
---

# spec_fixer — 确定性机械修订器（R1–R4）

`--fix` 修订链的**确定性快路径**（决策 self-improve-loop.md 部件②）：动作库默认
动作 = 机械保守项，零 LLM、同输入必同输出。与 llm_fixer 同接口：
`input(SPEC 页, violations, params) → output(revisions, audit)`，产物交
revisioner.apply_revisions 结构级应用。

## 机械规则（= 动作库默认动作）

| 规则 | 触发 | 默认动作 |
|---|---|---|
| R1 autofit | T 文本 autofit 溢出（min_fs 硬底 / 超框标记）| 逐级降号（2pt 步长，to min_fs）；仍溢 → 安全区内扩框（clamp） |
| R2 safety | G 几何溢出安全区 | margin 内平移 + 等比例收缩（保宽高比与相对位）|
| R3 overlap | D/S 遮挡无合法源 | 保守补 `relations.overlap` 声明（判重防重复）|
| R4 zfix | z_override 冲突（物证再报）| 按声明序补 `relations.z_override`（z = 声明序 + 1）|
| 附属 fontscale | S 字号越档 | clamp 到 styleguide type_scale 合法区间；无显式 fs → 新增显式 |

## 接口

```python
fix_page(spec_page, page_params, violations) -> (revisions, audit)
# revision 结构（revisioner 消费）：
#   {"action", "path", "old", "new", "basis", "confidence", "data_source"}
#   path 为逻辑页内路径，如 ("elements", 1, "rect", 1)；pg 由调用方标注
```

- `detail` 解析：`_RE_RECT`（rect=...）/ `_RE_HZ`（max_w/框宽）/ `_RE_VT`（need_h/
  框高）/ `_RE_FS_MIN`（fs/min）/ `_RE_SCALE`（fs 规范区间）/ `_RE_BODY`；
  **解析不到数值 → 该动作降级 manual**（不瞎改）；
- `basis` 记触发违规原文（fix.diff 审计溯源）；`confidence` 机械 = 1.0；
- 修订后的回环 verify 由 build_ppt 主循环强制（不收即 rollback）。

## 设计边界

- R1 降号在真实管道中少触发——ir_builder 的 textmesh autofit 已吸收大部分溢出，
  R1 是 min_fs 硬底 / 超框标记场景的兜底（正当边界，非缺陷）；
- 只产出**确定性**动作；多解（浓缩文本 / 换邻色 / 调间距等表现力决策）留给
  llm_fixer 菜单。