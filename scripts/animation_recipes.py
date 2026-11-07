# -*- coding: utf-8 -*-
"""animation_recipes.py — 安逸的PPT动画库 35 宏参数化配方（skill 内自含）。

来源：外部资产「安逸的PPT动画库【插件版】」宏方案/安逸的PPT动画库 宏_UTF8.bas
（3081 行，35 宏，UTF-8 副本；GBK 原件只读不改）。本文件手写转录，不依赖
外部目录——skill 可分发。每宏 = msoAnimEffectCustom + AnimationBehavior 叠加
+ `#ppt_` 相对公式关键帧。配方只记**非默认/非注释** timing 值（默认见下）。

配方 schema（ANIMATION_BEHAVIORS 键语义）：
  RECIPES[宏名] = {
    "category": "enter"|"persist"|"emphasize"|"exit",
    "desc": 一句效果说明,
    "dur": float,            # AddEffect 后 eff.Timing.Duration
    "repeat": int,           # RepeatCount（999 = 无限循环）
    "timing": {},            # effect 级非默认 timing：
                             #   smooth_start/smooth_end: bool；accelerate/
                             #   decelerate: float≠0；auto_reverse: bool True
    "behaviors": [ ...构造序，含随后将被 Delete 的 set... ],
    "delete_first": bool,    # 末尾 eff.Behaviors(1).Delete（PowerPoint 定终态）
    "text_unit": "paragraph"|"character"|None,
    "source_truncated": bool,# 源文件截断（仅 先淡入后淡出_fanbal）
    "notes": "L79-155 …特殊点",
  }

  behavior = {
    "type": "set|filter|property|scale|rotation|motion",
    "dur": float,            # bhv.Timing.Duration
    "delay": float,          # TriggerDelayTime（≠0 才记）
    "smooth_start"/"smooth_end": bool True 才记,
    "accelerate"/"decelerate": float ≠0 才记,
    "auto_reverse": bool True 才记,
    # 类型专属：
    #   set:      "prop": "visibility", "to": 0|1
    #   filter:   "filter_type": "fade", "reveal": True|False
    #   property: "attrib": "x|y|width|height|rotation",
    #             "points": [[time, value] 或 [time, value, formula]]
    #   scale:    "from_x"/"from_y"/"to_x"/"to_y"（百分比）
    #   rotation: "from"/"to"（度）
    #   motion:   "from_x"/"from_y"/"to_x"/"to_y" + "path"（字符串原样）
  }

timing 默认值（Absence = 默认，仅非默认入配方）：
  Duration 0.001~ 必记；TriggerDelayTime=0；RepeatCount=1；SmoothStart/End、
  BounceEnd=False；Accelerate/Decelerate=0；AutoReverse=False。

公式字符串原文落 COM（`pt.Value`/`pt.Formula`），不做换算。配方提取要点：
  07 组 behavior 的 Points 起点公式无 `#` 前缀（"ppt_x-0.02"），与带 `#`
  的终值混用——照抄，PowerPoint 语义由其解释。
  无限陀螺旋_顺/逆 参数相同（源即如此）。
  先淡入后淡出_fanbal 源文件截断于 3081 行，仅确证首段行为，标 source_truncated。
"""

# 进入动画（15）
_ENTER = "enter"
# 持续动画（6）
_PERSIST = "persist"
# 强调动画（3）
_EMPHASIZE = "emphasize"
# 退出动画（11）
_EXIT = "exit"

