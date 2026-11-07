# -*- coding: utf-8 -*-
"""params.py — 数值接口化单一事实源（skill 工程铁律：引擎核心无散落硬编码数值）。

设计原则：
  1. 一切可调数值（magic number）都收敛到 DEFAULTS 字典，键名即参数契约。
  2. SPEC 的 meta.params: 可覆盖任意键（agent 可操控旋钮）。
  3. 优先"自适应公式"：能从输入推导的量（面板/字量/节点数）不写死。
  4. 单位：长度一律英寸(in)，字号一律磅(pt)，由 layout_rect 负责换算。
"""
import copy

DEFAULTS = {
    "slide": {"w": 13.333, "h": 7.5},

    # ---- 字族双轨（latin + ea=东亚；模板 extract 的 stylecard fonts 会 setdefault 进这里）----
    "font": {
        "latin": "Calibri",        # 西文字族（renderer 每 run latin typeface）
        "ea": "微软雅黑",           # 东亚字族（NameFarEast 双轨）
        "title_latin": "Calibri Light",
        "title_ea": "微软雅黑",
        "title_bold": False,       # 标题角色默认不加粗
        "title_fs_min": 24.0,      # fs ≥ 此值即标题角色（用 major 字族；大文本 = 标题）
        # B5 字体可移植：请求 COM 端 EmbedTrueTypeFonts（须 Office；--embed-fonts）
        # portable_list = 交付前需人工确认在目标机可用的字族清单（记录进日志/报告）
        "portable": False,
        "portable_list": [],
    },

    # ---- 文本测量（实测：微软雅黑/Calibri，见 references/text-measurement.md）----
    "text": {
        "em_cjk": 1.00,       # CJK 字符 em 宽系数（vs 字号）
        "em_asc": 0.54,       # ASCII 字符 em 宽系数
        "line_h": 1.2,        # 行高 = line_h × fs
        "margin_w": 1.03,     # 逐字符累加 vs 整行 BoundWidth 的 2~3% 误差余量
        "autofit_iters": 4,   # autofit 迭代上限
        "min_fs": 4.0,        # 字号硬底（防缩至不可读；再超框即 FAIL 由 T 家族拦）
        "fs0_node": 12.0,     # 节点起始字号（style_guide.node 下限可覆盖）
        "fs0_block": 18.0,    # 顶层文本/形状文本起始字号（agent 未声明 fs 时）
        "edge_label_fs": 9.0, # graph 边标签起始字号
        "notes_fs": 12.0,     # 备注页字号（meta.notes / slides[i].notes 渲染）
        # 类型尺度（deck 级）：text_style.scale 角色 → 起始字号(pt)。主题派生覆盖；
        # 逐元素 fs 仍优先（scale 只供 fs0 缺省）。ir_builder._apply_text 消费。
        "scale": {"hero": 54.0, "title": 36.0, "subtitle": 24.0,
                  "body": 18.0, "caption": 12.0},
    },

    # ---- 设计语言 / 主题（deck 级几何；几何唯一消费路径见下，铁律 1）----
    # 主题（meta.theme）经 spec_compile 下降到此组（配置栈最低层；作者可覆盖）。
    # 刻意只保留有真实消费路径的键——死键不入面（曾误列 title_y/title_h/
    # content_top/content_bottom/gap/card_style/bg_style，均无消费方，已删）：
    #   margin      → build_pages 打底 meta.margin（版心留白；未声明 margin 时才用）
    #   card_radius → themes._overlay 同步写 style.rounded_radius（render_pptx 消费）
    "theme": {
        "margin": {"l": 0.5, "t": 0.45, "r": 0.5, "b": 0.45},  # 版心边距(in)
        "card_radius": 0.10,   # 圆角卡母题（占短边比例；镜像自 style.rounded_radius）
        # 结构/母题（meta.theme 下降）：消费方 = build_pages（三明治逐页 bg）/
        #   ir_builder（母题背衬圆）。缺省零行为变化。
        "structure": "uniform",   # uniform|sandwich|dark
        "motif": "none",          # none|circle_icon
        "motif_circle_scale": 1.45,  # circle_icon 背衬圆直径占图标边长比例
        "motif_circle_tint": 78,     # 背衬圆填充 = accent 向白提亮此百分比
    },

    # ---- 样式默认（renderer 无魔法色：未声明即取此表）----
    "style": {
        "fill": "#DCE9F7",        # 形状默认填充（浅蓝）
        "border": "#1F2A44",      # 形状默认描边（深蓝灰）
        "text_color": "#1F2A44",  # 文本默认色
        "emphasis": "#C00000",    # 行内强调色（[[...]] 标记，richtext 链）
        "text_color_dark": "#F2F2F2",  # 深底页文字反色（structure=sandwich/dark 消费）
        "line_color": "#1F2A44",  # 连线默认色
        "line_weight": 1.5,       # 连线默认磅值
        "icon_weight": 1.5,       # 矢量图标（icon）默认描边磅值
        "accent": "#2D6CDF",      # 全局强调色（cover 页型 deco/副标题等引擎展开用）
        "group_fill": "#F2F5FA",  # graph 组包围盒填充
        "group_border": "#8FA3BF",# graph 组包围盒描边
        "shadow": True,           # 形状默认投影
        "rounded_radius": 0.10,   # 节点圆角占短边比例（adjustments[0]）
        "group_radius": 0.05,     # 组包围盒圆角比例（adjustments[0]）
        "group_line_w": 1.0,      # 组包围盒描边磅值
        "body_fs_min": None,      # 正文下限覆盖（pt）：None = 用 styleguide body 下限；
                                  #   显式数值 = 作者降准（功能演示/密集表格可用）；
                                  #   verify S1b 消费（copyediting §字号分层契约的例外通道）
    },

    # ---- 边标签排版（graph 边 label 几何）----
    "label": {
        "pad": 0.03,      # 标签文本内边距(in)
        "min_w": 0.2,     # 标签最小宽(in)（防极短段）
        "h_cap": 0.30,    # 标签高上限(in)；行高取 autofit need_h
        "rise": 0.015,    # 折线上方标签上移量(in)
        "seg_floor": 0.4, # 直连线水平段长度下限(in)（标签宽基准）
    },

    # ---- 组标签排版（graph groups label 几何）----
    "group_label": {
        "h_cap": 0.25,    # 组标签高上限(in)；行高取 autofit need_h
        "min_w": 0.3,     # 标签最小宽(in)
        "pad_w": 0.06,    # 宽侧文本内距(in)
        "pad_h": 0.04,    # 高侧文本内距(in)
        "off_x": 0.08,    # 距包围盒左缘(in)
        "off_y": 0.04,    # 距包围盒上缘(in)
    },

    # ---- 图面板(graph 容器) ----
    "graph": {
        "inner_margin": 0.18,      # 面板内容区内壁距
        "gutter_ratio": 0.18,      # 行/列间距占层步长的比例（自适应：面板大→间隔大）
        "min_abs_gap": 0.08,       # 相邻节点最小绝对间隔(in)，文本挤迫时的下限
        "group_pad": 0.3,          # 组包围盒外扩(in)
        "node_h_default": 0.75,    # graph 节点缺省高(in)（SPEC 容器 node_h 可覆盖）
        "node_w_default": 1.2,     # graph 节点缺省宽(in)（组织树垂直布局；SPEC node_w 覆盖）
        "shape_text_fit": {        # 非矩形节点：文本可用区 = 外接矩形 × 内切比例(宽,高)。
            # 菱形/椭圆/圆柱的顶点与边角不可容纳文本，autofit 与 verify 共用此表
            # （菱形理论内接矩形 0.5×0.5，取 0.6 稍放宽容错；椭圆 ≈√2/2≈0.71；圆柱顶被椭圆占据）
            "diamond": (0.60, 0.60),
            "oval": (0.72, 0.72),
            "can": (0.92, 0.80),
        },
    },

    # ---- 正交路由（回边）----
    "route": {
        "bend_clearance": 0.10,    # 折线走廊距参考 AABB 的最小净空(in)
        "corner_pad": 0.15,        # 走廊水平段两端竖直段的水平余量(in)
    },

    # ---- z 阶梯 ----
    "z_gap": {
        "edge_label": 1,           # 边 → 盖线标签
        "label_group": 10,         # 盖线标签 → 组容器
    },

    # ---- 校验 ----
    "verify": {
        "eps": 1e-3,               # 浮点边界容差(in)
        # ---- A1 版式多样性（多页序列；页型意图页不参与内容版式统计）----
        "layout_variety": {
            "enabled": True,
            "min_pages": 5,        # 内容页数 ≥ 此值才断言（少页天然不重复）
            "min_distinct": 3,     # 至少不同版式数
            "distinct_ratio": 0.5, # 不同版式 ≥ 内容页数 × 比例
            "max_same": 3,         # 同一版式最多出现页数
            "grid": [4, 3],        # 归一化网格（列, 行）
            "min_area_ratio": 0.02,# 小于 slide 面积此比例视为装饰（不参与签名）
        },
        # ---- A2 排版规范（逐页；references/design-norms.md）----
        "typography": {
            "max_emphasis": 4,     # 每页 [[强调]] 处数上限（重点不泛滥）
            "max_title_cjk": 16,   # 标题字数上限（CJK 计 1；纯西文按 2 字符计 1）
            "body_chars_max": 220, # 正文密度上限（CJK 字数；0 = 关闭）
            "body_chars_min": 0,   # 正文密度下限（0 = 关闭；避免空页/过度留白）
            "title_fs_min": 0,     # 标题字号下限（0 = 关闭；推荐 24–32）
        },
        # ---- 视觉丰度（advisory；源 _r_design-rules.md §密度目标）----
        "abundance": {
            "visual_ratio_min": 0.34,  # 内容页有视觉主体的页占比下限
            "density_max": 0.85,       # 单页元素覆盖 cell 占比上限（栅格并集；防堆砌）
                                       #   0.85 容结构化版式（面板/网格本就要铺），
                                       #   仅拦极端填满（源官方 60–75% 指内容密度，
                                       #   此处按 shape 覆盖度量故上抬）
            "type_span_min": 3,        # 全篇用到的字号档数下限（尺度对比）
            "margins_respected": True, # 元素是否留边（不贴版心边缘）
        },
        # ---- AI 感痕迹（advisory；源 anthropics/skills pptx SKILL.md §Avoid）----
        # 官方点名两类 "hallmark of AI-generated slides"：①标题下细横条；
        # ②装饰性色条/强调条（跨页宽头/脚条、竖直侧条、卡片单边条、"单边描边"）。
        # 只对内容页报；页型意图页的 deco/band 按引擎归属豁免（见 report.design_audit）。
        "ai_tells": {
            "enabled": True,
            "thin_h": 0.08,        # 细条高上限(in)——低于此且够宽的横条即"标题下划线"嫌疑
            "title_gap": 0.22,     # 标题底到细条顶的最大间距(in)——超此不算"标题下条"
            "bar_h_max": 0.38,     # 装饰条高上限(in)——"条"而非"块"
            "full_w_ratio": 0.90,  # 满宽条宽占 slide 宽比例（跨页头/脚条判定）
            "edge_band": 0.55,     # 满宽条的贴边带高(in)——条落在上下此带内即头/脚条
            "stripe_w_max": 0.09,  # 卡片单边条宽上限(in)
            "stripe_h_min": 0.25,  # 卡片单边条高下限(in)——高过矮的细条才是"侧条"
            "edge_gap": 0.07,      # 贴边判定容差(in)
        },
        # ---- 配色支配度（advisory；源官方 §Dominance over equality）----
        "color_dominance": {
            "min_share": 0.55,     # 填充面积最大色占比 ≥ 此值才算"有主导色"；否则平分权重
            "area_floor": 4.0,     # 彩色面积下限(in²)——低于此样本不足，不判
        },
    },

    # ---- COM 后处理 ----
    "com": {
        "follow_test_pt": 60,      # 随动自检：移动起点节点的步长(pt)
        "export_scale": 100,       # PNG 导出 = slide尺寸 × 比例(px/in) → 13.333in→1333px
        "dispatch_retries": 2,     # Dispatch 失败重试次数（CO_E_SERVER_EXEC_FAILURE 等瞬时启动错误）
        "dispatch_wait": 2.0,      # 重试间隔（秒），指数递增基
        "overflow_tol_pt": 1.0,    # B4 文本溢出真实回读容差（pt）：COM TextFrame2 实高
                                   #   超框内高 > 此值即 WARN 记账（离线 textmesh 为第一来源）
    },

    # ---- 图面框架层（背景/页眉/页脚；不进 IR，豁免遮挡/安全区校验）----
    "framework": {
        "header_fs": 10.0,        # 页眉起始字号（SPEC meta.framework.header.fs 可覆盖）
        "header_color": "#8899AA",
        "header_align": "left",
        "header_pad": 0.15,       # 页眉区：slide 顶部向下留白(in)
        "footer_fs": 9.0,         # 页脚起始字号
        "footer_color": "#8899AA",
        "footer_align": "left",
        "footer_pad": 0.2,        # 页脚区：slide 底部向上留白(in)
        "page_token": "{page}",   # 页脚页码占位符（多页序列逐页展开）
        "page_offset": 0,         # 页码偏移：显示页码 = 实际页号 + offset（可为负，
                                  #   如封面不计页码 + 正文从 1 起 → offset=-1）
    },

    # ---- 表格（table 元素——原生 a:tbl 积木）----
    "table": {
        "fs": 11.0,               # 表体起始字号(pt)
        "header_fs": 12.0,        # 表头起始字号
        "header_fill": "#1F2A44", # 表头行底色
        "header_color": "#FFFFFF",
        "header_bold": True,
        "cell_pad": 0.06,         # 单元格内边距（每侧,in；文本量测/渲染同源）
        "border_color": "#B8C4D8",
        "border_w": 0.75,         # 单元格边框磅值
    },

    # ---- 公式（formula 元素）----
    "formula": {
        "fs_default": 18.0,        # 未声明 text_style.fs 时的公式字号(pt)
    },

    # ---- 图片占位（B3 借鉴 ppt-studio：缺图不静默，产提示词清单）----
    "images": {
        "strict": False,           # --strict-images：占位/缺图即编译错（exit 2）
        "prompt_file": "img_prompts.md",   # out_dir 下缺图提示清单文件名
        "placeholder_fill": "#F2F5FA",     # 占位框填充（色值/palette token）
        "placeholder_border": "#8FA3BF",   # 占位框描边（虚线）
        "placeholder_fs": 12.0,            # 占位框文字字号(pt)
        "missing_key": "占位图",            # placeholder 为 True 且无 caption 时的兜底文案
    },

    # ---- 图表（chart 元素——python-pptx add_chart，零 COM）----
    # 样式卡（Power BI 数字大屏审美）：默认透明图表区/绘图区（母版/页底透出）、
    # 浅色细网格、挺拔窄柱、可选数据标签与预设 chart_style；全部可被
    # SPEC 元素级 style.* 覆盖（同名键），色值支持 palette token。
    "chart": {
        "colors": ["#2D6CDF", "#E0A800", "#1FA88C", "#B4536B", "#7B5EA7", "#8FA3BF"],
        "legend_pos": "right",     # right|bottom|top|left|none
        "legend_fs": 9.0,          # 图例字号(pt)
        "legend_color": None,      # 图例字色（None → 图表全局字色）
        "data_labels": False,      # 数值标签默认关（SPEC style.data_labels 覆盖）
        "label_pos": None,         # None=Excel 默认；center|inside_end|inside_base|
                                   #   outside_end|best_fit|above|below|left|right
        "label_fs": 8.0,           # 数据标签字号(pt)
        "label_color": None,       # 数据标签字色（None → 图表全局字色）
        "label_bold": False,       # 数据标签加粗
        "label_format": "0",       # 数据标签数字格式（Excel 记法，如 0.0 / 0% / #,##0）
        "tick_fs": 9.0,            # 轴刻度字号(pt)
        "tick_color": None,        # 轴刻度字色（None → 图表全局字色）
        "gridlines": True,         # 数值轴主网格线
        "gridline_color": "#E4E9F2",  # 网格线色（浅灰，弱化不抢眼）
        "axis_line": True,         # 数值轴/分类轴轴线
        "value_min": None,         # 数值轴最小刻度（None → Excel 自动）
        "value_max": None,         # 数值轴最大刻度（None → Excel 自动）
        "value_format": None,      # 数值轴数字格式（None → 沿用默认）
        "gap_width": 60,           # 柱/条间距（% gap，Excel 默认 150，收窄显挺拔）
        "overlap": None,           # 簇状重叠%（-100..100；None → Excel 默认）
        "line_width": 2.0,         # 折线宽度(pt)
        "smooth": False,           # 折线平滑（曲线）
        "markers": False,          # 折线数据点标记
        "chart_style": None,       # PowerPoint 预设图表样式 1..48（None → 默认）
        "font_family": None,       # 图表全局字族（None → params.font.latin）
        "chart_fill": "none",      # 图表区填充 none|色（默认透明，页底透出）
        "plot_fill": "none",       # 绘图区填充 none|色（默认透明）
        "donut_hole": 55,          # 圆环孔洞大小（10..90；doughnut 专用）
    },

    # ---- 页型意图版式（page_intent 审定菜单；grilling 收敛：agent 只选 intent，
    #      布局由 ir_builder 确定性展开 → 防刻板且保 harness；每原型 = 布局代码
    #      + verify 断言。**变体家族**：每 intent 一族审定变体（scripts/intents.py
    #      FAMILIES 为机器源；缺省按 deck 内出现次序轮换）——本层扁平键 = 家族首变体
    #      的常量，其余变体挂同名子 dict。cover = 破格封面族：非几何居中 / 左置大
    #      标题 / 不对称 deco 脊柱 / 右下角落款锚点）----
    "page_intent": {
        # intent 页缺省入场动画：开启后由 ir_builder 按元素序/类型错峰注入
        # （展开产物不带 authored animation，故需引擎侧补）；默认关闭。
        "anim_default": False,
        "cover": {   # 家族：("left", "band", "split")；扁平键 = left
            "deco_w_ratio": 0.16,    # deco 强调条宽占版心比例
            "deco_h": 0.14,          # deco 条高(in)
            "deco_y_ratio": 0.315,   # deco 条上缘占 slide 高比例
            "title_w_ratio": 0.72,   # 标题宽占版心比例（左配重 → 中心偏离破格）
            "title_y_ratio": 0.36,   # 标题块上缘占 slide 高比例
            "title_h": 1.6,          # 标题块高(in)（textmesh autofit 输入）
            "sub_gap": 0.12,         # 副标题距标题下缘(in)
            "sub_w_ratio": 0.55,     # 副标题宽占版心比例
            "meta_w_ratio": 0.30,    # 落款宽占版心比例
            "meta_h": 0.4,           # 落款高(in)
            "break_ratio": 0.10,     # 破格度断言：标题中心偏离 slide 中心 ≥ 版心×此比
            # --- 变体 band：横向色带贯穿（标题在上、副题在下）---
            "band": {
                "band_y_ratio": 0.54,     # 色带上缘占 slide 高比例
                "band_h": 0.85,           # 色带高(in)
                "title_y_ratio": 0.20,    # 标题上缘占 slide 高比例
                "title_h": 1.5,           # 标题块高(in)
                "sub_gap": 0.22,          # 副题距色带下缘(in)
                "band_w_min_ratio": 0.90, # 破格断言：色带宽 ≥ 版心×此比（横向贯穿）
                "band_h_min": 0.5,        # 破格断言：色带高 ≥ 此值(in)（是"带"不是"线"）
            },
            # --- 变体 split：左纵贯色块 + 右侧副题/落款 ---
            "split": {
                "panel_w_ratio": 0.42,    # 左侧色块宽占版心比例
                "panel_h_ratio": 0.88,    # 色块高占版心高比例（纵贯）
                "pad": 0.35,              # 色块内文本内距(in)
                "title_y_ratio": 0.34,    # 标题上缘（色块内，相对色块高）
                "title_h": 1.7,           # 标题块高(in)
                "sub_x_gap": 0.30,        # 副题距色块右缘(in)
                "sub_y_ratio": 0.60,      # 副题上缘相对版心顶
                "panel_h_min_ratio": 0.70, # 破格断言：色块高 ≥ 版心高×此比（纵贯）
            },
        },
        # section 破格节标题页：超大节序号贯穿（破格点 1）+ 节名大字号层级
        # （破格点 2）+ 左侧竖向强调条 + 水平引导线。
        "section": {   # 家族：("num_left", "num_giant", "band")；扁平键 = num_left
            "deco_w": 0.10,          # 右缘竖向强调条宽(in)——与左侧大数字块构成左右双锚
            "deco_h_ratio": 0.32,    # 强调条高占版心高比例
            "deco_y_ratio": 0.10,    # 强调条上缘相对版心顶
            "num_w_ratio": 0.30,     # 节序号块宽占版心比例
            "num_h_ratio": 0.50,     # 节序号块高占版心比例（> 贯穿下限才显"大数字"）
            "num_y_ratio": 0.16,     # 节序号块上缘相对版心顶
            "num_fs": 96,            # 节序号字号(pt)——版式主导视觉
            "guide_w_ratio": 0.24,   # 引导线宽占版心比例
            "guide_h": 0.05,         # 引导线高(in)
            "guide_y_ratio": 0.70,   # 引导线上缘相对版心顶（num 之下、title 之上）
            "title_w_ratio": 0.62,   # 节名宽占版心比例
            "title_fs": 40,          # 节名字号(pt)
            "title_y_ratio": 0.77,   # 节名上缘相对版心顶
            "title_h": 1.1,          # 节名块高(in)
            "num_h_min_ratio": 0.40, # 贯穿度断言：sec_num 高 ≥ 版心高×此比
            # --- 变体 num_giant：巨型序号贴右下，节名+引导线居左上 ---
            "num_giant": {
                "num_w_ratio": 0.50,      # 序号块宽占版心比例
                "num_h_ratio": 0.50,      # 序号块高占版心高比例
                "num_y_ratio": 0.40,      # 序号块上缘相对版心顶
                "num_fs": 200,            # 巨型序号字号(pt)
                "title_y_ratio": 0.06,    # 节名上缘相对版心顶
                "title_h": 1.1,           # 节名块高(in)
                "guide_y_ratio": 0.30,    # 引导线上缘相对版心顶
                "right_tol": 0.15,        # 破格断言：序号右缘贴版心右缘容差(in)
                "num_h_min_ratio": 0.45,  # 破格断言：序号块高 ≥ 版心高×此比
            },
            # --- 变体 band：节序号 + 节名同嵌一条横贯色带 ---
            "band": {
                "band_y_ratio": 0.34,     # 色带上缘相对版心顶
                "band_h_ratio": 0.26,     # 色带高占版心高比例
                "pad": 0.35,              # 色带内文本内距(in)
                "num_w_ratio": 0.20,      # 序号块宽占版心比例
                "num_fs": 80,             # 序号字号(pt)
                "title_x_ratio": 0.30,    # 节名左缘相对版心左
                "title_w_ratio": 0.62,    # 节名宽占版心比例
                "band_w_min_ratio": 0.90, # 破格断言：色带宽 ≥ 版心×此比（横向贯穿）
                "band_h_min_ratio": 0.20, # 破格断言：色带高 ≥ 版心高×此比
            },
        },
        # data/compare/… 原型按需逐个加（每原型 = 布局代码 + verify 断言）
        # ---- 科研三件套（C1）：problem / versus / route（破格科研页族）----
        "problem": {
            "badge_w": 0.95,          # 左上问题标记块宽(in)
            "badge_h_ratio": 0.40,    # 标记块高占版心高比例（纵向贯穿视觉）
            "badge_y_ratio": 0.06,    # 标记块上缘相对版心顶
            "badge_fs": 60,           # 标记字号(pt)——"?!" 类问题符号
            "title_x_gap": 0.30,      # 主问题距标记块右缘(in)
            "title_y_ratio": 0.12,    # 主问题上缘相对版心顶
            "title_h": 1.15,          # 主问题块高(in)
            "title_fs": 30,           # 主问题字号(pt)
            "items_y_ratio": 0.55,    # 子问题清单上缘相对版心顶
            "items_w_ratio": 0.92,    # 清单宽占版心比例
            "items_h": 2.6,           # 清单块高(in)
            "items_fs": 17,           # 清单字号(pt)
            "badge_h_min_ratio": 0.32, # 贯穿度断言：标记块高 ≥ 版心高×此比
        },
        "versus": {
            "gap": 0.55,              # 两栏水平间距(in)（居中留 VS 位）
            "col_pad": 0.22,          # 栏内文本内距(in)
            "panel_y_ratio": 0.16,    # 面板上缘相对版心顶
            "panel_h_ratio": 0.70,    # 面板高占版心高比例
            "title_h": 0.72,          # 栏题块高(in)
            "title_fs": 22,           # 栏题字号(pt)
            "body_fs": 16,            # 栏体字号(pt)
            "tag_w": 1.1,             # VS 标宽(in)
            "tag_h": 0.55,            # VS 标高(in)
            "tag_fs": 20,             # VS 字号(pt)
            "divider_w": 0.045,       # 中缝分割线宽(in)
            "balance_tol": 0.5,       # 均衡断言：|左栏宽−右栏宽| ≤ 此值(in)
            "sym_tol_ratio": 0.02,    # 对称断言：分割线中心偏离 slide 中心 ≤ 版心×此比
        },
        "route": {
            "title_y_ratio": 0.10,    # 页题上缘相对版心顶（可选）
            "title_h": 0.7,           # 页题块高(in)
            "title_fs": 26,           # 页题字号(pt)
            "y_ratio": 0.40,          # 阶段条上缘相对版心顶
            "h": 1.15,                # 阶段条高(in)
            "gap": 0.30,              # 相邻阶段水平间隙(in)（放箭头）
            "arrow_w": 2.0,           # 阶段间箭头连线磅值
            "stage_fs": 16,           # 阶段标签字号(pt)（≥ 正文下限 16）
            "count_min": 2,           # 阶段数下限（<2 编译拒）
            "even_tol": 0.4,          # 等步距断言：相邻中心间距极差 ≤ 此值(in)
        },
        # ---- 内容页结构生成样板（references/page-intents.md §10）----
        "panels": {
            "title_y_ratio": 0.0,     # 页题上缘相对版心顶
            "title_h": 0.7,           # 页题块高(in)
            "title_fs": 26,           # 页题字号(pt)
            "grid_y_ratio": 0.15,     # 面板网格上缘相对版心顶
            "grid_h_ratio": 0.80,     # 网格高占版心高比例
            "gap": 0.24,              # 面板间隙(in)
            "pad": 0.20,              # 面板内文本内距(in)
            "head_fs": 18,            # 面板标题字号(pt)
            "body_fs": 16,            # 面板正文字号(pt)（≥ deck 正文下限）
            "cols_default": 3,        # 缺省列数（SPEC cols 覆盖）
            "hero_h_ratio": 0.34,     # hero_left：首板高占网格高比例（全宽）
            "grid_span_ratio_min": 0.90,  # 断言：网格铺满版心宽下限
        },
        "columns": {
            "title_y_ratio": 0.0, "title_h": 0.7, "title_fs": 26,
            "body_y_ratio": 0.14,     # 栏体区上缘相对版心顶
            "body_h_ratio": 0.86,     # 栏体区高占版心高比例
            "col_gap": 0.40,          # 栏间隙(in)
            "pad": 0.18,              # 栏内文本内距(in)
            "head_fs": 20,            # 栏题字号(pt)
            "item_fs": 16,            # 栏体字号(pt)（≥ deck 正文下限）
            "bottom_h": 0.85,         # 底部横条高(in)（声明 bottom 才留位）
            "bottom_gap": 0.22,       # 栏体与底条间隙(in)
            "arrow_w": 1.8,           # 栏间箭头连线磅值
            "cols_default": 2,        # 缺省栏数（SPEC cols 覆盖）
            "span_ratio_min": 0.90,   # 断言：栏组铺满版心宽下限
        },
        "kpis": {
            "title_y_ratio": 0.0, "title_h": 0.7, "title_fs": 26,
            "row_y_ratio": 0.34,      # 指标行上缘相对版心顶
            "card_h": 2.2,            # 卡高(in)
            "gap": 0.32,              # 卡间隙(in)
            "pad": 0.18,              # 卡内文本内距(in)
            "value_fs": 40,           # 数值字号(pt)——主导视觉
            "label_fs": 14,           # 标签字号(pt)
            "badge_side_ratio": 0.55, # rings：圆标边长占卡高比例
            "span_ratio_min": 0.88,   # 断言：指标行铺满版心宽下限
            "value_ratio_min": 1.6,   # 断言：数值字号 ≥ 标签字号×此比（尺度对比）
        },
        "cards": {
            "title_y_ratio": 0.0, "title_h": 0.7, "title_fs": 26,
            "grid_y_ratio": 0.15,     # 网格上缘相对版心顶
            "grid_h_ratio": 0.80,     # 网格高占版心高比例
            "gap": 0.26,              # 卡间隙(in)
            "pad": 0.22,              # 卡内文本内距(in)
            "cols_default": 3,        # 缺省列数（SPEC cols 覆盖）
            "head_fs": 17,            # 卡题字号(pt)
            "body_fs": 16,            # 卡体字号(pt)（≥ deck 正文下限）
            "num_fs": 30,             # 编号/数字顶饰字号(pt)
            "icon_side": 0.55,        # 图标顶饰边长(in)
            "grid_span_ratio_min": 0.88,  # 断言：网格铺满版心宽下限
        },
        "figure_text": {
            "title_y_ratio": 0.0, "title_h": 0.7, "title_fs": 26,
            "body_y_ratio": 0.14,     # 图文区上缘相对版心顶
            "body_h_ratio": 0.86,     # 图文区高占版心高比例
            "fig_w_ratio": 0.52,      # 图侧宽占版心比例
            "gap": 0.34,              # 图/文间隙(in)
            "pad": 0.20,              # 卡内文本内距(in)
            "block_fs": 16,           # 正文字号(pt)（≥ deck 正文下限）
            "head_fs": 16,            # 图注/小标题字号(pt)
            "cap_fs": 11,             # 图注字号(pt)
            "fig_ratio_min": 0.34,    # 断言：图侧宽 ≥ 版心宽×此比
        },
    },
}

