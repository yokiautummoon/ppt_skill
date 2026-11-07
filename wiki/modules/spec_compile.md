---
tags: [module]
module: spec_compile
parent: build_ppt
depends_on:
  - animation_recipes
  - anim_group
  - template_analyzer
  - richtext
updated: 2026-10-09
---

# spec_compile — SPEC 编译

YAML → 编译态：语法/单位/引用/动画 effect 校验（容器拒收 animation、children 放行）；
也背书 chart 数据账目、slides 多页契约（`meta.slides` 后顶层禁 elements/relations）、
framework 保留名（bg/hdr/ftr）、`meta.brief`/`slides[i].brief` 类型（非字符串 →
exit 2）、`type:typst` 契约（三源互斥 `typst`/`typst_src`/`design`、须顶层声明、
外链 `.typ` 存在性、preamble 字符串、vars 键 isidentifier、design 未落地拦截）。
违规 SpecCompileError → exit 2。load_yaml 依赖 PyYAML（本地 python3 无 → 必须 win_py）。

- **具名锚点（scansci 内化块 1）**：shape `anchors` = {名: [nx, ny]}，nx,ny ∈
  [0,1]² 归一坐标（相对 rect）；glue `from_anchor`/`to_anchor` 可缺省（回退 AABB
  边中点），声明则**须成对**（单端具名 → exit 2：消除「半具名」glue——G5/G6
  豁免与 G10 覆盖的前提不变量），锚点名必须存在于端点元素 anchors。
- **编辑单元（scansci 内化块 2）**：`relations.edit_groups` = [{id, members}]；
  组 id 非空、members 非空列表、成员须为**顶层产生形状的元素**（stack/dock/graph
  容器拒绝——不产单形状，group:true 容器自动并入无需声明）、**跨组重复成员
  禁止**（编辑单元原子性：一个元素只属一个组）。
- **cilinder 契约**：`slice`/`opacity`/`face_opacity` 仅 cylinder 支持（其余 kind
  带它们 → exit 2）；`face_opacity ≤ opacity` 无解（端面无法比底层更透）→ exit 2。
- **行内富文本（A2）**：元素 `text`、table 单元格、graph 节点 text / 边 label /
  组 label 均过 `richtext.parse` 语法闸门——`**加粗**` / `[[强调]]` 可嵌套
  （`**[[…]]**`），`{{UnicodeMath}}` 为文本内公式（写进当前文本框，同行=
  行内式 / 独占一段=显示式）；**未闭合 / 空标记 / 嵌套 [[ ]] / 交叉 /
  公式嵌套在加粗强调内** → exit 2（fail-closed：不把标记字符原样渲染到
  幻灯片）。富文本解析只做一次（compile 校验 → IR plain+runs，切段形态由
  `richtext.paragraphs` 在渲染/物证阶段共用）。
- **能力档案（capabilities.py 消费，EasySlides 借鉴）**：PAGE_INTENTS /
  PAGE_INTENT_FIELDS / PAGE_INTENT_EL_IDS 由注册表派生（消重复字面量）；
  **planned 页型编译拒**——`page_intent: data/compare/conclusion/quote` →
  "尚未落地（status=planned）" exit 2（此前静默无展开，潜伏 no-op）；
  **intent 字段 dict 同步强制**——`cover:`/`section:` dict 与 page_intent 双向
  校验：dict 出现却无 intent、或 intent 声明却缺 dict → 均 exit 2（此前一半
  静默）；anchors/link/animation/edit_group/children（top_level_only）校验驱动
  自 ELEMENT_CAPS 能力带——容器/线/typst/curve 不支持即拒，不留"字段合法却
  什么也没发生"的 no-op（fail-closed，见 wiki/modules/capabilities.md）。
- **流程图方法论契约（A，graph_sig 签名基座消费；styleguides.flowchart.
  semantics 单一事实源）**：`style_guide: flowchart` 且横向 graph 时——节点数
  ≥ branch_min_nodes（默认 5）却无分支表达（无出度≥2 节点）= 全直线链
  （同质化主因）→ exit 2「无分支表达」；真线性流程显式 `linear: true` 逃生
  （不误伤合法直线）、vertical（组织树）豁免、非 flowchart 豁免。`variant`
  枚举校验（snake 蛇形）。见 references/flowchart-method.md 与
  tests/test_graph_contract.py。
- **页级校验**（多页模式 `slides[i]`）：每页元素存在性/唯一 id（页内作用域）、
  relations 页内自洽、页级 `params` 类型（`_check_params`：深校验，page_offset
  强类型 int）、页级 `framework` 键级合并、`anim` 页级编排组
  （`check_anim_groups`，AgError → SpecCompileError：模式/trigger/start/gap/items
  类型、成员存在且**带 animation**、容器与 cylinder 引用拦截、重复成员）、
  页级 `transition` 有效值解析（显式优先于全局，effect/spd 枚举）。
- 编译产物每页 dict 透传 `params`/`anim`/`brief`/`transition` 供后续 stage 消费。- **书法矢量字（C3，`type: brush`）**：`_check_brush`——text 必填非空（字形源）、
  font 必填（别名 kai/hei/song/fang/yahei 或 .ttf/.ttc 路径）、align ∈ left|center|right、
  anchor ∈ top|middle|bottom、spacing ≥0（em 比例）；`style` 白名单 = fill/grad/image/alpha，
  **fill 与 image 互斥**（填充二选一），grad 须两色列表，image 路径相对 SPEC 目录解析
  且**必须存在**（fail-closed，编译期写回绝对路径）。`brush` 专属 `style` schema 走
  独立分支（与 chart/curve 同，不在通用 `_check_style` 白名单）。
- **矢量图标（B1，`type: icon`）**：`_check_icon`——icon 必填非空（名/关键词字符串；
  未命中不报错，渲染期 `icon_lib.resolve` fail-soft 回退 circle-dot）、align/anchor 枚举；
  `style` 白名单 = color/weight（描边语义，weight>0）。`icon` 专属 `style` schema 走
  独立分支（与 brush/chart/curve 同，不在通用 `_check_style` 白名单）。
- **切换效果（C3）**：`transition.effect` 枚举加 `morph`（fade/push/wipe/cut/morph/none）；
  `dur` 仅 morph 可声明（毫秒 100~5000），非 morph 带 dur → exit 2。
