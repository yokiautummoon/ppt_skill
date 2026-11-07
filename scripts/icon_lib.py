# -*- coding: utf-8 -*-
"""icon_lib.py — 矢量图标库（B1）：Lucide SVG 图元 → 归一化子路径表。

把 Lucide 图标 JSON（`assets/icons/lucide.json`：`{name: {"n": [[tag, attrs], ...],
"t": [tags]}}`，24×24 viewBox、描边式）解析成统一的子路径表，供渲染层写进原生
`a:custGeom` 形状。与 brush（字形填充）不同，图标是**描边**语义：渲染层按子路径
逐条 `a:path`（描边项 `fill="none"`，实心项 `fill="norm"`）+ 形状级 `a:ln` 描线。

定位 = **图标路径产出器**：只出「子路径 + viewBox 尺寸 + 实心子路径索引」，
元素 rect 仍由 ir_builder 定（铁律 1 的 icon 对应物）。

坐标系原样保留（24×24，y 向下）——本模块只做语法解析与归一化缩放，不做落位。
"""
import json
import os
from functools import lru_cache

import svgpath

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "assets", "icons", "lucide.json")

# 归一化缩放：24×24 viewBox × _SCALE → custGeom 路径单位（保小数精度，取整误差可忽略）
_SCALE = 1000.0
_DEFAULT = "circle-dot"

# 中文关键词 → Lucide 图标名/英文标签（find/resolve 的中文入口；命中优先精确名）
_ZH = {
    "水": ["droplet", "water"], "水滴": ["droplet"], "云": ["cloud"],
    "火": ["flame", "fire"], "设置": ["settings", "cog", "gear"],
    "用户": ["user", "person"], "人": ["user", "person"], "群": ["users"],
    "搜索": ["search"], "查找": ["search"], "首页": ["home"],
    "文件": ["file"], "文件夹": ["folder"], "目录": ["folder"],
    "文档": ["file-text"], "邮件": ["mail"], "消息": ["message-square", "message-circle"],
    "通知": ["bell"], "铃": ["bell"], "日历": ["calendar"], "时间": ["clock"],
    "时钟": ["clock"], "位置": ["map-pin"], "地图": ["map"], "地点": ["map-pin"],
    "锁": ["lock"], "解锁": ["lock-open"], "钥匙": ["key"],
    "盾": ["shield"], "安全": ["shield-check", "shield"], "警告": ["triangle-alert", "alert-triangle"],
    "错误": ["circle-x", "x-circle"], "成功": ["circle-check", "check"],
    "对": ["check"], "勾": ["check"], "叉": ["x"], "关闭": ["x"],
    "加": ["plus"], "加号": ["plus"], "减": ["minus"], "删除": ["trash-2", "trash"],
    "编辑": ["pencil", "square-pen"], "笔": ["pencil"], "保存": ["save"],
    "下载": ["download"], "上传": ["upload"], "分享": ["share-2", "share"],
    "链接": ["link"], "图片": ["image"], "照片": ["image"], "视频": ["video"],
    "音乐": ["music"], "播放": ["play"], "暂停": ["pause"], "停止": ["square"],
    "星": ["star"], "收藏": ["star", "bookmark"], "心": ["heart"],
    "赞": ["thumbs-up"], "踩": ["thumbs-down"], "评论": ["message-square"],
    "购物车": ["shopping-cart"], "包": ["shopping-bag"], "礼物": ["gift"],
    "钱": ["dollar-sign", "banknote"], "钱包": ["wallet"],
    "图表": ["bar-chart-3", "chart-column", "bar-chart"], "柱状图": ["bar-chart-3", "chart-column"],
    "折线": ["line-chart", "chart-line"], "饼图": ["pie-chart", "chart-pie"],
    "趋势": ["trending-up"], "上升": ["trending-up", "arrow-up"], "下降": ["trending-down", "arrow-down"],
    "放大": ["zoom-in", "search"], "缩小": ["zoom-out"],
    "齿轮": ["settings", "cog"], "工具": ["wrench"], "构建": ["hammer"],
    "数据库": ["database"], "服务器": ["server"], "云盘": ["cloud"],
    "网络": ["network"], "wifi": ["wifi"], "信号": ["signal"],
    "代码": ["code", "code-xml"], "终端": ["terminal"], "命令": ["terminal"],
    "机器人": ["bot"], "cpu": ["cpu"], "芯片": ["cpu"], "灯泡": ["lightbulb"],
    "想法": ["lightbulb"], "目标": ["target"], "标记": ["flag", "bookmark"],
    "书": ["book", "book-open"], "笔筒": ["graduation-cap"], "学位": ["graduation-cap"],
    "学校": ["graduation-cap", "school"], "实验室": ["flask-conical", "test-tube"],
    "原子": ["atom"], "科学": ["flask-conical", "atom", "microscope"],
    "显微镜": ["microscope"], "滴管": ["pipette"], "试管": ["test-tube"],
    "地球": ["globe"], "世界": ["globe"], "定位": ["map-pin"],
    "用户组": ["users"], "团队": ["users"], "组织": ["network"],
    "流程": ["workflow"], "循环": ["refresh-cw", "rotate-cw"], "刷新": ["refresh-cw"],
    "菜单": ["menu"], "更多": ["more-horizontal", "ellipsis"], "列表": ["list"],
    "网格": ["grid-3x3", "layout-grid"], "布局": ["layout-dashboard", "layout-grid"],
    "太阳": ["sun"], "月亮": ["moon"], "晴": ["sun"], "雨": ["cloud-rain"],
    "飞机": ["plane"], "车": ["car"], "卡车": ["truck"], "房子": ["house", "home"],
    "建筑": ["building", "building-2"], "工厂": ["factory"],
    "手": ["hand"], "眼睛": ["eye"], "指纹": ["fingerprint"],
    "打印机": ["printer"], "相机": ["camera"], "手机": ["smartphone"],
    "电脑": ["monitor", "laptop"], "键盘": ["keyboard"], "鼠标": ["mouse"],
    "电源": ["power"], "电池": ["battery"], "闪电": ["zap"], "速度": ["gauge"],
    "火箭": ["rocket"], "奖杯": ["trophy"], "奖牌": ["medal"], "皇冠": ["crown"],
    "微笑": ["smile"], "哭": ["frown"], "检查": ["clipboard-check"],
    "清单": ["clipboard-list"], "任务": ["list-todo", "clipboard-list"],
    "标签": ["tag", "tags"], "过滤": ["filter", "funnel"], "漏斗": ["filter", "funnel"],
    "排序": ["arrow-up-down"], "重复": ["copy"], "粘贴": ["clipboard"],
    "打印": ["printer"], "字体": ["type"], "文本": ["type", "file-text"],
    "颜色": ["palette"], "调色板": ["palette"], "画笔": ["paintbrush", "brush"],
    "图层": ["layers"], "组件": ["component", "blocks"], "方块": ["square", "box"],
    "立方": ["box"], "盒子": ["box"], "球": ["circle"], "圆": ["circle"],
}


