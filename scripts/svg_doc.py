# -*- coding: utf-8 -*-
"""svg_doc.py — SVG 文档 → 原生化形状组（type: svg 的几何源）。

把一份 SVG（矢量图形）解析为「形状组」列表，供 ir_builder 展开为原生 DrawingML
custGeom 形状（可编辑矢量图，非位图）。铁律 1 的对应物：本模块只出「子路径 +
填充/描边 + 包围盒（root SVG 用户坐标）」——元素 rect 仍由 ir_builder 定。

解析范围（覆盖 typst / Illustrator / Inkscape 常见导出）：
  <defs>/<symbol> 定义 + <use> 实例化（含 x/y 附加平移）+ <g transform> 累积；
  图元 path/rect/circle/ellipse/line/polyline/polygon（复用 svgpath 解析）；
  仿射合成 matrix/translate/scale/rotate/skewX/skewY；fill/stroke/stroke-width 继承。

分组（按顶层元素）：root <svg> 的每个直接子元素为一个「边界」，边界内再按 paint
样式（fill 色 / stroke 色+宽）切分——custGeom 的 a:path 只能 fill=norm|none，
颜色是形状级，异色必须拆形状。

fail-closed：遇不支持构造（image/text/filter/clipPath/mask/渐变/pattern/外链 use/
CSS <style>）抛 SvgDocError（含定位），不静默降级（ppt-master _require_* 哲学）。
局限（v1，文档明示）：fill-opacity/stroke-opacity 与 url() 渐变均不支持（渐变报错、
opacity 忽略）。
"""
import math
import re
import xml.etree.ElementTree as ET

import svgpath

_SVG = "{http://www.w3.org/2000/svg}"
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"

# 不支持的构造（fail-closed）：出现即报错（含定位）
_UNSUPPORTED = {"image", "text", "tspan", "textPath", "filter", "clipPath", "mask",
                "pattern", "linearGradient", "radialGradient", "foreignObject",
                "style", "marker"}
_SHAPE_TAGS = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
_CONTAINER_TAGS = {"g", "symbol", "svg", "a"}
# 渲染生效属性：在 shape/container 上出现 = 须复现滤镜/裁剪/遮罩——我们不做 → fail-closed。
# （<defs> 中的定义是惰性内容，被缩略跳过；引用它的属性在此被拦下。）
_RENDER_AFFECT_ATTRS = ("filter", "clip-path", "clipPath", "clip_path", "mask")
_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?")
# 少量命名色（typst/工具常用 hex，命名色兜底常见集）
_NAMED = {"black": "#000000", "white": "#FFFFFF", "red": "#FF0000",
          "green": "#008000", "blue": "#0000FF", "gray": "#808080",
          "grey": "#808080", "yellow": "#FFFF00", "orange": "#FFA500"}


class SvgDocError(ValueError):
    pass


def _local(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def _floats(s):
    return [float(v) for v in _NUM.findall(s or "")]


def _fnum(v, default):
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---- 2D 仿射（a,b,c,d,e,f ≡ |a c e; b d f; 0 0 1|）----

def _mul(m1, m2):
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * e2 + c1 * f2 + e1, b1 * e2 + d1 * f2 + f1)


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _parse_transform(s):
    m = _IDENTITY
    if not s or not s.strip():
        return m
    for name, args in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", s):
        a = _floats(args)
        n = name.lower()
        try:
            if n == "matrix":
                t = tuple(a[:6])
                if len(t) < 6:
                    raise ValueError("matrix 需 6 参")
            elif n == "translate":
                t = (1.0, 0.0, 0.0, 1.0, a[0], a[1] if len(a) > 1 else 0.0)
            elif n == "scale":
                sx = a[0]
                sy = a[1] if len(a) > 1 else a[0]
                t = (sx, 0.0, 0.0, sy, 0.0, 0.0)
            elif n == "rotate":
                ang = math.radians(a[0])
                cs, sn = math.cos(ang), math.sin(ang)
                t = (cs, sn, -sn, cs, 0.0, 0.0)
                if len(a) >= 3:
                    cx, cy = a[1], a[2]
                    t = _mul((1.0, 0.0, 0.0, 1.0, cx, cy),
                             _mul(t, (1.0, 0.0, 0.0, 1.0, -cx, -cy)))
            elif n == "skewx":
                t = (1.0, 0.0, math.tan(math.radians(a[0])), 1.0, 0.0, 0.0)
            elif n == "skewy":
                t = (1.0, math.tan(math.radians(a[0])), 0.0, 1.0, 0.0, 0.0)
            else:
                raise SvgDocError(f"不支持的 transform 函数 {name!r}")
        except (IndexError, ValueError, TypeError) as ex:
            raise SvgDocError(f"transform {name}({args!r}) 参数非法：{ex}")
        m = _mul(m, t)
    return m


