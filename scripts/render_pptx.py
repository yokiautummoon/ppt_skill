# -*- coding: utf-8 -*-
"""render_pptx.py — 渲染器：纯消费 IR（不重算几何/锚点/z），组件银行 + used 记账。

/!\\ 铁律：这是确定性阶段的最后一环，任何几何都不得在此重算或"微调"——
     改布局 = 改 SPEC，让上游重跑（verify 会背书一致性）。
组件银行（used 记账 → metrics）：
  panel_shape / node_shape / gradient / shadow / cover_label / edge_connector /
  polyline / arrowhead / group_container / textbox / image_crop / glue_connector
"""
import copy
import os
from lxml import etree

from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.dml import MSO_LINE_DASH_STYLE as MSOL
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import (XL_CHART_TYPE, XL_LEGEND_POSITION,
                             XL_LABEL_POSITION, XL_MARKER_STYLE)

import formula_omml
import formula_templates
import layout_rect as LR

MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
A14_NS = "http://schemas.microsoft.com/office/drawing/2010/main"

CJK = "微软雅黑"

# 框架层形状名（COM 按名查找 / XML 物证按名定位同机制；不进 IR）
BG_NAME = "bg"
HDR_NAME = "hdr"
FTR_NAME = "ftr"

SHAPE_BY_KIND = {"src": MSO_SHAPE.CAN, "proc": MSO_SHAPE.ROUNDED_RECTANGLE,
                 "judge": MSO_SHAPE.DIAMOND, "end": MSO_SHAPE.OVAL}
TOP_SHAPE = {"rect": MSO_SHAPE.RECTANGLE, "rounded_rect": MSO_SHAPE.ROUNDED_RECTANGLE,
             "oval": MSO_SHAPE.OVAL, "diamond": MSO_SHAPE.DIAMOND,
             "can": MSO_SHAPE.CAN, "parallelogram": MSO_SHAPE.PARALLELOGRAM,
             "hexagon": MSO_SHAPE.HEXAGON}

# chart_type → python-pptx 图表类型（随附 workbook，零 COM）
CHART_BY_TYPE = {"column_clustered": XL_CHART_TYPE.COLUMN_CLUSTERED,
                 "column_stacked": XL_CHART_TYPE.COLUMN_STACKED,
                 "column_stacked_100": XL_CHART_TYPE.COLUMN_STACKED_100,
                 "bar_clustered": XL_CHART_TYPE.BAR_CLUSTERED,
                 "bar_stacked": XL_CHART_TYPE.BAR_STACKED,
                 "bar_stacked_100": XL_CHART_TYPE.BAR_STACKED_100,
                 "line": XL_CHART_TYPE.LINE,
                 "line_stacked": XL_CHART_TYPE.LINE_STACKED,
                 "line_markers": XL_CHART_TYPE.LINE_MARKERS,
                 "line_markers_stacked": XL_CHART_TYPE.LINE_MARKERS_STACKED,
                 "area": XL_CHART_TYPE.AREA,
                 "area_stacked": XL_CHART_TYPE.AREA_STACKED,
                 "area_stacked_100": XL_CHART_TYPE.AREA_STACKED_100,
                 "pie": XL_CHART_TYPE.PIE,
                 "pie_exploded": XL_CHART_TYPE.PIE_EXPLODED,
                 "doughnut": XL_CHART_TYPE.DOUGHNUT,
                 "doughnut_exploded": XL_CHART_TYPE.DOUGHNUT_EXPLODED}
LEGEND_POS = {"right": XL_LEGEND_POSITION.RIGHT, "bottom": XL_LEGEND_POSITION.BOTTOM,
              "top": XL_LEGEND_POSITION.TOP, "left": XL_LEGEND_POSITION.LEFT}
LABEL_POS = {"center": XL_LABEL_POSITION.CENTER, "inside_end": XL_LABEL_POSITION.INSIDE_END,
             "inside_base": XL_LABEL_POSITION.INSIDE_BASE,
             "outside_end": XL_LABEL_POSITION.OUTSIDE_END,
             "best_fit": XL_LABEL_POSITION.BEST_FIT, "above": XL_LABEL_POSITION.ABOVE,
             "below": XL_LABEL_POSITION.BELOW, "left": XL_LABEL_POSITION.LEFT,
             "right": XL_LABEL_POSITION.RIGHT}
# 行为族：柱条（有 gap_width/overlap）/ 折线（线描边、可平滑打点）/
# 面积（填充、无间距）/ 饼环（无坐标轴）
CHART_BAR_TYPES = {k for k in CHART_BY_TYPE if k.split("_")[0] in ("column", "bar")}
CHART_LINE_TYPES = {"line", "line_stacked", "line_markers", "line_markers_stacked"}
CHART_PIE_TYPES = {"pie", "pie_exploded", "doughnut", "doughnut_exploded"}
CHART_MARKER_TYPES = {"line_markers", "line_markers_stacked"}
_CN_C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"

# style.border_dash / curve.style.dash / line.dash → python-pptx 线型
# （dot → ROUND_DOT：MSOL.DOT 不存在，probe 实测枚举成员无 DOT）
_DASH = {"dash": MSOL.DASH, "dot": MSOL.ROUND_DOT, "dash_dot": MSOL.DASH_DOT}


def _hex(c):
    c = c.lstrip("#")
    return RGBColor(int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _lum_lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb):
    """sRGB 相对亮度（WCAG 2.x）：0(黑)..1(白)。"""
    return 0.2126 * _lum_lin(rgb[0]) + 0.7152 * _lum_lin(rgb[1]) + 0.0722 * _lum_lin(rgb[2])


