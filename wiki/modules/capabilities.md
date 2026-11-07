---
tags: [module]
module: capabilities
parent: spec_compile
depends_on: []
updated: 2026-10-08
---

# capabilities — 能力档案注册表（fail-closed 声明）

借鉴 EasySlides capability profile：每个可复用单元在此**显式声明支持什么**；
不支持的能力编译期（exit 2）拒绝，**宁可报错不静默降级**（不留"字段合法却
什么也没发生"的 no-op）。与白名单分工：spec_compile/spec_validator 管
"字段是否存在、类型对不对"（字段级）；本模块管"这个单元**能不能**承接该能力"
（能力级）。纯数据 + 极小查询助手，无逻辑（同 styleguides.py 风格）。

三张表（唯一事实源）：

1. **ELEMENT_CAPS** — 13 种元素类型 → 能力旗标：
   `shape_producing`（容器 = False）、`animatable`/`linkable`/`edit_group_member`
   （单形状派生能力，容器全 False）、`anchorable`（可声明具名锚点；容器/线 False，
   其余 True）、`top_level_only`（table/chart/typst → 必须顶层）、`composite`（文档性）。
2. **PAGE_INTENT_CAPS** — 页型原型 → `status`（implemented/planned）+ 专属字段
   白名单 + 展开保留 id + 展开函数名 + **`variants` 审变体族序**（cover
   left/band/split、section num_left/num_giant/band，计划页型空族）。**spec_compile
   的 PAGE_INTENTS / PAGE_INTENT_FIELDS / PAGE_INTENT_EL_IDS 全部由此派生**
   （消重复字面量）；`PAGE_INTENT_VARIANTS` 为 `variants` 快照，事实源仍是
   `scripts/intents.py::FAMILIES`（test_deck_rules 漂移断言背书）——
   见 references/page-intents.md §9「变体家族」。
3. **COMPONENT_CONTRACTS** — 复合积木（cylinder/curve/typst/table/chart/formula/
   stack/dock/graph + cover/section 页型）→ `renderer` 模块列表、`required`
   SPEC 必需键、`invariants`（verify 源码子串背书）、可选 `capacity`/`qa`。
   `RENDERER_MODULES` 与 `renderer_modules_exist()` 供测试核对。

fail-closed 三个实锤（spec_compile 消费）：

- **planned 页型编译拒**：`page_intent: data/compare/conclusion/quote` → "尚未落地
  （status=planned）" exit 2（此前静默无展开——潜伏 no-op）。
- **intent 字段 dict 同步强制**：`cover:`/`section:` dict 出现却无 page_intent、
  或 page_intent 声明却缺 dict → 均 exit 2（此前一半静默）。
- **anchors 能力级拒收**：容器/线声明 anchors → exit 2（此前非 shape 元素既
  不校验也不展开）；结构校验从 shape 专属泛化到全部 anchorable 类型。

消费方：`spec_compile.py`（编译期 fail-closed）；`verify.py` 的断言是其
invariants 背书的兑现；测试 `tests/test_capabilities.py` 卡三张表与真实行为
一致（required 满减必报错、invariants 子串在 verify.py、renderer 模块在场、
文档 references/component-contracts.md 覆盖全部契约 id）。
**C3 补充**：`ELEMENT_CAPS["brush"]`（书法矢量字 = 单 custGeom 形状 → 动画/链接/
编辑组/锚点全支持，composite）；`COMPONENT_CONTRACTS["brush"]`（renderer =
ink_text/ir_builder/render_pptx，required = rect/text/font，invariants 空——物证 4.4b
背书而非 verify 断言）。详见 references/ink-brush.md。
**B1 补充**：`ELEMENT_CAPS["icon"]`（矢量图标 = 单 custGeom 形状 → 动画/链接/编辑组/
锚点全支持，composite）；`COMPONENT_CONTRACTS["icon"]`（renderer =
icon_lib/svgpath/ir_builder/render_pptx，required = rect/icon，invariants 空——物证 4.4c
背书而非 verify 断言）。详见 references/icon-library.md。
