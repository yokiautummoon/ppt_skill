# -*- coding: utf-8 -*-
"""ink_text.py — 书法矢量字（C3 视觉补充）：字体字形 → custGeom 矢量路径。

动机（借鉴 ppt-studio brush.py）：书法/艺术字若用字体渲染，换机缺字即丢字形；
把字形**矢量化成原生 custGeom 形状**后，字体不再依赖，且可渐变 / 图片填充 / 缩放。

铁律 1 的对应物：本模块只产出「字形路径 + ink 包围盒（em 单位）」——
元素 rect 仍由 ir_builder 定（按 ink 比例适配声明盒），渲染层据 IR 写 custGeom，
几何唯一真相源不变。

字体解析：别名（kai/hei/song/fang/yahei）→ Windows 字体目录；亦接受 .ttf/.ttc 路径。
依赖 fontTools + skia-pathops（win_py 已装）。
"""
import os
from functools import lru_cache

from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from fontTools.pens.transformPen import TransformPen
import pathops

_WIN = r"C:\Windows\Fonts"
_USER = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts")
# 别名 → Windows 字体文件（楷体 simkai = 最接近书法的常见内置字体）
ALIASES = {"kai": "simkai.ttf", "hei": "simhei.ttf", "fang": "simfang.ttf",
           "song": "simsun.ttc", "yahei": "msyh.ttc"}


def font_file(name):
    """别名/文件名/绝对路径 → 本机字体文件路径（不存在则 fail-closed 抛错）。"""
    fn = ALIASES.get(name, name)
    if os.path.isabs(fn) and os.path.isfile(fn):
        return fn
    for d in (_WIN, _USER):
        p = os.path.join(d, fn)
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(f"书法字体不可用：{name!r}（解析为 {fn!r}；"
                            f"可选别名 {sorted(ALIASES)}）")


@lru_cache(maxsize=None)
def _font(name):
    f = TTFont(font_file(name), lazy=True)
    return f, f.getGlyphSet(), f.getBestCmap(), f["head"].unitsPerEm


class _Rec(BasePen):
    """记录轮廓为 svgpath 式子路径；二次曲线段转三次（pathops 亦支持，双保险）。"""

    def __init__(self):
        BasePen.__init__(self, None)
        self.subs, self.cur = [], None

    def _moveTo(self, p):
        self.cur = {"start": p, "segs": [], "closed": False}
        self.subs.append(self.cur)

    def _lineTo(self, p):
        self.cur["segs"].append(("L",) + tuple(p))

    def _curveToOne(self, a, b, c):
        self.cur["segs"].append(("C",) + tuple(a) + tuple(b) + tuple(c))

    def _qCurveToOne(self, a, b):
        p0 = self._getCurrentPoint()
        c1 = (p0[0] + 2 / 3 * (a[0] - p0[0]), p0[1] + 2 / 3 * (a[1] - p0[1]))
        c2 = (b[0] + 2 / 3 * (a[0] - b[0]), b[1] + 2 / 3 * (a[1] - b[1]))
        self.cur["segs"].append(("C",) + c1 + c2 + tuple(b))

    def _closePath(self):
        self.cur["closed"] = True

    def _endPath(self):
        pass


def _outline(text, font, spacing=0.0):
    """字符串并集轮廓（em 单位、y 向上）：逐字按 hmtx 前进量排布 → pathops 并集。"""
    f, gs, cmap, upm = _font(font)
    hm = f["hmtx"]
    path = pathops.Path()
    pos = 0.0
    for ch in text:
        if ch == " ":
            pos += 0.5
            continue
        g = cmap.get(ord(ch))
        if g is None:
            raise KeyError(f"字体 {font!r} 无字形 {ch!r}")
        k = 1.0 / upm
        # y 取指为负：字体 Y 向上 → 目标 Y 向下
        gs[g].draw(TransformPen(path.getPen(), (k, 0, 0, k, pos, 0)))
        pos += (hm[g][0] / upm) + spacing
    path.simplify(fix_winding=True)     # 去笔画重叠，单路径填充不镂空
    return path


def measure(text, font, spacing=0.0):
    """ink 紧密包围盒（em 单位）→ (w_em, h_em)。ir_builder 据此适配声明盒。"""
    x0, y0, x1, y1 = _outline(text, font, spacing).bounds
    return x1 - x0, y1 - y0


def subpaths(text, font, scale=4000.0, spacing=0.0):
    """归一化子路径：平移到 (0,0) 起点、y 翻转为向下、乘 scale。
    返回 (subs, vb_w, vb_h)：subs = [{start:(x,y), segs:[('L',x,y)|('C',x1,y1,x2,y2,x3,y3)], closed}]。"""
    path = _outline(text, font, spacing)
    rec = _Rec()
    path.draw(rec)
    x0, y0, x1, y1 = path.bounds

    def tr(x, y):
        return (x - x0) * scale, (y1 - y) * scale

    out = []
    for s in rec.subs:
        segs = []
        for sg in s["segs"]:
            if sg[0] == "L":
                segs.append(("L",) + tr(sg[1], sg[2]))
            else:
                segs.append(("C",) + tr(sg[1], sg[2]) + tr(sg[3], sg[4])
                            + tr(sg[5], sg[6]))
        out.append({"start": tr(*s["start"]), "segs": segs, "closed": True})
    return out, (x1 - x0) * scale, (y1 - y0) * scale