def _contrast(a, b):
    """两色对比度比（1..21）。"""
    la, lb = _luminance(a), _luminance(b)
    lo, hi = min(la, lb), max(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def guard_text_color(text_rgb, bg_rgb, dark_rgb, light_rgb, min_ratio=3.0):
    """文字色与所在图形填充对比不足（<min_ratio）→ 反色为白/黑（按 bg 明暗）。
    只产出两族（深=dark_rgb / 浅=light_rgb），未触发保持原色——同层汉字颜色一致。"""
    if bg_rgb is None or _contrast(text_rgb, bg_rgb) >= min_ratio:
        return text_rgb
    return light_rgb if _luminance(bg_rgb) < 0.45 else dark_rgb


def _fill_guard_color(fill_ref, palette, fallback):
    """填充主色（守卫用）：solid → 单色；grad → 两端亮度均值的近似灰（仅判明暗）。"""
    mode, colors = resolve_fill(fill_ref, palette, fallback)
    if mode == "solid":
        return colors[0]
    lum = (_luminance(colors[0]) + _luminance(colors[1])) / 2
    g = int(255 * (lum ** 0.6))
    return RGBColor(g, g, g)


def _resolve_color(ref, palette, fallback):
    """色引用（hex / palette token）→ RGBColor。token 优先查 palette。"""
    if isinstance(ref, str):
        if ref in palette:
            v = palette[ref]
            if "solid" in v:
                return _hex(v["solid"])
        if ref.startswith("#") or len(ref) == 6:
            return _hex(ref)
    return _hex(fallback)


def resolve_fill(ref, palette, fallback):
    """style.fill 语义 → (mode, colors)：mode ∈ solid|grad。token → palette 展开。"""
    if isinstance(ref, dict):           # grad dict（ir_builder kind 族生成）
        gd = ref.get("grad")
        if gd:
            return "grad", [_hex(c) for c in gd]
    if isinstance(ref, str):
        if ref in palette:
            v = palette[ref]
            if "grad" in v:
                return "grad", [_hex(c) for c in v["grad"]]
            return "solid", [_hex(v["solid"])]
        if ref.startswith("#") or len(ref) == 6:
            return "solid", [_hex(ref)]
    return "solid", [_hex(fallback)]


def set_cjk(r, name=CJK):
    rPr = r._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", name)


def _set_run_fonts(r, p, role="body"):
    """latin+ea 双轨字族：role ∈ title|body（fs ≥ font.title_fs_min → title 用 major 字族）。
    双轨保证中西文混排不缺字形（params.font 是唯一事实源，样式卡 extract 可灌入）。"""
    rf = p["font"]
    set_cjk(r, rf["title_ea"] if role == "title" else rf["ea"])
    r.font.name = rf["title_latin"] if role == "title" else rf["latin"]


def _title_role(fs, p, role=None):
    """字体角色：IR 显式 ts.role（类型尺度 scale 派生，title|body）优先；
    缺省按字号二分（fs ≥ font.title_fs_min → title）。无 role 的元素行为不变。"""
    return role or ("title" if fs >= p["font"]["title_fs_min"] else "body")


def inject_outer_shadow(sp, color="#1F2A44", alpha=52000):
    """OOXML 投影：a:outerShdw 的直接子元素即颜色选择器（无 a:clr 包装层）。
    实测带 a:clr 包装会 0x80070570 文档损坏。"""
    spPr = sp._element.spPr
    el = spPr.makeelement(qn("a:effectLst"), {})
    sh = spPr.makeelement(qn("a:outerShdw"),
                          {"blurRad": "38100", "dist": "19050",
                           "dir": "5400000", "rotWithShape": "0"})
    rgb = spPr.makeelement(qn("a:srgbClr"), {"val": color.lstrip("#")})
    al = spPr.makeelement(qn("a:alpha"), {"val": str(alpha)})
    rgb.append(al)
    sh.append(rgb)
    el.append(sh)
    spPr.append(el)


def _apply_fill(sp, fill_ref, palette, p):
    mode, colors = resolve_fill(fill_ref, palette, p["style"]["fill"])
    if mode == "grad":
        sp.fill.gradient()
        sp.fill.gradient_stops[0].color.rgb = colors[0]
        sp.fill.gradient_stops[1].color.rgb = colors[1]
        return "gradient"
    sp.fill.solid()
    sp.fill.fore_color.rgb = colors[0]
    return "solid"


def _apply_fill_alpha(sp, opacity):
    """solidFill 半透明（a:alpha 0~100000 注进 srgbClr）。FillFormat 无 transparency
    API，脚本内 cylinder 侧壁用；其余形状可复用（style.opacity → IR → 此）。"""
    if opacity is None:
        return
    spPr = sp._element.spPr
    sf = spPr.find(qn("a:solidFill"))
    if sf is None:
        return
    rgb = sf.find(qn("a:srgbClr"))
    if rgb is None:
        return
    al = rgb.makeelement(qn("a:alpha"), {"val": str(int(round(opacity * 100000)))})
    rgb.append(al)


def _seg_lines(segs):
    """富文本段 → 按行切分（公式段独占一行）。
    公式只能整行成段：a14:m 是块级数学，与行内 run 混排 PowerPoint 会错位。"""
    lines = [[]]
    for s in segs:
        if "formula" in s:
            if lines[-1]:
                lines.append([])
            lines.append([s])
            lines.append([])
            continue
        for k, part in enumerate(str(s.get("text") or "").split("\n")):
            if k:
                lines.append([])
            if part:
                lines[-1].append({"text": part, "bold": s.get("bold"),
                                  "emph": s.get("emph")})
    return [ln for ln in lines if ln]


def _put_run(pg, seg, fs, rgb, emph_rgb, base_bold, p, role):
    r = pg.add_run()
    r.text = seg["text"]
    r.font.size = Pt(fs)
    # 强调 = 加粗 + 强调色 + 下划线（高校科学课件的关键字样式，三位一体）
    emph = bool(seg.get("emph"))
    r.font.bold = bool(base_bold or seg.get("bold") or emph)
    _set_run_fonts(r, p, role)
    r.font.color.rgb = emph_rgb if emph else rgb
    if emph:
        r.font.underline = True
    return r


def _set_text(tf, text, text_style, text_layout, p, palette=None, guard_bg=None,
              box_w_pt=None, runs=None):
    """一份文本写入 text_frame：alignment/anchor/字号由 IR 决定（不重算）。
    guard_bg：所在图形填充主色——文字与之对比不足即反色（白/黑）。
    box_w_pt：容器宽(pt)——左/右对齐时按文本实测宽加左缩进，使文本块居中于图形。
    runs：富文本段 [{text,bold,emph}] 或 [{formula:expr}]（IR 已解析）；
    缺省 = 单 run 旧路径。含公式段时按行切段（每行一个 a:p，公式段为 a14:m）。"""
    ts = text_style or {}
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.word_wrap = True
    tl = text_layout or {}
    fs = tl.get("fs", ts.get("fs", 12))
    al = ts.get("align", "center")
    role = _title_role(fs, p, ts.get("role"))
    base_bold = bool(ts.get("bold", role == "title" and p["font"]["title_bold"]))
    rgb = _resolve_color(ts.get("color", p["style"]["text_color"]),
                         palette or {}, p["style"]["text_color"])
    if guard_bg is not None:
        rgb = guard_text_color(rgb, guard_bg,
                               _hex(p["style"]["text_color"]), _hex("FFFFFF"))
    emph_rgb = _resolve_color(p["style"].get("emphasis", p["style"]["text_color"]),
                              palette or {}, p["style"]["text_color"])

    def para_props(pg):
        pg.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER,
                        "right": PP_ALIGN.RIGHT,
                        "justify": PP_ALIGN.JUSTIFY}.get(al, PP_ALIGN.CENTER)
        # 规则2：左/右对齐时文本块在框内水平居中（框居中于图形，行内保持对齐）。
        # 例外：显式声明了 indent_chars 的元素（含 0 = 只对齐不缩进）不居中文本块——
        # 左边界要贴齐图形内边距；否则宽卡片里的短段/标签行会被推到中间，看着像居中。
        if (al in ("left", "right") and box_w_pt and tl.get("max_w")
                and "indent_chars" not in ts):
            slack = float(box_w_pt) - float(tl["max_w"])
            if slack > 1.0:
                pg._p.get_or_add_pPr().set("marL", str(int(slack / 2 * 12700)))
        # 规则2：自然排列场景首行缩进（indent_chars = 缩进字符数，1 字 ≈ 1×字号）
        ic = ts.get("indent_chars")
        if ic and fs:
            ind_emu = int(int(ic) * fs * 12700)
            if ind_emu > 0:
                # OOXML 属性名是 indent（不是 ind）；值单位 EMU
                pg._p.get_or_add_pPr().set("indent", str(ind_emu))

    segs = runs or [{"text": text, "bold": base_bold, "emph": False}]
    if any("formula" in s for s in segs):
        lines = _seg_lines(segs)
        for k, line in enumerate(lines):
            pg = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
            para_props(pg)
            for seg in line:
                if "formula" in seg:
                    _append_math(pg, seg["formula"], fs, rgb)
                else:
                    _put_run(pg, seg, fs, rgb, emph_rgb, base_bold, p, role)
        return
    para = tf.paragraphs[0]
    para_props(para)
    for seg in segs:
        if not seg.get("text"):
            continue
        # 段内换行写 a:br（不把裸 \n 塞进 a:t——既非合法断行，物证段数也对不上）
        for k, part in enumerate(str(seg["text"]).split("\n")):
            if k:
                para._p.append(para._p.makeelement(qn("a:br"), {}))
            if part:
                _put_run(para, {"text": part, "bold": seg.get("bold"),
                                "emph": seg.get("emph")},
                         fs, rgb, emph_rgb, base_bold, p, role)


def _append_math(pg, expr, fs, rgb):
    """行内公式：a:p 内追加 a14:m（UnicodeMath → 原生 OMML）。
    与既有 type: formula 元素同构（同页 XML 实测 PowerPoint 可直接读）。"""
    r = formula_omml.parse_expr(expr, fs=fs, color=str(rgb))
    if not r.get("ok"):
        # 子集外：退化为纯文本（带等号的表达式仍可读），不静默吞内容
        run = pg.add_run()
        run.text = expr
        run.font.size = Pt(fs)
        return
    pg._p.append(etree.fromstring(formula_omml.omath_paragraph(r["omml"])))


def _add_connector(sl, a1, a2, color, weight, arrow=False, dash=None):
    c = sl.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,
                                Inches(a1[0]), Inches(a1[1]),
                                Inches(a2[0]), Inches(a2[1]))
    c.line.color.rgb = _hex(color)
    c.line.width = Pt(weight)
    if dash:
        c.line.dash_style = dash
    if arrow:
        _arrow(c)
    return c


def _arrow(c):
    ln = c.line._get_or_add_ln()
    te = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(te)


def render(irs, compiled, p, out_path, pps=None):
    """IR 列表 → base.pptx（单页传 [ir]；多页 = 长演示/课件序列，逐页 add_slide）。
    页面尺寸全局一份（meta.slide），各页 framework/margin 已由 build_pages 合并。
    footer {page} 占位符按页号展开。返回 (used_components_set, errors)。
    pps：逐页参数栈（配置栈页级 resolve，build_ppt 传 pages[i]["_p"]）；缺省 = 全局
    p 全页同参。渲染按页取 p（框架字号/表格 pad 等随页级 params 覆盖一致）。
    meta.template：seed 模式以模板为基底 add_slide(选中版式)；extract/seed 结束后
    palette 里 accent1..6/dk1/lt1 系 token 写回 theme1.xml（品牌色进原生 UI）。"""
    palette = compiled["palette"]
    tpl = compiled.get("_template") or {}
    seed = tpl.get("mode") == "seed" and tpl.get("layout_info")
    if seed:
        prs = Presentation(tpl["src"])
        layout = _match_layout(prs, tpl["layout_info"])
        if layout is None:
            raise RuntimeError(f"seed: 版式「{tpl['layout_info']['name']}」在模板中找不到"
                               "（模板被外部修改？）")
        # 打底语义：产出仅含本 SPEC 页面——模板自带示例页剥离（母版/版式保留），
        # 否则物证按页号配对会错位、成品重复内容
        _strip_slides(prs)
    else:
        prs = Presentation()
    sw, sh = irs[0]["slide"]
    prs.slide_width = Inches(sw)
    prs.slide_height = Inches(sh)
    used = set()
    errors = []
    # 两遍循环：先建全部 slide，再逐个渲染——link slide 跳转需跨页访问
    # 目标 slide part（渲染页 1 时页 2 必须已存在，否则 rel 目标索引越界）
    sls = [prs.slides.add_slide(layout if seed else prs.slide_layouts[6])
           for _ in irs]
    pps = pps or [p] * len(irs)
    for pi, (sl, ir) in enumerate(zip(sls, irs)):
        _render_slide(sl, ir, palette, pps[pi], used, errors, page_no=pi + 1,
                      seed_layout=tpl.get("layout_info") if seed else None,
                      prs=prs)
    prs.save(out_path)
    if tpl.get("mode") == "extract" or compiled.get("_theme"):
        try:
            _inject_theme(palette, out_path, compiled.get("_theme"))
        except Exception as ex:
            errors.append(f"主题色注入失败: {ex}")
    return used, errors


def _match_layout(prs, layout_info):
    """按版式名在模板的母版/版式树中匹配 layout（编译期 analyzer 已背书存在性）。"""
    for master in prs.slide_masters:
        for ly in master.slide_layouts:
            if ly.name == layout_info.get("name"):
                return ly
    return None