def _xform_sub(sp, m):
    return {"start": _apply(m, *sp["start"]),
            "segs": [("L",) + _apply(m, sg[1], sg[2]) if sg[0] == "L"
                     else ("C",) + _apply(m, sg[1], sg[2]) + _apply(m, sg[3], sg[4])
                     + _apply(m, sg[5], sg[6])
                     for sg in sp["segs"]],
            "closed": sp["closed"]}


def _sp_points(sp):
    yield sp["start"]
    for sg in sp["segs"]:
        if sg[0] == "L":
            yield (sg[1], sg[2])
        else:
            yield (sg[1], sg[2])
            yield (sg[3], sg[4])
            yield (sg[5], sg[6])


def _bbox(subs):
    xs, ys = [], []
    for sp in subs:
        for (x, y) in _sp_points(sp):
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def _norm_color(v, which):
    """paint 值 → 规范 hex（#RRGGBB）或 None（none）。渐变/非法 → fail-closed。"""
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() == "none":
        return None
    low = s.lower()
    if low.startswith("url("):
        raise SvgDocError(f"{which}=url(...) 渐变/图案填充不支持（fail-closed）")
    if low == "currentcolor":
        return "#000000"
    if low in _NAMED:
        return _NAMED[low]
    if low.startswith("#"):
        h = low[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 8:                 # 忽略 alpha（v1 局限）
            h = h[:6]
        if len(h) == 6 and re.match(r"^[0-9a-f]{6}$", h):
            return "#" + h.upper()
    m = re.match(r"^rgb\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)", low)
    if m:
        return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(float(g)))))
                                      for g in m.groups())
    raise SvgDocError(f"{which}={v!r} 颜色无法解析（fail-closed）")


