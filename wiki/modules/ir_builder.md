---
tags: [module]
module: ir_builder
parent: build_ppt
depends_on:
  - textmesh
  - params
  - layout_rect
  - richtext
updated: 2026-10-09
---

# ir_builder — 布局中间表示

几何/锚点/z 唯一真相源（铁律 1）：顶层 rect 直通、容器求解（layout_stack/dock/graph/rect
四个 layout_* 模块消费）、唯一 z 出口（声明序/z_override/容器内阶梯，冲突顺延）、
owner 树、text autofit、glue 端口锚点。产物 IR 是渲染层唯一消费物。布局/锚点/z
只在这里定，渲染与 COM 绝不重算（铁律 1）；按页取 p（`shim["_p"]`，见 params 配置栈）。

- **行内富文本（A2）**：`_apply_text` 调 `richtext.runs_if_markup` 只解析一次——
  IR 存 `text`（plain，供测量/文本断言）与 `runs`（`[{text,bold,emph}]` 或
  `[{formula,expr}]`，仅有标记时）；`{{公式}}` 段进入 runs，渲染/物证用
  `richtext.paragraphs` 判行内式/显示式；无标记保持旧 IR 结构（零行为变化）。`_emit_basic` table 单元格
  plain 进 `data`、有标记才进 `cell_runs`（矩阵同形）；graph 节点/边标签/
  组标签先转 plain 再交 layout_graph（排版量测不吃标记字符），emit 时把 runs
  挂回对应元素（`_emit_edge_label` 返回元素）。**渲染层只消费 runs，不重解析**
  （铁律 1：解析一次）。
- **cylinder 复合展开 + alpha 反解**（`_emit_cylinder`，性质②）：展开为 5~6 部件
  半透明侧壁 `eid.side`（alpha=声明 `opacity`）+ 顶/底椭圆 `eid.top/bot`
  （alpha=反解 `face_a`）+ 2 条等高弧 + 可选文字；`face_a =
  alpha_math.face_alpha(face_opacity, opacity)` 使叠区合成不透明度
  `merge([side_a, face_a]) = face_opacity`（声明目标），避免叠区过度深色；
  face_opacity 缺省 1.0 → face_a=1.0 实色向后兼容；无解 → ValueError
  （spec_compile 已拦 `face_opacity ≤ opacity`）。数学见
  wiki/modules/alpha_math.md 与 references/alpha-blend.md。
- **动画编排组展开**（`_expand_anim_groups`，性质①）：页级 `anim` 经
  anim_group.expand_group 展开为绝对秒时间轴，改写成员 `animation.trigger/delay`
  （delay 减法导出，负值降级 with_previous）+ 注出 `ir.anim_timeline`
  （leaves，绝对秒）与 `ir.anim_sequence`（AddEffect 全局按 start 稳定排序序）；
  时间一致性断言违反 → ValueError。见 wiki/modules/anim_group.md。
- **typst 自动围切**：`type:typst` 元素按 stage1.5 产物 bbox 重算实际 rect——
  实际 rect = 声明 rect 原点 + `_typst.offset`（内容偏移）、尺寸 =
  `_typst.size`（内容 bbox）；渲染层零重算，直接消费 `typst_size`。
- `type:typst` 透传 stage1.5 产物（`svg`/`png`/`typst_size`，缺失 → ValueError）。
- **具名锚点（scansci 内化块 1）**：`_abs_anchors(rect, anchors)` 把归一坐标
  [nx,ny]×rect 解成绝对位（英寸，round 3）；`_side_of` 由相对中心偏移导出端口
  （|nx|≥|ny| ↔ E/W，否则 N/S）；`_emit_glue` 有 `from_anchor`/`to_anchor` 时
  优先用锚点绝对位（`an1`/`an2` 键入 IR glue，G5/G6 豁免依据），省略回退
  LR.anchor_pair AABB；`_emit_basic` shape 透传 `el["anchors"]` 绝对位。
- **编辑单元（scansci 内化块 2）**：`_coalesce_edit_groups(compiled, out)` 把
  显式组 + 容器 group:true 并组（owner==cid 派生物）合成统一组表，按成员
  min_z 升序整块连续分配（组内保原 z 序、组间不交叠、非组员被占顺延），回写
  z 并注出 `ir.edit_groups` = [{id, members, z_lo, z_hi}]；z_max 保持含 glue 的
  旧最大值（框架层页眉/页脚置顶借 z_max，不因元素收拢塌陷）。
- **页型展开只处理 implemented**（build_ir 按 `meta.page_intent` 分发到
  `_expand_cover/_expand_section/_expand_problem/_expand_versus/_expand_route`；
  注册表 `capabilities.PAGE_INTENT_CAPS[*].expand` 记函数名供一致性背书）：
  planned 页型（data/compare/conclusion/quote）**编译期已拒**（spec_compile
  fail-closed，exit 2）——本层不具备兜底展开，遇未注册 intent 抛 ValueError
  （不静默跳过）；容器/线断言能力由编译期拦截后，本层无需再防御。
- **graph 形态旋钮（B）**：`variant: snake` 蛇形折返流——长流程按声明序两行
  双向（奇数行 L→R、偶数行 R→L），边一律 anchor_pair 直连（蛇形无"同层
  走廊"语义）；效果 = 同结构输入也能出异视觉（同质化治理第三层，见
  references/flowchart-method.md）；`linear: true` 逃生直通布局（显式授权，
  布局不特殊处理）。
- **z 类序（连线治理，2026-10-09 决策）**：graph 容器内部 z 类基
  `_Z_CLASS = {"group_box": 10, "edge": 1000, "node": 2000, "group_label":
  3000, "edge_label": 4000}`——类基步长 1000 ≫ 类内索引步长 10（`_z_of`），
  任意边/节点数下类序稳定。不变式：组包络 < 边 < 节点 < 组标签 < 边标签，
  **节点必须严格高于边**（否则越层连线盖节点文字，G12 拦截）。旧步长类内=
  类间=10 直接相撞（边/节点 z 交错）——根因与布局层节点 rect 3 位统一圆整
  （与端口锚点 round 一致，消走廊竖线 0.0005" 悬入）见
  wiki/decisions/2026-10-09-line-governance.md。- **书法矢量字（C3，`type: brush`）**：`_emit_brush` 用 `ink_text.measure()` 取字形
  ink bbox（em 单位）→ 按 `min(w/w_em, h/h_em)` 等比缩放适配声明盒、按 align/anchor
  定位 → IR 元素（`brush{text,font,spacing}` + 字形紧密 rect）。几何唯一源仍在本层：
  声明盒 → 字形盒的适配只在此解一次，渲染层照常消费（不重算）。能力档案
  `capabilities.ELEMENT_CAPS["brush"]`（单形状 → 动画/链接/编辑组/锚点全支持）。
- **矢量图标（B1，`type: icon`）**：`_emit_icon` 经 `icon_lib.resolve` 把名/关键词
  归一（未命中回退 circle-dot）→ 24×24 视图盒按 `side = min(w, h)` **正方**适配声明盒、
  按 align/anchor 定位 → IR 元素（`icon: <名>` + 正方 rect）。几何唯一源仍在本层：
  声明盒 → 正方盒的适配只在此解一次，渲染层照常消费（不重算）。能力档案
  `capabilities.ELEMENT_CAPS["icon"]`（单形状 → 动画/链接/编辑组/锚点全支持）。