# 覆盖合并：SPEC.meta.params 深覆盖 DEFAULTS（只允许覆盖已存在键，未知键报错）
def resolve(meta_params=None, page_params=None, overrides=None, theme_params=None):
    """配置栈（性质③：JAnim utils/config.py 分层回退移植）——参数统一合并链：

        DEFAULTS（单一事实源）
          ↓ 主题层   theme_params（meta.theme 下降；设计语言打底，spec_compile 产出）
          ↓ 全局层   meta.params（agent 整篇旋钮；template extract 已在编译期
                  注入此层：extract 的 params.font ← 模板字族双轨）
          ↓ 页级层   meta.slides[i].params（多页逐页覆盖；布局/校验/渲染/物证
                  全链路按页取 p，见 build_ppt.build_pages/_check）
          ↓ CLI 层   --param key=value（临时覆盖不改 SPEC；last-wins）

    每层深覆盖已存在键、未知键报错（同一 _merge 原语，无手写分支）；
    修订器覆盖 = 修订链写回 SPEC（meta.params 本就属其可改结构，自然生效于
    上游层）。返回合并后的参数 dict（DEFAULTS 深拷贝，层间不污染）。
    """
    p = copy.deepcopy(DEFAULTS)
    for layer in (theme_params, meta_params, page_params, overrides):
        if layer:
            _merge(p, layer, "")
    return p


def layer_merge(base, override, path=""):
    """配置层级间的统一合并原语：深覆盖 base（override 键存在才可覆盖，未知键
    报错）。margin/framework 的『全局打底 + 页级覆盖』也走此（消除 build_pages
    手写浅 merge：页级只覆盖部分键时其余显式值保留，而非静默回退默认）。"""
    for k, v in override.items():
        key = f"{path}.{k}" if path else k
        if k not in base:
            raise KeyError(f"{key}: 未知键（不在全局配置）")
        if isinstance(v, dict):
            if not isinstance(base[k], dict):
                raise KeyError(f"{key}: 类型冲突，应为标量")
            layer_merge(base[k], v, key)
        else:
            base[k] = v
    return base


def _merge(base, override, path):
    """params 层专用封装：未知键报错带 params 语境（spec_validator 依赖其可抛）。"""
    try:
        layer_merge(base, override, path)
    except KeyError as ex:
        raise KeyError(f"params 未知键: {ex.args[0]}（请检查 scripts/params.py DEFAULTS）")