RECIPES = {
    # ============================== 进入动画 ==============================
    "进入动画_自上浮入_改": {
        "category": _ENTER,
        "desc": "顶部落入+淡入，缓出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "#ppt_y-.05"], [1, "#ppt_y"]]},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2-78；Y 起于上（#ppt_y-.05）",
    },
    "进入动画_自下浮入_改": {
        "category": _ENTER,
        "desc": "底部上浮+淡入，缓出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "#ppt_y+.05"], [1, "#ppt_y"]]},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L79-155",
    },
    "进入动画_自左浮入_改": {
        "category": _ENTER,
        "desc": "左侧划入+淡入，缓出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "#ppt_x-.05"], [1, "#ppt_x"]]},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L156-232",
    },
    "进入动画_自右浮入_改": {
        "category": _ENTER,
        "desc": "右侧划入+淡入，缓出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "#ppt_x+.05"], [1, "#ppt_x"]]},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L233-309",
    },
    "进入动画_自上缩小浮入": {
        "category": _ENTER,
        "desc": "顶部+缩放+淡入（细节丰富）",
        "dur": 0.5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "ppt_y-0.02"], [1, "#ppt_y"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "scale", "dur": 0.5, "from_x": 110, "from_y": 110,
             "to_x": 100, "to_y": 100, "smooth_end": True, "decelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L310-403；property 起点公式不带 # 前缀",
    },
    "进入动画_自下缩小浮入": {
        "category": _ENTER,
        "desc": "底部+缩放+淡入",
        "dur": 0.5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "ppt_y+0.02"], [1, "#ppt_y"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "scale", "dur": 0.5, "from_x": 110, "from_y": 110,
             "to_x": 100, "to_y": 100, "smooth_end": True, "decelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L404-497",
    },
    "进入动画_自左缩小浮入": {
        "category": _ENTER,
        "desc": "左侧+缩放+淡入",
        "dur": 0.5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "ppt_x-0.02"], [1, "#ppt_x"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "scale", "dur": 0.5, "from_x": 110, "from_y": 110,
             "to_x": 100, "to_y": 100, "smooth_end": True, "decelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L498-591",
    },
    "进入动画_自右缩小浮入": {
        "category": _ENTER,
        "desc": "右侧+缩放+淡入",
        "dur": 0.5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "ppt_x+0.02"], [1, "#ppt_x"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "scale", "dur": 0.5, "from_x": 110, "from_y": 110,
             "to_x": 100, "to_y": 100, "smooth_end": True, "decelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L592-685",
    },
    "进入动画_快速淡入": {
        "category": _ENTER,
        "desc": "快速出现，类似打字机/柔和版出现",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_start": True, "accelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.125, "filter_type": "fade", "reveal": True,
             "smooth_end": True, "decelerate": 1.0},
            {"type": "set", "dur": 0.375, "delay": 0.125,
             "prop": "visibility", "to": 1},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L686-757；尾部补一个可见 set（延迟淡入段）",
    },
    "进入动画_安逸Q弹": {
        "category": _ENTER,
        "desc": "Q 弹弹出，弹性形变小，韧性强",
        "dur": 0.75, "repeat": 1,
        "timing": {"smooth_start": True, "smooth_end": True,
                   "accelerate": 0.2, "decelerate": 0.8},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "scale", "dur": 0.158, "from_x": 0, "from_y": 0,
             "to_x": 110, "to_y": 110, "smooth_end": True, "decelerate": 1.0},
            {"type": "scale", "dur": 0.197, "delay": 0.158,
             "from_x": 110, "from_y": 110, "to_x": 95, "to_y": 95,
             "smooth_start": True, "accelerate": 0.5},
            {"type": "scale", "dur": 0.395, "delay": 0.355,
             "from_x": 95, "from_y": 95, "to_x": 100, "to_y": 100,
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.079, "filter_type": "fade",
             "reveal": True, "smooth_end": True, "decelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L759-866",
    },
    "进入动画_随机旋入淡入": {
        "category": _ENTER,
        "desc": "短距离随机旋入淡入",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "ppt_y+rand(0.125)-0.0625"], [1, "#ppt_y"]]},
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "ppt_x+rand(0.125)-0.0625"], [1, "#ppt_x"]]},
            {"type": "property", "dur": 0.5, "attrib": "rotation",
             "points": [[0, "ppt_r+rand(-180)+90"], [1, "#ppt_r"]]},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L868-981；rand() 公式无 # 前缀",
    },
    "进入动画_纵向归位": {
        "category": _ENTER,
        "desc": "Y 轴随机淡出后归位",
        "dur": 1, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade", "reveal": True},
            {"type": "set", "dur": 0.5, "delay": 0.5,
             "prop": "visibility", "to": 1},
            {"type": "property", "dur": 1, "attrib": "y",
             "points": [[0, "ppt_y+((ceil(rand(-2)+1))+(rand(2)-1))*0.125"],
                        [1, "ppt_y"]],
             "smooth_end": True, "decelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L983-1073；ceil/rand 复合公式",
    },
    "进入动画_落子效果": {
        "category": _ENTER,
        "desc": "淡化并从大缩小，落子质感",
        "dur": 0.75, "repeat": 1,
        "timing": {"smooth_start": True, "smooth_end": True,
                   "accelerate": 0.3, "decelerate": 0.7},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.6, "filter_type": "fade", "reveal": True,
             "smooth_end": True, "decelerate": 1.0},
            {"type": "property", "dur": 0.75, "attrib": "height",
             "points": [[0, "ppt_h*2.1"], [0.45, "ppt_h*1.04"], [1, "#ppt_h"]]},
            {"type": "property", "dur": 0.75, "attrib": "width",
             "points": [[0, "ppt_w*2.1"], [0.45, "ppt_w*1.04"], [1, "#ppt_w"]]},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L1075-1173；多点关键帧",
    },
    "进入动画_软糖出现": {
        "category": _ENTER,
        "desc": "高宽交替变化，Q 弹",
        "dur": 1.25, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "scale", "dur": 0.25, "from_x": 0, "from_y": 0,
             "to_x": 120, "to_y": 105},
            {"type": "scale", "dur": 0.187, "delay": 0.25,
             "from_x": 120, "from_y": 105, "to_x": 100, "to_y": 115},
            {"type": "scale", "dur": 0.313, "delay": 0.437,
             "from_x": 100, "from_y": 115, "to_x": 110, "to_y": 100},
            {"type": "scale", "dur": 0.25, "delay": 0.75,
             "from_x": 110, "from_y": 100, "to_x": 100, "to_y": 110},
            {"type": "scale", "dur": 0.25, "delay": 1,
             "from_x": 100, "from_y": 110, "to_x": 100, "to_y": 100},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L1175-1301；XY 不等比缩放链",
    },
    "进入动画_旋涡出现": {
        "category": _ENTER,
        "desc": "旋转 10 圈+淡入",
        "dur": 1, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 1, "filter_type": "fade", "reveal": True},
            {"type": "property", "dur": 0.998, "attrib": "rotation",
             "points": [[0, "#ppt_r"], [1, "36000"]]},
            {"type": "property", "dur": 0.001, "delay": 0.999,
             "attrib": "rotation",
             "points": [[0, "ppt_r"], [0.5, "#ppt_r"]],
             "smooth_end": True, "decelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "character",
        "notes": "L1302-1396；36000 = 100 圈？源即如此",
    },
    # ============================== 持续动画 ==============================
    "持续动画_九边形抖动": {
        "category": _PERSIST,
        "desc": "快速抖动（不建议用于文字）",
        "dur": 0.75, "repeat": 999,
        "timing": {},
        "behaviors": [
            {"type": "motion", "dur": 0.75, "from_x": 0, "from_y": 0,
             "to_x": 100, "to_y": 100,
             "path": "M 0 -0.0037 C -0.00017 -0.0037 -0.00139 0.00209 "
                     "-0.00122 0.00209 C -0.00104 0.00232 0.00122 -0.00231 "
                     "0.00122 -0.00254 C 0.00104 -0.00278 -0.00208 0.00023 "
                     "-0.00208 0.00047 C -0.00191 0.00093 0.00174 -0.00023 "
                     "0.00174 -0.00046 C 0.00174 -0.00092 -0.00191 -0.00208 "
                     "-0.00208 -0.00185 C -0.00208 -0.00139 0.00087 0.00185 "
                     "0.00122 0.00139 C 0.00122 0.00116 -0.00087 -0.00347 "
                     "-0.00122 -0.00347 C -0.00122 -0.00324 -0.00017 0.00278 "
                     "0 0.00278 C 0.00017 0.00255 0.00017 -0.0037 0 -0.0037 "
                     "L 0 -0.00347 L 0 -0.0037 Z "},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1398-1443；MotionEffect.path 原样；源在 Add 后多调一次 "
                 "ConvertToTextUnitEffect（怪癖，不影响终态）",
    },
    "持续动画_呼吸效果": {
        "category": _PERSIST,
        "desc": "可循环的放大缩小微动效",
        "dur": 3, "repeat": 999,
        "timing": {},
        "behaviors": [
            {"type": "scale", "dur": 0.75, "from_x": 100, "from_y": 100,
             "to_x": 110, "to_y": 110, "smooth_end": True, "decelerate": 0.5},
            {"type": "scale", "dur": 1.5, "delay": 0.75,
             "from_x": 110, "from_y": 110, "to_x": 90, "to_y": 90,
             "smooth_start": True, "smooth_end": True,
             "accelerate": 0.5, "decelerate": 0.5},
            {"type": "scale", "dur": 0.75, "delay": 2.25,
             "from_x": 90, "from_y": 90, "to_x": 100, "to_y": 100,
             "smooth_start": True, "accelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1445-1522",
    },
    "持续动画_无限陀螺旋_顺": {
        "category": _PERSIST,
        "desc": "无限顺时针旋转",
        "dur": 1, "repeat": 999,
        "timing": {},
        "behaviors": [
            {"type": "rotation", "dur": 1, "from": 0, "to": 360},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1525-1566",
    },
    "持续动画_无限陀螺旋_逆": {
        "category": _PERSIST,
        "desc": "无限旋转（源参数与顺相同）",
        "dur": 1, "repeat": 999,
        "timing": {},
        "behaviors": [
            {"type": "rotation", "dur": 1, "from": 0, "to": 360},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1568-1609；源与顺宏参数相同（怀疑原意逆=负角，照抄）",
    },
    "持续动画_随机抖动_fanbal": {
        "category": _PERSIST,
        "desc": "一直随机且自然抖动",
        "dur": 5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 5, "attrib": "x",
             "points": [[0, "0", "rand(0.01)+#ppt_x"], [1, "1"]]},
            {"type": "property", "dur": 5, "attrib": "y",
             "points": [[0, "0", "rand(0.01)+#ppt_y"], [1, "1"]]},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1610-1689；Formula 字段用 rand(0.01) 叠加（Value 只是占位）",
    },
    # ============================== 强调动画 ==============================
    "强调动画_两次放大": {
        "category": _EMPHASIZE,
        "desc": "快速放大两次（建议调快时长）",
        "dur": 0.1, "repeat": 2,
        "timing": {"auto_reverse": True},
        "behaviors": [
            {"type": "scale", "dur": 0.1, "from_x": 100, "from_y": 100,
             "to_x": 120, "to_y": 120},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1692-1735；effect 级 Repeat=2 + AutoReverse",
    },
    "强调动画_色块儿划过": {
        "category": _EMPHASIZE,
        "desc": "色块横掠强调（可改颜色透明度）",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "#ppt_x-#ppt_w/2"], [0.5, "#ppt_x"],
                        [1, "#ppt_x+#ppt_w/2"]]},
            {"type": "property", "dur": 0.5, "attrib": "width",
             "points": [[0, "0"], [0.5, "#ppt_w"], [1, "0"]]},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0,
             "smooth_end": True, "decelerate": 1.0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1738-1836；尾段隐藏 set To=0",
    },
    "强调动画_禁止摇摆": {
        "category": _EMPHASIZE,
        "desc": "衰减往复，类似禁止点击 UI 动效",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_start": True, "smooth_end": True,
                   "accelerate": 0.5, "decelerate": 0.5},
        "behaviors": [
            {"type": "motion", "dur": 0.5, "from_x": 0, "from_y": 0,
             "to_x": 100, "to_y": 100,
             "path": "M -3.61111E-6 -2.59259E-6 L -0.00816 -2.59259E-6 "
                     "L 0.00955 -2.59259E-6 L -0.00416 -2.59259E-6 "
                     "L 0.00504 -2.59259E-6 L -3.61111E-6 -2.59259E-6 Z "},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1838-1883；源在 Add 后多调一次 ConvertToTextUnitEffect（怪癖）",
    },
    # ============================== 退出动画 ==============================
    "退出动画_自上浮出": {
        "category": _EXIT,
        "desc": "顶部淡出移出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "#ppt_y"], [1, "#ppt_y+.05"]]},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1885-1974；退出组 FilterEffect.Reveal=False（淡出）",
    },
    "退出动画_自下浮出": {
        "category": _EXIT,
        "desc": "底部淡出移出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "#ppt_y"], [1, "#ppt_y-.05"]]},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L1976-2065",
    },
    "退出动画_自左浮出": {
        "category": _EXIT,
        "desc": "左侧淡出移出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "#ppt_x"], [1, "#ppt_x+.05"]]},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2067-2156",
    },
    "退出动画_自右浮出": {
        "category": _EXIT,
        "desc": "右侧淡出移出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "ppt_x"], [1, "ppt_x-0.05"]]},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2158-2247；隐藏 set 在 property 前；property 无 # 前缀",
    },
    "退出动画_自上放大浮出": {
        "category": _EXIT,
        "desc": "顶部放大淡出",
        "dur": 0.5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "ppt_y"], [1, "#ppt_y+0.02"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "scale", "dur": 0.5, "from_x": 100, "from_y": 100,
             "to_x": 110, "to_y": 110, "smooth_end": True, "decelerate": 1.0},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2249-2355",
    },
    "退出动画_自下放大浮出": {
        "category": _EXIT,
        "desc": "底部放大淡出",
        "dur": 0.5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "ppt_y"], [1, "#ppt_y-0.02"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "scale", "dur": 0.5, "from_x": 100, "from_y": 100,
             "to_x": 110, "to_y": 110, "smooth_end": True, "decelerate": 1.0},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2358-2464",
    },
    "退出动画_自左放大浮出": {
        "category": _EXIT,
        "desc": "左侧放大淡出",
        "dur": 0.5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "#ppt_x"], [1, "ppt_x+0.02"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "scale", "dur": 0.5, "from_x": 100, "from_y": 100,
             "to_x": 110, "to_y": 110, "smooth_end": True, "decelerate": 1.0},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2466-2572；property 终点无 # 前缀",
    },
    "退出动画_自右放大浮出": {
        "category": _EXIT,
        "desc": "右侧放大淡出",
        "dur": 0.5, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "#ppt_x"], [1, "ppt_x-0.02"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "scale", "dur": 0.5, "from_x": 100, "from_y": 100,
             "to_x": 110, "to_y": 110, "smooth_end": True, "decelerate": 1.0},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2575-2681",
    },
    "退出动画_弹跳跑了": {
        "category": _EXIT,
        "desc": "压缩弹跳后跑出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_start": True, "smooth_end": True,
                   "accelerate": 0.1, "decelerate": 0.9},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "property", "dur": 0.093, "delay": 0.314, "attrib": "width",
             "points": [[0, "#ppt_w"], [1, "0"]],
             "smooth_start": True, "accelerate": 1.0},
            {"type": "property", "dur": 0.093, "delay": 0.314, "attrib": "height",
             "points": [[0, "#ppt_h"], [1, "0"]],
             "smooth_start": True, "accelerate": 1.0},
            {"type": "scale", "dur": 0.088, "delay": 0.136,
             "from_x": 110, "from_y": 110, "to_x": 100, "to_y": 100,
             "auto_reverse": True},
            {"type": "scale", "dur": 0.136, "delay": 0,
             "from_x": 95, "from_y": 95, "to_x": 100, "to_y": 100,
             "smooth_end": True, "decelerate": 0.5, "auto_reverse": True},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2683-2810；两个 scale 带 behavior 级 AutoReverse 怪癖",
    },
    "退出动画_随机旋出淡化": {
        "category": _EXIT,
        "desc": "短距离随机旋出淡化",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "#ppt_y"], [1, "ppt_y+rand(0.125)-0.0625"]]},
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.5, "filter_type": "fade",
             "reveal": False},
            {"type": "property", "dur": 0.5, "attrib": "x",
             "points": [[0, "#ppt_x"], [1, "ppt_x+rand(0.125)-0.0625"]]},
            {"type": "property", "dur": 0.5, "attrib": "rotation",
             "points": [[0, "ppt_r+rand(-180)+90"], [1, "#ppt_r"]]},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2812-2939",
    },
    "退出动画_纵向移出": {
        "category": _EXIT,
        "desc": "Y 轴随机偏移移出",
        "dur": 0.5, "repeat": 1,
        "timing": {"smooth_end": True, "decelerate": 1.0},
        "behaviors": [
            {"type": "set", "dur": 0.001, "prop": "visibility", "to": 1},
            {"type": "filter", "dur": 0.25, "delay": 0.25,
             "filter_type": "fade", "reveal": False},
            {"type": "property", "dur": 0.5, "attrib": "y",
             "points": [[0, "ppt_y"],
                        [1, "ppt_y+((ceil(rand(-2)+1))+(rand(2)-1))*0.125"]],
             "smooth_end": True, "decelerate": 1.0},
            {"type": "set", "dur": 0.001, "delay": 0.499,
             "prop": "visibility", "to": 0},
        ],
        "delete_first": True, "text_unit": "paragraph",
        "notes": "L2941-3030",
    },
    "退出动画_先淡入后淡出_fanbal": {
        "category": _EXIT,
        "desc": "先淡入后淡出（源截断，仅首段可确证）",
        "dur": 1, "repeat": 1,
        "timing": {},
        "behaviors": [
            {"type": "set", "dur": 0.01, "prop": "visibility", "to": 1},
        ],
        "delete_first": False, "text_unit": None,
        "source_truncated": True,
        "notes": "L3032-3081：源文件截断于此宏第 2 个 behavior，完整行为链 "
                 "无法转录（推断为淡入+淡出+隐藏）。配方仅含确证部分，"
                 "构造时行为不完整，勿用于重要演示。",
    },
}

