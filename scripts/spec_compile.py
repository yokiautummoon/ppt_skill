# -*- coding: utf-8 -*-
"""spec_compile.py — SPEC YAML → 编译 JSON（语法/类型/单位/引用 静态检查）。

职责边界（与 spec_validator 分工）：
  - 本模块：结构层——YAML 语法、顶层段、元素/容器形状、字段类型、数值单位、
            引用存在性（重复 id / 边端点 / group 成员 / glue / z_override）。
  - spec_validator：白名单层——未知字段、palette token 引用、style_guide 存在、
            语义规则（params 键可解析等）。
错误风格：收集式（多条 violations），不得静默吞 YAML 陷阱（on/yes/重复 key）。
"""
import os
import re

import capabilities as CAP
import richtext as RT
import themes as THEMES

HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")
TOP_KEYS = {"meta", "palette", "elements", "relations", "anim"}
ELEMENT_TYPES = {"text", "shape", "image", "diagram", "line", "formula",
                 "table", "chart", "stack", "dock", "graph", "curve", "typst",
                 "brush", "icon", "svg"}
CHART_TYPES = {"column_clustered", "column_stacked", "column_stacked_100",
               "bar_clustered", "bar_stacked", "bar_stacked_100",
               "line", "line_stacked", "line_markers", "line_markers_stacked",
               "area", "area_stacked", "area_stacked_100",
               "pie", "pie_exploded", "doughnut", "doughnut_exploded"}
# chart 元素 style.* 白名单 → 校验子（bool / 数值域 / 颜色 / 枚举）
CHART_STYLE_BOOL = {"data_labels", "label_bold", "gridlines", "axis_line",
                    "smooth", "markers"}
CHART_STYLE_COLOR = {"colors", "legend_color", "label_color", "tick_color",
                     "gridline_color", "chart_fill", "plot_fill"}
CHART_STYLE_NUM = {"legend_fs", "label_fs", "tick_fs", "gap_width", "overlap",
                   "line_width", "value_min", "value_max", "donut_hole",
                   "chart_style"}
CHART_STYLE_ENUM = {"legend": {"right", "bottom", "top", "left", "none"},
                    "label_pos": {"center", "inside_end", "inside_base",
                                  "outside_end", "best_fit", "above", "below",
                                  "left", "right"}}
CHART_STYLE_STR = {"label_format", "value_format", "font_family"}
# cylinder = 圆柱积木（ir_builder 展开为侧壁/顶底椭圆/等高弧，非单一形状）
SHAPE_KINDS = {"rounded_rect", "oval", "can", "diamond", "rect", "parallelogram",
               "hexagon", "cylinder"}
BORDER_DASH = {"dash", "dot", "dash_dot"}
TEXT_ALIGN = {"left", "center", "right", "justify"}
# 类型尺度角色（text_style.scale）：fs 缺省源 + 字体角色（hero/title → major 字族）
TEXT_SCALE = {"hero", "title", "subtitle", "body", "caption"}


class SpecCompileError(ValueError):
    pass


def _num(v, what, path):
    """数值校验：int/float 且有限；bool 明确拒绝（YAML on/yes 陷阱）。"""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise SpecCompileError(f"{path}.{what}: 需要数值（YAML 陷阱提示：on/yes/True 会被解析为布尔，"
                               f"请加引号），实为 {type(v).__name__}={v!r}")
    if not (float(v) == v or isinstance(v, int)):
        raise SpecCompileError(f"{path}.{what}: 数值非法 {v!r}")
    return float(v)


def _check_color(v, path, palette):
    if isinstance(v, str):
        if v in palette:
            return
        if HEX_RE.match(v):
            return
        raise SpecCompileError(f"{path}: 颜色必须是 palette token 或 6 位 hex，实为 {v!r}")
    raise SpecCompileError(f"{path}: 颜色字段类型错误 {type(v).__name__}")


def _check_rect(rect, path, permissive=False):
    if not isinstance(rect, (list, tuple)) or len(rect) != 4:
        raise SpecCompileError(f"{path}.rect: 必须为 [x, y, w, h] 四元组，实为 {rect!r}")
    vals = [_num(v, "rect[]", path) for v in rect]
    if not permissive:
        if vals[2] <= 0 or vals[3] <= 0:
            raise SpecCompileError(f"{path}.rect: 宽高必须为正，实为 {rect[2:]!r}")
    for v in vals:
        if v < 0:
            raise SpecCompileError(f"{path}.rect: 不允许负坐标 {rect!r}")
    return vals


