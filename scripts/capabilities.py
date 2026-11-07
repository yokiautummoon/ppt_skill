# -*- coding: utf-8 -*-
"""capabilities.py — 能力档案注册表（fail-closed 声明单一事实源）。

借鉴 EasySlides 的 capability profile：每个可复用单元（元素类型 / 页型原型 /
复合积木）在此**显式声明它支持什么**。不支持的能力在编译期（exit 2）拒绝——
宁可编译报错，也不留"字段合法却什么也没发生"的静默降级。

三张表（纯数据，无逻辑；断言由 spec_compile / verify 消费）：
  ELEMENT_CAPS        元素类型 → 能力旗标（能否动画/挂链接/具名锚点/进编辑组…）
  PAGE_INTENT_CAPS    页型原型 → status（implemented/planned）+ 字段 + 展开 id
  COMPONENT_CONTRACTS 复合积木 → renderer 模块 + 必需字段 + 背书的 verify 断言

与既有白名单的分工：spec_compile 管"字段是否存在、类型对不对"（字段级）；
本模块管"这个单元**能不能**承接该能力"（能力级）。两者都 fail-closed，但层级不同。
"""
import os

# ---- 元素能力旗标 ----
# shape_producing    渲染层是否产出可命名单形状（容器 = False：只产 children）
# animatable/linkable/edit_group_member  单形状的派生能力（容器全 False）
# anchorable         能否声明具名锚点 anchors（须有可锚定的 rect；容器/线 False）
# top_level_only     必须顶层（不进容器 children）
# composite          展开为多形状 / 整块图（文档性：非单形状积木）
ELEMENT_CAPS = {
    "text":    dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=False, composite=False),
    "shape":   dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=False, composite=False),
    "image":   dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=False, composite=False),
    "diagram": dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=False, composite=False),
    "line":    dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=False,
                    top_level_only=False, composite=False),
    "formula": dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=False, composite=False),
    # table/chart/typst：rect 固定、整块产图/原生表 → 必须顶层（不进 children）
    "table":   dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=True,  composite=False),
    "chart":   dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=True,  composite=False),
    "typst":   dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=False,
                    top_level_only=True,  composite=True),
    "curve":   dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=False,
                    top_level_only=False, composite=True),
    # brush 书法矢量字（C3）：字形 → 单个 custGeom 形状（换机不丢字形）；
    # 产可命名单形状 → 动画/链接/编辑组/锚点全支持；rect 由 ir_builder 按 ink 适配
    "brush":   dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=False, composite=True),
    # icon 矢量图标（B1）：Lucide 图标 → 单个 custGeom 形状（描边语义，缩放不糊）；
    # 产可命名单形状 → 动画/链接/编辑组/锚点全支持；rect 由 ir_builder 正方适配
    "icon":    dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=True,
                    top_level_only=False, composite=True),
    # svg 矢量图（references/svg-figures.md）：整块多形状 → 必须顶层（不进 children，
    # 同 typst/chart 律）；产可命名单形状片 → 动画/链接/编辑组/锚点全支持
    "svg":     dict(shape_producing=True,  animatable=True,  linkable=True,
                    edit_group_member=True,  anchorable=False,
                    top_level_only=True,  composite=True),
    # 容器：不产单形状 → 动画/链接/编辑组成员/锚点全部不支持
    "stack":   dict(shape_producing=False, animatable=False, linkable=False,
                    edit_group_member=False, anchorable=False,
                    top_level_only=False, composite=True),
    "dock":    dict(shape_producing=False, animatable=False, linkable=False,
                    edit_group_member=False, anchorable=False,
                    top_level_only=False, composite=True),
    "graph":   dict(shape_producing=False, animatable=False, linkable=False,
                    edit_group_member=False, anchorable=False,
                    top_level_only=False, composite=True),
}

CONTAINER_TYPES = tuple(t for t, c in ELEMENT_CAPS.items() if not c["shape_producing"])