def _strip_slides(prs):
    """剥离模板自带页面（seed 打底的"基底"语义 = 母版/版式，不含示例页）。
    必须连 rel 一起摘（仅移 sldIdLst 会留下 presentation→slide rel，
    slide part 仍可达 → 序列化出重复 partname 的坏 zip）。"""
    sldIdLst = prs.slides._sldIdLst
    for sldId in list(sldIdLst):
        rId = sldId.get(qn("r:id"))
        if rId:
            try:
                prs.part.drop_rel(rId)
            except KeyError:
                pass
        sldIdLst.remove(sldId)


def _render_slide(sl, ir, palette, p, used, errors, page_no, seed_layout=None,
                  prs=None):
    """单页渲染体（创建序 → 按 z 稳定重排；背景垫底、页眉/页脚压顶）。
    seed 打底：ph 元素不自绘，向匹配占位符写入文本（落点/样式留模板）；其余照常。
    prs：link slide 跳转需访问 Presentation 全页（跨页 rel 目标）。"""
    sw, sh = ir["slide"]
    fw = ir.get("framework") or {}
    if fw.get("background"):
        # 背景在最底：创建序领先一切（z=0，_apply_z_order 后仍最底）
        _render_framework_bg(sl, fw["background"], palette, p, used, errors, sw, sh)
    order = sorted(ir["elements"], key=lambda e: e["z"])
    for e in order:
        if e.get("ph_info"):
            if seed_layout is not None:
                _render_ph(sl, e, palette, p, used, errors)
            else:
                errors.append(f"{e['id']}: ph 元素但非 seed 模式（编译期应已拦截）")
            continue
        _render_element(sl, e, palette, p, used, errors, prs=prs)
    for g in sorted(ir["groups"], key=lambda g: g["z"]):
        _render_group(sl, g, palette, p, used)
    for ln in sorted(ir["lines"], key=lambda x: x["z"]):
        _render_line(sl, ln, palette, p, used)
    for gl in sorted(ir["glue"], key=lambda x: x["z"]):
        _render_glue(sl, gl, palette, p, used)
    zmap = _name_z_map(ir)
    if fw:
        zmap.update(_framework_zmap(ir, fw))
        _render_framework_hf(sl, fw, ir["margin"], palette, p, used, sw, sh, page_no)
    if ir.get("notes"):
        _render_notes(sl, ir["notes"], p, used, errors)
    if ir.get("transition"):
        _inject_transition(sl, ir["transition"])
        used.add("transition")
    _apply_z_order(sl, zmap)


def _framework_zmap(ir, fw):
    """框架层 z 语义：背景=0（最底），页眉/页脚=全局最大 z 之上（最顶）。
    渲染与物证的层级检查共用同一规则（不在 IR，故此处单独分配）。"""
    zm = {}
    if fw.get("background"):
        zm[BG_NAME] = 0
    zmax = ir.get("z_max", 0)
    if fw.get("header", {}).get("text"):
        zm[HDR_NAME] = zmax + 1
    if fw.get("footer", {}).get("text"):
        zm[FTR_NAME] = zmax + (2 if HDR_NAME in zm else 1)
    return zm


def _render_framework_bg(sl, bg, palette, p, used, errors, sw, sh):
    """全幅背景矩形：solid 或 grad 填充，无描边（z 最低垫底）。"""
    try:
        sp = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(sw), Inches(sh))
        sp.name = BG_NAME
        sp.line.fill.background()
        _apply_fill(sp, bg["fill"], palette, p)
        used.add("framework_bg")
    except Exception as ex:
        errors.append(f"framework 背景失败: {ex}")


def _render_framework_hf(sl, fw, margin, palette, p, used, sw, sh, page_no=1):
    """页眉/页脚文本层（最顶）：段落对齐定位，无需量测宽度。
    x 范围 = margin.l..sw-margin.r；页脚 {page} 占位符按实际页号展开
    （多页序列逐页编号，渲染与物证同规则）。"""
    ml = float(margin.get("l", 0.5))
    mr = float(margin.get("r", 0.5))
    for key, name, ck in (("header", HDR_NAME, "header"),
                          ("footer", FTR_NAME, "footer")):
        hf = fw.get(key)
        if not hf or not hf.get("text"):
            continue
        text = hf["text"]
        if key == "footer":
            # 显示页码 = 实际页号 + page_offset（封面不计页码等场景；render/物证同规）
            text = text.replace(p["framework"]["page_token"],
                                str(page_no + p["framework"]["page_offset"]))
        fs = hf.get("fs", p["framework"][f"{key}_fs"])
        ts = {"fs": fs, "color": hf.get("color", p["framework"][f"{key}_color"]),
              "align": hf.get("align", p["framework"][f"{key}_align"])}
        pad = p["framework"][f"{key}_pad"]
        h = fs / 72.0 * 1.5                    # 单行文本区高（行高余量）
        y = pad if key == "header" else sh - pad - h
        box = sl.shapes.add_textbox(Inches(ml), Inches(y),
                                    Inches(sw - ml - mr), Inches(h))
        box.name = name
        box.fill.background()
        box.line.fill.background()
        _set_text(box.text_frame, text, ts, None, p, palette)
        used.add(f"framework_{ck}")


def _render_notes(sl, notes, p, used, errors):
    """备注页文本：notes_slide，每行一段 run（多行 = 多段）。纯渲染层（零 COM），
    不占 slide spTree（notes part 是独立部件）；物证按 slide rel 找 notes part 核对。"""
    try:
        tf = sl.notes_slide.notes_text_frame
        tf.clear()                     # 清光全部段落，留一个空段（python-pptx clear() 契约）
        para = tf.paragraphs[0]
        for i, line in enumerate(str(notes).split("\n")):
            if i:
                para = tf.add_paragraph()
            r = para.add_run()
            r.text = line
            r.font.size = Pt(p["text"]["notes_fs"])
            _set_run_fonts(r, p, "body")
        used.add("notes")
    except Exception as ex:
        errors.append(f"备注页失败: {ex}")


_TRANSITION_TAGS = {"fade": "fade", "push": "push", "wipe": "wipe", "cut": "cut"}


def _inject_transition(sl, tr):
    """页级切换：p:transition 注入 slide XML。CT_Slide 子元素固定序列
    cSld/clrMapOvr → transition → timing → extLst，故插入 clrMapOvr 之后。
    effect 子元素换挡（fade/push/wipe/cut），push/wipe 带 dir="l"（从左推入/擦入）；
    spd 是 OOXML 定性档位（slow|med|fast，无秒级精度——CD 对齐 render/物证）。

    morph（C3 平滑切换）走 mc:AlternateContent：Choice[Requires=p159] 内
    p:transition(spd) + p14:dur(ms) + p159:morph(option=byObject)，Fallback 降级
    p:fade——不认识 morph 的旧版播放器仍出淡入。同名对象跨页自动补间变形。"""
    if not tr:
        return
    eff = tr.get("effect")
    if eff == "morph":
        _inject_morph(sl, tr)
        return
    tag = _TRANSITION_TAGS.get(eff)
    if tag is None:                  # effect: none / 缺省 = 不注入（无切换）
        return
    sld = sl._element
    clr = sld.find(qn("p:clrMapOvr"))
    tr_el = sld.makeelement(qn("p:transition"), {"spd": tr.get("spd", "med")})
    eff_el = tr_el.makeelement(qn(f"p:{tag}"), {})
    if tag in ("push", "wipe"):
        eff_el.set("dir", "l")
    tr_el.append(eff_el)
    if clr is not None:
        clr.addnext(tr_el)
    else:
        sld.append(tr_el)


_P159_NS = "http://schemas.microsoft.com/office/powerpoint/2015/09/main"
_P14_NS = "http://schemas.microsoft.com/office/powerpoint/2010/main"


def _inject_morph(sl, tr):
    """平滑切换（Morph）：mc:AlternateContent + p159:morph + p14:dur；fade 回退。
    时长 dur 毫秒（p14:dur，缺省 700）；spd 同步给 Choice/Fallback 两版 p:transition。"""
    sld = sl._element
    spd = tr.get("spd", "med")
    dur = int(tr.get("dur", 700))
    ac = etree.Element("{%s}AlternateContent" % MC_NS,
                       nsmap={"mc": MC_NS, "p159": _P159_NS, "p14": _P14_NS})
    choice = etree.SubElement(ac, "{%s}Choice" % MC_NS)
    choice.set("Requires", "p159")
    ch_tr = etree.SubElement(choice, qn("p:transition"), {"spd": spd})
    ch_tr.set("{%s}dur" % _P14_NS, str(dur))
    etree.SubElement(ch_tr, "{%s}morph" % _P159_NS).set("option", "byObject")
    fbk = etree.SubElement(ac, "{%s}Fallback" % MC_NS)
    fb_tr = etree.SubElement(fbk, qn("p:transition"), {"spd": spd})
    etree.SubElement(fb_tr, qn("p:fade"))
    clr = sld.find(qn("p:clrMapOvr"))
    if clr is not None:
        clr.addnext(ac)
    else:
        sld.append(ac)


def _name_z_map(ir):
    """name → z 映射（name 唯一；与 COM 按名查找 / XML 物证同机制）。
    注意：不可用 id(oxml) 作键——lxml 代理对象 GC 后 id 可复用，重排即错位。"""
    zmap = {}
    for e in ir["elements"]:
        zmap[e["id"]] = e["z"]
    for g in ir["groups"]:
        zmap[g["id"]] = g["z"]
    for ln in ir["lines"]:
        if ln.get("curve"):
            zmap[ln["id"]] = ln["z"]         # freeform 单形状（非 .segN 分段）
        elif ln.get("pts"):
            for i in range(len(ln["pts"]) - 1):
                zmap[f"{ln['id']}.seg{i}"] = ln["z"]
        else:
            zmap[ln["id"]] = ln["z"]
    for gl in ir["glue"]:
        zmap[gl["id"]] = gl["z"]
    return zmap


