---
tags: [module]
module: intents
parent: ir_builder
depends_on: [params]
updated: 2026-10-18
---

# intents — 页型变体家族 + 确定性选型

防刻板第二块地基（第一块 = page_intent 页型意图本身）。一个 intent 只有一种
几何展开 → 同一 deck 里 3 个 section 页像素级相同；而 A1 版式多样性当时把
intent 页豁免 → 引擎展开的重复无人拦（门禁盲区）。本模块给每 intent 挂一族
**审定变体**，并做确定性选型。

## FAMILIES（唯一事实源）

```python
FAMILIES = {
    "cover":   ("left", "band", "split"),
    "section": ("num_left", "num_giant", "band"),
    "problem": ("badge",), "versus": ("split",), "route": ("chain",),
}
```

`capabilities.PAGE_INTENT_VARIANTS` 是其只读快照（供编译期/测试消费）；
`tests/test_deck_rules.py` 有漂移断言（两表族序必须一致、未实现 intent 空族）。

## 选型（确定性、可复现）

`resolve(intent, explicit=None)` → 显式优先，否则家族首变体（单页/直构场景）。
`plan(slides)` → deck 级：逐页产出 `{index, intent, variant, explicit}`——
**显式 `variant:` 优先；缺省按该 intent 在本 deck 内的出现次序在族内轮换**
（`fam[n % len(fam)]`）。同一 SPEC 每次构建得同一选型。

## 消费方

- `build_ppt.build_pages`：取 `plan`，给 `meta[intent]["variant"]` 注入缺省值
  （页仅透传，不自己算）→ `ir_builder._expand_<intent>` 用 `IN.resolve` 取有效
  变体，写 IR 的 `page_intent_variant`。
- `spec_compile`：`page_intent` 字段 dict 若带 `variant`，用 `IN.known` 校验
  （未知变体 / 跨 intent 误用 → exit 2）。
- `verify`：`_intent_variant` 取有效变体分支断言；`_layout_page_sig` 对 intent 页
  返回 `(("intent", intent, 变体),)` → **intent 页以真实签名纳入 A1 门禁（不再
  豁免）**，同变体重复被判同质。
- `report._layout_sig`：设计体检同规（同签名页集一致）。

## 铁律 / 边界

- 变体是**布局代码分支 + 每变体 verify 反向破格断言**，不是喂模型的 prose；
  换文案不改签名、换变体即换签名。
- 变体内的叠放（如 split 标题嵌入色块、band 序号与节名同嵌色带）靠**同 owner
  令牌**取得 G4 遮挡合法性——背景 shape 与前景文本必须挂同一 `owner`。
- 未实现 intent 的族为空 `()`；problem/versus/route 当前单变体，预留扩展。

完整语法/家族表/断言清单见 references/page-intents.md §9。