# ---- 页型原型能力档案 ----
# status: implemented（引擎展开 + 断言落地）/ planned（仅占名，编译即拒 —— fail-closed）
# fields: 该 intent 允许的专属字段白名单；ids: 展开产出的保留元素 id
# expand: ir_builder 展开函数名（None = 不产出专属构件，如 content 走默认版式）
# id_prefix: 展开产物为可变数量时（如 route 的逐阶段 rte_stage*, rte_stage 数量
#   = len(stages)），用保留前缀做冲突检测（非固定 id 集合）
PAGE_INTENT_CAPS = {
    "cover":      dict(status="implemented", expand="_expand_cover",
                       fields={"title", "subtitle", "meta", "accent", "variant"},
                       variants=("left", "band", "split"),
                       ids={"cov_title", "cov_sub", "cov_meta", "cov_deco"}),
    "section":    dict(status="implemented", expand="_expand_section",
                       fields={"num", "title", "accent", "variant"},
                       variants=("num_left", "num_giant", "band"),
                       ids={"sec_num", "sec_title", "sec_deco", "sec_guide"}),
    # 科研三件套（C1）：problem 问题陈述 / versus 对照 / route 技术路线——
    # 破格科研页族（references/page-intents.md §8，每原型 = 布局代码 + 断言）
    "problem":    dict(status="implemented", expand="_expand_problem",
                       fields={"title", "items", "accent"},
                       variants=("badge",),
                       ids={"prb_badge", "prb_title", "prb_items"}),
    "versus":     dict(status="implemented", expand="_expand_versus",
                       fields={"left_title", "right_title", "left_items",
                               "right_items", "vs", "accent"},
                       variants=("split",),
                       ids={"vsv_panel_l", "vsv_panel_r", "vsv_title_l",
                            "vsv_title_r", "vsv_body_l", "vsv_body_r",
                            "vsv_divider", "vsv_tag"}),
    "route":      dict(status="implemented", expand="_expand_route",
                       fields={"title", "stages", "accent"},
                       variants=("chain",),
                       ids={"rte_title"}, id_prefix="rte_"),
    "content":    dict(status="implemented", expand=None,
                       fields=set(), variants=(), ids=set()),
    # 内容页结构生成样板（内容处理转换律落地，references/page-intents.md §10）：
    # agent 只给结构化内容（items/cols/kpis…），网格/分栏/指标行/卡网格/图文
    # 布局由引擎确定性展开——"每页像被设计过"的引擎侧杠杆。
    "panels":     dict(status="implemented", expand="_expand_panels",
                       fields={"title", "items", "cols", "accent", "variant"},
                       variants=("even", "hero_left"),
                       ids={"pnl_title"}, id_prefix="pnl_"),
    "columns":    dict(status="implemented", expand="_expand_columns",
                       fields={"title", "cols", "bottom", "accent", "variant"},
                       variants=("even", "arrow"),
                       ids={"col_title"}, id_prefix="col_"),
    "kpis":       dict(status="implemented", expand="_expand_kpis",
                       fields={"title", "items", "accent", "variant"},
                       variants=("cards", "row", "rings"),
                       ids={"kpi_title"}, id_prefix="kpi_"),
    "cards":      dict(status="implemented", expand="_expand_cards",
                       fields={"title", "items", "cols", "accent", "variant"},
                       variants=("icon_top", "number", "icon_left"),
                       ids={"crd_title"}, id_prefix="crd_"),
    "figure_text": dict(status="implemented", expand="_expand_figure_text",
                        fields={"title", "image", "caption", "blocks", "side",
                                "accent", "variant"},
                        variants=("right", "left"),
                        ids={"fgt_title"}, id_prefix="fgt_"),
    "data":       dict(status="planned", expand=None, fields=set(),
                       variants=(), ids=set()),
    "compare":    dict(status="planned", expand=None, fields=set(),
                       variants=(), ids=set()),
    "conclusion": dict(status="planned", expand=None, fields=set(),
                       variants=(), ids=set()),
    "quote":      dict(status="planned", expand=None, fields=set(),
                       variants=(), ids=set()),
}