def _check_ratio_rect(rect, path):
    """rect_kind=ratio 的 rect = dict{x,y,w,h}（0–1 分数，相对页内容区/整页）。
    静态校验：分数域 ∈[0,1]、宽高正、x+w≤1（越界 exit 2）。几何在 build_pages
    解成绝对 rect（铁律 1：IR 只见绝对）。"""
    if not isinstance(rect, dict) or set(rect) != {"x", "y", "w", "h"}:
        raise SpecCompileError(f"{path}.rect: rect_kind=ratio 时必须为 dict"
                               f"{{x, y, w, h}}（0–1 分数），实为 {rect!r}")
    vals = {}
    for k in ("x", "y", "w", "h"):
        v = rect[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise SpecCompileError(f"{path}.rect.{k}: 必须为数值（分数），实为 {v!r}")
        vals[k] = float(v)
    for k in ("x", "y"):
        if not 0.0 <= vals[k] <= 1.0:
            raise SpecCompileError(f"{path}.rect.{k}: 必须 ∈ [0,1]（分数），实为 {vals[k]!r}")
    if vals["w"] <= 0 or vals["h"] <= 0:
        raise SpecCompileError(f"{path}.rect: 宽高分数必须为正，实为 w={vals['w']} h={vals['h']}")
    for k in ("x", "y"):
        if vals[k] + (vals["w"] if k == "x" else vals["h"]) > 1.0 + 1e-9:
            raise SpecCompileError(f"{path}.rect: x+w 或 y+h 越界（超内容区），"
                                   f"实为 {vals[k]!r}")
    return vals


def _check_rich_text(v, path):
    """行内标记（**加粗** / [[强调]]）语法校验：未闭合/交叉/空标记 = exit 2。"""
    try:
        RT.parse(v)
    except RT.RichTextError as ex:
        raise SpecCompileError(f"{path}: 富文本标记非法 — {ex}")


def _check_text_style(ts, path, palette):
    for k, v in ts.items():
        kp = f"{path}.text_style.{k}"
        if k == "fs":
            fs = _num(v, "fs", kp)
            if not 4.0 <= fs <= 96.0:
                raise SpecCompileError(f"{kp}: 字号必须 ∈ [4, 96]pt（4pt=min_fs 硬底），实为 {v!r}")
        elif k in ("bold", "italic"):
            if not isinstance(v, bool):
                raise SpecCompileError(f"{kp}: 必须为 true/false，实为 {v!r}")
        elif k == "color":
            _check_color(v, kp, palette)
        elif k == "align":
            if v not in TEXT_ALIGN:
                raise SpecCompileError(f"{kp}: align 必须 ∈ {TEXT_ALIGN}，实为 {v!r}")
        elif k == "indent_chars":
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise SpecCompileError(f"{kp}: 必须为非负整数（首行缩进字符数，"
                                       f"1 字 ≈ 1×字号），实为 {v!r}")
        elif k == "scale":
            if v not in TEXT_SCALE:
                raise SpecCompileError(f"{kp}: scale 必须 ∈ {sorted(TEXT_SCALE)}"
                                       f"（类型尺度角色，供 fs 缺省 + 字族角色），实为 {v!r}")
        else:
            raise SpecCompileError(f"{kp}: 未知 text_style 键 {k!r}")


def _check_style(st, path, palette):
    for k, v in st.items():
        kp = f"{path}.style.{k}"
        if k == "fill":
            _check_color(v, kp, palette)
        elif k == "border":
            if isinstance(v, str) and v == "none":
                continue
            _check_color(v, kp, palette)
        elif k == "shadow":
            if isinstance(v, bool):
                continue
            if isinstance(v, str):
                _check_color(v, kp, palette)
                continue
            raise SpecCompileError(f"{kp}: shadow 必须为 true/false 或颜色，实为 {v!r}")
        elif k == "adjustment":
            adj = _num(v, "adjustment", kp)
            if not 0.0 <= adj <= 1.0:
                raise SpecCompileError(f"{kp}: adjustment 必须 ∈ [0, 1]，实为 {v!r}")
        elif k == "border_dash":
            if v not in BORDER_DASH:
                raise SpecCompileError(f"{kp}: border_dash 必须 ∈ {sorted(BORDER_DASH)}，"
                                       f"实为 {v!r}")
        else:
            raise SpecCompileError(f"{kp}: 未知 style 键 {k!r}")


_TABLE_STYLE_KEYS = {"fs", "color", "bold", "fill"}


def _check_table_style(ts, path, palette):
    """table header/body 样式子键。"""
    for k, v in ts.items():
        kp = f"{path}.{k}"
        if k == "fs":
            fs = _num(v, "fs", kp)
            if not 4.0 <= fs <= 96.0:
                raise SpecCompileError(f"{kp}: 字号必须 ∈ [4, 96]pt")
        elif k == "color":
            _check_color(v, kp, palette)
        elif k == "bold":
            if not isinstance(v, bool):
                raise SpecCompileError(f"{kp}: 必须为 true/false")
        elif k == "fill":
            _check_color(v, kp, palette)
        else:
            raise SpecCompileError(f"{kp}: 未知 table 样式键 {k!r}")


def _check_table(el, path, palette):
    """table 元素：data 矩阵一致性 + col_widths 账目（和 == rect 宽）。"""
    if "rect" not in el:
        raise SpecCompileError(f"{path}: table 必须为顶层元素（声明绝对 rect）")
    data = el.get("data")
    if not isinstance(data, list) or not data:
        raise SpecCompileError(f"{path}.data: table 必须声明非空 data 矩阵")
    ncol = None
    for i, row in enumerate(data):
        if not isinstance(row, list) or not row:
            raise SpecCompileError(f"{path}.data[{i}]: 必须为非空列表")
        if ncol is None:
            ncol = len(row)
        if len(row) != ncol:
            raise SpecCompileError(f"{path}.data[{i}]: 列数 {len(row)} ≠ 首行 {ncol}")
        for j, v in enumerate(row):
            if isinstance(v, bool) or not isinstance(v, (str, int, float)):
                raise SpecCompileError(f"{path}.data[{i}][{j}]: 单元格必须为字符串/数值")
            if isinstance(v, str):
                _check_rich_text(v, f"{path}.data[{i}][{j}]")
    cols = el.get("cols")
    if cols is not None and cols != ncol:
        raise SpecCompileError(f"{path}.cols: {cols} ≠ data 推导列数 {ncol}（行/列由 data 推导即可）")
    cws = el.get("col_widths")
    if cws is not None:
        if not isinstance(cws, list) or len(cws) != ncol:
            raise SpecCompileError(f"{path}.col_widths: 必须为 {ncol} 项列表")
        for i, v in enumerate(cws):
            _num(v, f"col_widths[{i}]", path)
        if abs(sum(cws) - el["rect"][2]) > 1e-6:
            raise SpecCompileError(f"{path}.col_widths: 和 {sum(cws)} ≠ rect 宽 {el['rect'][2]}"
                                   f"（表格总宽固定 = rect.w）")
    hdr = el.get("header")
    if hdr is not None and hdr is not False:
        if not isinstance(hdr, dict) or not hdr:
            raise SpecCompileError(f"{path}.header: 必须为样式 dict（fs/color/bold/fill）或 false")
        _check_table_style(hdr, f"{path}.header", palette)
    bd = el.get("body")
    if bd is not None:
        if not isinstance(bd, dict) or not bd:
            raise SpecCompileError(f"{path}.body: 必须为样式 dict（fs/color/bold/fill）")
        _check_table_style(bd, f"{path}.body", palette)
    brd = el.get("borders")
    if brd is not None:
        if isinstance(brd, str) and brd == "none":
            pass
        elif isinstance(brd, bool):
            pass
        else:
            _check_color(brd, f"{path}.borders", palette)


def _check_chart(el, path, palette):
    """chart 元素：数据账目（series.values 个数 == categories）+ chart_type 白名单
    + style 语义。必须顶层（绝对 rect）；pie 仅单序列（Excel 饼图语义）。"""
    if "rect" not in el:
        raise SpecCompileError(f"{path}: chart 必须为顶层元素（声明绝对 rect）")
    ct = el.get("chart_type")
    if ct not in CHART_TYPES:
        raise SpecCompileError(f"{path}.chart_type: 必须 ∈ {sorted(CHART_TYPES)}，实为 {ct!r}")
    cats = el.get("categories")
    if not isinstance(cats, list) or not cats:
        raise SpecCompileError(f"{path}.categories: 必须为非空类别列表")
    for i, v in enumerate(cats):
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            raise SpecCompileError(f"{path}.categories[{i}]: 类别必须为字符串/数值，实为 {v!r}")
    series = el.get("series")
    if not isinstance(series, list) or not series:
        raise SpecCompileError(f"{path}.series: 必须为非空序列列表")
    if ct == "pie" and len(series) != 1:
        raise SpecCompileError(f"{path}.series: pie 图仅支持单序列，实为 {len(series)}")
    for i, s in enumerate(series):
        sp = f"{path}.series[{i}]"
        if not isinstance(s, dict) or "name" not in s or "values" not in s:
            raise SpecCompileError(f"{sp}: 必须声明 name 与 values")
        name = s["name"]
        if not isinstance(name, str) or not name:
            raise SpecCompileError(f"{sp}.name: 必须为非空字符串")
        vals = s["values"]
        ok_len = isinstance(vals, list) and len(vals) == len(cats)
        if not ok_len:
            raise SpecCompileError(f"{sp}.values: 必须为 {len(cats)} 项数值列表（== categories 数），"
                                   f"实为 {len(vals) if isinstance(vals, list) else type(vals).__name__} 项")
        for j, v in enumerate(vals):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise SpecCompileError(f"{sp}.values[{j}]: 必须为数值，实为 {v!r}")
    st = el.get("style")
    if st is not None:
        if not isinstance(st, dict):
            raise SpecCompileError(f"{path}.style: 必须为 dict")
        for k, v in st.items():
            kp = f"{path}.style.{k}"
            if k in CHART_STYLE_ENUM:
                if v not in CHART_STYLE_ENUM[k]:
                    raise SpecCompileError(f"{kp}: 必须 ∈ {'|'.join(sorted(CHART_STYLE_ENUM[k]))}")
            elif k in CHART_STYLE_BOOL:
                if not isinstance(v, bool):
                    raise SpecCompileError(f"{kp}: 必须为 true/false")
            elif k == "colors":
                if not isinstance(v, list) or not v:
                    raise SpecCompileError(f"{kp}: 必须为非空颜色列表")
                for i, c in enumerate(v):
                    _check_color(c, f"{kp}[{i}]", palette)
            elif k in CHART_STYLE_COLOR:
                if v == "none":
                    continue          # chart_fill/plot_fill 允许 none（透明）
                _check_color(v, kp, palette)
            elif k in CHART_STYLE_NUM:
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise SpecCompileError(f"{kp}: 必须为数值")
                if k == "gap_width" and not (0 <= v <= 500):
                    raise SpecCompileError(f"{kp}: 必须 ∈ [0,500]")
                if k == "overlap" and not (-100 <= v <= 100):
                    raise SpecCompileError(f"{kp}: 必须 ∈ [-100,100]")
                if k == "chart_style" and not (1 <= v <= 48):
                    raise SpecCompileError(f"{kp}: 必须 ∈ [1,48]")
                if k == "donut_hole" and not (10 <= v <= 90):
                    raise SpecCompileError(f"{kp}: 必须 ∈ [10,90]")
            elif k in CHART_STYLE_STR:
                if not isinstance(v, str) or not v:
                    raise SpecCompileError(f"{kp}: 必须为非空字符串")
            else:
                raise SpecCompileError(
                    f"{kp}: 未知 chart style 键 {k!r}（合法键："
                    f"{'/'.join(sorted(CHART_STYLE_BOOL | CHART_STYLE_COLOR | CHART_STYLE_NUM | set(CHART_STYLE_ENUM) | CHART_STYLE_STR | {'colors'}))}）")


def _check_margin(m, path):
    """meta.margin / 页级 margin：{l,t,r,b} 数值（多页每页可覆盖）。"""
    if not isinstance(m, dict):
        raise SpecCompileError(f"{path}: 必须为 dict(l/t/r/b)")
    for k, v in m.items():
        kp = f"{path}.{k}"
        if k not in ("l", "t", "r", "b"):
            raise SpecCompileError(f"{kp}: 未知键（l/t/r/b）")
        _num(v, k, kp)


def _check_fill(v, path, palette):
    """fill 语义：hex / palette token / {grad: [c1, c2]}（与 palette 语法共用）。
    grad 端色只允许字面 hex——渲染层 resolve_fill 对 grad 元素直接 _hex()，
    token 嵌套会崩（palette 段的同型隐患不在本层收紧范围）。"""
    if isinstance(v, dict):
        if set(v) != {"grad"} or not isinstance(v.get("grad"), list) \
           or len(v["grad"]) != 2:
            raise SpecCompileError(f"{path}.fill: dict 仅支持 {{grad: [c1, c2]}}，"
                                   f"实为 {v!r}")
        for i, c in enumerate(v["grad"]):
            if not isinstance(c, str) or not HEX_RE.match(c):
                raise SpecCompileError(f"{path}.fill.grad[{i}]: 渐变端色必须为 6 位 "
                                       f"hex（不支持 token 嵌套），实为 {c!r}")
        return
    _check_color(v, f"{path}.fill", palette)


def _check_header_footer(hf, path, palette):
    """meta.framework.header/footer：text/align/fs/color。"""
    if not isinstance(hf, dict):
        raise SpecCompileError(f"{path}: 必须为 dict")
    for k, v in hf.items():
        kp = f"{path}.{k}"
        if k == "text":
            if not isinstance(v, str):
                raise SpecCompileError(f"{kp}: 必须为字符串")
        elif k == "align":
            if v not in ("left", "center", "right"):
                raise SpecCompileError(f"{kp}: align 必须 ∈ left|center|right")
        elif k == "fs":
            fs = _num(v, "fs", kp)
            if not 4.0 <= fs <= 96.0:
                raise SpecCompileError(f"{kp}: 字号必须 ∈ [4, 96]pt")
        elif k == "color":
            _check_color(v, kp, palette)
        else:
            raise SpecCompileError(f"{kp}: 未知键（text/align/fs/color）")


def _check_framework(fw, path, palette):
    """meta.framework：background(fill) + header/footer（框架层，不进 IR）。"""
    if not isinstance(fw, dict):
        raise SpecCompileError(f"{path}: 必须为 dict")
    for k, v in fw.items():
        fp = f"{path}.{k}"
        if k == "background":
            if not isinstance(v, dict) or "fill" not in v:
                raise SpecCompileError(f"{fp}: 必须声明 fill")
            for kk in v:
                if kk != "fill":
                    raise SpecCompileError(f"{fp}.{kk}: 未知键（仅 fill）")
            _check_fill(v["fill"], fp, palette)
        elif k in ("header", "footer"):
            _check_header_footer(v, fp, palette)
        else:
            raise SpecCompileError(f"{fp}: 未知 framework 键（background/header/footer）")


def _check_params(ps, path):
    """meta.params：数值接口面。只纠需要强类型的键——page_offset 是页码语义，
    显示页码 = 实际页号 + offset 必须为整数（float 会出「第 2.5 页」这类怪象）。"""
    if ps is None:
        return
    if not isinstance(ps, dict):
        raise SpecCompileError(f"{path}: 必须为 dict")
    fw = ps.get("framework")
    if isinstance(fw, dict):
        off = fw.get("page_offset")
        if off is not None and (isinstance(off, bool) or not isinstance(off, int)):
            raise SpecCompileError(f"{path}.framework.page_offset: 必须为整数（可为负；"
                                   f"正数前移、负数后移页码），实为 {off!r}")


def _check_graph(g, path, palette):
    """graph 容器内部：nodes/edges/groups 自洽。"""
    if g.get("orientation") is not None and g["orientation"] not in ("horizontal", "vertical"):
        raise SpecCompileError(f"{path}.orientation: 必须为 horizontal|vertical")
    if g.get("variant") is not None and g["variant"] not in ("snake",):
        raise SpecCompileError(f"{path}.variant: 必须为 snake（蛇形折返流，B 形态多样性）"
                               f"，实为 {g['variant']!r}")
    nodes = g.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise SpecCompileError(f"{path}: graph 必须声明非空 nodes")
    ids = {}
    for i, n in enumerate(nodes):
        if not isinstance(n, dict) or "id" not in n:
            raise SpecCompileError(f"{path}.nodes[{i}]: 必须为含 id 的 dict")
        nid = n["id"]
        if not isinstance(nid, str) or not nid:
            raise SpecCompileError(f"{path}.nodes[{i}].id: 必须为非空字符串")
        if nid in ids:
            raise SpecCompileError(f"{path}.nodes: id 重复 {nid!r}")
        ids[nid] = True
        for k, v in n.items():
            if k == "id":
                continue
            if k == "kind" and v in {"src", "proc", "judge", "end", "note"}:
                continue
            if k == "text" and isinstance(v, str):
                _check_rich_text(v, f"{path}.nodes[{i}].text")
                continue
            raise SpecCompileError(f"{path}.nodes[{i}].{k}: 不支持字段或值 {v!r}（kind ∈ src|proc|judge|end|note）")
    for i, e in enumerate(g.get("edges", [])):
        ep = f"{path}.edges[{i}]"
        if not isinstance(e, dict) or "from" not in e or "to" not in e:
            raise SpecCompileError(f"{ep}: 必须声明 from 与 to")
        for k, v in e.items():
            if k in ("from", "to"):
                if v not in ids:
                    raise SpecCompileError(f"{ep}.{k}: 引用不存在的节点 {v!r}（可选: {sorted(ids)}）")
            elif k == "label":
                if not isinstance(v, str):
                    raise SpecCompileError(f"{ep}.label: 必须为字符串")
                _check_rich_text(v, f"{ep}.label")
            elif k == "way":
                if v not in ("straight", "orth"):
                    raise SpecCompileError(f"{ep}.way: 必须为 straight|orth")
            else:
                raise SpecCompileError(f"{ep}.{k}: 未知边字段 {k!r}（可用 from/to/label/way）")
    groups = g.get("groups", [])
    for i, gr in enumerate(groups):
        gp = f"{path}.groups[{i}]"
        if not isinstance(gr, dict) or "id" not in gr or "members" not in gr:
            raise SpecCompileError(f"{gp}: 必须声明 id 与 members")
        if not isinstance(gr["members"], list) or not gr["members"]:
            raise SpecCompileError(f"{gp}.members: 必须为非空列表")
        for m in gr["members"]:
            if m not in ids:
                raise SpecCompileError(f"{gp}.members: 引用不存在的节点 {m!r}")
        for k, v in gr.items():
            if k not in ("id", "label", "members"):
                raise SpecCompileError(f"{gp}.{k}: 未知 group 字段 {k!r}")
        if isinstance(gr.get("label"), str):
            _check_rich_text(gr["label"], f"{gp}.label")
    start = g.get("start")
    if start is not None and start not in ids:
        raise SpecCompileError(f"{path}.start: 引用不存在的节点 {start!r}")


def _check_graph_semantics(out, sg):
    """A 契约（flowchart 方法论合同消费；styleguides.flowchart.semantics 单一事实源）。

    复杂图（节点数 ≥ branch_min_nodes）必须显式声明分支结构——全 proc 线性链
    是同质化主因：fail-closed exit 2（不静默放行"字段合法却同质化"）；真线性
    流程显式 linear: true 逃生（不误伤合法直线）；简单流程（< 阈值）放行；
    vertical（组织树）天然层级，不适用。signature = graph_sig.linear_chain。"""
    if sg != "flowchart":
        return
    import graph_sig as GS
    import styleguides as _SG
    sem = (_SG.RULE_SETS.get("flowchart") or {}).get("semantics") or {}
    bmin = int(sem.get("branch_min_nodes", 5))
    escape = sem.get("linear_escape", "linear")
    for si, sl in enumerate(out.get("slides") or []):
        pp = f"meta.slides[{si}]"
        for i, e in enumerate(sl.get("elements") or []):
            if e.get("type") != "graph":
                continue
            if (e.get("orientation") or "horizontal") == "vertical":
                continue
            if e.get(escape):
                continue
            if GS.linear_chain(e, bmin):
                raise SpecCompileError(
                    f"{pp}.elements[{i}]: 流程图 {e['id']} 节点数 {len(e.get('nodes') or [])}"
                    f" ≥ {bmin} 却无分支表达（全直线链 = 同质化主因）。请补分支/判断"
                    f"结构（出度≥2 节点、judge 语义、end 终点），真线性流程则显式"
                    f"声明 {escape}: true 逃生（方法论见 references/flowchart-method.md）")


def _check_container_children(children, path, palette, cur_page=None, n_pages=None,
                              base_dir=None):
    """stack/dock children：形状元素，无 rect 或相对尺寸。"""
    if not isinstance(children, list) or not children:
        raise SpecCompileError(f"{path}.children: 必须为非空列表")
    for i, c in enumerate(children):
        cp = f"{path}.children[{i}]"
        if not isinstance(c, dict) or "id" not in c:
            raise SpecCompileError(f"{cp}: 必须为含 id 的 dict")
        if "rect" in c:
            raise SpecCompileError(f"{cp}: 容器 children 不得声明绝对 rect（由求解器产 rect）")
        _check_elem(c, cp, palette, is_child=True, cur_page=cur_page,
                    n_pages=n_pages, base_dir=base_dir)


def _check_link(lk, path, cur_page=None, n_pages=None):
    """元素级超链接：{url|slide|email} 三选一。slide = 1-based 页号，编译期
    边界校验（≤ 总页数；指向本页的自跳无意义——链接须跨页）。"""
    if not isinstance(lk, dict):
        raise SpecCompileError(f"{path}: 必须为 dict{{url|slide|email}}，实为 {lk!r}")
    for k in lk:
        if k not in ("url", "slide", "email"):
            raise SpecCompileError(f"{path}.{k}: 未知键（url/slide/email 三选一）")
    n = sum(1 for k in ("url", "slide", "email") if k in lk)
    if n != 1:
        raise SpecCompileError(f"{path}: 必须仅声明 url|slide|email 之一，实为 {n} 项")
    if "url" in lk:
        u = lk["url"]
        if not isinstance(u, str) or not u.strip():
            raise SpecCompileError(f"{path}.url: 必须为非空字符串")
    elif "email" in lk:
        em = lk["email"]
        if not isinstance(em, str) or not em.strip():
            raise SpecCompileError(f"{path}.email: 必须为非空字符串")
    else:
        s = lk["slide"]
        if isinstance(s, bool) or not isinstance(s, int):
            raise SpecCompileError(f"{path}.slide: 必须为整数页号（1-based）")
        npg = n_pages if n_pages is not None else 1
        if s < 1 or s > npg:
            raise SpecCompileError(f"{path}.slide: 跳转目标页 {s} 越界（共 {npg} 页，"
                                   f"页号 1-based）")
        if cur_page is not None and s == cur_page:
            raise SpecCompileError(f"{path}.slide: 跳转目标 {s} = 本页（第 {cur_page} 页），"
                                   f"恒等自跳无意义；请指向其他页")


def _check_cylinder(e, path):
    """cylinder 专属键：slice（可见切面比例，<1 = 剖视不画顶面）、
    opacity（侧壁不透明度）、face_opacity（端面目标不透明度，缺省 1 = 实色）。
    slice 是切面语义——0 < slice ≤ 1（1 = 完整圆柱）。"""
    sl = e.get("slice")
    if sl is not None:
        v = _num(sl, "slice", path)
        if not 0.0 < v <= 1.0:
            raise SpecCompileError(f"{path}.slice: 必须 ∈ (0, 1]（1 = 完整圆柱，"
                                   f"<1 = 剖视不画顶面），实为 {sl!r}")
    op = e.get("opacity")
    if op is not None:
        v = _num(op, "opacity", path)
        if not 0.0 <= v <= 1.0:
            raise SpecCompileError(f"{path}.opacity: 必须 ∈ [0, 1]（侧壁不透明度），"
                                   f"实为 {op!r}")
    fo = e.get("face_opacity")
    if fo is not None:
        v = _num(fo, "face_opacity", path)
        if not 0.0 < v <= 1.0:
            raise SpecCompileError(f"{path}.face_opacity: 必须 ∈ (0, 1]"
                                   f"（端面目标不透明度），实为 {fo!r}")
        # 端面叠于侧壁之上（2 层合成 = face_opacity），端面自身须比侧壁更不透明；
        # 否则叠区不可能达到目标（alpha_math.face_alpha 反解无解）
        if v <= _num(op if op is not None else 0.35, "opacity", path):
            raise SpecCompileError(f"{path}.face_opacity: 必须 > opacity"
                                   f"（端面叠于侧壁之上，合成不透明度 ≥ 侧壁），"
                                   f"实为 {fo!r} ≤ {op or 0.35!r}")


def _check_brush(e, path, palette, base_dir=None):
    """brush 积木（C3 书法矢量字）：text 必填非空；font 别名/路径；
    style 白名单 = fill/image/alpha（fill 与 image 互斥——填充二选一）；
    align/anchor = 字形在声明盒内的落位；spacing = 字距（em 比例，≥0）。"""
    tx = e.get("text")
    if not isinstance(tx, str) or not tx.strip():
        raise SpecCompileError(f"{path}.text: brush 必须声明非空 text（字形源），"
                               f"实为 {tx!r}")
    ft = e.get("font")
    if not isinstance(ft, str) or not ft.strip():
        raise SpecCompileError(f"{path}.font: 必须为字体别名（kai/hei/song/fang/yahei）"
                               f"或 .ttf/.ttc 路径，实为 {ft!r}")
    if "align" in e and e["align"] not in ("left", "center", "right"):
        raise SpecCompileError(f"{path}.align: 必须 ∈ left/center/right，实为 {e['align']!r}")
    if "anchor" in e and e["anchor"] not in ("top", "middle", "bottom"):
        raise SpecCompileError(f"{path}.anchor: 必须 ∈ top/middle/bottom，实为 {e['anchor']!r}")
    if "spacing" in e:
        sp = _num(e["spacing"], "spacing", path)
        if sp < 0:
            raise SpecCompileError(f"{path}.spacing: 不允许负数（em 比例字距）")
    st = e.get("style")
    if st is not None:
        if not isinstance(st, dict):
            raise SpecCompileError(f"{path}.style: 必须为 dict")
        for k in st:
            if k not in ("fill", "grad", "image", "alpha"):
                raise SpecCompileError(f"{path}.style.{k}: 未知键"
                                       f"（fill/grad/image/alpha）")
        if "fill" in st and "image" in st:
            raise SpecCompileError(f"{path}.style: fill 与 image 互斥（实色/渐变 vs 图片填充）")
        if "fill" in st:
            _check_color(st["fill"], f"{path}.style.fill", palette)
        if "grad" in st:
            g = st["grad"]
            if not isinstance(g, list) or len(g) != 2:
                raise SpecCompileError(f"{path}.style.grad: 必须为两色列表 [c1, c2]")
            for i, c in enumerate(g):
                _check_color(c, f"{path}.style.grad[{i}]", palette)
        if "image" in st:
            img = st["image"]
            if not isinstance(img, str) or not img.strip():
                raise SpecCompileError(f"{path}.style.image: 必须为非空图片路径字符串")
            resolved = img if os.path.isabs(img) else os.path.abspath(
                os.path.join(base_dir or ".", img))
            if not os.path.isfile(resolved):
                raise SpecCompileError(f"{path}.style.image: 图片文件不存在 {resolved!r}"
                                       f"（相对 SPEC 目录解析）")
            st["image"] = resolved          # 写回绝对路径（渲染层直接使用）
        if "alpha" in st:
            a = _num(st["alpha"], "alpha", path)
            if not 0.0 <= a <= 1.0:
                raise SpecCompileError(f"{path}.style.alpha: 必须 ∈ [0, 1]，实为 {st['alpha']!r}")


def _check_icon(e, path, palette):
    """icon 积木（B1 矢量图标库）：icon 必填（Lucide 名或中文/英文关键词——
    未命中由 icon_lib.resolve 回退 circle-dot，fail-soft 不阻断）；style 专属
    schema = color/weight（描边语义，无填充）；align/anchor = 图标在声明盒内落位。"""
    ic = e.get("icon")
    if not isinstance(ic, str) or not ic.strip():
        raise SpecCompileError(f"{path}.icon: 必须为图标名或关键词字符串，实为 {ic!r}")
    if "align" in e and e["align"] not in ("left", "center", "right"):
        raise SpecCompileError(f"{path}.align: 必须 ∈ left/center/right，实为 {e['align']!r}")
    if "anchor" in e and e["anchor"] not in ("top", "middle", "bottom"):
        raise SpecCompileError(f"{path}.anchor: 必须 ∈ top/middle/bottom，实为 {e['anchor']!r}")
    st = e.get("style")
    if st is not None:
        if not isinstance(st, dict):
            raise SpecCompileError(f"{path}.style: 必须为 dict")
        for k in st:
            if k not in ("color", "weight"):
                raise SpecCompileError(f"{path}.style.{k}: 未知键（icon 只有 color/weight）")
        if "color" in st:
            _check_color(st["color"], f"{path}.style.color", palette)
        if "weight" in st:
            w = _num(st["weight"], "weight", path)
            if w <= 0:
                raise SpecCompileError(f"{path}.style.weight: 必须 > 0（描边磅值），"
                                       f"实为 {st['weight']!r}")


def _check_curve(e, path, palette):
    """curve 积木：rect 包围盒 + 归一化点列（0~1 相对 rect，ir_builder 展开为绝对
    坐标 polyline，freeform 渲染）。style 白名单 = color/weight/dash（线语义，无填充）。"""
    pts = e.get("points")
    if not isinstance(pts, list) or len(pts) < 3:
        raise SpecCompileError(f"{path}.points: 必须为 ≥3 个归一化点 "
                               f"（[[x,y],…]，0~1 相对 rect），实为 {pts!r}")
    for i, p in enumerate(pts):
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise SpecCompileError(f"{path}.points[{i}]: 点必须为 [x, y] 二元素，"
                                   f"实为 {p!r}")
        for j, v in enumerate(p):
            vv = _num(v, f"points[{i}][{j}]", path)
            if not 0.0 <= vv <= 1.0:
                raise SpecCompileError(f"{path}.points[{i}][{j}]: 归一化坐标必须 "
                                       f"∈ [0, 1]，实为 {v!r}")
    # 退化防护：全同点列 → 0 尺寸 freeform（a:ext cx/cy=0，违反 ST_PositiveSize2D）
    if len({(float(p[0]), float(p[1])) for p in pts}) < 2:
        raise SpecCompileError(f"{path}.points: 至少需 2 个相异点"
                               f"（全同点产出 0 尺寸曲线），实为 {pts!r}")
    st = e.get("style")
    if st is not None:
        if not isinstance(st, dict):
            raise SpecCompileError(f"{path}.style: 必须为 dict")
        for k in st:
            if k not in ("color", "weight", "dash"):
                raise SpecCompileError(f"{path}.style.{k}: 未知键"
                                       f"（color/weight/dash）")
        if "color" in st:
            _check_color(st["color"], f"{path}.style.color", palette)
        if "weight" in st:
            wt = _num(st["weight"], "weight", f"{path}.style")
            if wt <= 0:
                raise SpecCompileError(f"{path}.style.weight: 必须为正数值，"
                                       f"实为 {st['weight']!r}")
        if "dash" in st:
            if st["dash"] not in BORDER_DASH:
                raise SpecCompileError(f"{path}.style.dash: 必须 ∈ "
                                       f"{sorted(BORDER_DASH)}，实为 {st['dash']!r}")


def _check_typst(e, path, base_dir=None):
    """typst 排版块：源三分互斥（inline `typst` / 外链 `typst_src` / `design` 意图）。
    必须顶层（绝对 rect）——排版块整块为图（SVG），不进容器 children（与 chart 同律）。
    编译由 stage1.5 typst_compile 接管（编译失败 → exit 2，见 build_ppt）。"""
    if "rect" not in e:
        raise SpecCompileError(f"{path}: typst 必须为顶层元素（声明绝对 rect；"
                               "排版块整块为图，不进容器 children）")
    srcs = [k for k in ("typst", "typst_src", "design") if e.get(k) is not None]
    if len(srcs) != 1:
        raise SpecCompileError(
            f"{path}: typst 元素须恰声明 typst（inline 源码）/ typst_src（外链 .typ）/ "
            f"design（LLM 辅助设计）之一，实为 {srcs or '无'}")
    if e.get("typst") is not None and not isinstance(e["typst"], str):
        raise SpecCompileError(f"{path}.typst: 必须为字符串（typst 源码）")
    ts = e.get("typst_src")
    if ts is not None:
        if not isinstance(ts, str) or not ts.strip():
            raise SpecCompileError(f"{path}.typst_src: 必须为非空路径字符串")
        p_ = ts if os.path.isabs(ts) else os.path.join(base_dir or ".", ts)
        if not os.path.isfile(p_):
            raise SpecCompileError(f"{path}.typst_src: 文件不存在 {ts!r}（解析为 {p_}）")
    if e.get("design") is not None:
        raise SpecCompileError(
            f"{path}.design: LLM 辅助设计尚未落地（作业协议见 "
            f"references/typst-chain.md）——请先跑设计作业产出 .typ 后改用 "
            f"typst_src，或直接写内联 typst 源码")
    pre = e.get("preamble")
    if pre is not None and not isinstance(pre, str):
        raise SpecCompileError(f"{path}.preamble: 必须为字符串（共享前导："
                               "字体/宏/@preview 导入）")
    vs = e.get("vars")
    if vs is not None:
        if not isinstance(vs, dict):
            raise SpecCompileError(f"{path}.vars: 必须为 dict(名→值)")
        for k, v in vs.items():
            if not isinstance(k, str) or not k.isidentifier():
                raise SpecCompileError(f"{path}.vars 键 {k!r}: 必须为合法标识符"
                                       "（typst #let 变量名）")
            if isinstance(v, bool) or not isinstance(v, (str, int, float)):
                raise SpecCompileError(f"{path}.vars.{k}: 值须为字符串/数值/布尔，"
                                       f"实为 {type(v).__name__}")


def _check_svg(e, path, base_dir=None):
    """svg 矢量图：源二分互斥（外链 `src` / 内联 `svg`）。必须顶层（绝对 rect）——
    整块多形状（svg_doc 分组），不进容器 children（与 typst/chart 同律）。"""
    if "rect" not in e:
        raise SpecCompileError(f"{path}: svg 必须为顶层元素（声明绝对 rect；"
                               "矢量图整块多形状，不进容器 children）")
    srcs = [k for k in ("src", "svg") if e.get(k) is not None]
    if len(srcs) != 1:
        raise SpecCompileError(
            f"{path}: svg 元素须恰声明 src（外链 .svg 文件）/ svg（内联源码）"
            f"之一，实为 {srcs or '无'}")
    s = e.get("src")
    if s is not None:
        if not isinstance(s, str) or not s.strip():
            raise SpecCompileError(f"{path}.src: 必须为非空 .svg 路径字符串")
        p_ = s if os.path.isabs(s) else os.path.join(base_dir or ".", s)
        if not os.path.isfile(p_):
            raise SpecCompileError(f"{path}.src: 文件不存在 {s!r}（解析为 {p_}）")
        if not str(s).lower().endswith(".svg"):
            raise SpecCompileError(f"{path}.src: 必须为 .svg 文件（得 {s!r}）")
    if e.get("svg") is not None and not isinstance(e["svg"], str):
        raise SpecCompileError(f"{path}.svg: 必须为字符串（SVG 源码）")
    if "style" in e and not isinstance(e["style"], dict):
        raise SpecCompileError(f"{path}.style: 必须为 dict")
    fit = e.get("fit")
    if fit is not None and fit not in ("contain", "stretch"):
        raise SpecCompileError(f"{path}.fit: 必须为 contain|stretch，实为 {fit!r}")
    # 编译期解析 SVG → 缓存分组表（_svg；铁律 1：ir_builder 只做变换零重算）
    import svg_doc
    stxt = e.get("svg")
    if stxt is not None:
        try:
            e["_svg"] = svg_doc.parse(stxt)
        except svg_doc.SvgDocError as ex:
            raise SpecCompileError(f"{path}: svg 源码解析失败 — {ex}")
    else:
        p_ = e["src"] if os.path.isabs(e["src"]) else os.path.join(
            base_dir or ".", e["src"])
        try:
            e["_svg"] = svg_doc.parse_file(p_)
        except svg_doc.SvgDocError as ex:
            raise SpecCompileError(f"{path}: svg 源解析失败（{e['src']}）— {ex}")


def _check_animation(anim, path):
    """元素级动画：{effect: 配方引用 | behaviors: 直写} 二选一，可附
    trigger（with_previous/after_previous/on_click）编排时序；
    delay 为 after_previous 触发时的间隔秒。按页递进逻辑即同页元素
    以 with_previous 同批 + after_previous 串批的"批次—接续"编排。
    effect 引用 animation_recipes 的 35 宏；behaviors 逃生通道逐条校验
    （type ∈ 6 类，字段 = timing 白名单 + 类型专属白名单，property 关键帧
    [time, value(, formula?)]）。"""
    import animation_recipes as AR
    if not isinstance(anim, dict):
        raise SpecCompileError(f"{path}: 必须为 dict{{effect|behaviors}}，实为 {anim!r}")
    for k in anim:
        if k not in ("effect", "behaviors", "trigger", "delay"):
            raise SpecCompileError(f"{path}.{k}: 未知键（effect/behaviors/trigger/delay）")
    tr = anim.get("trigger", "with_previous")
    if tr not in ("with_previous", "after_previous", "on_click"):
        raise SpecCompileError(f"{path}.trigger: 未知触发 {tr!r}"
                               f"（可选 with_previous/after_previous/on_click）")
    if "delay" in anim and (isinstance(anim["delay"], bool)
                            or not isinstance(anim["delay"], (int, float))
                            or anim["delay"] < 0):
        raise SpecCompileError(f"{path}.delay: 必须为非负数值秒，实为 {anim['delay']!r}")
    has_e, has_b = "effect" in anim, "behaviors" in anim
    if has_e == has_b:
        raise SpecCompileError(f"{path}: 必须仅声明 effect 或 behaviors 之一，"
                               f"实为 effect={has_e} behaviors={has_b}")
    if has_e:
        name = anim["effect"]
        if not isinstance(name, str) or name not in AR.RECIPES:
            raise SpecCompileError(f"{path}.effect: 未知动画配方 {name!r}"
                                   f"（可用 {sorted(AR.RECIPES)}）")
        return
    bhs = anim["behaviors"]
    if not isinstance(bhs, list) or not bhs:
        raise SpecCompileError(f"{path}.behaviors: 必须为非空列表")
    for i, b in enumerate(bhs):
        bp = f"{path}.behaviors[{i}]"
        if not isinstance(b, dict) or "type" not in b:
            raise SpecCompileError(f"{bp}: 必须为含 type 的 dict")
        t = b["type"]
        if t not in AR.BEHAVIOR_TYPE_FIELDS:
            raise SpecCompileError(f"{bp}.type: 未知行为类型 {t!r}"
                                   f"（可用 {sorted(AR.BEHAVIOR_TYPE_FIELDS)}）")
        if "dur" not in b or not isinstance(b["dur"], (int, float)):
            raise SpecCompileError(f"{bp}: 必须声明数值 dur（时长）")
        for k in b:
            if k == "type" or k in AR.TIMING_FIELDS:
                continue
            if k not in AR.BEHAVIOR_TYPE_FIELDS[t]:
                raise SpecCompileError(f"{bp}.{k}: type={t} 不允许字段（可选 "
                                       f"{sorted(AR.TIMING_FIELDS | AR.BEHAVIOR_TYPE_FIELDS[t])}）")
        if t == "property":
            pts = b.get("points")
            if not isinstance(pts, list) or not pts:
                raise SpecCompileError(f"{bp}.points: property 必须声明关键帧点列表")
            for j, p in enumerate(pts):
                if (not isinstance(p, (list, tuple)) or len(p) not in (2, 3)
                        or isinstance(p[0], bool) or not isinstance(p[0], (int, float))):
                    raise SpecCompileError(f"{bp}.points[{j}]: 点必须为 "
                                           f"[time, value(, formula?)]，实为 {p!r}")


def _check_anchors(e, path):
    """具名锚点（scansci 内化）：锚点 = 归一坐标 [nx, ny] ∈ [0,1]²，相对元素 rect；
    连接配方 from_anchor/to_anchor 引用其名（glue 校验点承接）。

    能力级 fail-closed（capabilities.ELEMENT_CAPS.anchorable）：仅"有可锚定 rect 的
    单形状"可声明锚点——容器不产单形状、线锚点缺语义 → 编译即拒（防静默 no-op：
    此前非 shape 元素的 anchors 既不校验也不展开）。"""
    if "anchors" not in e:
        return
    if not CAP.supports(e.get("type"), "anchorable"):
        raise SpecCompileError(
            f"{path}.anchors: 元素类型 {e.get('type')!r} 不支持具名锚点"
            f"（须有可锚定 rect 的单形状；容器/线缺语义，见 capabilities.py）")
    if not isinstance(e["anchors"], dict) or not e["anchors"]:
        raise SpecCompileError(f"{path}.anchors: 必须为非空 dict"
                               "（name → [nx, ny]）")
    for an, val in e["anchors"].items():
        if not isinstance(an, str) or not an:
            raise SpecCompileError(f"{path}.anchors: 锚点名必须为非空字符串")
        if (not isinstance(val, (list, tuple)) or len(val) != 2
                or not all(isinstance(v, (int, float))
                           and not isinstance(v, bool) and 0.0 <= v <= 1.0
                           for v in val)):
            raise SpecCompileError(f"{path}.anchors.{an}: 必须为"
                                   " [nx, ny] 且 nx,ny ∈ [0,1]")


def _check_elem(e, path, palette, is_child=False, cur_page=None, n_pages=None,
                base_dir=None):
    etype = e.get("type")
    if etype not in ELEMENT_TYPES:
        raise SpecCompileError(f"{path}.type: 未知元素类型 {etype!r}（可用 {sorted(ELEMENT_TYPES)}）")
    if is_child and etype in CAP.CONTAINER_TYPES:
        raise SpecCompileError(f"{path}: 容器 children 内不得再嵌套容器（扁平代理：先建容器再 relations 互引）")
    # 顶层专属元素（table/chart/typst）：能力级拒收进 children（capabilities.top_level_only）
    if is_child and CAP.supports(etype, "top_level_only"):
        raise SpecCompileError(f"{path}: {etype} 必须为顶层元素（rect 固定、整块产图，"
                               f"不进容器 children；见 capabilities.py）")
    rk = e.get("rect_kind", "absolute")
    if rk not in ("absolute", "ratio"):
        raise SpecCompileError(f"{path}.rect_kind: 必须 ∈ absolute|ratio，实为 {rk!r}")
    if is_child and rk == "ratio":
        raise SpecCompileError(f"{path}.rect_kind: 容器 children 由求解器产 rect，不支持 ratio")
    if "rect" not in e:
        if not is_child:
            raise SpecCompileError(f"{path}: 顶层元素必须声明绝对 rect")
    elif rk == "ratio":
        _check_ratio_rect(e["rect"], path)
    elif etype == "line":
        # line 的 rect 是"线盒"（端点包围盒），允许 0 宽/0 高（纵向/横向边线）
        _check_rect(e["rect"], path, permissive=True)
    else:
        _check_rect(e["rect"], path)
    if "z" in e:
        z = _num(e["z"], "z", path)
        if z != int(z) or int(z) < 0:
            raise SpecCompileError(f"{path}.z: 必须为非负整数，实为 {e['z']!r}")
        e["z"] = int(z)
    if "style" in e and etype not in ("chart", "curve", "brush", "icon"):
        # chart/curve/brush/icon 的 style 是专属 schema：chart（legend/data_labels/colors…）
        # 由 _check_chart 校验；curve（color/weight/dash 线语义）由 _check_curve 校验；
        # brush（fill/grad/image/alpha 填充语义）由 _check_brush 校验；
        # icon（color/weight 描边语义）由 _check_icon 校验
        _check_style(e["style"], path, palette)
    if "text_style" in e:
        _check_text_style(e["text_style"], path, palette)
    _check_anchors(e, path)
    if etype == "shape":
        kind = e.get("kind", "rounded_rect")
        if kind not in SHAPE_KINDS:
            raise SpecCompileError(f"{path}.kind: 必须 ∈ {sorted(SHAPE_KINDS)}，实为 {kind!r}")
        if "text" in e and not isinstance(e["text"], str):
            raise SpecCompileError(f"{path}.text: 必须为字符串")
        if "text" in e:
            _check_rich_text(e["text"], f"{path}.text")
        if kind == "cylinder":
            _check_cylinder(e, path)
        elif "slice" in e or "opacity" in e:
            raise SpecCompileError(f"{path}: slice/opacity 仅 cylinder 支持"
                                   f"（kind={kind}）")
    elif etype == "text":
        if "text" not in e or not isinstance(e["text"], str):
            raise SpecCompileError(f"{path}.text: text 元素必须声明文本字符串")
        _check_rich_text(e["text"], f"{path}.text")
    elif etype in ("image", "diagram"):
        src = e.get("src")
        ph = e.get("placeholder")
        if ph is not None and not isinstance(ph, (bool, str)):
            raise SpecCompileError(f"{path}.placeholder: 必须为布尔或提示字符串")
        if isinstance(ph, str) and not ph.strip():
            raise SpecCompileError(f"{path}.placeholder: 提示字符串不得为空（缺省用 caption/兜底文案）")
        cap = e.get("caption")
        if cap is not None and not isinstance(cap, str):
            raise SpecCompileError(f"{path}.caption: 必须为字符串")
        if etype == "diagram" and ph:
            raise SpecCompileError(f"{path}: diagram 不支持 placeholder"
                                   f"（diagram = 外部预渲染产物逃生通道，必须给 src）")
        if not ph and (not isinstance(src, str) or not src.strip()):
            raise SpecCompileError(f"{path}.src: 必须为图像路径字符串"
                                   f"（或声明 placeholder: true/<提示词> 占位）")
        vb = e.get("visual_bounds")
        if vb is not None and vb != "auto":
            raise SpecCompileError(f"{path}.visual_bounds: 仅支持 'auto'（alpha 裁切 + 放大补偿）")
    elif etype == "table":
        _check_table(e, path, palette)
    elif etype == "chart":
        _check_chart(e, path, palette)
    elif etype == "formula":
        expr = e.get("expr")
        if not isinstance(expr, str) or not expr.strip():
            raise SpecCompileError(f"{path}.expr: formula 必须声明非空 expr（UnicodeMath 子集，"
                                   f"边界见 references/formula-omml.md）")
    elif etype == "line":
        for k in ("x1", "y1", "x2", "y2"):
            _num(e.get(k), k, path)
        if "dash" in e and e["dash"] not in BORDER_DASH:
            raise SpecCompileError(f"{path}.dash: 必须 ∈ {sorted(BORDER_DASH)}，"
                                   f"实为 {e['dash']!r}")
    elif etype == "curve":
        _check_curve(e, path, palette)
    elif etype == "brush":
        _check_brush(e, path, palette, base_dir=base_dir)
    elif etype == "icon":
        _check_icon(e, path, palette)
    elif etype == "typst":
        _check_typst(e, path, base_dir)
    elif etype == "svg":
        _check_svg(e, path, base_dir)
    elif etype == "stack":
        if "orientation" in e and e["orientation"] not in ("vertical", "horizontal"):
            raise SpecCompileError(f"{path}.orientation: 必须为 vertical|horizontal")
        if "gap" in e:
            g_ = _num(e["gap"], "gap", path)
            if g_ < 0:
                raise SpecCompileError(f"{path}.gap: 不允许负数间距")
        _check_container_children(e.get("children", []), path, palette,
                                  base_dir=base_dir)
    elif etype == "dock":
        pads = e.get("padding", {})
        if not isinstance(pads, dict):
            raise SpecCompileError(f"{path}.padding: 必须为 dict(l/t/r/b)")
        for k, v in pads.items():
            if k not in ("l", "t", "r", "b"):
                raise SpecCompileError(f"{path}.padding.{k}: 未知键（l/t/r/b）")
            _num(v, k, f"{path}.padding")
        _check_container_children(e.get("children", []), path, palette,
                                  base_dir=base_dir)
    elif etype == "graph":
        _check_graph(e, path, palette)
    # link（元素级超链接）：能力级拒收（capabilities.linkable）——容器不产单形状，
    # 渲染无形状可挂 hlinkClick；children 形状允许（随容器求解出 rect 后同律注入）
    lk = e.get("link")
    if lk is not None:
        if not CAP.supports(etype, "linkable"):
            raise SpecCompileError(f"{path}.link: 元素类型 {etype!r} 不支持超链接"
                                   f"（不产单形状；children 形状可挂）")
        _check_link(lk, f"{path}.link", cur_page, n_pages)
    # animation（动效）：能力级拒收（capabilities.animatable）——容器不产单形状，
    # 渲染无单形状可挂时间轴；children 形状允许
    anim = e.get("animation")
    if anim is not None:
        if not CAP.supports(etype, "animatable"):
            raise SpecCompileError(f"{path}.animation: 元素类型 {etype!r} 不支持动画"
                                   f"（不产单形状；children 形状可挂）")
        _check_animation(anim, f"{path}.animation")
    aexit = e.get("animation_exit")
    if aexit is not None:
        if not CAP.supports(etype, "animatable"):
            raise SpecCompileError(f"{path}.animation_exit: 元素类型 {etype!r} 不支持动画"
                                   f"（不产单形状；children 形状可挂）")
        _check_animation(aexit, f"{path}.animation_exit")


TRANSITION_EFFECTS = {"fade", "push", "wipe", "cut", "morph", "none"}
TRANSITION_SPD = {"slow", "med", "fast"}

# 页型意图（page_intent）—— 审定版式菜单的枚举选择（grilling 收敛：agent 只选
# intent token，布局由引擎确定性展开，防刻板且保 harness）。每页型对应一个
# 版式族 + 专属字段 + verify 专属断言（references/page-intents.md）。
# 能力档案（scripts/capabilities.py）是唯一事实源：枚举/字段/id 均由其派生；
# status=planned 的页型编译即拒（fail-closed，防"字段合法却无展开"的静默 no-op）。
PAGE_INTENTS = CAP.PAGE_INTENTS
PAGE_INTENT_FIELDS = CAP.PAGE_INTENT_FIELDS
PAGE_INTENT_EL_IDS = CAP.PAGE_INTENT_EL_IDS

SLIDE_KEYS = {"title", "elements", "relations", "margin", "framework", "notes",
              "transition", "page_intent", "brief", "anim", "params"} | PAGE_INTENTS


def _check_notes(v, path):
    if v is not None and not isinstance(v, str):
        raise SpecCompileError(f"{path}: 必须为字符串（备注页文本）")


def _pi_cover(val, fp, slide, palette):
    title = val.get("title")
    if not isinstance(title, str) or not title.strip():
        raise SpecCompileError(f"{fp}.title: cover 必须声明非空 title")
    for k in ("subtitle", "meta"):
        if k in val and not isinstance(val[k], str):
            raise SpecCompileError(f"{fp}.{k}: 必须为字符串")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    dup = [e["id"] for e in slide.get("elements", [])
           if e.get("id") in PAGE_INTENT_EL_IDS]
    if dup:
        raise SpecCompileError(f"{fp}: 元素 id {dup} 与 cover 引擎展开保留"
                               "（cov_title/cov_sub/cov_meta/cov_deco）冲突，"
                               "请换元素 id")


def _pi_section(val, fp, slide, palette):
    for k in ("title", "num"):
        if not (isinstance(val.get(k), str) and val[k].strip()):
            raise SpecCompileError(f"{fp}.{k}: section 必须声明非空 {k}")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    dup = [e["id"] for e in slide.get("elements", [])
           if e.get("id") in PAGE_INTENT_EL_IDS]
    if dup:
        raise SpecCompileError(f"{fp}: 元素 id {dup} 与 section 引擎展开保留"
                               "（sec_num/sec_title/sec_deco/sec_guide）冲突，"
                               "请换元素 id")


def _pi_problem(val, fp, slide, palette):
    title = val.get("title")
    if not (isinstance(title, str) and title.strip()):
        raise SpecCompileError(f"{fp}.title: problem 必须声明非空 title")
    items = val.get("items")
    if items is not None:
        if not (isinstance(items, list) and items
                and all(isinstance(s, str) and s.strip() for s in items)):
            raise SpecCompileError(f"{fp}.items: 须为非空字符串列表")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    dup = [e["id"] for e in slide.get("elements", [])
           if e.get("id") in PAGE_INTENT_EL_IDS]
    if dup:
        raise SpecCompileError(f"{fp}: 元素 id {dup} 与 problem 引擎展开保留"
                               "（prb_badge/prb_title/prb_items）冲突，请换元素 id")


def _pi_versus(val, fp, slide, palette):
    for k in ("left_title", "right_title"):
        if not (isinstance(val.get(k), str) and val[k].strip()):
            raise SpecCompileError(f"{fp}.{k}: versus 必须声明非空 {k}")
    for k in ("left_items", "right_items"):
        lst = val.get(k)
        if lst is not None and not (isinstance(lst, list)
                                    and all(isinstance(s, str) for s in lst)):
            raise SpecCompileError(f"{fp}.{k}: 须为字符串列表")
    vsv = val.get("vs")
    if vsv is not None and not isinstance(vsv, str):
        raise SpecCompileError(f"{fp}.vs: 必须为字符串")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    dup = [e["id"] for e in slide.get("elements", [])
           if e.get("id") in PAGE_INTENT_EL_IDS]
    if dup:
        raise SpecCompileError(f"{fp}: 元素 id {dup} 与 versus 引擎展开保留"
                               "（vsv_panel_*/vsv_title_*/vsv_body_*/vsv_divider/"
                               "vsv_tag）冲突，请换元素 id")


def _pi_route(val, fp, slide, palette):
    stages = val.get("stages")
    if not (isinstance(stages, list)
            and len(stages) >= 2
            and all(isinstance(s, str) and s.strip() for s in stages)):
        raise SpecCompileError(f"{fp}.stages: route 须声明 ≥2 项非空字符串列表"
                               "（技术路线的阶段链）")
    title = val.get("title")
    if title is not None and not isinstance(title, str):
        raise SpecCompileError(f"{fp}.title: 必须为字符串")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    dup = [e["id"] for e in slide.get("elements", [])
           if isinstance(e.get("id"), str) and e["id"].startswith("rte_")]
    if dup:
        raise SpecCompileError(f"{fp}: 元素 id {dup} 占用 route 引擎保留前缀"
                               " rte_（rte_title/rte_stage*/rte_lnk*），请换元素 id")


# 页型深检注册表（数据驱动；键 ⊆ capabilities.PAGE_INTENTS_IMPLEMENTED）。
# 通用白名单/变体/id 检查在 _check_page_intent 内，逐页型深检在此查表。

def _pi_title_required(val, fp, name):
    t = val.get("title")
    if not (isinstance(t, str) and t.strip()):
        raise SpecCompileError(f"{fp}.title: {name} 必须声明非空 title（页题）")


def _pi_items(val, fp, key="items", allow_dict=True):
    items = val.get(key)
    if not (isinstance(items, list) and items):
        raise SpecCompileError(f"{fp}.{key}: 须为非空列表（每项字符串或 {{head/body}}）")
    for i, it in enumerate(items):
        if isinstance(it, str):
            if not it.strip():
                raise SpecCompileError(f"{fp}.{key}[{i}]: 字符串项不可为空")
        elif isinstance(it, dict) and allow_dict:
            if not any(k in it for k in ("head", "title", "value")):
                raise SpecCompileError(f"{fp}.{key}[{i}]: dict 项须含 head/title/value")
        else:
            raise SpecCompileError(f"{fp}.{key}[{i}]: 须为字符串或 dict（{{head,body}}）")


def _pi_prefix_dup(val, fp, slide, prefix, hint):
    dup = [e["id"] for e in slide.get("elements", [])
           if isinstance(e.get("id"), str) and e["id"].startswith(prefix)]
    if dup:
        raise SpecCompileError(f"{fp}: 元素 id {dup} 占用 {hint} 引擎保留前缀 {prefix}，"
                               "请换元素 id")


def _pi_panels(val, fp, slide, palette):
    _pi_title_required(val, fp, "panels")
    _pi_items(val, fp)
    cols = val.get("cols")
    if cols is not None and (isinstance(cols, bool) or not isinstance(cols, int) or cols < 1):
        raise SpecCompileError(f"{fp}.cols: 必须为正整数（列数）")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    _pi_prefix_dup(val, fp, slide, "pnl_", "panels")


def _pi_columns(val, fp, slide, palette):
    _pi_title_required(val, fp, "columns")
    cols = val.get("cols")
    if not (isinstance(cols, list) and cols):
        raise SpecCompileError(f"{fp}.cols: 须为非空列表（每栏字符串或 {{head,items}}）")
    for i, c in enumerate(cols):
        if isinstance(c, str):
            if not c.strip():
                raise SpecCompileError(f"{fp}.cols[{i}]: 字符串项不可为空")
        elif isinstance(c, dict):
            if not any(k in c for k in ("head", "title", "items")):
                raise SpecCompileError(f"{fp}.cols[{i}]: dict 栏须含 head/title 或 items")
            its = c.get("items")
            if its is not None and not (isinstance(its, list)
                                        and all(isinstance(s, str) for s in its)):
                raise SpecCompileError(f"{fp}.cols[{i}].items: 须为字符串列表")
        else:
            raise SpecCompileError(f"{fp}.cols[{i}]: 须为字符串或 dict")
    bottom = val.get("bottom")
    if bottom is not None and not (isinstance(bottom, str)
                                   or (isinstance(bottom, list)
                                       and all(isinstance(s, str) for s in bottom))):
        raise SpecCompileError(f"{fp}.bottom: 须为字符串或字符串列表")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    _pi_prefix_dup(val, fp, slide, "col_", "columns")


def _pi_kpis(val, fp, slide, palette):
    _pi_title_required(val, fp, "kpis")
    _pi_items(val, fp)
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    _pi_prefix_dup(val, fp, slide, "kpi_", "kpis")


def _pi_cards(val, fp, slide, palette):
    _pi_title_required(val, fp, "cards")
    _pi_items(val, fp)
    cols = val.get("cols")
    if cols is not None and (isinstance(cols, bool) or not isinstance(cols, int) or cols < 1):
        raise SpecCompileError(f"{fp}.cols: 必须为正整数（列数）")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    _pi_prefix_dup(val, fp, slide, "crd_", "cards")


def _pi_figure_text(val, fp, slide, palette):
    _pi_title_required(val, fp, "figure_text")
    img = val.get("image")
    if img is not None and not isinstance(img, str):
        raise SpecCompileError(f"{fp}.image: 必须为字符串（图片路径；缺省 = 占位框）")
    cap = val.get("caption")
    if cap is not None and not isinstance(cap, str):
        raise SpecCompileError(f"{fp}.caption: 必须为字符串")
    blocks = val.get("blocks")
    if not (isinstance(blocks, list) and blocks):
        raise SpecCompileError(f"{fp}.blocks: 须为非空列表（正文块）")
    for i, b in enumerate(blocks):
        if isinstance(b, str):
            if not b.strip():
                raise SpecCompileError(f"{fp}.blocks[{i}]: 字符串项不可为空")
        elif not isinstance(b, dict):
            raise SpecCompileError(f"{fp}.blocks[{i}]: 须为字符串或 dict")
    side = val.get("side")
    if side is not None and side not in ("left", "right"):
        raise SpecCompileError(f"{fp}.side: 必须 ∈ left|right")
    acc = val.get("accent")
    if acc is not None:
        _check_color(acc, f"{fp}.accent", palette)
    _pi_prefix_dup(val, fp, slide, "fgt_", "figure_text")


_PI_VALIDATORS = {
    "cover": _pi_cover,
    "section": _pi_section,
    "problem": _pi_problem,
    "versus": _pi_versus,
    "route": _pi_route,
    "panels": _pi_panels,
    "columns": _pi_columns,
    "kpis": _pi_kpis,
    "cards": _pi_cards,
    "figure_text": _pi_figure_text,
}


def _check_page_intent(slide, pp, palette):
    """页型意图：page_intent ∈ 枚举；页型专属字段（cover/section/…）只随对应
    intent 出现、字段白名单校验（cover.title 必填，subtitle/meta/accent 可选，
    accent 为 palette token）。展开元素 id（cov_*）与页内用户元素 id 不得撞名。
    逐页型深检 = _PI_VALIDATORS 查表（数据驱动，扩展新页型只加一项）。"""
    intent = slide.get("page_intent")
    if intent is None:
        # 页型字段出现却未声明 page_intent → 静默 no-op（引擎无从展开）→ fail-closed
        stray = [fk for fk in PAGE_INTENTS if slide.get(fk) is not None]
        if stray:
            raise SpecCompileError(
                f"{pp}.{stray[0]}: 页型字段 {stray[0]} 出现但未声明 page_intent"
                f"（字段须随对应 intent 声明；可选 {sorted(CAP.PAGE_INTENTS_IMPLEMENTED)}）")
        return None, None
    if not isinstance(intent, str) or intent not in PAGE_INTENTS:
        raise SpecCompileError(f"{pp}.page_intent: 未知页型 {intent!r}"
                               f"（可选 {sorted(PAGE_INTENTS)}）")
    if not CAP.intent_implemented(intent):
        raise SpecCompileError(
            f"{pp}.page_intent: 页型 {intent!r} 尚未落地（status=planned），"
            f"暂不可用（可选 {sorted(CAP.PAGE_INTENTS_IMPLEMENTED)}）；"
            f"落地协议见 references/page-intents.md §扩展新原型")
    # 有专属字段的页型（cover/section）：字段 dict 是引擎展开的必需输入，缺则编译拒
    # （fail-closed：防 page_intent 声明了却不给展开输入，把违约留到 verify）
    if CAP.PAGE_INTENT_FIELDS[intent] and slide.get(intent) is None:
        raise SpecCompileError(
            f"{pp}.{intent}: page_intent={intent!r} 必须声明 {intent}: 字段"
            "（引擎展开的必需输入，见 references/page-intents.md）")
    for fk in PAGE_INTENTS:
        val = slide.get(fk)
        if val is None:
            continue
        fp = f"{pp}.{fk}"
        if fk != intent:
            raise SpecCompileError(f"{fp}: 页型字段 {fk} 与 page_intent={intent!r}"
                                   " 不符（字段须随对应 intent 出现）")
        if not isinstance(val, dict):
            raise SpecCompileError(f"{fp}: 必须为 dict")
        for k in val:
            if k not in PAGE_INTENT_FIELDS[fk]:
                raise SpecCompileError(f"{fp}.{k}: 未知键"
                                       f"（可选 {sorted(PAGE_INTENT_FIELDS[fk])}）")
        if "variant" in val and val["variant"] is not None:
            import intents as _IN
            var = val["variant"]
            if not isinstance(var, str) or not _IN.known(fk, var):
                raise SpecCompileError(
                    f"{fp}.variant: 未知变体 {var!r}（{fk} 可选 {_IN.variants(fk)}；"
                    "见 references/page-intents.md「变体家族」）")
        _vfn = _PI_VALIDATORS.get(fk)
        if _vfn:
            _vfn(val, fp, slide, palette)
    return intent, slide.get(intent)


def _check_transition(t, path):
    """页级切换：{effect, spd?, dur?}。effect=none → 渲染不注入 p:transition
    （关闭全局默认切换的手段）；effect=morph → 平滑切换（同名对象跨页变形，
    render 以 mc:AlternateContent + p159:morph 写入、p:fade 回退），dur = 毫秒
    时长（仅 morph 生效，100–5000，缺省 700）。返回归一化 dict（spd 缺省 med）。"""
    if t is None:
        return None
    if not isinstance(t, dict):
        raise SpecCompileError(f"{path}: 必须为 dict{{effect, spd?, dur?}}，实为 {t!r}")
    for k in t:
        if k not in ("effect", "spd", "dur"):
            raise SpecCompileError(f"{path}.{k}: 未知键（effect/spd/dur）")
    eff = t.get("effect")
    if eff not in TRANSITION_EFFECTS:
        raise SpecCompileError(f"{path}.effect: 必须 ∈ {sorted(TRANSITION_EFFECTS)}"
                               f"，实为 {eff!r}")
    spd = t.get("spd", "med")
    if spd not in TRANSITION_SPD:
        raise SpecCompileError(f"{path}.spd: 必须 ∈ {sorted(TRANSITION_SPD)}"
                               f"，实为 {spd!r}")
    out = {"effect": eff, "spd": spd}
    if "dur" in t:
        if eff != "morph":
            raise SpecCompileError(f"{path}.dur: 仅 effect=morph 支持（实为 {eff!r}）")
        d = t["dur"]
        if not isinstance(d, int) or isinstance(d, bool) or not (100 <= d <= 5000):
            raise SpecCompileError(f"{path}.dur: 必须为 100–5000 的整数毫秒，实为 {d!r}")
        out["dur"] = d
    return out


def _check_slide(slide, si, palette, n_pages=None, base_dir=None):
    """meta.slides[si] 单页：elements/relations 引用自洽 + 页级 margin/framework。
    id 唯一作用域 = 页内（跨页互不感知，遮挡校验按页隔离）。
    n_pages：跨页引用（link.slide 跳转目标）边界校验用。"""
    pp = f"meta.slides[{si}]"
    if not isinstance(slide, dict):
        raise SpecCompileError(f"{pp}: 必须为 dict")
    for k in slide:
        if k not in SLIDE_KEYS:
            raise SpecCompileError(f"{pp}.{k}: 未知键（title/elements/relations/margin/framework/notes/transition/brief/anim/params）")
    br = slide.get("brief")
    if br is not None and not isinstance(br, str):
        raise SpecCompileError(f"{pp}.brief: 必须为字符串（意图上下文，供修订器消费）")
    elems = slide.get("elements", [])
    if not isinstance(elems, list):
        raise SpecCompileError(f"{pp}.elements: 必须为列表")
    seen = {}
    for i, e in enumerate(elems):
        ep = f"{pp}.elements[{i}]"
        if not isinstance(e, dict) or "id" not in e:
            raise SpecCompileError(f"{ep}: 必须为含 id 的 dict")
        eid = e["id"]
        if not isinstance(eid, str) or not eid:
            raise SpecCompileError(f"{ep}.id: 必须为非空字符串")
        if eid in seen:
            raise SpecCompileError(f"{pp}.elements: id 重复 {eid!r}")
        if eid in ("bg", "hdr", "ftr"):
            raise SpecCompileError(f"{ep}.id: {eid!r} 为框架层保留名（bg/hdr/ftr），请换 id")
        seen[eid] = i
        _check_elem(e, ep, palette, cur_page=si + 1, n_pages=n_pages,
                    base_dir=base_dir)
    rel = slide.get("relations") or {}
    if not isinstance(rel, dict):
        raise SpecCompileError(f"{pp}.relations: 必须为 dict")
    for k in rel:
        if k not in ("edges", "glue", "overlap", "z_override", "edit_groups"):
            raise SpecCompileError(f"{pp}.relations.{k}: 未知关系段"
                                   "（edges/glue/overlap/z_override/edit_groups）")
    for i, ov in enumerate(rel.get("z_override", [])):
        op = f"{pp}.relations.z_override[{i}]"
        if not isinstance(ov, dict) or "id" not in ov or "z" not in ov:
            raise SpecCompileError(f"{op}: 必须声明 id 与 z")
        if ov["id"] not in seen:
            raise SpecCompileError(f"{op}.id: 引用不存在的元素 {ov['id']!r}")
        _num(ov["z"], "z", op)
    for i, gl in enumerate(rel.get("glue", [])):
        gp = f"{pp}.relations.glue[{i}]"
        if not isinstance(gl, dict) or "from" not in gl or "to" not in gl:
            raise SpecCompileError(f"{gp}: 必须声明 from 与 to")
        for k in ("from", "to"):
            if gl[k] not in seen:
                raise SpecCompileError(f"{gp}.{k}: 引用不存在的元素 {gl[k]!r}")
        if "label" in gl and not isinstance(gl["label"], str):
            raise SpecCompileError(f"{gp}.label: 必须为字符串")
        # 具名锚点（scansci 内化）：from_anchor/to_anchor 可缺省（省略 → 回退
        # AABB 边中点现状）；声明则须成对（消除"单端具名"混合 glue——G5/G6
        # 豁免与 G10 覆盖的前提不变量），且锚点名必须存在于端点元素 anchors
        if ("from_anchor" in gl) != ("to_anchor" in gl):
            raise SpecCompileError(f"{gp}: from_anchor/to_anchor 须成对声明"
                                   "（具名锚点连接，双向指定端点）")
        for at_key in ("from_anchor", "to_anchor"):
            if at_key not in gl:
                continue
            end_id = gl["from"] if at_key == "from_anchor" else gl["to"]
            anchors = next((x.get("anchors") or {})
                           for x in elems if x["id"] == end_id)
            if gl[at_key] not in anchors:
                raise SpecCompileError(
                    f"{gp}.{at_key}: 锚点名 {gl[at_key]!r} 不在元素 {end_id!r} "
                    f"anchors（可选 {sorted(anchors)}）")
    for i, ov in enumerate(rel.get("overlap", [])):
        op = f"{pp}.relations.overlap[{i}]"
        if not isinstance(ov, dict) or "id" not in ov or "with" not in ov:
            raise SpecCompileError(f"{op}: 必须声明 id 与 with")
        if ov["id"] not in seen:
            raise SpecCompileError(f"{op}.id: 引用不存在的元素 {ov['id']!r}")
        if ov["with"] not in seen:
            raise SpecCompileError(f"{op}.with: 引用不存在的元素 {ov['with']!r}")
    # 编辑单元（scansci 内化块 2）：成员须为顶层产生形状的元素、禁跨组重复
    # （编辑单元原子性）；id 非空；group:true 容器自动并入，无需显式声明
    for i, eg in enumerate(rel.get("edit_groups", [])):
        ep = f"{pp}.relations.edit_groups[{i}]"
        if not isinstance(eg, dict) or "id" not in eg or not isinstance(eg.get("id"), str) \
                or not eg["id"]:
            raise SpecCompileError(f"{ep}: 必须声明非空 id")
        mems = eg.get("members")
        if not isinstance(mems, list) or not mems:
            raise SpecCompileError(f"{ep}.members: 必须为非空列表（顶层元素 id）")
        for mk in mems:
            if mk not in seen:
                raise SpecCompileError(f"{ep}.members: 引用不存在的元素 {mk!r}")
            mtype = next((x["type"] for x in elems if x["id"] == mk), None)
            if not CAP.supports(mtype, "edit_group_member"):
                raise SpecCompileError(f"{ep}.members: {mk!r}（{mtype}）不产单形状，"
                                       "不能为编辑组成员"
                                       "（group:true 容器自动并入，无需声明）")
    member_owner = {}
    for i, eg in enumerate(rel.get("edit_groups", [])):
        for mk in eg.get("members", []):
            if mk in member_owner:
                raise SpecCompileError(
                    f"{pp}.relations.edit_groups[{i}].members: {mk!r} 已属"
                    f"编辑组 {member_owner[mk]!r}（跨组重复成员不允许）")
            member_owner[mk] = eg.get("id")
    if "margin" in slide and slide["margin"] is not None:
        _check_margin(slide["margin"], f"{pp}.margin")
    if "framework" in slide and slide["framework"] is not None:
        _check_framework(slide["framework"], f"{pp}.framework", palette)
    # 页级 params：配置栈页级层（性质③——多页逐页覆盖；键合法性由
    # build_pages 的 layer_merge/resolve 报错，此处只强类型）
    _check_params(slide.get("params"), f"{pp}.params")
    _check_notes(slide.get("notes"), f"{pp}.notes")
    tr = _check_transition(slide.get("transition"), f"{pp}.transition")
    intent, intent_val = _check_page_intent(slide, pp, palette)
    if slide.get("anim") is not None:
        # 动画组语义（组员存在/带动画/无自带时序）+ 容器等引用约束
        import anim_group as AG
        try:
            AG.check_anim_groups(slide["anim"], {e["id"]: e for e in elems},
                                 f"{pp}.anim")
        except AG.AgError as ex:
            raise SpecCompileError(str(ex))
    page = {"title": slide.get("title"), "elements": elems,
            "relations": rel, "margin": slide.get("margin"),
            "framework": slide.get("framework"), "notes": slide.get("notes"),
            "transition": tr, "page_intent": intent, "brief": slide.get("brief"),
            "anim": slide.get("anim"), "params": slide.get("params")}
    if intent:
        page[intent] = intent_val
    return page


# ================== meta.template：extract 注入 / seed 打底 ==================
# 两种模式（母版版式能力的两条腿，见 references/stylecard.md）：
#   extract —— 模板风格「提炼」：slide/palette/framework/params 按 fill-only 原则
#              （agent 显式声明优先）注入，编译期确定性合并；渲染仍走自绘，
#              主题色在渲染后写回 theme1.xml（品牌色进原生 UI）。
#   seed    —— 模板「打底」：渲染器以模板为基底 add_slide(选中版式)，
#              元素级 ph 字段填充模板占位符（模板层豁免校验，SPEC 层照常）。

_TEMPLATE_KEYS = {"slide", "palette", "framework", "params"}
_THEME_SLOTS = ("accent1", "accent2", "accent3", "accent4",
                "accent5", "accent6", "dk1", "lt1", "dk2", "lt2")


def _analyze_template(tinfo):
    """stylecard 分析（只读，不写模板）。ValueError → 编译错（exit 2）。"""
    try:
        import template_analyzer as _TA
        return _TA.analyze(tinfo["src"])
    except ValueError as ex:
        raise SpecCompileError(f"meta.template: 模板分析失败: {ex}")


def _check_template(cfg, path, base_dir=None):
    """meta.template 语法/文件存在性。返回规范化 dict（src 已绝对化）。"""
    if not isinstance(cfg, dict):
        raise SpecCompileError(f"{path}: 必须为 dict")
    for k in cfg:
        if k not in ("src", "mode", "keys", "layout"):
            raise SpecCompileError(f"{path}.{k}: 未知键（src/mode/keys/layout）")
    src = cfg.get("src")
    if not isinstance(src, str) or not src.strip():
        raise SpecCompileError(f"{path}.src: 必须为非空模板路径")
    mode = cfg.get("mode", "extract")
    if mode not in ("extract", "seed"):
        raise SpecCompileError(f"{path}.mode: 必须为 extract|seed（默认 extract）")
    resolved = os.path.abspath(os.path.join(base_dir or ".", src))
    if not os.path.isfile(resolved):
        raise SpecCompileError(f"{path}.src: 模板文件不存在 {resolved!r}"
                               f"（相对 SPEC 目录解析）")
    keys = cfg.get("keys")
    if keys is not None:
        if mode != "extract":
            raise SpecCompileError(f"{path}.keys: 仅 extract 模式支持 keys")
        if not isinstance(keys, list) or not keys:
            raise SpecCompileError(f"{path}.keys: 必须为非空列表")
        for k in keys:
            if k not in _TEMPLATE_KEYS:
                raise SpecCompileError(f"{path}.keys: 未知键 {k!r}"
                                       f"（可选 {sorted(_TEMPLATE_KEYS)}）")
    if cfg.get("layout") is not None and mode != "seed":
        raise SpecCompileError(f"{path}.layout: 仅 seed 模式使用 layout")
    return {"src": resolved, "mode": mode,
            "keys": set(keys) if keys is not None else set(_TEMPLATE_KEYS),
            "layout": cfg.get("layout"), "notes": []}


def _template_bg_fill(card):
    """母版背景 → framework 背景 fill 引用（solid 色 / 渐变两色）；
    其余形态（pic/inherit/…）回退主题 lt1（浅基色）。"""
    for m in card.get("masters") or []:
        bg = m.get("bg") or {}
        if bg.get("kind") == "solid" and isinstance(bg.get("color"), str):
            return bg["color"]
        if bg.get("kind") == "grad" and len(bg.get("colors") or []) == 2:
            return {"grad": list(bg["colors"])}
    lt1 = ((card.get("theme") or {}).get("colors") or {}).get("lt1")
    if isinstance(lt1, str) and lt1.startswith("#"):
        return lt1
    return None


def _apply_extract(meta, palette, tinfo):
    """extract 提炼：fill-only 合并（agent 声明优先）；注记写 tinfo['notes']。"""
    keys = tinfo["keys"]
    card = _analyze_template(tinfo)
    tinfo["card"] = card
    notes = tinfo["notes"]
    if "slide" in keys and card.get("slide"):
        meta.setdefault("slide", dict(card["slide"]))
    if "palette" in keys and card.get("theme") and card["theme"].get("colors"):
        cols = card["theme"]["colors"]
        for slot in _THEME_SLOTS:
            if slot in palette:
                continue                     # fill-only：agent 声明的 token 不动
            c = cols.get(slot)
            if isinstance(c, str) and c.startswith("#"):
                palette[slot] = {"solid": c}
                notes.append(f"[extract] palette.{slot} ← 模板 {c}")
    if "framework" in keys:
        fw = meta.setdefault("framework", {})
        if "background" not in fw:
            bg = _template_bg_fill(card)
            if bg is not None:
                fw["background"] = {"fill": bg}
                notes.append("[extract] framework.background ← 模板母版背景")
    if "params" in keys:
        f = (card.get("theme") or {}).get("fonts") or {}
        if any(v for v in (f.get("minor_latin"), f.get("minor_ea"),
                           f.get("major_latin"), f.get("major_ea"))):
            font = meta.setdefault("params", {}).setdefault("font", {})
            if f.get("minor_latin"):
                font.setdefault("latin", f["minor_latin"])
            if f.get("minor_ea"):
                font.setdefault("ea", f["minor_ea"])
            if f.get("major_latin"):
                font.setdefault("title_latin", f["major_latin"])
            if f.get("major_ea"):
                font.setdefault("title_ea", f["major_ea"])
            notes.append("[extract] params.font ← 模板字族双轨")
    for pit in (card.get("pitfalls") or [])[:5]:
        notes.append(f"[extract] 容错: {pit}")


def _pick_default_layout(layouts):
    """默认版式：含 title 占位符 → 占位符最多 → 首个（确定性优先序）。"""
    for ly in layouts:
        if any((isinstance(p.get("idx"), int) and p["idx"] == 0)
               or "TITLE" in str(p.get("type", "")).upper()
               for p in ly["ph"]):
            return ly
    return max(layouts, key=lambda ly: len(ly["ph"]))


def _seed_prep(tinfo):
    """seed 打底：选中版式（按名/索引/默认），layout_info 供渲染器与物证。"""
    card = _analyze_template(tinfo)
    tinfo["card"] = card
    layouts = card.get("layouts") or []
    if not layouts:
        raise SpecCompileError("meta.template(seed): 模板无版式可打底"
                               "（python-pptx 分析失败或模板缺版式）")
    sel = tinfo.get("layout")
    ly = None
    if sel is not None:
        if isinstance(sel, int):
            if 0 <= sel < len(layouts):
                ly = layouts[sel]
        elif isinstance(sel, str):
            cands = [l for l in layouts if l["name"] == sel]
            if cands:
                ly = cands[0]
        if ly is None:
            raise SpecCompileError(
                f"meta.template.layout: 版式 {sel!r} 不存在（可用 "
                f"{[l['name'] for l in layouts]} 或索引 0..{len(layouts)-1}）")
    else:
        ly = _pick_default_layout(layouts)
    tinfo["layout_info"] = ly
    tinfo["notes"].append(
        f"[seed] 基底模板 {os.path.basename(tinfo['src'])} · 版式「{ly['name']}」"
        f" · 占位符 {len(ly['ph'])} 项")


def _apply_seed(meta, tinfo):
    """seed 打底：页面尺寸 setdefault 自模板（几何与版式一致；显式声明可覆盖）。"""
    card = tinfo.get("card") or {}
    if card.get("slide"):
        meta.setdefault("slide", dict(card["slide"]))


def _check_ph(slides, tinfo):
    """ph 字段校验（seed）：仅 text 元素、目标占位符存在（按 idx/名）、
    不进 relations（glue/overlap/z_override）；解析结果写 e['ph_info']。
    非 seed 模式声明 ph → 编译错。"""
    if tinfo is None or tinfo.get("mode") != "seed":
        for pi, page in enumerate(slides):
            for e in page["elements"]:
                if "ph" in e:
                    raise SpecCompileError(
                        f"slides[{pi}].elements({e['id']}).ph: ph 字段仅 "
                        "meta.template.mode=seed 使用（当前未声明或为 extract）")
        return
    li = tinfo["layout_info"]
    ph_map = {}
    for p in li["ph"]:
        if isinstance(p.get("idx"), int):
            ph_map[str(p["idx"])] = p
        if p.get("name"):
            ph_map[p["name"]] = p
    avail_idx = sorted({str(p["idx"]) for p in li["ph"] if isinstance(p.get("idx"), int)})
    avail_name = sorted({p["name"] for p in li["ph"] if p.get("name")})
    for pi, page in enumerate(slides):
        for e in page["elements"]:
            if "ph" not in e:
                continue
            if "link" in e:
                raise SpecCompileError(
                    f"slides[{pi}].elements({e['id']}).link: ph 占位符填充不支持"
                    "超链接（文本写入模板占位符，无自建形状可挂 hlinkClick）")
            if e["type"] != "text":
                raise SpecCompileError(
                    f"slides[{pi}].elements({e['id']}).ph: ph 仅支持 text 元素"
                    f"（实为 {e['type']}）")
            target = e["ph"]
            info = None
            if isinstance(target, int):
                info = ph_map.get(str(target))
            elif isinstance(target, str):
                info = ph_map.get(target)
            if info is None:
                raise SpecCompileError(
                    f"slides[{pi}].elements({e['id']}).ph: 版式无占位符 {target!r}"
                    f"（可用 idx {avail_idx} 或名 {avail_name}）")
            e["ph_info"] = {"idx": info.get("idx"), "name": info.get("name"),
                            "type": info.get("type")}
        ph_ids = {e["id"] for e in page["elements"] if "ph_info" in e}
        if ph_ids:
            rel = page.get("relations") or {}
            for seg in ("glue", "overlap", "z_override"):
                for i, item in enumerate((rel.get(seg) or [])):
                    for r in (item.get("from"), item.get("to"),
                              item.get("id"), item.get("with")):
                        if r in ph_ids:
                            raise SpecCompileError(
                                f"slides[{pi}].relations.{seg}[{i}]: 引用 ph 元素 {r!r}"
                                "——ph 占位符填充不走关系（glue/overlap/z_override 均不支持）")


def compile_spec(data, palette_over=None, base_dir=None):
    """data: 已解析 dict（YAML safe_load 结果）。返回规范化 dict。
       不抛错返回 polyline；抛 SpecCompileError 含全部 violations。"""
    errors = []

    def guard(fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except SpecCompileError as ex:
            errors.append(str(ex))
            raise

    # 顶层段
    for k in data:
        if k not in TOP_KEYS:
            errors.append(f"顶层未知段 {k!r}（可用 {sorted(TOP_KEYS)}）")
    if errors:
        raise SpecCompileError("\n".join(errors))
    slides_cfg = (data.get("meta") or {}).get("slides")
    if "elements" not in data and slides_cfg is None:
        raise SpecCompileError("缺少顶层段 elements（或声明 meta.slides 多页序列）")

    # palette 语法
    palette = dict(palette_over or {})
    for tok, val in (data.get("palette") or {}).items():
        if not isinstance(tok, str) or not tok:
            raise SpecCompileError(f"palette token 必须为非空字符串，实为 {tok!r}")
        if isinstance(val, str) and HEX_RE.match(val):
            palette[tok] = {"solid": val}
        elif isinstance(val, dict) and "solid" in val:
            _check_color(val["solid"], f"palette.{tok}", palette)
            palette[tok] = {"solid": val["solid"]}
        elif isinstance(val, dict) and "grad" in val:
            gd = val["grad"]
            if not isinstance(gd, list) or len(gd) != 2:
                raise SpecCompileError(f"palette.{tok}.grad: 必须为两色 [c1, c2]")
            _check_color(gd[0], f"palette.{tok}.grad[0]", palette)
            _check_color(gd[1], f"palette.{tok}.grad[1]", palette)
            palette[tok] = {"grad": list(gd)}
        else:
            raise SpecCompileError(f"palette.{tok}: 必须为 hex / {{solid: hex}} / {{grad: [c1,c2]}}")

    # meta.theme（设计语言/主题）——palette 解析后、meta.template 前：主题 token 并入
    # palette（SPEC 可写 style.fill: pale / accent: primary），覆盖层下降为 params
    # （配置栈最低层）。模板 extract 可再覆盖主题色（顺序：主题 → 模板，模板赢）。
    _theme = None
    _theme_params = None
    _theme_cfg = (data.get("meta") or {}).get("theme")
    if _theme_cfg is not None:
        try:
            _theme = THEMES.resolve(_theme_cfg)
        except (ValueError, KeyError) as ex:
            raise SpecCompileError(f"meta.theme: {ex}")
        palette.update(_theme["palette_tokens"])
        _theme_params = _theme["params_overlay"]
    data["_theme"] = _theme
    data["_theme_params"] = _theme_params

    # meta.template（extract 注入 / seed 打底）——palette 解析后、framework/元素校验前；
    # 注入只改 meta 副本与 palette，不污染原始文档；下游（renderer/物证/report）走
    # compiled["_template"] 共享同一份规范化事实。
    meta = dict(data.get("meta") or {})
    sg = meta.get("style_guide")
    data = dict(data)
    data["meta"] = meta
    tinfo = None
    if meta.get("template") is not None:
        tinfo = _check_template(meta["template"], "meta.template", base_dir)
        if tinfo["mode"] == "seed":
            _seed_prep(tinfo)
            _apply_seed(meta, tinfo)
        else:
            _apply_extract(meta, palette, tinfo)
        data["_template"] = tinfo

    # meta.framework（背景/页眉页脚）——palette 先解析完，fill token 可查；
    # 模板注入的背景 fill（hex/grad 字面量）同样在此受检
    fw = meta.get("framework")
    if fw is not None:
        guard(_check_framework, fw, "meta.framework", palette)
    _check_params(meta.get("params"), "meta.params")
    _check_notes(meta.get("notes"), "meta.notes")
    if meta.get("page_intent") is not None:
        raise SpecCompileError("meta.page_intent: 页型意图仅多页序列（meta.slides）"
                               "的 slides[i] 声明（页型是页间分类语义）；"
                               "单页模式请删去或用 meta.slides 声明")

    # ---- 多页序列：meta.slides 每个元素一页（长演示/课件/汇报）。
    #      顶层 elements/relations 在该模式须移入各页（避免"页面元素归属歧义"，
    #      编译期拦截），故多页分支在此提前返回；单页模式走下方既有校验。
    #      恒产 compiled["slides"]（单页模式 = [顶层] 向后兼容）。----
    slides_cfg = (data.get("meta") or {}).get("slides")
    if slides_cfg is not None:
        if "elements" in data or "relations" in data or "anim" in data:
            raise SpecCompileError(
                "meta.slides 存在时顶层 elements/relations/anim 须移入各页"
                "（slides[i].elements / slides[i].relations / slides[i].anim）")
        if not isinstance(slides_cfg, list) or not slides_cfg:
            raise SpecCompileError("meta.slides: 必须为非空页面列表")
        if meta.get("notes") is not None:
            raise SpecCompileError("meta.notes 仅单页模式使用；多页序列请在 slides[i].notes"
                                   " 逐页声明（备注是页级内容，无全局继承语义）")
        out = dict(data)
        out["palette"] = palette
        out["slides"] = [_check_slide(s, i, palette, n_pages=len(slides_cfg),
                                      base_dir=base_dir)
                     for i, s in enumerate(slides_cfg)]
        # 切换：全局 meta.transition 为默认，页级 slides[i].transition 覆盖（页显式
        # 声明才覆盖，含 effect: none 显式关闭）；编译期解析，IR/渲染只消费有效值
        gtr = None
        if meta.get("transition") is not None:
            gtr = guard(_check_transition, meta["transition"], "meta.transition")
        for sl in out["slides"]:
            if sl.get("transition") is None:
                sl["transition"] = gtr
        _check_graph_semantics(out, sg)
        _check_ph(out["slides"], tinfo)
        w = _seed_bg_warning(meta, tinfo)
        if w:
            out["warnings"] = [w]
        return out

    # 切换是页间行为：单页模式（无 meta.slides）声明 meta.transition 无切换对象
    if meta.get("transition") is not None:
        raise SpecCompileError("meta.transition: 切换为页间行为，仅多页序列（meta.slides）"
                               "下有语义；单页模式请删去（或改用 meta.slides 声明多页）")

    # elements：id 唯一
    seen = {}
    elems = data["elements"]
    if not isinstance(elems, list):
        raise SpecCompileError("elements 必须为列表")
    for i, e in enumerate(elems):
        ep = f"elements[{i}]"
        if not isinstance(e, dict) or "id" not in e:
            raise SpecCompileError(f"{ep}: 必须为含 id 的 dict")
        eid = e["id"]
        if not isinstance(eid, str) or not eid:
            raise SpecCompileError(f"{ep}.id: 必须为非空字符串")
        if eid in seen:
            raise SpecCompileError(f"elements: id 重复 {eid!r}")
        if eid in ("bg", "hdr", "ftr"):
            raise SpecCompileError(f"{ep}.id: {eid!r} 为框架层保留名（bg/hdr/ftr），请换 id")
        seen[eid] = i
        _check_elem(e, ep, palette, cur_page=1, n_pages=1, base_dir=base_dir)

    # relations：引用存在性
    rel = data.get("relations") or {}
    for k in rel:
        if k not in ("edges", "glue", "overlap", "z_override", "edit_groups"):
            raise SpecCompileError(f"relations.{k}: 未知关系段"
                                   "（edges/glue/overlap/z_override/edit_groups）")
    for i, ov in enumerate(rel.get("z_override", [])):
        op = f"relations.z_override[{i}]"
        if not isinstance(ov, dict) or "id" not in ov or "z" not in ov:
            raise SpecCompileError(f"{op}: 必须声明 id 与 z")
        if ov["id"] not in seen:
            raise SpecCompileError(f"{op}.id: 引用不存在的元素 {ov['id']!r}")
        z = _num(ov["z"], "z", op)
        if z != int(z) or int(z) < 0:
            raise SpecCompileError(f"{op}.z: 必须为非负整数")
    for i, gl in enumerate(rel.get("glue", [])):
        gp = f"relations.glue[{i}]"
        if not isinstance(gl, dict) or "from" not in gl or "to" not in gl:
            raise SpecCompileError(f"{gp}: 必须声明 from 与 to")
        for k in ("from", "to"):
            if gl[k] not in seen:
                raise SpecCompileError(f"{gp}.{k}: 引用不存在的元素 {gl[k]!r}")
        if "label" in gl and not isinstance(gl["label"], str):
            raise SpecCompileError(f"{gp}.label: 必须为字符串")
        # 具名锚点（与页级 glue 校验同律）：成对声明 + 锚点名存在性
        if ("from_anchor" in gl) != ("to_anchor" in gl):
            raise SpecCompileError(f"{gp}: from_anchor/to_anchor 须成对声明"
                                   "（具名锚点连接，双向指定端点）")
        for at_key in ("from_anchor", "to_anchor"):
            if at_key not in gl:
                continue
            end_id = gl["from"] if at_key == "from_anchor" else gl["to"]
            anchors = next((x.get("anchors") or {})
                           for x in data["elements"] if x["id"] == end_id)
            if gl[at_key] not in anchors:
                raise SpecCompileError(
                    f"{gp}.{at_key}: 锚点名 {gl[at_key]!r} 不在元素 {end_id!r} "
                    f"anchors（可选 {sorted(anchors)}）")
    # overlap 引用存在性（遮挡合法源二类之一）
    for i, ov in enumerate(rel.get("overlap", [])):
        op = f"relations.overlap[{i}]"
        if not isinstance(ov, dict) or "id" not in ov or "with" not in ov:
            raise SpecCompileError(f"{op}: 必须声明 id 与 with")
        if ov["id"] not in seen:
            raise SpecCompileError(f"{op}.id: 引用不存在的元素 {ov['id']!r}")
        if ov["with"] not in seen:
            raise SpecCompileError(f"{op}.with: 引用不存在的元素 {ov['with']!r}")
    # 编辑单元（与页级同律）：成员须顶层产生形状、禁跨组重复
    for i, eg in enumerate(rel.get("edit_groups", [])):
        ep = f"relations.edit_groups[{i}]"
        if not isinstance(eg, dict) or "id" not in eg or not isinstance(eg.get("id"), str) \
                or not eg["id"]:
            raise SpecCompileError(f"{ep}: 必须声明非空 id")
        mems = eg.get("members")
        if not isinstance(mems, list) or not mems:
            raise SpecCompileError(f"{ep}.members: 必须为非空列表（顶层元素 id）")
        for mk in mems:
            if mk not in seen:
                raise SpecCompileError(f"{ep}.members: 引用不存在的元素 {mk!r}")
            mtype = next((x["type"] for x in data["elements"] if x["id"] == mk), None)
            if not CAP.supports(mtype, "edit_group_member"):
                raise SpecCompileError(f"{ep}.members: {mk!r}（{mtype}）不产单形状，"
                                       "不能为编辑组成员"
                                       "（group:true 容器自动并入，无需声明）")
    member_owner = {}
    for i, eg in enumerate(rel.get("edit_groups", [])):
        for mk in eg.get("members", []):
            if mk in member_owner:
                raise SpecCompileError(
                    f"relations.edit_groups[{i}].members: {mk!r} 已属"
                    f"编辑组 {member_owner[mk]!r}（跨组重复成员不允许）")
            member_owner[mk] = eg.get("id")

    if data.get("anim") is not None:
        import anim_group as AG
        try:
            AG.check_anim_groups(data["anim"], {e["id"]: e for e in elems}, "anim")
        except AG.AgError as ex:
            raise SpecCompileError(str(ex))

    out = dict(data)
    out["palette"] = palette
    out["slides"] = [{"title": None, "elements": data["elements"],
                      "relations": data.get("relations") or {},
                      "margin": None, "framework": None,
                      "notes": meta.get("notes"), "transition": None,
                      "anim": data.get("anim")}]
    _check_graph_semantics(out, sg)
    _check_ph(out["slides"], tinfo)
    w = _seed_bg_warning(meta, tinfo)
    if w:
        out["warnings"] = [w]
    return out


def _seed_bg_warning(meta, tinfo):
    """规则1：seed 模式 + 全局 framework.background = 全画布背景遮挡母版背景图。
    仅告警不阻断——特例页（封面/节标题）的页级覆盖是用户刻意授权，不受此查。"""
    if (tinfo is not None and tinfo.get("mode") == "seed"
            and (meta.get("framework") or {}).get("background")):
        return ("seed 模式 + meta.framework.background：全局纯色/渐变全画布背景会遮挡"
                "母版背景图，内容页将看不到模板母版样式。如需母版透出，请删除全局"
                " background（特例页用页级 framework.background 覆盖）")
    return None


def load_yaml(text):
    """YAML → dict；语法错误给友好提示（含重复 key）。"""
    try:
        import yaml
    except ImportError:
        raise SpecCompileError("缺少 PyYAML 依赖（win_py 应已装：win_py -m pip install pyyaml）")
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as ex:
        raise SpecCompileError(f"YAML 语法错误: {ex}")


def compile_file(path, palette_over=None):
    """文件入口：读 → parse → compile。返回 (compiled_dict, None)。"""
    with open(path, "r", encoding="utf-8") as f:
        data = load_yaml(f.read())
    if data is None:
        raise SpecCompileError("SPEC 文件为空")
    return compile_spec(data, palette_over)