---
tags: [decision]
parent: root
status: done
updated: 2026-10-08
scope: 借鉴 EasySlides（同作者开源 agent PPT skill）——落地三件强烈推荐：能力档案 fail-closed / 组件包契约 / 操作路由注册表
---

# 决策：EasySlides 借鉴三项落地（能力档案 / 组件包契约 / 路由注册表）

## 背景

2026-10-08 调研同作者开源项目 EasySlides，逐条对照本 skill 的可借鉴点，
交付对比报告并给候选分级：

- 强烈推荐（★★★）：① 能力档案 + fail-closed 声明、② 组件包契约、
  ③ 工作流/操作路由注册表 + 路由排除。
- 建议（★★）：评审产物 + SHA-256 锁定交接、确定性 Anti-repetition 选择。
- 观察：跨渲染器视觉回归（本项目无多渲染器诉求，YAGNI）。

用户批示：**强烈推荐的三项做，然后更新 wiki**。本决策记录三项的落地骨架
与取舍；不落地项的搁置理由见「取舍公开」。

## 决策

### ① 能力档案（capability profile）+ fail-closed

**`scripts/capabilities.py`**，纯数据 + 极小查询助手（同 styleguides.py 风格），
三张表唯一事实源：

- `ELEMENT_CAPS` — 13 元素类型 → 能力旗标：`shape_producing`（容器 False）、
  `animatable`/`linkable`/`edit_group_member`（单形状派生，容器 False）、
  `anchorable`（容器/线 False，其余 True）、`top_level_only`（table/chart/typst）、
  `composite`（文档性）。
- `PAGE_INTENT_CAPS` — 页型 → `status`（implemented/planned）+ 专属字段白名单 +
  展开保留 id + 展开函数名；**spec_compile 的 PAGE_INTENTS / PAGE_INTENT_FIELDS /
  PAGE_INTENT_EL_IDS 全由此派生**（消重复字面量，单一事实源）。
- `COMPONENT_CONTRACTS` — 积木（cylinder/curve/typst/table/chart/formula/
  stack/dock/graph + cover/section 页型）→ `renderer`/`required`/`invariants`/
  `capacity`/`qa`；`RENDERER_MODULES` + `renderer_modules_exist()` 供测试核对。

**spec_compile 消费，fail-closed 三实锤**：

1. **planned 页型编译拒**：`page_intent: data/compare/conclusion/quote` → exit 2
   （"尚未落地（status=planned）"）。修掉一个真正的潜伏 no-op——此前这些页型
   静默无展开。
2. **intent 字段 dict 同步强制**：`cover:`/`section:` dict 出现却无 page_intent、
   或 page_intent 声明却缺 dict → 均 exit 2（此前一半静默）。
3. **anchors 能力级拒收**：容器/线声明 anchors → exit 2；结构校验从 shape 专属
   泛化到全部 anchorable 类型。link/animation/edit_group/top_level_only 校验
   相应改由能力带驱动（语义不变，来源统一）。

### ② 组件包契约（Component Pack Contract）

`COMPONENT_CONTRACTS` 每个复合积木/页型显式声明：renderer 归属模块、required
SPEC 必需键、invariants = verify 源码断言子串背书。**`references/
component-contracts.md`** 为人读同步版（表格逐契约 = 一行）。

测试契约（tests/test_capabilities.py 逐个背书，契约不是橡皮图章）：
- required 满减 → 编译必报错（最小合法 SPEC 逐字段摘除）；
- invariants 子串必须在 verify.py 源码在场；
- renderer 模块必须在 scripts/ 真实存在；
- 人读版文档用 `\`cid\`` 覆盖全部契约 id。

### ③ 操作路由注册表（workflow registry + route-exclusion）

**`scripts/routes.py`**：`ROUTES` 8 条，每条四列（Trigger / Preconditions /
Route-exclusion → `excludes` + `exclude_conditions` / Output-contract →
`outputs`）+ 机器字段（`script` 实存 / `exits` ⊆ (0,2,3,4,5,6)）。`by_id()`
解析；`validate()` 机器校验（id 唯一、关键字段非空、excludes 引用有效且无
自引用、脚本文件实存）。**`references/routing-table.md`** 人读同步版（总则 +
每路由小节 = id 一字不差 + 名称进标题），tests/test_routes.py 卡同步。
加新路由不改跳转逻辑：只增注册表一条 + 同步人读版 + 测试卡两者。

## 取舍公开

- **不静默降级原则**：能力不支持 → 编译期拒绝（“字段合法却什么也没发生”的
  no-op 一律消灭，宁可报错）。此原则此前已零星存在（typst design 拦截、
  cylinder 参数专属），本次把它系统化为能力档案驱动。
- **planned 页型**：保持枚举在场、编译拒而非删除——菜单语义完整、fail-closed
  提示明确；真正落地时改 status 一行 + 写展开/断言（page-intents 落地协议不变）。
- **评审产物 + SHA-256 / Anti-repetition / 跨渲染器回归搁置**：本项目
  verify/物证已内建断言链、单渲染器（PowerPoint OOXML）+ COM 后处理，前三者
  收益低、复杂度高（YAGNI），需求出现再评估。

## 落地验收（status: done）

- capabilities.py / routes.py / references/component-contracts.md /
  references/routing-table.md 全部新建；spec_compile.py 接入能力档。
- tests/test_capabilities.py 81/81 · tests/test_routes.py 34/34 ·
  run_mutations 129/0 · regression 27/27（全部 win_py 实测）。
- wiki 更新：新模块页 capabilities.md / routes.md；spec_compile / ir_builder /
  verify 模块页补 fail-closed 说明；_index.md 模块表 + references + 测试计数 +
  关键概念；_log.md 变更条目。
- 已知边界：invariants 以**子串**背书 verify 断言名（非精确定位）；
  COMPONENT_CONTRACTS 未覆盖的积木（如 anim 宏）不在此契约范围（按需扩展）。