PAGE_INTENTS = set(PAGE_INTENT_CAPS)
PAGE_INTENTS_IMPLEMENTED = {k for k, v in PAGE_INTENT_CAPS.items()
                           if v["status"] == "implemented"}
PAGE_INTENT_FIELDS = {k: set(v["fields"]) for k, v in PAGE_INTENT_CAPS.items()}
PAGE_INTENT_EL_IDS = set().union(*[v["ids"] for v in PAGE_INTENT_CAPS.values()]) \
    if PAGE_INTENT_CAPS else set()
# 逐 intent 的保留 id 前缀（可变数量展开产物的冲突检测；无前缀 = None）
PAGE_INTENT_ID_PREFIX = {k: v.get("id_prefix") for k, v in PAGE_INTENT_CAPS.items()}
# 逐 intent 变体家族（机器源 = scripts/intents.py::FAMILIES；测试背书两者不漂移）
PAGE_INTENT_VARIANTS = {k: tuple(v.get("variants") or ())
                        for k, v in PAGE_INTENT_CAPS.items()}

# ---- 复合积木契约（component pack contract）----
# renderer  renderer 归属模块名列表（须为 scripts/ 下真实模块；测试背书）
# required  SPEC 必需键（测试背书：移除任一键 → 编译必须报错）
# invariants 该积木背书的 verify 断言 (verify 源码子串, 说明)——测试背书子串在场
# capacity  可选容量声明（文档性）
COMPONENT_CONTRACTS = {
    "cylinder": dict(renderer=["ir_builder", "render_pptx"],
                     required=["rect"], kind="shape",
                     invariants=[("cylinder ", "S7 端面叠区保真（alpha 反解闭合）")],
                     capacity={"shapes": 3}),
    # curve 为自由 polyline（非 orth 4 段折线），verify 无专属断言 → invariants 空
    "curve": dict(renderer=["ir_builder", "render_pptx"],
                  required=["rect", "points"], kind="element", invariants=[]),
    # brush 书法矢量字（C3）：字形 → custGeom；物证背书 4.4b（custGeom/单路径/三态填充）
    # 而非 verify 断言（渲染层产物，非几何）→ invariants 空
    "brush": dict(renderer=["ink_text", "ir_builder", "render_pptx"],
                  required=["rect", "text", "font"], kind="element",
                  invariants=[]),
    # icon 矢量图标（B1）：Lucide 图标 → custGeom；物证背书 4.4c（custGeom/逐子路径
    # 描边 fill=none/a:ln 圆头描线）而非 verify 断言（渲染层产物，非几何）→ invariants 空
    "icon": dict(renderer=["icon_lib", "svgpath", "ir_builder", "render_pptx"],
                 required=["rect", "icon"], kind="element",
                 invariants=[]),
    # svg 矢量图（references/svg-figures.md）：SVG → 原生 DrawingML custGeom 多形状
    # （可编辑矢量图，非位图）。语义由 svg_doc 解析 + 单测 tests/test_svg_doc.py 背书；
    # 渲染层产物 → invariants 空。
    "svg": dict(renderer=["svg_doc", "ir_builder", "render_pptx"],
                required=["rect", "src"], kind="element",
                invariants=[],
                qa="tests/test_svg_doc.py",
                capacity={"shapes": None}),
    # typst 整块为图（同 image/chart 级），不产可文本校验的形状 → verify 断言不适用；
    # 其语义由单测 tests/test_typst_compile.py 背书（svgBlip 双通道注入 / 围切）。
    "typst": dict(renderer=["typst_compile", "render_pptx"],
                  required=["rect"], kind="element",
                  invariants=[],
                  qa="tests/test_typst_compile.py",
                  capacity={"blocks": 1}),
    "table": dict(renderer=["ir_builder", "render_pptx"],
                  required=["rect", "data"], kind="element",
                  invariants=[("表格格", "T 家族：单元格文本 ≤ 单元格（列宽/行高 − 2×pad）")]),
    "chart": dict(renderer=["ir_builder", "render_pptx"],
                  required=["rect", "chart_type", "categories", "series"], kind="element",
                  invariants=[]),
    "formula": dict(renderer=["ir_builder", "render_pptx"],
                    required=["rect", "expr"], kind="element", invariants=[]),
    "stack": dict(renderer=["ir_builder", "layout_stack"],
                  required=["rect", "children"], kind="container",
                  invariants=[("stack 账目", "S5 栈账目：children 总尺寸 ≤ 容器")]),
    "dock": dict(renderer=["ir_builder", "layout_dock"],
                 required=["rect", "children"], kind="container",
                 invariants=[("dock 账目", "S5 坞账目：top/bottom 高和 ≤ 可用高")]),
    "graph": dict(renderer=["ir_builder", "layout_graph"],
                  required=["rect", "nodes"], kind="container",
                  invariants=[("节点", "D/G 家族：节点同高且 ⊆ 面板内容区")]),
    "cover": dict(renderer=["ir_builder", "verify"],
                  required=["page_intent", "cover"], kind="page_intent",
                  invariants=[("页型 cover 必需", "S6 封面必需构件（cov_deco/cov_title）"),
                              ("cover 破格度", "S6 破格度下限（反向断言，防回刻板）")]),
    "section": dict(renderer=["ir_builder", "verify"],
                    required=["page_intent", "section"], kind="page_intent",
                    invariants=[("页型 section 必需", "S6 节页必需构件（sec_deco/sec_num/sec_title）"),
                                ("section 贯穿度", "S6 贯穿度下限（大数字版面）"),
                                ("section 字号层级", "S6 字号层级（num fs > title fs）")]),
    # 科研三件套（C1）契约：problem/versus/route（references/page-intents.md §8）
    "problem": dict(renderer=["ir_builder", "verify"],
                    required=["page_intent", "problem"], kind="page_intent",
                    invariants=[("页型 problem 必需", "S6 问题页必需构件（prb_badge/prb_title）"),
                                ("problem 贯穿度", "S6 问题标记纵向贯穿下限"),
                                ("problem 左对齐破格", "S6 主问题左对齐（非居中破格）")]),
    "versus": dict(renderer=["ir_builder", "verify"],
                   required=["page_intent", "versus"], kind="page_intent",
                   invariants=[("页型 versus 必需", "S6 对照页必需构件（双面板/分割线/VS 标）"),
                               ("versus 均衡", "S6 双栏等宽（均衡下限）"),
                               ("versus 对称", "S6 分割线居中（对称破格）"),
                               ("versus 分色", "S6 双栏分色（对立着色）")]),
    "route": dict(renderer=["ir_builder", "verify"],
                  required=["page_intent", "route"], kind="page_intent",
                  invariants=[("页型 route 必需", "S6 路线页必需构件（rte_title/rte_stage*）"),
                              ("route 等步距", "S6 阶段等距推进下限"),
                              ("route 横向贯穿", "S6 阶段链铺满版心（横向贯穿）")]),
    # 内容页结构生成样板（references/page-intents.md §10）
    "panels": dict(renderer=["ir_builder", "verify"],
                   required=["page_intent", "panels"], kind="page_intent",
                   invariants=[("页型 panels 必需", "S6 面板页必需构件（pnl_title/pnl_panel*）"),
                               ("panels 网格贯穿", "S6 面板网格铺满版心"),
                               ("panels 面板等宽", "S6 面板网格等宽（even 变体）"),
                               ("panels 首板贯穿", "S6 首板全宽（hero_left 变体）")]),
    "columns": dict(renderer=["ir_builder", "verify"],
                    required=["page_intent", "columns"], kind="page_intent",
                    invariants=[("页型 columns 必需", "S6 分栏页必需构件（col_title/col_head*）"),
                                ("columns 栏组贯穿", "S6 栏组铺满版心"),
                                ("columns 分栏等宽", "S6 分栏等宽"),
                                ("columns 箭头在场", "S6 栏间箭头（arrow 变体）")]),
    "kpis": dict(renderer=["ir_builder", "verify"],
                 required=["page_intent", "kpis"], kind="page_intent",
                 invariants=[("页型 kpis 必需", "S6 指标页必需构件（kpi_title/kpi_card*）"),
                             ("kpis 指标等宽", "S6 指标卡等宽"),
                             ("kpis 数值层级", "S6 数值字号 > 标签字号（尺度对比）"),
                             ("kpis 行贯穿", "S6 指标行铺满版心")]),
    "cards": dict(renderer=["ir_builder", "verify"],
                  required=["page_intent", "cards"], kind="page_intent",
                  invariants=[("页型 cards 必需", "S6 卡片页必需构件（crd_title/crd_card*）"),
                              ("cards 网格贯穿", "S6 卡片网格铺满版心"),
                              ("cards 卡片等宽", "S6 卡片网格等宽"),
                              ("cards 顶饰在场", "S6 卡片顶饰（图标/编号）")]),
    "figure_text": dict(renderer=["ir_builder", "verify"],
                        required=["page_intent", "figure_text"], kind="page_intent",
                        invariants=[("页型 figure_text 必需", "S6 图文页必需构件（fgt_title/fgt_fig/fgt_body）"),
                                    ("figure_text 图文分栏", "S6 图/文左右分栏不重叠"),
                                    ("figure_text 破格占比", "S6 图侧宽 ≥ 版心×比（图文并置破格）")]),
}