def _cnv_name(el):
    """取形状 cNvPr@name（透传 mc:AlternateContent 取内层 sp，公式框按名定 z）。
    绝不可写 find(...) or find(...)：lxml 空元素（如 cNvPr）bool() 为 False，
    链式 or 会短路成 None。"""
    P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    cur = el
    if cur.tag == "{%s}AlternateContent" % MC_NS:
        inner = cur.find(f"{{%s}}Choice/{P}sp" % MC_NS)
        if inner is not None:
            cur = inner
    nv = cur.find(f"{P}nvSpPr/{P}cNvPr")
    if nv is None:
        nv = cur.find(f"{P}nvCxnSpPr/{P}cNvPr")
    if nv is None:
        nv = cur.find(f"{P}nvPicPr/{P}cNvPr")
    if nv is None:
        nv = cur.find(f"{P}nvGrpSpPr/{P}cNvPr")
    if nv is None:
        nv = cur.find(f"{P}nvGraphicFramePr/{P}cNvPr")   # 表格/图表 graphicFrame
    return nv.get("name") if nv is not None else None


def _apply_z_order(sl, zmap):
    """层级铁律强制执行：OOXML 层级 = spTree 文档序（越靠后越靠前）。
    各形状按创建顺序 append（元素→组→线），与 IR z 无关——必须按 z 稳定重排，
    否则组包络/连线会盖住更高 z 的节点。z 相同保持原插入序。"""
    spTree = sl.shapes._spTree
    kids = list(spTree)
    if len(kids) <= 2:
        return
    body = kids[2:]  # 跳过 nvGrpSpPr / grpSpPr 两个文档头
    body.sort(key=lambda el: zmap.get(_cnv_name(el), 1 << 30))
    for el in body:
        spTree.remove(el)
    for el in body:
        spTree.append(el)


def _apply_link(sl, shp, link, prs, used):
    """元素级超链接：cNvPr 下 a:hlinkClick 注入（零 COM）。
    slide → 本包 slide part rel + action="ppaction://hlinksldjump"
    （PowerPoint「本文档中的位置」原生格式）；url/email → 外部 hyperlink
    rel（TargetMode=External）。prs 供跨页访问目标 slide part。"""
    if shp is None:
        return
    P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    cNvPr = shp._element.find(f"{P}nvSpPr/{P}cNvPr")
    if cNvPr is None:
        cNvPr = shp._element.find(f"{P}nvPicPr/{P}cNvPr")
    if cNvPr is None:
        cNvPr = shp._element.find(f"{P}nvGraphicFramePr/{P}cNvPr")
    if cNvPr is None:
        raise RuntimeError("无 cNvPr 可挂 hlinkClick")
    kind = next((k for k in ("url", "slide", "email") if k in link), None)
    attrs = {}
    if kind == "slide":
        rid = sl.part.relate_to(prs.slides[link["slide"] - 1].part, RT.SLIDE)
        attrs["action"] = "ppaction://hlinksldjump"
    else:
        target = link["url"] if kind == "url" else f"mailto:{link['email']}"
        rid = sl.part.relate_to(target, RT.HYPERLINK, is_external=True)
    h = cNvPr.makeelement(qn("a:hlinkClick"), {qn("r:id"): rid, **attrs})
    cNvPr.append(h)
    used.add("link")


def _set_custgeom(sp, subs, vb_w, vb_h):
    """字形子路径写入 spPr 的 a:custGeom（替代 a:prstGeom）。所有子路径合一
    a:path → 口/日 等内孔保持镂空（分 path 会各自填充成实心）。"""
    spPr = sp._element.spPr
    old = spPr.find(qn("a:prstGeom"))
    if old is not None:
        spPr.remove(old)
    cg = spPr.makeelement(qn("a:custGeom"), {})
    for tag in ("a:avLst", "a:gdLst", "a:ahLst", "a:cxnLst"):
        cg.append(cg.makeelement(qn(tag), {}))
    cg.append(cg.makeelement(qn("a:rect"), {"l": "0", "t": "0", "r": "r", "b": "b"}))
    pl = cg.makeelement(qn("a:pathLst"), {})
    pe = pl.makeelement(qn("a:path"),
                        {"w": str(int(round(vb_w))), "h": str(int(round(vb_h)))})

    def pt(parent, x, y):
        parent.append(parent.makeelement(qn("a:pt"),
                                         {"x": str(int(round(x))), "y": str(int(round(y)))}))
    for s in subs:
        mv = pe.makeelement(qn("a:moveTo"), {})
        pt(mv, *s["start"])
        pe.append(mv)
        for sg in s["segs"]:
            if sg[0] == "L":
                ln = pe.makeelement(qn("a:lnTo"), {})
                pt(ln, sg[1], sg[2])
                pe.append(ln)
            else:
                cb = pe.makeelement(qn("a:cubicBezTo"), {})
                pt(cb, sg[1], sg[2])
                pt(cb, sg[3], sg[4])
                pt(cb, sg[5], sg[6])
                pe.append(cb)
        pe.append(pe.makeelement(qn("a:close"), {}))
    pl.append(pe)
    cg.append(pl)
    xfrm = spPr.find(qn("a:xfrm"))
    if xfrm is not None:
        xfrm.addnext(cg)          # CT 顺序：xfrm → geom → fill → ln
    else:
        spPr.insert(0, cg)


def _set_custgeom_stroke(sp, subs, vb_w, vb_h, filled):
    """图标子路径写入 spPr 的 a:custGeom（**描边**语义）：逐子路径一条 a:path——
    描边项 `fill="none"`（线描保留，不填充），实心项 `fill="norm"`（如 chart-scatter
    的点）。与 brush 的「单路径填充」语义相对（图标须线描，分 path 才各有 fill 语义）。
    形状级 a:ln（色/宽/cap/join）由调用方经 python-pptx API 设置。"""
    spPr = sp._element.spPr
    old = spPr.find(qn("a:prstGeom"))
    if old is not None:
        spPr.remove(old)
    cg = spPr.makeelement(qn("a:custGeom"), {})
    for tag in ("a:avLst", "a:gdLst", "a:ahLst", "a:cxnLst"):
        cg.append(cg.makeelement(qn(tag), {}))
    cg.append(cg.makeelement(qn("a:rect"), {"l": "0", "t": "0", "r": "r", "b": "b"}))
    pl = cg.makeelement(qn("a:pathLst"), {})
    W, H = str(int(round(vb_w))), str(int(round(vb_h)))

    def pt(parent, x, y):
        parent.append(parent.makeelement(qn("a:pt"),
                                         {"x": str(int(round(x))), "y": str(int(round(y)))}))
    for i, s in enumerate(subs):
        pe = pl.makeelement(qn("a:path"),
                            {"w": W, "h": H, "fill": "norm" if i in filled else "none"})
        mv = pe.makeelement(qn("a:moveTo"), {})
        pt(mv, *s["start"])
        pe.append(mv)
        for sg in s["segs"]:
            if sg[0] == "L":
                ln = pe.makeelement(qn("a:lnTo"), {})
                pt(ln, sg[1], sg[2])
                pe.append(ln)
            else:
                cb = pe.makeelement(qn("a:cubicBezTo"), {})
                pt(cb, sg[1], sg[2])
                pt(cb, sg[3], sg[4])
                pt(cb, sg[5], sg[6])
                pe.append(cb)
        if s["closed"]:
            pe.append(pe.makeelement(qn("a:close"), {}))
        pl.append(pe)
    cg.append(pl)
    xfrm = spPr.find(qn("a:xfrm"))
    if xfrm is not None:
        xfrm.addnext(cg)          # CT 顺序：xfrm → geom → fill → ln
    else:
        spPr.insert(0, cg)


def _set_picture_fill(sp, sl, img_path, alpha=1.0):
    """spPr 填充改 a:blipFill（形状/书法字内透出图片）。图片 part + rId 由 slide 持有；
    填充选择器排在 geom 之后、a:ln 之前（CT 顺序）。"""
    spPr = sp._element.spPr
    for tag in ("a:noFill", "a:solidFill", "a:gradFill", "a:blipFill",
                "a:pattFill", "a:grpFill"):
        old = spPr.find(qn(tag))
        if old is not None:
            spPr.remove(old)
    _img_part, rid = sl.part.get_or_add_image_part(img_path)
    bf = spPr.makeelement(qn("a:blipFill"), {"rotWithShape": "1"})
    blip = bf.makeelement(qn("a:blip"), {})
    blip.set(qn("r:embed"), rid)
    if alpha < 1.0:
        blip.append(blip.makeelement(qn("a:alphaModFix"),
                                     {"amt": str(int(alpha * 100000))}))
    bf.append(blip)
    stretch = bf.makeelement(qn("a:stretch"), {})
    stretch.append(bf.makeelement(qn("a:fillRect"), {}))
    bf.append(stretch)
    ln = spPr.find(qn("a:ln"))
    if ln is not None:
        ln.addprevious(bf)
    else:
        spPr.append(bf)


