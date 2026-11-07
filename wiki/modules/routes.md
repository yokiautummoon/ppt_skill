---
tags: [module]
module: routes
parent: build_ppt
depends_on: []
updated: 2026-10-08
---

# routes — 操作路由注册表（防误路由 + 协议显式化）

借鉴 EasySlides workflow registry 的四列（Trigger / Preconditions /
Route-exclusion / Output-contract）：每种操作入口在此**显式声明**何时该走、
前置、**何时不许走**、承诺产出与出口码。纯数据 + `validate()`/`by_id()` 两个
极小助手，无逻辑。唯一事实源；`references/routing-table.md` 是人读同步版，
`tests/test_routes.py` 卡两者一致（id 一字不差、name 进小节标题）。

`ROUTES`：8 条路由，每条 dict：

- **四列语义**：`trigger`（何时该走）、`preconditions`（前置条件）、
  `excludes`（引用其他路由 id = 此路不该走时的去向）、`exclude_conditions`
  （何时必须改道）、`outputs`（Output-contract：承诺产物）。
- **机器字段**：`script`（入口脚本，validate 核对文件真实存在）、`exits`
  （出口码 ⊆ ROUTE_EXITS = (0,2,3,4,5,6)）、`entry`（入口函数名，文档性）。

8 条：`main_generation`（SPEC → base.pptx，0/2/3/4）、`fix_loop`（--fix
修订链，0/3/4/6）、`com_postprocess`（COM 后处理，0/5）、`typst_block`
（typst 复杂排版块，0/2）、`page_intent`（页型意图破格版式，0/2/3）、
`template_extract`（模板风格卡提炼，0/2）、`template_seed`（模板打底，
0/2/3/4）、`anim_inject`（页级动画批量注入，0）。

**总则（所有路由共享）**：不手改产物 pptx/XML（动 z/锚点就改 SPEC 重跑）；
不静默降级（能力不支持 → 编译期拒绝，capabilities fail-closed）；数据红线
（LLM 改 data/categories/series 须溯源 brief 或标 `[占位]`，CHECK_OUT 强制
exit 3）；internal 归因停机（引擎算法 bug 不修 SPEC、不喂 LLM，exit 4）。

`validate()` 机器校验：id 全局唯一、四列/script/exits 非空、excludes 只引用
已知路由 id 且无自引用、exits ⊆ ROUTE_EXITS、script 文件在 scripts/ 真实存在。
加新路由协议：只改 `ROUTES` 一条（含 script 文件实存）→ 同步人读版小节 →
测试卡两者，无需改路由跳转逻辑。

消费方：`tests/test_routes.py`（validate 全过 + ≥8 条 + id 唯一 + by_id 可解析
+ 文档覆盖）；`references/routing-table.md`（人读操作手册，总则 + 每路由四列
明细 + 加新路由步骤）。