RENDERER_MODULES = {m for c in COMPONENT_CONTRACTS.values() for m in c["renderer"]}

# ---- 设计语言层能力档案（meta.theme；事实源 scripts/themes.py）----
# 三键为 deck 级开关（缺省 uniform/none/sans_sans = 零行为变化），非 SPEC 必需键，
# 故不入 COMPONENT_CONTRACTS（其 required 语义为"必需键"）。此处声明枚举域 +
# 背书的 verify 断言子串 + 消费方；presets 与 themes.PRESETS 漂移断言（测试背书）。
THEME_CAPS = {
    "structure": dict(consume=["build_pages", "ir_builder", "verify"],
                      options=("uniform", "sandwich", "dark"),
                      default="uniform",
                      invariants=[("三明治深页全幅背景", "S8 深页 framework.background 在场"),
                                  ("三明治深页文字反色", "S8 深页文本浅色（反色正确）")],
                      note="sandwich=封面/节页深底、内容页浅底；dark 须配 mode=dark"),
    "motif":     dict(consume=["ir_builder", "verify"],
                      options=("none", "circle_icon"),
                      default="none",
                      invariants=[("母题背衬圆", "S8 每个 icon 有 _circ 背衬圆")],
                      note="circle_icon=图标加 accent 系圆形背衬（全篇重复母题）"),
    "font_pair": dict(consume=["themes"],
                      options=("sans_sans", "serif_sans", "serif_serif"),
                      default="sans_sans",
                      invariants=[],
                      note="serif_sans/serif_serif=衬线标题×无衬线正文（安全字体配对）"),
}

