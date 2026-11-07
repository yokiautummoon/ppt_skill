---
tags: [decision]
parent: root
status: done
updated: 2026-09-30
scope: 内化 scansci-svg 三块经验——具名锚点 / 编辑单元分组 / 排版风格规则；全链贯穿 SPEC→IR→verify→render→COM→物证
---

# 决策：内化 scansci-svg 经验到 ppt-builder（具名锚点 / 编辑单元 / 排版规则）

## 背景

2026-09-30 调研 `Rimagination/scansci-svg`（科研绘图 skill）。用户明确聚焦：**不模仿
SVG 制作，而是为本 skill 在 PPT 页面制作 Office 图形组合与文字排版上吸取有力经验**。
经澄清，确定内化三块（用户 2026-09-30 批准）：

1. **具名锚点系统**（连接锚点）——来源 scansci「对象锚点 + 连接配方 + 归属先由形态
   确定、不把器官自动吸附到最近线条」。
2. **编辑单元分组**（edit groups）——来源 scansci「三种组织分开判断（科学归属 /
   绘制顺序 / 编辑单元）」、「整个对象有具名组，内部按用户会一起移动的部件分组」。
3. **排版/风格规则沉淀**——来源 scansci「复杂度预算 / 识别性优先 / 标签随部件 vs
   图例独立」。

现状缺口（代码实证）：
- `glue` 锚点 = `LR.anchor_pair`（AABB 最近边中点）+ side 四向；COM 绑定靠
  `com_layer.SITE_BY_KIND`（kind+侧边 → 连接点 index，probe 实测回退表）。无
  「指定具体部位」途径。
- 组合仅容器级 `group:true`（`ir["com_group"]` → COM `Shapes.Range().Group()`）；
  任意非容器元素（图形+标签、cylinder 部件、玻璃/边框/高光）无编辑单元声明途径。
- styleguides 规则集（type_scale/color_max/palette/spacing/connector）无按尺寸
  字号下限与标签随部件规则。

铁律保持：几何唯一源 = ir_builder（include 锚点/组区间全部布局层解出）；渲染与
COM 零重算；verify 与布局器两套代码路径独立重算。

## 决策

### 块 3：排版/风格规则沉淀（先行，最小风险）

**styleguides.py 规则集新增可选键**，`verify._s_family` 消费（默认缺省不变，现有
style 卡不启用即无行为变化）：

- `size_fs_floor`：小尺寸元素字号下限——元素 rect 短边 < 阈值（pt，参数化）时
  `fs ≥ floor`。把「缩小后识别性优先、保留辨识特征」转为可断言规则（区别于
  min_fs 硬底：本规则按尺寸生效）。
- `labels_follow`：`.label` 后缀文本须与其目标同 owner 或同 edit_group（graph 边
  标签已满足；约束自由标签的组织）。

**references/copyediting.md** 补 scansci 经验条目：复杂度预算原则、图例/标签组织、
连接锚点使用指引、编辑单元语义（文档层面，不新增断言）。

### 块 1：具名锚点系统

**语法**（同步 `spec_compile` 两处 glue 校验点 858/1261 + 全局关系段 1120 同律 +
`spec_validator` 白名单）：

```yaml
elements:
  - id: reactor
    type: shape
    anchors:
      inlet: [0.0, 0.5]     # 归一坐标 [0..1]²，相对元素 rect
      outlet: [1.0, 0.5]
relations:
  glue:
    - from: pump
      to: reactor
      from_anchor: outlet   # 省略 → 回退现状 anchor_pair（向后兼容）
      to_anchor: inlet
```

编译期拦截：锚点坐标范围 [0..1]²；glue 引用锚点名必须存在于端点元素。

**IR**：元素带 `anchors`（绝对坐标 dict）；glue 带 `an1/an2`（锚点名）+ `a1/a2`
（= 锚点绝对位）+ `side1/side2`（由锚点位置推导所在边；锚点落在角点/边界歧义时
取最近边，非角点相切可任一——实施时定优先序并断言背书）。

**verify**：新增 G10「具名锚点解析一致」——glue 端点 = 元素 `anchors[an]` 绝对位
±eps（独立重算）；具名锚点 glue 豁免 G5/G6 的 AABB 边中点判据。

