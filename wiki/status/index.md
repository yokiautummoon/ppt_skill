---
tags: [status]
module: root
parent: root
updated: 2026-10-18
---

# 当前进展

- **变体家族完成**（2026-10-18，防刻板第二块地基）：每 intent 一族审定变体
  （`scripts/intents.py::FAMILIES` —— cover: left/band/split；section:
  num_left/num_giant/band；problem/versus/route 单变体预留）。选型确定性
  （`plan`：SPEC `variant` 显式优先，缺省按同 intent 出现次序轮换）。**`intent:变体`
  即页面签名** → `verify._layout_page_sig` / `report._layout_sig` 对 intent 页返回该
  签名 → intent 页纳入 A1 版式多样性门禁（**不再豁免，堵"引擎展开逐页相同无人拦"
  盲区**）。`spec_compile` 校验 `variant` 成员（未知/跨 intent → exit 2）；
  `capabilities.PAGE_INTENT_VARIANTS` 快照（漂移断言背书）。示例
  `examples/pageintent/variants.yaml`（cover split + 三 section 自动轮换 + 内容对照，
  5 页 100/100）。语法/家族表/断言见 references/page-intents.md §9。
- **B1 矢量图标库完成**（2026-10-17，决策 2026-10-17-ppt-studio-absorption.md）：
  `type: icon` —— Lucide 图标（`assets/icons/lucide.json` 1857 枚，ISC）→ 原生
  `a:custGeom` 描边形状。新模块 `scripts/icon_lib.py`（名/中文关键词/英文标签解析，
  未命中回退 circle-dot；subpaths → 子路径 + 24×24 viewBox + 实心索引）+ `scripts/svgpath.py`
  （SVG path/图元解析，Q/T 与椭圆弧 A 转三次贝塞尔，纯 stdlib）。ir_builder `_emit_icon`
  正方适配声明盒；render `_render_icon` + `_set_custgeom_stroke`（**逐子路径** a:path：
  描边 fill=none / 实心 fill=norm + 形状级 a:ln 圆头描线——与 brush 单 path 填充相反）。
  物证 §4.4c；示例 `examples/icon` 2 页 110/110。**A/B 档内化 + C1/C3 视觉补充全链收官。**
- **ppt-studio 借鉴批次 1 完成**（2026-10-17，决策 2026-10-17-ppt-studio-absorption.md）：
  - A2 **富文本标记** `**加粗**` / `[[强调]]` 全链：richtext 解析（嵌套
    `**[[…]]**`、交叉拒绝）→ 编译校验（element/table/graph label）→ IR 存
    plain + runs → 多 run 渲染（强调色 style.emphasis）→ 逐 run 物证。
  - A1 **跨页版式多样性**：非标题视觉主体（4×3 网格, S/M/L, 类型）签名；
    多页阈值分级（min_distinct / distinct_ratio / max_same）。**page_intent 页
    以 `intent:变体` 签名参与（2026-10-18 变体家族：不再豁免——见下）。**
  - A3 **量化设计规范**：styleguides.QUANTITATIVE 可读副本 + verify S10 排版
    断言（强调密度/标题字数/正文密度/标题字号，advisory）；判定阈值归
    params.verify.typography / layout_variety；人读版 references/design-norms.md。
  - B2 **设计 DNA**：template_analyzer 逐页统计字号/字族/文字色/形状构成 +
    图片/表格/图表数，stylecard.md 增加「设计 DNA」段。
- **JAnim 三性质内化完成**（2026-09-14，性质①②③）：
  - ① **动画编排组**（anim_group）：SPEC 页级 `anim: {mode: succession|aligned|group,
    items: [...]}` 声明式时间轴 → 引擎确定性展开（subtraction 导出 delay、全局按
    start 稳定排序 AddEffect 序、块锚定、时间一致性断言 TIMELINE_EPS=1e-4）→ COM
    按序构造 + 回读 TriggerDelayTime 比对（0.02s WARN）。示例
    examples/animation/anim_group.yaml 28/28；单测 12 项。
  - ② **半透明层叠加反解**（alpha_math）：`merge = 1−∏(1−αi)` / `apart`
    闭式反解 / `face_alpha`；cylinder 侧壁 + 端面叠区保真
    （face_a 反解使合成值 = 声明 face_opacity，全链 40/40 物证不变），
    verify S7 独立重算断言（两套代码路径）。单测 9 项。
  - ③ **配置栈**（params.py resolve/layer_merge）：统一链 DEFAULTS → meta.params
    → slides[i].params → CLI `--param`（last-wins）；页级 p 穿透
    ir_builder/verify/render(pps)/物证全链路；未知键编译错、层间不污染。
    单测 10 项。