def _render_brush(sl, e, palette, p, used, errors):
    """书法矢量字（C3）：add_shape(RECTANGLE) → 换 custGeom 为字形轮廓 →
    style 三态填充（实色 / 渐变 / 图片）。字形路径由 ink_text 现算（艺术路径，
    非几何；元素 rect 已由 ir_builder 定死）。"""
    import ink_text
    b = e.get("brush") or {}
    rect = e["rect"]
    sp = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(rect[0]), Inches(rect[1]),
                             Inches(rect[2]), Inches(rect[3]))
    sp.name = e["id"]
    sp.line.fill.background()
    try:
        subs, vw, vh = ink_text.subpaths(b["text"], b["font"],
                                         spacing=float(b.get("spacing") or 0.0))
        _set_custgeom(sp, subs, vw, vh)
    except Exception as ex:
        errors.append(f"{e['id']} 字形矢量化失败: {ex}")
        return sp
    st = e.get("style") or {}
    if st.get("image"):
        _set_picture_fill(sp, sl, st["image"], float(st.get("alpha", 1.0)))
        used.add("brush_image")
    else:
        try:
            if st.get("grad"):
                g = st["grad"]
                sp.fill.gradient()
                sp.fill.gradient_stops[0].color.rgb = _resolve_color(g[0], palette, g[0])
                sp.fill.gradient_stops[-1].color.rgb = _resolve_color(g[1], palette, g[1])
                used.add("brush_grad")
            else:
                _apply_fill(sp, st.get("fill") or p["style"]["fill"], palette, p)
                used.add("brush")
        except Exception as ex:
            errors.append(f"{e['id']} fill 失败: {ex}")
        if st.get("alpha") is not None:
            _apply_fill_alpha(sp, st["alpha"])
    return sp


def _render_icon(sl, e, palette, p, used, errors):
    """矢量图标（B1）：add_shape(RECTANGLE) → 换 custGeom 为图标轮廓（描边语义）→
    形状无填充 + a:ln 描线（色/宽/cap=rnd/圆角连接）。子路径由 icon_lib 现算（图标
    路径非几何；元素 rect 已由 ir_builder 定死）。"""
    import icon_lib
    rect = e["rect"]
    sp = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(rect[0]), Inches(rect[1]),
                             Inches(rect[2]), Inches(rect[3]))
    sp.name = e["id"]
    sp.fill.background()               # 图标无填充：仅描边
    st = e.get("style") or {}
    color = _resolve_color(st.get("color"), palette, p["style"]["line_color"])
    weight = float(st.get("weight") or p["style"]["icon_weight"])
    try:
        subs, vw, vh, filled = icon_lib.subpaths(e["icon"])
        _set_custgeom_stroke(sp, subs, vw, vh, filled)
    except Exception as ex:
        errors.append(f"{e['id']} 图标矢量化失败: {ex}")
        return sp
    sp.line.color.rgb = color
    sp.line.width = Pt(weight)
    ln = sp.line._get_or_add_ln()
    ln.set("cap", "rnd")               # 圆头端点（Lucide 圆角风格）
    ln.append(ln.makeelement(qn("a:round"), {}))   # 圆角连接
    used.add("icon")
    return sp


def _render_svgpath(sl, e, palette, p, used, errors):
    """矢量图片（type: svg 展开）：局部子路径写 custGeom 形状——整片填充用
    _set_custgeom（单路径保内孔），含描边用 _set_custgeom_stroke（逐子路径
    fill=none|norm 线描 + a:ln 描线）。rect 与 subpaths 均由 ir_builder 定死
    （铁律 1）；本层零几何重算。"""
    pd = e["path"]
    rect = e["rect"]
    sp = sl.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                             Inches(rect[0]), Inches(rect[1]),
                             Inches(rect[2]), Inches(rect[3]))
    sp.name = e["id"]
    fill = pd.get("fill")
    stroke = pd.get("stroke")
    need_stroke = bool(stroke) and str(stroke).lower() != "none"
    vw, vh = int(round(pd.get("vb_w", 1))), int(round(pd.get("vb_h", 1)))
    try:
        if need_stroke and not fill:
            _set_custgeom_stroke(sp, pd["subs"], vw, vh, frozenset())
        else:
            # 有填充（含 fill+stroke 混合 → 按 fill 处理）：单路径合并保内孔
            _set_custgeom(sp, pd["subs"], vw, vh)
    except Exception as ex:
        errors.append(f"{e['id']} svg 形状失败: {ex}")
        return sp
    if fill:
        _apply_fill(sp, fill, palette, p)
    if need_stroke:
        sp.line.color.rgb = _hex(stroke)
        sp.line.width = Pt(pd.get("stroke_w") or 1.0)
        ln = sp.line._get_or_add_ln()
        ln.set("cap", "rnd")
        ln.append(ln.makeelement(qn("a:round"), {}))
    else:
        sp.line.fill.background()
    used.add("svg_shape")
    return sp


def _render_element(sl, e, palette, p, used, errors, prs=None):
    t = e["type"]
    rect = e["rect"]
    _el = None
    if t == "brush":
        _el = _render_brush(sl, e, palette, p, used, errors)
    elif t == "icon":
        _el = _render_icon(sl, e, palette, p, used, errors)
    elif t == "svgpath":
        _el = _render_svgpath(sl, e, palette, p, used, errors)
    elif t == "shape":
        kind = e["kind"]
        shape = TOP_SHAPE.get(kind, MSO_SHAPE.ROUNDED_RECTANGLE)
        if kind in SHAPE_BY_KIND:
            shape = SHAPE_BY_KIND[kind]
        sp = sl.shapes.add_shape(shape, Inches(rect[0]), Inches(rect[1]),
                                 Inches(rect[2]), Inches(rect[3]))
        sp.name = e["id"]          # COM 按名查找 / XML 物证核对
        st = e.get("style") or {}
        used.add("gradient" if isinstance(st.get("fill"), dict)
                 or (isinstance(st.get("fill"), str) and st.get("fill") in palette
                     and "grad" in palette[st["fill"]])
                 else "solid_fill")
        try:
            _apply_fill(sp, st.get("fill"), palette, p)
        except Exception as ex:
            errors.append(f"{e['id']} fill 失败: {ex}")
        border = st.get("border")
        if border:
            sp.line.color.rgb = _resolve_color(border, palette,
                                               p["style"]["border"])
        else:
            sp.line.fill.background()
        if st.get("border_dash"):
            # 虚线段式分区框（原稿虚线分区）：dash|dot|dash_dot 线型
            sp.line.dash_style = _DASH[st["border_dash"]]
        if st.get("opacity") is not None:
            # 半透明填充（cylinder 侧壁；alpha 直注 XML，FillFormat 无 transparency）
            _apply_fill_alpha(sp, st["opacity"])
        if kind in ("rounded_rect", "proc"):
            try:
                sp.adjustments[0] = p["style"]["rounded_radius"]
            except Exception:
                pass
        if st.get("shadow", p["style"]["shadow"]) is not False:
            inject_outer_shadow(sp)
            used.add("shadow")
        if e.get("text"):
            guard = _fill_guard_color(st.get("fill"), palette,
                                      p["style"]["fill"])
            _set_text(sp.text_frame, e["text"], e.get("text_style"),
                      e.get("text_layout"), p, palette, guard_bg=guard,
                      box_w_pt=rect[2] * 72, runs=e.get("runs"))
        used.add("node_shape")
        _el = sp
    elif t == "text":
        box = sl.shapes.add_textbox(Inches(rect[0]), Inches(rect[1]),
                                    Inches(rect[2]), Inches(rect[3]))
        box.name = e["id"]
        bg = (e.get("text_style") or {}).get("bg")
        if bg:
            box.fill.solid()
            box.fill.fore_color.rgb = _resolve_color(bg, palette,
                                                     p["style"]["fill"])
            used.add("cover_label")
        else:
            box.fill.background()
            box.line.fill.background()
        _set_text(box.text_frame, e["text"], e.get("text_style"),
                  e.get("text_layout"), p, palette, box_w_pt=rect[2] * 72,
                  runs=e.get("runs"))
        used.add("textbox")
        _el = box
    elif t in ("image", "diagram"):
        # diagram = 逃生通道：外部转换器预渲染产物按图片落版；
        # .vsdx 升级为原生 Visio OLE（双击可编辑）由 com_layer OLE 作业接管（本层跳过）。
        vsdx = t == "diagram" and str(e.get("src") or "").lower().endswith(".vsdx")
        if vsdx:
            used.add("ole_pending")
            return
        # B3 图片占位：显式 placeholder 或 src 文件缺失（非 --strict-images 时已
        # 在编译期放过）→ 落虚线占位框，缺图提示清单见 out_dir/img_prompts.md
        src_ok = bool(e.get("src")) and os.path.isfile(e["src"])
        if e.get("placeholder") or not src_ok:
            used.add("image_placeholder")
            _el = _render_image_placeholder(sl, e, palette, p)
        else:
            try:
                pic = sl.shapes.add_picture(e["src"], Inches(rect[0]), Inches(rect[1]),
                                            Inches(rect[2]), Inches(rect[3]))
                pic.name = e["id"]        # 与 shape/cxnSp 同律：按名定位/COM 按名查找
                used.add("diagram_png" if t == "diagram" else
                         ("image_crop" if e.get("visual_bounds") == "auto" else "image"))
                _el = pic
            except Exception as ex:
                errors.append(f"{e['id']} 图片失败: {ex}")
    elif t == "typst":
        # typst 排版块（references/typst-chain.md）：SVG(2016+ svgBlip) + PNG(fallback)
        # 双通道合一——svg 注入失败降级纯 PNG（WARN 记账，不阻断 exit）；
        # 整块为图 = 内容型积木（数据红线约束），非逐字可编辑
        png, svg = e.get("png"), e.get("svg")
        if not png or not os.path.isfile(png):
            errors.append(f"{e['id']} typst 产物缺失（PNG）")
        else:
            try:
                pic = sl.shapes.add_picture(png, Inches(rect[0]), Inches(rect[1]),
                                            Inches(rect[2]), Inches(rect[3]))
                pic.name = e["id"]
                used.add("typst_block")
                if svg and os.path.isfile(svg) and _inject_svg_blip(sl, pic, svg, prs):
                    used.add("typst_svg")
                else:
                    used.add("typst_png_fallback")
                _el = pic
            except Exception as ex:
                errors.append(f"{e['id']} typst 图片失败: {ex}")
    elif t == "formula":
        _el = _render_formula(sl, e, palette, p, used, errors)
    elif t == "table":
        _el = _render_table(sl, e, palette, p, used, errors)
    elif t == "chart":
        _el = _render_chart(sl, e, palette, p, used, errors)
    else:
        errors.append(f"{e['id']}: 未预期元素类型 {t}")
    if e.get("link") and _el is not None:
        # 元素级超链接（零 COM）：cNvPr 下 a:hlinkClick 注入
        try:
            _apply_link(sl, _el, e["link"], prs, used)
        except Exception as ex:
            errors.append(f"{e['id']} 链接失败: {ex}")