**渲染**：连接符端点 = 锚点绝对坐标（`_render_glue` 仅 a1/a2 取新值）。

**COM**：`BeginConnect` 站点选择仍按 side → `SITE_BY_KIND`（拖动跟随保持）；
锚点绝对位与站点位置偏差大 → WARN 披露（绑定失败保持坐标锚点直线，降级哲学
已有先例）。

**物证**：render_check_xml 对具名锚点 glue 端点断言 = 锚点绝对坐标（EMU eps）。

### 块 2：编辑单元分组

**语法**：新增 `relations.edit_groups` 段（与 overlap/z_override 同构）：

```yaml
relations:
  edit_groups:
    - id: window
      members: [glass, frame, highlight]   # 顶层元素 id
```

编译期拦截：成员须为顶层元素、跨组重复成员、组嵌套（先禁嵌套，YAGNI）。容器
`group:true` 自动并入 edit_groups（统一 COM 入口）。

**z 语义（关键）**：`alloc` 扩展——组成员 z 组内连续区间、组间区间互不交叠、
组区间参与全局序（容器 group:true 现状语义的泛化）。

**verify**：G4 遮挡合法源新增第三类「同 edit_group 成员互遮 = 合法」（玻璃/边框/
高光必然重叠）；新增 G11「编辑单元区间」——组成员 z ∈ [z_lo, z_hi] 且区间内全部
是组员。

**渲染/COM**：平铺渲染不变（成员 z 连续自然邻接）；com_layer 组合入口统一为
edit_groups + com_group：`Shapes.Range([members]).Group()`（现状逻辑泛化）。COM
Group 改变 spTree 结构 → 物证/目视复核（WARN 级；无 Office 时平铺验证照常跑）。

### 实施顺序与测试

顺序：块 3 → 块 1 → 块 2（z 语义最敏感殿后）。每块：单测（tests/run_mutations
扩展或独立 test_*）+ regression 示例（tests/regression.py 增例）+ wiki 模块页更新
（verify/ir_builder/spec_compile/spec_validator/render_pptx/com_layer/styleguides）。

## 取舍公开

- **锚点精度边界**：PPT 原生连接点位置由形状几何决定、无法自由指定——锚点绝对
  精确在渲染/物证层保证；COM 绑定就近站点 + 偏移 WARN。与「WARN 降级」哲学一致。
- **编辑单元 ≠ 不重叠**：同组成员可互遮（合法）；与 G4 的"同容器归属/overlap
  声明"并列第三类合法源。
- **edit_groups 禁嵌套**：先不设计树形编辑单元（YAGNI），需求出现再扩展。

## 后续迭代

用户约定：落地后实际使用发现问题再回馈迭代（本决策为 v1 基线）。

## 落地验收（status: done）

按 wiki/plans/2026-09-30-internalize-scansci-plan.md 三块全落地：

- 块 3 排版规则：styleguides 可选键 size_fs_floor / labels_follow（缺省关 =
  零行为变化）；verify S8/S9；tests/test_style_rules.py（8 用例）+ 突变注入。
- 块 1 具名锚点：elements.anchors（归一 [0,1]²）+ glue from_anchor/to_anchor
  成对强制；IR 锚点绝对位 + G10 独立重算；COM 绑定偏移 >0.25in WARN；
  _probe/anchors.yaml evidence 11/11。
- 块 2 编辑单元：relations.edit_groups 编译拦截（顶层形状/禁跨组重复）；
  ir `_coalesce_edit_groups` z 收拢（组内连续、组间不交叠、z_max 保 glue）；
  G4 第三源 + G11 独立重算；com 组循环泛化 + spTree 变更披露 WARN；
  _probe/edit_groups.yaml evidence 10/10。
- 测试：run_mutations 121/0 · test_scansci_compile 10/10 · regression 26/26
  · render_guards 全过 · test_style_rules 8/8。
- 已知边界：锚点绝对精确保证于渲染/物证层，COM 就近站点 + WARN（取舍公开）；
  edit_groups 禁嵌套（YAGNI）。