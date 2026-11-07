---
tags: [module]
module: verify
parent: build_ppt
depends_on:
  - textmesh
  - layout_rect
  - alpha_math
updated: 2026-10-09
---

# verify — G/T/D/S 四家族断言

G 几何（重叠/锚点/包络/图面/安全区）、T 文本（空/溢出）、D 容器（同层同高/账目）、
S 规范（ladder 单调/色数/构件/page_intent 破格）。违规 → exit 3；report.md 记家族与原因。

- **S7 叠区保真**（`_s_cylinder_alpha`，性质②）：对每个 cylinder 按部件 id 精确匹配
  `eid.side`/`eid.bot`/`eid.top`（不用 regex），独立重算
  `alpha_math.merge_alpha([side_a, face_a])` ≈ 声明 `face_opacity`（ε=EPS=1e-3），
  两条（bot+top）记「cylinder {eid} 端面{fk} 叠区保真」——校验器与布局器两套
  代码路径（verify 不信任单一实现，与 G 家族锚点重算同哲学）。
- 动画编排组时间一致性由 anim_group 编译期断言（ir_builder 消费），
  运行时回读比对在 com_layer `_check_timeline_after`。
- 按页取 p（`shim["_p"]`）：G/T/D/S 各断言阈值/字号硬底等参数旋钮可页级覆盖。
- **G10 具名锚点一致（scansci 内化块 1）**：具名锚点 glue（IR 含 `an1`）端点 =
  元素 anchors 绝对位（第二实现 `_abs_compiled_anchors` 从 compiled 归一坐标 +
  SPEC 原位 rect 重算，不读 IR 现成值），a1/a2 双端 ±eps 比对；此类 glue
  豁免 G5/G6（磁吸 AABB 判据不适用），编译期成对强制保证 an1 ⟹ an2。
- **G4 第三源 + G11（scansci 内化块 2）**：遮挡合法来源三类 = 同 owner /
  relations.overlap 声明 / **同编辑单元**（`ir.edit_groups` 成员互遮 = 组内构图）；
  G11 编辑单元区间独立重算——组成员 z 连续（hi−lo+1 = 成员数）且区间内无外部
  元素（z 收拢算法 bug 即违规，internal 停机）。
- **S8/S9 排版规则（scansci 内化块 3，styleguides 可选键，缺省不启用）**：
  `size_fs_floor` 小尺寸字号下限（元素 rect 短边 < threshold in → fs ≥ floor，
  角色豁免 lab/caption/note/units/foot/hdr/ftr/meta 与带 owner 者）；
  `labels_follow` 标签组织（`.label` 后缀文本须与目标同 owner 或同编辑组）。
- **契约背书（capabilities.py COMPONENT_CONTRACTS，EasySlides 借鉴）**：各积木/
  页型契约的 `invariants` 子串即本文件的断言检查名（如 `cylinder `、`表格格`、
  `stack 账目`、`dock 账目`、`节点`、`页型 cover 必需`、`cover 破格度`、
  `pages 贯穿度`、`section 字号层级`…）——`tests/test_capabilities.py` 逐个
  核对子串在本源码在场，背书不是空话；新增断言后同步契约表（反之亦然）。
- **页型意图破格断言（S6）**：`_s_page_intent` 按 `page_intent` 分发
  `_s_intent_cover/_s_intent_section/_s_intent_problem/_s_intent_versus/
  _s_intent_route`——每原型 = 必需构件 + **反向破格断言**（problem 贯穿度与
  左对齐、versus 双栏均衡/分色/中缝对称、route 阶段等步距/横向贯穿；
  cover 破格度、section 贯穿度与字号层级）。把"破格"修正回刻板即触发 exit 3。
- **C 跨页图去重**（`check_graph_dedup`，多页模式；graph_sig 拓扑签名 = 节点数
  + kind 直方图 + 出/入度直方图 + 最长链，与 id/文案无关）——复杂图（≥
  styleguides.flowchart.semantics.branch_min_nodes）签名跨页相同 → `图重复 sig`
  违规（exit 3，attribution advisory：改拓扑或主题）；简单图 / `linear: true`
  逃生图不判（阈值分级防误杀 + 显式授权）。由 build_ppt 页验证后注入对应页
  Report。见 references/flowchart-method.md 与 tests/test_graph_contract.py。
- **G12 连线不得盖节点文字（连线治理，2026-10-09 决策）**：graph 容器内任
  一边线段**实际穿越**某同图非端点节点盒时（`segment_rect_overlap`，深入
  穿越判定）→ 边 z 必须 < 节点 z（节点盖线）。**按实际穿越对断言而非全局
  "边<节点"**——编辑组收拢（`_coalesce_edit_groups`）压缩成员 z 到低段而边
  保持 1000+，全局判即误杀 group:true 容器。违规 = internal 停机（布局类序
  bug）。见 wiki/decisions/2026-10-09-line-governance.md。
- **G13 回边绕行不穿节点**：目标层 ≤ 源层的图边（水平布局，层号
  `_bfs_layers` 独立重算）不得穿越同图非端点节点盒——回边默认走走廊
  （layout_graph `way=orth`），残留穿越 = 显式 `way: straight` 或走廊受阻
  回退 → 违规（internal：改拓扑或扩面板）。前向边放行（节点 z 盖线，可接受）。
  见 wiki/decisions/2026-10-09-line-governance.md。**显式 `way: straight` 优先**：
  layout_graph 不静默改写作者意图（仅默认直线遇穿越才自动改走廊），残留穿越
  交本断言拦截。
- **S10 排版规范（A2/A3 内化，`_s_typography`）**：逐页核
  ① `[[强调]]` run 数 ≤ `verify.typography.max_emphasis`（重点不泛滥）；
  ② 标题字数（title/cov_title/sec_title；CJK 计 1、纯西文 2 字符计 1）
  ≤ `max_title_cjk`；③ 非标题正文 CJK 字数 ∈ [`body_chars_min`,
  `body_chars_max`]（下限默认关闭）；④ 标题 `text_layout.fs` ≥ `title_fs_min`
  （默认关闭，推荐 24–32）。全部 advisory（信息取舍是语义裁定），阈值见
  references/design-norms.md。
- **C2 版式多样性（A1 内化，`check_layout_variety`）**：多页模式跨页断言。
  版式签名 = 非标题视觉主体的（4×3 网格落位, 尺寸档 S/M/L, 类型/子类）排序
  元组——换文案/换配色不改签名；小面积装饰与 line 不参与。内容页数
  ≥ `min_pages`（默认 5）才判：不同版式数 ≥ max(`min_distinct`,
  ⌈页数×`distinct_ratio`⌉)，同一签名最多 `max_same` 页（默认 3）。页型意图页
  （cover/section）不参与内容版式统计。由 build_ppt 注入对应页 Report；
  attribution advisory（换骨架/并页）。