def _render_image_placeholder(sl, e, palette, p):
    """图片占位框（B3）：虚线圆角矩形 + 居中提示文案，name=id（物证/COM 按名定位）。
    几何直接取 IR rect（铁律 1：渲染层不重算）；文案优先级 caption > placeholder
    字符串 > images.missing_key 兜底。返回形状供 link 复用。"""
    cfg = p["images"]
    x, y, w, h = e["rect"]
    box = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                              Inches(x), Inches(y), Inches(w), Inches(h))
    box.name = e["id"]
    fill_rgb = _resolve_color(cfg.get("placeholder_fill"), palette, "#F2F5FA")
    box.fill.solid()
    box.fill.fore_color.rgb = fill_rgb
    box.line.color.rgb = _resolve_color(cfg.get("placeholder_border"), palette, "#8FA3BF")
    box.line.dash_style = MSOL.DASH
    ph = e.get("placeholder")
    txt = e.get("caption") or (ph if isinstance(ph, str) and ph.strip()
                               else cfg.get("missing_key", "占位图"))
    _set_text(box.text_frame, txt, {"fs": cfg.get("placeholder_fs", 12.0)},
              None, p, palette, guard_bg=fill_rgb, box_w_pt=w * 72)
    return box


def _inject_svg_blip(sl, pic, svg_path, prs):
    """SVG 直嵌 OOXML 2016+（a:blip 内 extLst > ext > asvg:svgBlip，双 rId 结构）：
    现代 PPT 渲染矢量 SVG，2016 前旧版显示 PNG fallback。失败返回 False（调用方
    降级纯 PNG，WARN 不阻断）。"""
    try:
        pkg = prs.part.package
        nxt = pkg.next_image_partname("png")
        svg_partname = PackURI(str(nxt).rsplit(".", 1)[0] + ".svg")
        with open(svg_path, "rb") as f:
            svg_part = Part(svg_partname, "image/svg+xml", pkg, f.read())
        r_svg = sl.part.relate_to(svg_part, RT.IMAGE)
        blip = pic._element.blipFill.blip
        ext_lst = blip.makeelement(qn("a:extLst"), {})
        ext = blip.makeelement(qn("a:ext"),
                               {"uri": "{96DAC541-7B7A-43D3-8B79-37D633B846F1}"})
        svg_blip = blip.makeelement(
            "{http://schemas.microsoft.com/office/drawing/2016/SVG/main}svgBlip",
            {qn("r:embed"): r_svg})
        ext.append(svg_blip)
        ext_lst.append(ext)
        blip.append(ext_lst)
        return True
    except Exception:
        return False


def _render_formula(sl, e, palette, p, used, errors):
    """formula 元素：Choice 版 a14:m 原生公式 + Fallback 版表达式原文（零 Office
    也可读）；子集外降级为普通文本框（文本=原文），com_layer 按 name 兜底替换。
    mc 包装对齐实测（Word 产物）：AlternateContent 内两 p:sp 共用同一 id。"""
    rect = e["rect"]
    ts = e.get("text_style") or {}
    fs = ts.get("fs", p["formula"]["fs_default"])
    color = ts.get("color")
    if isinstance(color, str) and color in palette:
        color = palette[color]["solid"]
    color_hex = color.lstrip("#") if color else None
    expr = e["expr"]

    box = sl.shapes.add_textbox(Inches(rect[0]), Inches(rect[1]),
                                Inches(rect[2]), Inches(rect[3]))
    box.name = e["id"]
    box.fill.background()
    box.line.fill.background()
    tf = box.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.word_wrap = True
    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.CENTER
    run = para.add_run()
    run.text = expr                     # 初始文本=原文（Fallback 版直接可用）
    run.font.size = Pt(fs)
    _set_run_fonts(run, p, "body")

    r = formula_omml.parse_expr(expr, fs, color_hex)
    if r["ok"]:
        used.add("formula_omml")
        _wrap_formula_mc(sl, box._element, r["omml"])
    else:
        # 辅助手段：离线模板库命中（子集外高频写法，零 Word/零中间文件注入）
        t_omml = formula_templates.resolve(expr, fs, color_hex)
        if t_omml is not None:
            used.add("formula_template")
            _wrap_formula_mc(sl, box._element, t_omml)
            print(f"[stage4] {e['id']} 公式模板命中（离线库）→ 注入，无需 --com")
        else:
            # 子集外且未命中模板：普通文本框降级（com_layer 兜底时按 name
            # 替换为引擎 OMML）。与 glue 降级同哲学：WARN 不阻断，物证侧查占位文本。
            used.add("formula_pending")
            print(f"[stage4] WARN {e['id']} 公式子集外（{r['reason']}）→ 占位文本；"
                  f"--com 时 com_layer 批量兜底")
    return box


def _wrap_formula_mc(sl, sp_el, omml_body):
    """spTree 层 mc:AlternateContent 包装：Choice 插 a14:m 公式，Fallback 保留文本。"""
    P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    # 显式声明 mc/a14 前缀（libxml 自动前缀 ns0 语义正确但避免与其他工具不一致）
    mc_el = etree.Element("{%s}AlternateContent" % MC_NS, nsmap={"mc": MC_NS})
    choice = etree.SubElement(mc_el, "{%s}Choice" % MC_NS, nsmap={"a14": A14_NS})
    choice.set("Requires", "a14")
    fbk = etree.SubElement(mc_el, "{%s}Fallback" % MC_NS)
    csp = copy.deepcopy(sp_el)
    # Choice 版 txBody：清空 run，注入公式段（txBody 子元素是 a:p，非 p:p）
    tx = csp.find(f"{P}txBody")
    p_el = tx.find(qn("a:p")) if tx is not None else None
    for r in p_el.findall(qn("a:r")):
        p_el.remove(r)
    p_el.append(etree.fromstring(formula_omml.omath_paragraph(omml_body)))
    choice.append(csp)
    fbk.append(copy.deepcopy(sp_el))
    spTree = sl.shapes._spTree
    for i, kid in enumerate(spTree):
        if kid is sp_el:
            spTree.remove(kid)
            spTree.insert(i, mc_el)
            break


def _set_cell_borders(cell, color_rgb, w_pt):
    """单元格四边框（a:tcPr 子元素 lnT/B/L/R；python-pptx 无边框 API，手写）。
    ln 必须排在 fill 元素之前（CT_TableCellProperties 固定序列）→ addprevious。"""
    tcPr = cell._tc.get_or_add_tcPr()
    fill_el = tcPr.find(qn("a:solidFill"))
    if fill_el is None:
        fill_el = tcPr.find(qn("a:noFill"))
    w_emu = str(int(w_pt * 12700))
    for side in ("lnL", "lnR", "lnT", "lnB"):
        ln = tcPr.makeelement(qn(f"a:{side}"),
                              {"w": w_emu, "cap": "flat", "cmpd": "sng", "algn": "ctr"})
        sf = ln.makeelement(qn("a:solidFill"), {})
        rgb = ln.makeelement(qn("a:srgbClr"), {"val": str(color_rgb).lstrip("#")})
        sf.append(rgb)
        ln.append(sf)
        if fill_el is not None:
            fill_el.addprevious(ln)
        else:
            tcPr.append(ln)


def _render_table(sl, e, palette, p, used, errors):
    """table 元素 → GraphicFrame 内原生 a:tbl（python-pptx add_table，零 COM）。
    行高均分 rect.h；列宽=IR col_widths（和 == rect.w，编译已保证）。"""
    x, y, w, h = e["rect"]
    rows, cols = e["rows"], e["cols"]
    try:
        gf = sl.shapes.add_table(rows, cols, Inches(x), Inches(y), Inches(w), Inches(h))
    except Exception as ex:
        errors.append(f"{e['id']} 表格创建失败: {ex}")
        return
    gf.name = e["id"]
    tb = gf.table
    # 关闭主题条纹样式：本积木自绘全部样式（表头/边框/字体），防止 PPT 混入默认条纹
    try:
        tb.first_row = False
        tb.horz_banding = False
    except Exception:
        pass
    for ri in range(rows):
        tb.rows[ri].height = Inches(h / rows)
    for ci in range(cols):
        tb.columns[ci].width = Inches(e["col_widths"][ci])
    brd = e.get("borders", True)
    if isinstance(brd, str):
        brd = brd != "none"
        brd_color = _resolve_color(e["borders"], palette, p["table"]["border_color"])
    else:
        brd_color = _hex(p["table"]["border_color"])
    hdr = e.get("header")  # dict（启用）或 False/None
    tp = p["table"]
    for ri in range(rows):
        is_hdr = ri == 0 and isinstance(hdr, dict)
        st = dict(hdr) if is_hdr else dict(e.get("body") or {})
        fs = e.get("header_fs") if is_hdr else e.get("cell_fs")
        for ci in range(cols):
            cell = tb.cell(ri, ci)
            cell.margin_left = cell.margin_right = Inches(tp["cell_pad"])
            cell.margin_top = cell.margin_bottom = Inches(tp["cell_pad"] / 2)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cr = e.get("cell_runs")
            cell_runs = cr[ri][ci] if cr else None
            _fill_table_cell(cell, is_hdr, st, palette, p, fs,
                             str(e["data"][ri][ci]), runs=cell_runs)
            if brd:
                _set_cell_borders(cell, brd_color, tp["border_w"])
    used.add("table")
    return gf