# 预设基座（WPS 兼容关键）：AddEffect 用 presetID≠0（msoAnimEffect 预设）
# 而非 Custom=0——WPS 只播 presetID≠0 的效果（根因见 references/animation.md）。
# 值 ∈ {"fade", "zoom", "bounce", "grow_shrink", "spin", "pulse"}；
# 预设自带 behaviors 均以 set 可见开头，com_layer 的 delete_first 删之
# 后余预设动画行为 + 配方叠加，与插件版产物（presetID=53/10/42…+set+叠加）
# 同构。纯 custom 逃逸 = 无 preset_base 键 → 回退 Custom=0（WPS 不播）。
PRESET_BASE = {
    # ---------- enter ----------
    "进入动画_自上浮入_改": "fade",
    "进入动画_自下浮入_改": "fade",
    "进入动画_自左浮入_改": "fade",
    "进入动画_自右浮入_改": "fade",
    "进入动画_自上缩小浮入": "zoom",
    "进入动画_自下缩小浮入": "zoom",
    "进入动画_自左缩小浮入": "zoom",
    "进入动画_自右缩小浮入": "zoom",
    "进入动画_快速淡入": "fade",
    "进入动画_安逸Q弹": "bounce",
    "进入动画_随机旋入淡入": "spin",
    "进入动画_纵向归位": "fade",
    "进入动画_落子效果": "zoom",
    "进入动画_软糖出现": "bounce",
    "进入动画_旋涡出现": "spin",
    # ---------- persist ----------
    "持续动画_九边形抖动": "fade",
    "持续动画_呼吸效果": "grow_shrink",
    "持续动画_无限陀螺旋_顺": "spin",
    "持续动画_无限陀螺旋_逆": "spin",
    "持续动画_随机抖动_fanbal": "fade",
    # ---------- emphasize ----------
    "强调动画_两次放大": "grow_shrink",
    "强调动画_色块儿划过": "fade",
    "强调动画_禁止摇摆": "spin",
    # ---------- exit ----------
    "退出动画_自上浮出": "fade",
    "退出动画_自下浮出": "fade",
    "退出动画_自左浮出": "fade",
    "退出动画_自右浮出": "fade",
    "退出动画_自上放大浮出": "fade",
    "退出动画_自下放大浮出": "fade",
    "退出动画_自左放大浮出": "fade",
    "退出动画_自右放大浮出": "fade",
    "退出动画_弹跳跑了": "fade",
    "退出动画_随机旋出淡化": "spin",
    "退出动画_纵向移出": "fade",
    "退出动画_先淡入后淡出_fanbal": "fade",
}
PRESET_BASE_WHITELIST = {"fade", "zoom", "bounce", "grow_shrink", "spin",
                         "pulse"}