def _walk(el, m, inherit, defs, out, boundary, depth):
    if depth > 32:
        raise SvgDocError("SVG 嵌套过深（>32 层）")
    tag = _local(el.tag)
    if tag in _UNSUPPORTED:
        raise SvgDocError(f"不支持的 SVG 构造 <{tag}>（fail-closed）")
    # 渲染生效属性：出现在渲染树节点（shape/container，非 <defs> 惰性定义）上
    # = 该元素受滤镜/裁剪/遮罩影响——无法复现 → fail-closed（绝不静默丢效果）
    if tag != "defs":
        for _ra in _RENDER_AFFECT_ATTRS:
            if _ra in el.attrib:
                raise SvgDocError(f"<{tag}> {_ra}=url(...) 滤镜/裁剪/遮罩不支持（fail-closed）")
    m = _mul(m, _parse_transform(el.get("transform")))
    inh = dict(inherit)
    for k, attr in (("fill", "fill"), ("stroke", "stroke"),
                    ("stroke_w", "stroke-width")):
        if el.get(attr) is not None:
            inh[k] = el.get(attr)
    if tag == "defs":
        return
    if tag == "use":
        href = el.get("href") or el.get(_XLINK_HREF)
        if not href or not href.startswith("#"):
            raise SvgDocError(f"<use> 仅支持内部引用（#id），实为 {href!r}")
        ref = defs.get(href[1:])
        if ref is None:
            raise SvgDocError(f"<use> 引用未找到：{href!r}")
        ux, uy = _fnum(el.get("x"), 0.0), _fnum(el.get("y"), 0.0)
        _walk(ref, _mul(m, (1.0, 0.0, 0.0, 1.0, ux, uy)), inh, defs, out,
              boundary, depth + 1)
        return
    if tag in _SHAPE_TAGS:
        try:
            subs = svgpath.node_to_subpaths(tag, el.attrib)
        except Exception as ex:
            raise SvgDocError(f"<{tag}> 路径解析失败：{ex}")
        if not subs:
            return
        subs = [_xform_sub(sp, m) for sp in subs]
        # fill 缺省 = 黑（SVG 初值）；显式 none → 无填充
        if "fill" not in inh:
            fill = "#000000"
        else:
            fill = _norm_color(inh.get("fill"), "fill")
        stroke = _norm_color(inh.get("stroke"), "stroke")
        sw = _fnum(inh.get("stroke_w"), None)
        out.append({"subpaths": subs, "fill": fill, "stroke": stroke,
                    "stroke_w": sw, "boundary": boundary})
        return
    if tag in _CONTAINER_TAGS:
        for ch in list(el):
            _walk(ch, m, inh, defs, out, boundary, depth + 1)
        return
    raise SvgDocError(f"不支持的 SVG 元素 <{tag}>（fail-closed）")


def _collect_defs(root):
    defs = {}
    for el in root.iter():
        eid = el.get("id")
        if eid and _local(el.tag) in (_SHAPE_TAGS | _CONTAINER_TAGS):
            defs[eid] = el
    return defs


def _group(paints):
    """按（边界, 填充色, 描边色, 描边宽）切分 → 形状组（首见序保留）。"""
    groups, index = [], {}
    for p in paints:
        sw = None if p["stroke_w"] is None else round(p["stroke_w"], 3)
        key = (p["boundary"], p["fill"], p["stroke"], sw)
        g = index.get(key)
        if g is None:
            g = {"subpaths": [], "fill": p["fill"], "stroke": p["stroke"],
                 "stroke_w": p["stroke_w"], "boundary": p["boundary"]}
            index[key] = g
            groups.append(g)
        g["subpaths"] += p["subpaths"]
    out = []
    for g in groups:
        bb = _bbox(g["subpaths"])
        if bb is not None:
            g["bbox"] = bb
            out.append(g)
    return out


def parse(text):
    """SVG 文本 → 形状组列表。每组 = {subpaths, fill, stroke, stroke_w, bbox, boundary}。

    subpaths 已套用全部 transform（root SVG 用户坐标）；fill/stroke 为 #RRGGBB 或 None。
    """
    try:
        root = ET.fromstring(text)
    except ET.ParseError as ex:
        raise SvgDocError(f"SVG 解析失败：{ex}")
    if _local(root.tag) != "svg":
        raise SvgDocError(f"根元素必须为 <svg>，实为 <{_local(root.tag)}>")
    defs = _collect_defs(root)
    paints = []
    for bi, child in enumerate(list(root)):
        if _local(child.tag) == "defs":
            continue
        _walk(child, _IDENTITY, {}, defs, paints, bi, 0)
    groups = _group(paints)
    if not groups:
        raise SvgDocError("SVG 无可见图形（空或仅 defs）")
    return groups


def parse_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return parse(f.read())


def doc_bbox(groups):
    """全部形状组的联合包围盒（root SVG 用户坐标）。"""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for g in groups:
        x0, y0, x1, y1 = g["bbox"]
        xs0.append(x0)
        ys0.append(y0)
        xs1.append(x1)
        ys1.append(y1)
    return (min(xs0), min(ys0), max(xs1), max(ys1))