def _fill_table_cell(cell, is_hdr, st, palette, p, fs, text, runs=None):
    """单元格填充 + 单段文本（表头居中加粗/底色；正文左对齐）。
    runs：富文本段（IR 已解析）；emphasis 段用 params.style.emphasis 色。"""
    tp = p["table"]
    if is_hdr:
        cell.fill.solid()
        cell.fill.fore_color.rgb = _resolve_color(st.get("fill", tp["header_fill"]),
                                                  palette, tp["header_fill"])
    elif st.get("fill"):
        cell.fill.solid()
        cell.fill.fore_color.rgb = _resolve_color(st["fill"], palette,
                                                  p["style"]["fill"])
    else:
        cell.fill.background()
    tf = cell.text_frame
    tf.clear()
    para = tf.paragraphs[0]
    # 规则2：文字在表格中居中（表头与正文单元格均居中）
    para.alignment = PP_ALIGN.CENTER
    base_bold = bool(st.get("bold", tp["header_bold"] if is_hdr else False))
    col = st.get("color") or (tp["header_color"] if is_hdr else p["style"]["text_color"])
    rgb = _resolve_color(col, palette, col)
    emph_rgb = _resolve_color(p["style"].get("emphasis", p["style"]["text_color"]),
                              palette, p["style"]["text_color"])
    for seg in (runs or [{"text": text, "bold": base_bold, "emph": False}]):
        if not seg.get("text"):
            continue
        r = para.add_run()
        r.text = seg["text"]
        r.font.size = Pt(fs)
        emph = bool(seg.get("emph"))
        r.font.color.rgb = emph_rgb if emph else rgb
        r.font.bold = bool(base_bold or seg.get("bold") or emph)
        if emph:
            r.font.underline = True
        _set_run_fonts(r, p, "body")


def _chart_default_font(chart, latin, ea):
    """图表全局字族：chartSpace/c:txPr 的 defRPr 写 latin+ea 双轨
    （中西混排不缺字形；params.font 是唯一事实源）。"""
    f = chart.font
    f.name = latin
    rPr = f._rPr
    for tag in ("a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", ea)


def _chart_area_fill(chart, where, ref, palette, p):
    """图表区/绘图区填充。ref：None=不干预；"none"=透明（a:noFill，页底透出）；
    色值/token=实心。spPr 按 CT 顺序插入（chartSpace 紧随 c:chart；plotArea 末位）。"""
    if ref is None:
        return
    cs = chart._chartSpace
    if where == "chart":
        spPr = cs.find(qn("c:spPr"))
        if spPr is None:
            spPr = cs.makeelement(qn("c:spPr"), {})
            cs.find(qn("c:chart")).addnext(spPr)
    else:
        pa = cs.find(f"{_CN_C}chart/{_CN_C}plotArea")
        if pa is None:
            return
        spPr = pa.find(qn("c:spPr"))
        if spPr is None:
            spPr = pa.makeelement(qn("c:spPr"), {})
            pa.append(spPr)
    for tag in ("a:noFill", "a:solidFill", "a:gradFill"):
        old = spPr.find(qn(tag))
        if old is not None:
            spPr.remove(old)
    if ref == "none":
        spPr.insert(0, spPr.makeelement(qn("a:noFill"), {}))
    else:
        rgb = _resolve_color(ref, palette, p["style"]["fill"])
        sf = spPr.makeelement(qn("a:solidFill"), {})
        sf.append(sf.makeelement(qn("a:srgbClr"),
                                 {"val": "%02X%02X%02X" % (rgb[0], rgb[1], rgb[2])}))
        spPr.insert(0, sf)


def _set_doughnut_hole(chart, size):
    """圆环孔洞：c:doughnutChart/c:holeSize（python-pptx 无 API → 直注 XML；
    CT_DoughnutChart 顺序 holeSize 紧随 firstSliceAng）。"""
    dn = chart._chartSpace.find(
        f"{_CN_C}chart/{_CN_C}plotArea/{_CN_C}doughnutChart")
    if dn is None:
        return
    hs = dn.find(qn("c:holeSize"))
    if hs is None:
        hs = dn.makeelement(qn("c:holeSize"), {})
        fsa = dn.find(qn("c:firstSliceAng"))
        (fsa.addnext(hs) if fsa is not None else dn.append(hs))
    hs.set("val", str(int(size)))


def _chart_marker(series, rgb):
    """折线数据点标记：实心圆点 + 系列色描边（数字大屏的清晰数据点）。"""
    mk = series.marker
    mk.style = XL_MARKER_STYLE.CIRCLE
    mk.size = 6
    mk.format.fill.solid()
    mk.format.fill.fore_color.rgb = rgb
    mk.format.line.color.rgb = rgb
    mk.format.line.width = Pt(0.75)


def _render_chart(sl, e, palette, p, used, errors):
    """chart 元素：python-pptx add_chart（随附 workbook，零 COM）。
    样式 = params.chart 打底 + 元素 style.* 覆盖（同名键）。覆盖面：预设样式 /
    全局字族 / 图例 / 图表区·绘图区填充 / 序列色 / 数据标签（位·形·色）/
    坐标轴（刻度·网格·量程·数字格式）/ 柱间距·重叠 / 折线宽·平滑·点标 / 圆环孔洞。
    图表名 = IR id（物证按名解析关联 chart part）。"""
    rect = e["rect"]
    ctname = e["chart_type"]
    ct = CHART_BY_TYPE.get(ctname)
    if ct is None:
        errors.append(f"{e['id']}: 未知 chart_type {ctname!r}")
        return
    cd = CategoryChartData()
    cd.categories = [str(c) for c in e["categories"]]
    for s in e["series"]:
        cd.add_series(s["name"], [float(v) for v in s["values"]])
    try:
        gf = sl.shapes.add_chart(ct, Inches(rect[0]), Inches(rect[1]),
                                 Inches(rect[2]), Inches(rect[3]), cd)
    except Exception as ex:
        errors.append(f"{e['id']} 图表失败: {ex}")
        return
    gf.name = e["id"]
    chart = gf.chart
    chart.has_title = False          # 标题走 text 元素（排版由 SPEC 掌控）
    cp = p["chart"]
    st = e.get("style") or {}
    txt_default = p["style"]["text_color"]

    def sg(k, dk=None):
        return st[k] if k in st else cp[dk or k]

    # ---- 预设样式 + 全局字族 ----
    if sg("chart_style") is not None:
        try:
            chart.chart_style = int(sg("chart_style"))
        except Exception:
            pass
    _chart_default_font(chart, sg("font_family") or p["font"]["latin"], p["font"]["ea"])

    # ---- 图例 ----
    legend = sg("legend", "legend_pos")
    if legend == "none":
        chart.has_legend = False
    else:
        chart.has_legend = True
        chart.legend.position = LEGEND_POS.get(legend, XL_LEGEND_POSITION.RIGHT)
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(sg("legend_fs"))
        if sg("legend_color"):
            chart.legend.font.color.rgb = _resolve_color(sg("legend_color"), palette, txt_default)

    # ---- 图表区 / 绘图区填充（默认透明 → 母版/页底透出）----
    _chart_area_fill(chart, "chart", sg("chart_fill"), palette, p)
    _chart_area_fill(chart, "plot", sg("plot_fill"), palette, p)

    # ---- 序列色 + 族别造型 ----
    colors = sg("colors")
    plot = chart.plots[0]
    for i, s in enumerate(plot.series):
        rgb = _resolve_color(colors[i % len(colors)], palette,
                             cp["colors"][i % len(cp["colors"])])
        if ctname in CHART_LINE_TYPES:
            s.format.line.color.rgb = rgb
            s.format.line.width = Pt(sg("line_width"))
            s.format.fill.background()
            if sg("smooth"):
                try:
                    s.smooth = True
                except Exception:
                    pass
            if ctname in CHART_MARKER_TYPES or sg("markers"):
                try:
                    _chart_marker(s, rgb)
                except Exception:
                    pass
        else:                               # 柱/条/面积/饼 系列填充
            s.format.fill.solid()
            s.format.fill.fore_color.rgb = rgb

    # ---- 数据标签 ----
    if sg("data_labels"):
        plot.has_data_labels = True
        dl = plot.data_labels
        dl.font.size = Pt(sg("label_fs"))
        dl.font.bold = bool(sg("label_bold"))
        if sg("label_color"):
            dl.font.color.rgb = _resolve_color(sg("label_color"), palette, txt_default)
        dl.number_format = str(sg("label_format"))
        dl.number_format_is_linked = False
        if sg("label_pos") in LABEL_POS:
            try:
                dl.position = LABEL_POS[sg("label_pos")]
            except Exception:
                pass

    # ---- 圆环孔洞 ----
    if ctname in ("doughnut", "doughnut_exploded"):
        try:
            _set_doughnut_hole(chart, sg("donut_hole"))
        except Exception:
            pass

    # ---- 坐标轴（饼/环无轴）----
    if ctname not in CHART_PIE_TYPES:
        cat_ax, val_ax = chart.category_axis, chart.value_axis
        for ax in (cat_ax, val_ax):
            ax.tick_labels.font.size = Pt(sg("tick_fs"))
            if sg("tick_color"):
                ax.tick_labels.font.color.rgb = _resolve_color(sg("tick_color"), palette, txt_default)
        if sg("gridlines"):
            val_ax.has_major_gridlines = True
            gl = val_ax.major_gridlines.format.line
            gl.color.rgb = _resolve_color(sg("gridline_color"), palette, "#E4E9F2")
            gl.width = Pt(0.75)
        else:
            val_ax.has_major_gridlines = False
        if not sg("axis_line"):
            val_ax.format.line.fill.background()
            cat_ax.format.line.fill.background()
        if sg("value_min") is not None:
            val_ax.minimum_scale = float(sg("value_min"))
        if sg("value_max") is not None:
            val_ax.maximum_scale = float(sg("value_max"))
        if sg("value_format"):
            val_ax.tick_labels.number_format = str(sg("value_format"))
            val_ax.tick_labels.number_format_is_linked = False
        if ctname in CHART_BAR_TYPES:
            try:
                plot.gap_width = int(sg("gap_width"))
            except Exception:
                pass
            if sg("overlap") is not None:
                try:
                    plot.overlap = int(sg("overlap"))
                except Exception:
                    pass
    used.add(f"chart_{ctname}")
    return gf


