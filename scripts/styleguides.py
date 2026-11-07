# -*- coding: utf-8 -*-
"""styleguides.py — 规范规则库（按 style_guide 类型分组的 S 家族断言）。

RULE_SETS[type] 每个字段都是"规则契约"（verify 的 S 家族消费）：
  type_scale    字号规范 {角色: (下限, 上限)} pt —— T 家族 min_fs 之外的规范约束
  color_max     同一视觉单元内允许的语义色上限（含 kind 族）
  palette       该规则集允许使用的 palette token 名集合子集（None = 不限）
  components_required 必需构件 list（如 flow 图必须有 start/end 节点）
  spacing       间距/尺寸规范 {键: (min, max)}（如 step_height/gap）
  connector     连线规范 {way/…}
可选键（scansci 经验内化，缺省不启用 → 零行为变化）：
  size_fs_floor  小尺寸字号下限 {threshold: in, fs: pt} —— 元素 rect 短边
                  < threshold 时 fs ≥ floor（"缩小后识别性优先"可断言化；
                  区别于 min_fs 硬底：按尺寸生效）
  labels_follow  标签组织布尔 —— .label 后缀文本须与其目标同 owner 或
                  同 edit_group（"标签随部件移动"约束自由标签的组织）
断言由 verify.py 执行；本模块只声明规则（可读数据，无逻辑）。
"""
# 流程类（graph 容器）的节点角色字号规范
RULE_SETS = {
    "flowchart": {
        "type_scale": {
            "title": (20, 40),
            "node": (8, 16),
            "edge_label": (6, 12),
            "caption": (6, 14),
        },
        "color_max": 5,
        "palette": None,
        "components_required": [],         # graph 类自洽由 G 家族查（start/edges）
        "spacing": {
            "node_min_gap": (0.08, 3.0),   # 相邻节点最小间隔（graph adapt）
            "group_pad": (0.15, 1.0),
        },
        "connector": {"ways": ("straight", "orth"), "label_max": 8},
        # 方法论契约（A 机器约束 + D 生成指引单一事实源，graph_sig 消费特征）：
        # 复杂图（节点数 ≥ branch_min_nodes）必须显式声明分支结构；真线性流程
        # 显式声明 linear: true 逃生（不误伤合法直线）。vertical（组织树）天然
        # 层级，不适用。人读版 references/flowchart-method.md（tests 卡同步）。
        "semantics": {
            "branch_min_nodes": 5,
            "linear_escape": "linear",
            "guide": ("流程图不是一条直线：复杂流程（≥5 节点）须有分支表达"
                      "（判断/分叉节点，出度≥2）；简单线性流程（<5 节点）直接放行，"
                      "真线性长流程显式声明 linear: true 逃生。分支用 judge 语义，"
                      "回边用 way: orth，终点用 end——让每页流程有自己的拓扑，"
                      "避免多页同质化。"),
        },
    },
    "ladder": {
        "type_scale": {
            "title": (20, 40),
            "step": (8, 18),
            "caption": (6, 12),
        },
        "color_max": 3,
        "palette": None,
        "components_required": ["title", "steps"],
        "spacing": {
            "step_height": (0.6, 1.4),
            "stack_gap": (0.1, 0.6),
        },
        "connector": None,
        "width_monotonic": True,           # 梯形递进：children 宽度必须严格单调
    },
    "dashboard": {
        "type_scale": {"title": (20, 40), "card": (10, 20), "caption": (6, 12)},
        "color_max": 6,
        "palette": None,
        "components_required": ["title"],
        "spacing": {"card_gap": (0.1, 0.8)},
        "connector": None,
    },
    "deck": {
        # 正文下限 16pt——校对经验（references/copyediting.md §字号分层）：
        # 课件/汇报正文、卡片、要点条须 16–18（后排可读、大气）；
        # 小字角色（lab/caption/units/foot/meta 等）豁免，见 verify._s_family body 检查。
        "type_scale": {"title": (24, 48), "body": (16, 24), "caption": (8, 14)},
        "color_max": 6,
        "palette": None,
        "components_required": ["title"],
        "spacing": {},
        "connector": None,
    },
}

# 量化设计规范（A3 内化；人读版 references/design-norms.md）。
# 本表是"推荐值"的可读副本（风格卡 / 设计 DNA 比对 / 文档共用）；实际判定
# 走 params.verify.typography / layout_variety（数值接口单一事实源）。
QUANTITATIVE = {
    "body_fs": (14, 18),             # 正文 14–18pt（mode 16）
    "title_fs": (28, 32),            # 页标题 28–32pt（大标题可至 40）
    "hero_fs": (54, 96),             # 封面主标题 54–96pt
    "caption_fs": (8, 14),           # 注释/单位/落款 8–14pt
    "line_w": (0.5, 1.5),            # 描边/连线 0.5–1.5pt（mode 1.0）
    "line_spacing": (1.2, 1.5),
    "saturated_fill_ratio": 0.25,    # 饱和填充面积 ≤ 25%（强调而非刷墙）
    "max_emphasis": 4,               # 每页 [[强调]] 处数
    "max_title_cjk": 16,             # 标题字数
    "max_same_layout": 3,            # 同一版式最多页数
    "min_layout_variety": 7,         # 10–15 页建议 ≥7 种版式（阈值见 params）
    "pictures_per_page": 1,          # 关键页至少 1 个视觉素材（图/图表/typst）
}