- **typst 最小边界盒围切**（2026-09-14）：stage1.5 编译后按内容 bbox 自动围切
  （PNG 裁空白 / SVG 重写 viewBox）→ 元素实际 rect = 声明原点 + 内容偏移、
  尺寸 = 内容 bbox（铁律 1 排版块对应物）；修复示例公式顶部缺失/底部空白。
- **typst 复杂精美排版链路完成**：`type:typst` → 官方 CLI 编译 SVG+PNG 双产物 →
  渲染层 svgBlip 2016+ 双通道注入 → 物证逐块核对。示例聚焦复杂排版：**整页个人
  简历**（examples/typst 1 块 7/7；双栏侧栏/时间线/点阵评级/标签胶囊，设计语言
  移植官网 impressive-impression；preamble 显式 `#set page` → 视图与 rect 1:1
  不围切；meta.brief 数据红线示范）。
- **--fix 自优修订链完成**（决策 self-improve-loop.md v2）：违规归因三类 → 机械
  默认动作 R1–R4 + LLM 作业模式（exit 6 稳态暂停）→ revisioner 事务应用 +
  fix.diff + `.snap.N` 回滚；meta.brief 数据红线落地。
- **页型意图 page_intent 完成**（审定菜单 7 枚举 + cover 27/27 + section 25/25 +
  **科研三件套 C1** problem/versus/route，examples/research 3 页 63/63）。
- **C3 视觉补充完成**（Morph 平滑切换 `transition.effect=morph`——`mc:AlternateContent`
  兼容包 p159:morph 跨页同名补间；书法矢量字 `type: brush`——字形→原生 custGeom
  单形状 [单 a:path 保内孔镂空+三态填充]，图片填充文字 = 形状级 blipFill，换机不丢
  字形；新模块 ink_text.py；examples/ink 2 页 41/41）。
- **cylinder/curve 积木完成**（复合圆柱 + freeform + 虚线，examples/method 40/40）。
- **动画集成完成**（35 宏配方 + COM 实时构造 9/9 自检 ok + 编译期校验；
  官方向导脚本 anim_inject.py 批量页级动画注入）。
- **交付五件套在案**：notes / transition / link / pageoffset / PDF + closure
  总验收 6 页；**渲染默认规则**（render_guards 断言背书：颜色一致性 / 居中优先 /
  自然排列 / 制图选型——示意图首选 typst，其次组合 Office 形状）。
- 全测试绿：突变 184/184、回归 33/33、anim_group 12/12、alpha_math 9/9、
  params 配置栈 10/10、typst 11/11（含围切 3 项）、模板 46/46、分析器 14/14、
  渲染守卫 5/5、图面契约 38/38、排版规则 test_deck_rules 47/47（含变体家族 + 设计体检）、
  test_capabilities 110/110、COM 自检 7/7（需 Office）、修订链 run_fixer 5/5 + 单测 7/6/4、
  图片占位 25/25、字体嵌入 15/15、溢出回读 9/9。

## 已知缺口

- 动画编排组 / 35 宏全量真验：首轮仅验 8 个代表宏，余 27 宏构造未逐一 Office
  复核；动画播放终态与 anim-group 时间轴目视复核待做（属用户行为）。
- cylinder/curve、page_intent 封面/节页/科研三件套、**变体家族示例
  （cover band/split、section num_giant/band 观感）**、typst 示例（矢量放大不糊 /
  右键 "转换为形状"）、C3 书法/Morph、B1 图标示例均待目视复核。
- 其余 4 页型（data/compare/conclusion/quote）仅枚举白名单在场，
  展开/断言待按 recipe 落地；problem/versus/route 变体族当前单变体（预留扩展）。
- LLM 修订链未接真实 API：--llm-client 直连预留，当前作业模式由 agent 回填；
  typst `design` 字段 LLM 辅助设计通道未落地（协议已文档化，CLI 待实现）。
- ppt-studio 借鉴（A/B 内化 + C1/C3 视觉补充）**全部批次已落地**；无剩余批次。