def _render_group(sl, g, palette, p, used):
    x, y, w, h = g["bbox"]
    sp = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                             Inches(w), Inches(h))
    sp.name = g["id"]
    try:
        sp.adjustments[0] = p["style"]["group_radius"]
    except Exception:
        pass
    sp.fill.solid()
    sp.fill.fore_color.rgb = _hex(p["style"]["group_fill"])
    sp.line.color.rgb = _hex(p["style"]["group_border"])
    sp.line.width = Pt(p["style"]["group_line_w"])
    used.add("group_container")


def _render_curve(sl, ln, palette, p, used):
    """freeform polyline 曲线（cylinder 等高弧 / 函数曲线）。

    单位约定（probe 实测）：python-pptx 把局部坐标点 round() 成整数后再 ×scale
    转 EMU——局部单位必须足够细，取整误差才可忽略：此处 1 局部单位 = 1/10000 in，
    scale = 91.44（914400/10000）→ 取整误差 ≤ 0.00005 in（物证 eps=1pt 覆盖）。
    convert_to_shape(Emu(0)) 使局部原点 = slide 原点 → xfrm = 点集 min-max 盒。"""
    pts = ln["pts"]
    S = 10000.0
    fb = sl.shapes.build_freeform(pts[0][0] * S, pts[0][1] * S, 914400 / S)
    shp = (fb.add_line_segments([(x * S, y * S) for x, y in pts[1:]], close=False)
           .convert_to_shape(Emu(0), Emu(0)))
    shp.name = ln["id"]
    shp.fill.background()
    color = ln.get("color") or p["style"]["line_color"]
    if isinstance(color, str) and color in palette:
        color = palette[color]["solid"]
    shp.line.color.rgb = _hex(color)
    shp.line.width = Pt(ln.get("weight") or p["style"]["line_weight"])
    if ln.get("dash"):
        shp.line.dash_style = _DASH[ln["dash"]]
    used.add("curve")


def _render_line(sl, ln, palette, p, used):
    if ln.get("curve"):
        _render_curve(sl, ln, palette, p, used)
        return
    color = ln.get("color") or p["style"]["line_color"]
    if isinstance(color, str) and color in palette:
        color = palette[color]["solid"]
    weight = ln.get("weight") or p["style"]["line_weight"]
    pts = ln.get("pts")
    if pts:
        # orth 4 段折线：逐段 connector，末段箭头
        segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        for i, ((x1, y1), (x2, y2)) in enumerate(segs):
            last = (i == len(segs) - 1)
            c = _add_connector(sl, (x1, y1), (x2, y2), color, weight,
                               arrow=last and ln.get("arrow", True),
                               dash=MSOL.ROUND_DOT if ln.get("way") == "orth" else None)
            c.name = f"{ln['id']}.seg{i}"
        used.add("polyline")
        if ln.get("way") == "orth":
            used.add("dash_emphasis")
    else:
        dsh = _DASH[ln["dash"]] if ln.get("dash") else None
        c = _add_connector(sl, ln["a1"], ln["a2"], color, weight,
                           arrow=ln.get("arrow", True), dash=dsh)
        c.name = ln["id"]
        used.add("edge_connector")


def _render_glue(sl, gl, palette, p, used):
    color = p["style"]["line_color"]
    c = _add_connector(sl, gl["a1"], gl["a2"], color, p["style"]["line_weight"],
                       arrow=True)
    c.name = gl["id"]
    used.add("glue_connector")


def _find_placeholder(sl, ph_info):
    """按 idx（优先）或 name 找已实例化的占位符形状（python-pptx 模型层：
    继承占位符的 idx 是生效值，与编译期 analyzer 的版式 idx 一致）。"""
    idx, name = ph_info.get("idx"), ph_info.get("name")
    for ph in sl.placeholders:
        try:
            pi = ph.placeholder_format.idx
        except Exception:
            continue
        if idx is not None and pi == idx:
            return ph
        if idx is None and name and ph.name == name:
            return ph
    return None


def _render_ph(sl, e, palette, p, used, errors):
    """seed 打底：ph 元素填充模板占位符。模板的占位符样式/对齐/几何全保留，
    只覆写文本（字号来自 autofit 测量结果；段落对齐：显式声明才覆盖）。"""
    ph = _find_placeholder(sl, e.get("ph_info") or {})
    if ph is None:
        errors.append(f"{e['id']}: 占位符未找到（idx={e.get('ph_info', {}).get('idx')}）"
                      "——版式在模板中勾选但占位符未实例化？")
        return
    try:
        tf = ph.text_frame
        tf.clear()                     # 清模板默认提示文本（如 "Click to edit…"）
        para = tf.paragraphs[0]
        ts = e.get("text_style") or {}
        tl = e.get("text_layout") or {}
        fs = tl.get("fs", ts.get("fs", 12))
        al = ts.get("align")
        if al:
            para.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER,
                              "right": PP_ALIGN.RIGHT}.get(al, PP_ALIGN.CENTER)
        r = para.add_run()
        r.text = e.get("text", "")
        r.font.size = Pt(fs)
        role = _title_role(fs, p, ts.get("role"))
        r.font.bold = bool(ts.get("bold", role == "title" and p["font"]["title_bold"]))
        _set_run_fonts(r, p, role)
        r.font.color.rgb = _resolve_color(ts.get("color", p["style"]["text_color"]),
                                          palette, p["style"]["text_color"])
        used.add("template_ph_fill")
    except Exception as ex:
        errors.append(f"{e['id']} 占位符填充失败: {ex}")


_THEME_SLOTS = ("accent1", "accent2", "accent3", "accent4",
                "accent5", "accent6", "dk1", "lt1", "dk2", "lt2")
# meta.theme 角色 → clrScheme 槽：设计语言品牌色进原生 UI（新建形状/图表默认跟随）
_THEME_ROLE_SLOTS = {
    "accent1": "primary", "accent2": "deep", "accent3": "emph",
    "accent4": "panel_line", "accent5": "accent", "accent6": "muted",
    "dk2": "deep", "lt2": "pale",
}


def _inject_theme(palette, out_path, theme=None):
    """theme1.xml clrScheme 槽 ← palette 同名 token + 主题角色映射（品牌色进原生
    UI：新建形状/图表默认/取色器跟随）。只写存在对应 token 的槽；值相同则跳过；
    整包保序重写。theme（Theme dict）在场时把角色色映射到槽。"""
    import shutil
    import zipfile
    slots = {}
    for s in _THEME_SLOTS:
        tok = palette.get(s)
        if tok and tok.get("solid"):
            slots[s] = tok["solid"].lstrip("#").upper()
    if theme:
        for slot, role in _THEME_ROLE_SLOTS.items():
            tok = palette.get(role)
            if tok and tok.get("solid"):
                slots[slot] = tok["solid"].lstrip("#").upper()
    if not slots:
        return
    tmp = out_path + ".t"
    with zipfile.ZipFile(out_path) as zin, \
            zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("ppt/theme/theme") \
                    and item.filename.endswith(".xml"):
                data = _rewrite_theme(data, slots)
            zout.writestr(item, data)
    shutil.move(tmp, out_path)


def _rewrite_theme(data, slots):
    """clrScheme 槽 srgbClr@val 覆写。槽的 srgbClr 缺失（如 sysClr）→ 整体替换为
    单个 srgbClr（CT_ColorScheme 每槽恰一子元素，否则文档损坏）。"""
    root = etree.fromstring(data)
    A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    cs = root.find(f".//{A}clrScheme")
    if cs is None:
        return data
    changed = False
    for slot, val in slots.items():
        el = cs.find(f"{A}{slot}")
        if el is None:
            continue
        srgb = el.find(f"{A}srgbClr")
        if srgb is not None:
            if (srgb.get("val") or "").upper() == val:
                continue
            srgb.set("val", val)
            changed = True
        else:
            for child in list(el):
                el.remove(child)
            etree.SubElement(el, f"{A}srgbClr", {"val": val})
            changed = True
    if not changed:
        return data
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8",
                          standalone=True)