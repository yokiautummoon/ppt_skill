---
tags: [module]
module: revisioner
parent: build_ppt
depends_on:
  - attribution
  - params
updated: 2026-09-14
---

# revisioner — 修订链调度 + 动作库 + 事务应用

`--fix` 修订链的调度中枢（决策 self-improve-loop.md 部件②核心）：归因结果 →
修订计划（修订器归属分配），并把修订**结构级事务性**应用到原始 SPEC dict
（不写盘；写盘由 build_ppt 统一 dump_spec）。

## 修复动作库（机械修复与 LLM 菜单共用）

```python
MENU = {
  "autofit":   ["降号", "扩框", "浓缩文本", "拆元素", "人工"],
  "safety":    ["平移/收缩", "调换位置", "缩放", "人工"],
  "overlap":   ["补overlap", "移A", "移B", "挪开", "人工"],
  "zfix":      ["补z_override", "人工"],
  "fontscale": ["调至合法档", "人工"],
  "content":   ["从brief生成文本", "引用现有文本", "移除(若装饰)", "人工"],
  "manual":    ["人工"],
}
```

- 无 LLM：机械规则 R1–R4 = **动作库默认动作**（菜单首项 = 机械保守项）→ 确定性执行；
- 有 LLM：llm_fixer 从**同一动作集**按 brief 选（候选菜单钳制 → 可预期/可重放/可审计）；
- 菜单确定性 → 修订可审计：与 page_intent「审定菜单 + 引擎展开」哲学一以贯之。

## 接口

```python
plan(violations) -> (internal, items)   # internal 出现 → 调用方停机 exit 4
apply_revisions(spec_raw, revisions) -> (new_spec_raw, diffs, errors)  # 事务性
write_fix_diff(path, diffs, round_n, fixer)   # fix.diff 追写
snapshot_file(spec_path, round_n) / rollback(spec_path, round_n)  # .snap.N
dump_spec(spec_raw, newline)   # dict → YAML（CRLF 保留；注释不保留——SPEC 是 agent 生成物）
```

- `path` 是**逻辑页内路径**（`("elements", idx, 字段...)` 或 `("relations", 段,
  idx|"+", 字段)`）；单页顶层形态与多页 `meta.slides` 由 `_page_container` 判定映射，
  页标 `pg` 由调用方用 `_annotate_page` 标注；
- 事务性：任一修订失败（old 不匹配 / 索引越界 / 中间段非 dict）→ errors 非空、
  返回原样 spec_raw——调用方不得落盘、须回滚本轮快照；
- 缺失层自动创建（如 `text_style.fs` 新增）；list 下标（rect 数值段）类型感知
  （`_set_leaf`：dict 查键、list 查下标，不做值成员检查）。

## fix.diff 行格式（审计 + --revert 依据）

```
轮次|修订器|动作|字段路径|旧→新|理由|置信度|数据来源
1|spec|safety|elements[1].rect[1]|6.5→6.4|G2 底边越界...|1.0|
```

- 字段路径经 format_path 统一（`elements[1].rect[1]`；多页前缀 `slides[pg].`）；
- `--revert` 恢复最近 `.snap.N` 快照（fix.diff 留痕给人工审计）。

## 序列化注意

apply_revisions 对浅拷贝 work 应用（setdefault 落在返回对象上）；多页时
`meta.slides` 深拷贝一层再映射——**新增段（relations 等）必须落在 work 侧**
（早期 host alias bug 教训：在 raw 上 setdefault 导致修订未落盘）。