# 设计语言预设名（漂移断言：须与 themes.PRESETS 键一致）
THEME_PRESETS = ("nsfc_blue", "nsfc_navy", "nsfc_red", "nsfc_green", "nsfc_purple",
                 "modern_light", "midnight_executive", "forest_moss", "coral_energy",
                 "warm_terracotta", "ocean_gradient", "charcoal_minimal", "teal_trust",
                 "berry_cream", "sage_calm", "cherry_bold")


def caps(etype):
    """元素类型 → 能力旗标（未知类型返回 None）。"""
    return ELEMENT_CAPS.get(etype)


def supports(etype, ability):
    """该类型是否支持某能力（未知类型 = False，fail-closed）。"""
    c = ELEMENT_CAPS.get(etype)
    return bool(c and c.get(ability))


def intent_caps(intent):
    return PAGE_INTENT_CAPS.get(intent)


def intent_implemented(intent):
    c = PAGE_INTENT_CAPS.get(intent)
    return bool(c and c["status"] == "implemented")


def renderer_modules_exist(scripts_dir):
    """renderer 声明的模块名是否都在 scripts/ 下真实存在（测试背书）。"""
    return {m for m in RENDERER_MODULES
            if not os.path.isfile(os.path.join(scripts_dir, m + ".py"))}