# 类型专属字段白名单（com_layer 校验 + spec 逃生通道复用）
BEHAVIOR_TYPE_FIELDS = {
    "set": {"prop", "to"},
    "filter": {"filter_type", "reveal"},
    "property": {"attrib", "points"},
    "scale": {"from_x", "from_y", "to_x", "to_y"},
    "rotation": {"from", "to"},
    "motion": {"from_x", "from_y", "to_x", "to_y", "path"},
}

# 通用 timing 字段（behavior/effect 通用）
TIMING_FIELDS = {"dur", "delay", "smooth_start", "smooth_end",
                 "accelerate", "decelerate", "repeat", "auto_reverse"}

# 非默认 semantics：timing 缺失不重建默认，仅按 "True" 显式字段应用
_SMOOTH = ("smooth_start", "smooth_end")


def selfcheck():
    """配方静态自检：35 键 / 字段白名单 / 类型专属字段。返回 (ok, [err...])。

    无 Office 环境可跑：`win_py scripts/animation_recipes.py` 或纯 python3。
    """
    errs = []

    def err(m):
        errs.append(m)

    names = list(RECIPES)
    if len(names) != 35:
        err(f"宏数 {len(names)} != 35")
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        err(f"重复键: {dup}")
    for n, r in RECIPES.items():
        if r["category"] not in ("enter", "persist", "emphasize", "exit"):
            err(f"{n}: category 非法 {r['category']!r}")
        if not isinstance(r.get("dur"), (int, float)):
            err(f"{n}: dur 非数值")
        if not isinstance(r.get("repeat"), int):
            err(f"{n}: repeat 非 int")
        if not isinstance(r.get("behaviors"), list) or not r["behaviors"]:
            err(f"{n}: behaviors 空")
        for k in r.get("timing", {}):
            if k not in TIMING_FIELDS - {"dur", "delay", "repeat"}:
                err(f"{n}.timing 未知键 {k!r}")
        if r.get("text_unit") not in (None, "paragraph", "character"):
            err(f"{n}: text_unit 非法 {r.get('text_unit')!r}")
    for i, b in enumerate(r["behaviors"]):
            t = b.get("type")
            if t not in BEHAVIOR_TYPE_FIELDS:
                err(f"{n}.behaviors[{i}]: type 非法 {t!r}")
                continue
            if "dur" not in b or not isinstance(b["dur"], (int, float)):
                err(f"{n}.behaviors[{i}]: 缺 dur")
            for k in b:
                if k in ("type", "dur") or k in TIMING_FIELDS:
                    continue
                if k not in BEHAVIOR_TYPE_FIELDS[t]:
                    err(f"{n}.behaviors[{i}]: type={t} 不允许字段 {k!r}")
            if t == "property":
                if not b.get("points"):
                    err(f"{n}.behaviors[{i}]: property 必须声明关键帧 points")
                    continue
                for pts in b.get("points", []):
                    if (not isinstance(pts, (list, tuple)) or len(pts) < 2
                            or len(pts) > 3):
                        err(f"{n}.behaviors[{i}]: 点格式非法 {pts!r}")
    if set(PRESET_BASE) != set(RECIPES):
        err(f"PRESET_BASE 键数与宏数不符: PRESET_BASE {len(PRESET_BASE)} "
            f"vs RECIPES {len(RECIPES)}")
    for n, base in PRESET_BASE.items():
        if base not in PRESET_BASE_WHITELIST:
            err(f"{n}: preset_base {base!r} 不在白名单")
    ok = not errs
    return ok, errs


if __name__ == "__main__":
    ok, errs = selfcheck()
    if ok:
        print(f"animation_recipes 自检通过：{len(RECIPES)} 宏")
        cats = {}
        for r in RECIPES.values():
            cats[r["category"]] = cats.get(r["category"], 0) + 1
        print("分布:", ", ".join(f"{k}={v}" for k, v in cats.items()))
        print("截断宏:", [n for n, r in RECIPES.items()
                          if r.get("source_truncated")])
    else:
        import sys
        for e in errs:
            print("ERR:", e)
        sys.exit(1)