@lru_cache(maxsize=1)
def _data():
    with open(_DATA, encoding="utf-8") as f:
        return json.load(f)


def names():
    """全部图标名（有序）。"""
    return sorted(_data().keys())


def exists(name):
    return name in _data()


def _match_score(name, tags, kw):
    """关键词命中小分：名字精确 100 / 名字含 60 / 标签精确 40 / 标签含 30。"""
    k = kw.lower()
    if name == k:
        return 100
    if k in name:
        return 60
    if k in tags:
        return 40
    if any(k in t for t in tags):
        return 30
    return 0


def find(keyword, limit=8):
    """按中文关键词 / 英文名 / 英文标签检索图标名（按相关度排序）。"""
    d = _data()
    kw = str(keyword).strip()
    cands = _ZH.get(kw, [kw])
    scored = {}
    for c in cands:
        cl = c.lower()
        for name, v in d.items():
            s = _match_score(name, v.get("t") or [], cl)
            if s:
                scored[name] = max(scored.get(name, 0), s)
    ranked = sorted(scored.items(), key=lambda kv: (-kv[1], kv[0]))
    return [n for n, _ in ranked[:limit]]


def resolve(name_or_kw, default=_DEFAULT):
    """图标名或关键词 → 确定图标名；未命中回退 default（fail-soft，落 circle-dot）。"""
    s = str(name_or_kw).strip()
    if s in _data():
        return s
    hits = find(s, limit=1)
    if hits:
        return hits[0]
    return default


def subpaths(name, scale=_SCALE):
    """图标名 → (subs, vb_w, vb_h, filled)。

    subs   = svgpath 子路径表（归一化 ×scale，y 向下）
    filled = 实心子路径（下标）的 frozenset：谓词来自 Lucide 节点的 fill 属性
             （如 `fill="currentColor"`）；描边子路径不在其中。
    """
    d = _data()
    name = resolve(name)
    nodes = d[name]["n"]
    subs = []
    filled = set()
    for tag, attrs in nodes:
        sub_list = svgpath.node_to_subpaths(tag, attrs)
        is_filled = "fill" in attrs
        for sp in sub_list:
            idx = len(subs)
            subs.append(_scaled(sp, scale))
            if is_filled:
                filled.add(idx)
    vb = 24.0 * scale
    return subs, vb, vb, frozenset(filled)


def _scaled(sp, scale):
    """子路径 ×scale（视图盒原样 24×24，不做落位）。"""
    start = (round(sp["start"][0] * scale, 2), round(sp["start"][1] * scale, 2))
    segs = []
    for sg in sp["segs"]:
        if sg[0] == "L":
            segs.append(("L", round(sg[1] * scale, 2), round(sg[2] * scale, 2)))
        else:                                       # C: x1,y1,x2,y2,x,y
            segs.append(("C",) + tuple(round(v * scale, 2) for v in sg[1:]))
    return {"start": start, "segs": segs, "closed": sp["closed"]}
