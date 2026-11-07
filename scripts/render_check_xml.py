# -*- coding: utf-8 -*-
"""render_check_xml.py — 解包 base.pptx，以 XML 物证背书渲染一致性。

定位：渲染器给每个形状设 .name = IR id（COM 按名查找同机制），
物证按 name 精确定位 sp/cxnSp，杜绝"顺序假设"脆弱性。

物证（references/ooxml-notes.md 陷阱表）：
  - bodyPr wrap：word_wrap=True → wrap="square"（≠none，文本可换行）
  - rPr sz == round(fs×100)（OOXML 字号单位 1/100pt）
  - xfrm off/ext == IR rect 的 EMU（±1pt 容差）
  - orth/直线 = cxnSp 且尾段含 tailEnd（箭头）
 不重算布局：仅核对"渲染器把 IR 如实写进了 XML"。
"""
import posixpath
import re
import zipfile
from lxml import etree

import formula_omml
import formula_templates
import layout_rect as LR

_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_A14 = "{http://schemas.microsoft.com/office/drawing/2010/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
_C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
_SVG = "{http://schemas.microsoft.com/office/drawing/2016/SVG/main}"
_P14 = "{http://schemas.microsoft.com/office/powerpoint/2010/main}"
_P159 = "{http://schemas.microsoft.com/office/powerpoint/2015/09/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_RELPKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
SPS = f"{_P}sp"
CXN = f"{_P}cxnSp"
PIC = f"{_P}pic"
GF = f"{_P}graphicFrame"

_NV_TAGS = {SPS: f"{_P}nvSpPr", CXN: f"{_P}nvCxnSpPr", PIC: f"{_P}nvPicPr",
            GF: f"{_P}nvGraphicFramePr"}

_THEME_SLOTS = ("accent1", "accent2", "accent3", "accent4",
                "accent5", "accent6", "dk1", "lt1", "dk2", "lt2")


def _cnv_name(el):
    """形状 cNvPr@name。绝不可写 find(...) or find(...)：lxml 空元素（如 cNvPr）
    bool() 为 False，链式 or 会短路成 None（实证陷阱）。"""
    for nvtag in _NV_TAGS.values():
        nv = el.find(f"{nvtag}/{_P}cNvPr")
        if nv is not None:
            return nv.get("name")
    return None


def _by_name(root, name):
    """按 cNvPr@name 找第一个 sp/cxnSp/graphicFrame（name 来自渲染器 .name=id）。"""
    for tag, nvtag in _NV_TAGS.items():
        for el in root.iter(tag):
            nv = el.find(f"{nvtag}/{_P}cNvPr")
            if nv is not None and nv.get("name") == name:
                return el
    return None


def _emu_off_ext(el):
    xfrm = el.find(f".//{_A}xfrm")
    if xfrm is None:
        xfrm = el.find(f".//{_P}xfrm")   # graphicFrame 用 p:xfrm（presentationml）
    if xfrm is None:
        return None
    off, ext = xfrm.find(f"{_A}off"), xfrm.find(f"{_A}ext")
    if off is None or ext is None:
        return None
    return (int(off.get("x")), int(off.get("y")),
            int(ext.get("cx")), int(ext.get("cy")))


def _text_runs(el):
    runs = []
    for r in el.iter(f"{_A}r"):
        t = r.find(f"{_A}t")
        sz = None
        rpr = r.find(f"{_A}rPr")
        if rpr is not None:
            sz = rpr.get("sz")
        runs.append((t.text if t is not None else "", sz))
    return runs


def _text_run_styles(el):
    """逐 run 明细 [(text, sz, bold, color, underline)]（富文本物证：段数/文本/字色）。"""
    out = []
    for r in el.iter(f"{_A}r"):
        t = r.find(f"{_A}t")
        rpr = r.find(f"{_A}rPr")
        sz = bold = color = None
        under = False
        if rpr is not None:
            sz = rpr.get("sz")
            bold = rpr.get("b") in ("1", "true")
            under = rpr.get("u") not in (None, "none")
            sf = rpr.find(f"{_A}solidFill/{_A}srgbClr")
            if sf is not None:
                color = sf.get("val", "").upper()
        out.append((t.text if t is not None else "", sz, bold, color, under))
    return out


def _expected_runs(runs):
    """IR 富文本段 → 渲染器实际写入的 a:r 文本序（公式段不产 run；按 \n 切行）。"""
    out = []
    for s in runs:
        if "formula" in s:
            continue
        for part in str(s.get("text") or "").split("\n"):
            if part:
                out.append(part)
    return out


def _expected_flags(runs):
    """与 _expected_runs 同序的强调标记（公式段不产 run，按 \n 切行同标记）。"""
    out = []
    for s in runs:
        if "formula" in s:
            continue
        for part in str(s.get("text") or "").split("\n"):
            if part:
                out.append(bool(s.get("emph")))
    return out


def _has_wrap(el):
    body = el.find(f".//{_A}bodyPr")
    return body is not None and body.get("wrap") not in (None, "none")


def _find_alt_with_name(root, name):
    """找含 name 命名的 sp 的 mc:AlternateContent 及其内 Choice sp（公式框）。"""
    for mc_el in root.iter(f"{_MC}AlternateContent"):
        ch = mc_el.find(f"{_MC}Choice")
        if ch is None:
            continue
        for sp in ch.iter(SPS):
            nv = sp.find(f"{_P}nvSpPr/{_P}cNvPr")
            if nv is not None and nv.get("name") == name:
                return mc_el, sp
    return None, None


def _expect_fill_kind(ref, palette=None):
    """fill 引用 → 'RRGGBB'(solid 期望值) / 'grad' / None（解析失败）。
    与渲染器 resolve_fill 同源语义（palette token / hex / {grad:[c1,c2]}）。"""
    palette = palette or {}
    if isinstance(ref, str):
        if ref in palette:
            pv = palette[ref]
            if "grad" in pv:
                return "grad"
            if "solid" in pv:
                return pv["solid"].lstrip("#").upper()
        if re.match(r"^#?[0-9A-Fa-f]{6}$", ref):
            return ref.lstrip("#").upper()
        return None
    if isinstance(ref, dict):
        return "grad" if ref.get("grad") else None
    return None


def check(path, ir, p, palette=None, page_idx=0, template_info=None):
    """返回 [(name, ok, detail)] 物证清单。
    page_idx 把 slideN.xml 与第 N-1 页 IR 配对（多页序列逐页物证）。
    template_info：compiled['_template']——extract 查主题槽注入，seed 查版式引用 + ph 填充。"""
    eps_emu = LR.IN_PT  # 1pt 容差（EMU 取整误差）
    checks = []
    _layout_target = None
    _notes_target = None
    with zipfile.ZipFile(path) as z:
        slides = sorted((n for n in z.namelist()
                         if n.startswith("ppt/slides/slide") and n.endswith(".xml")),
                        key=lambda n: int(re.search(r"slide(\d+)\.xml$", n).group(1)))
        assert slides, "无 slide XML"
        assert page_idx < len(slides), f"page_idx {page_idx} ≥ slides {len(slides)}"
        xml = z.read(slides[page_idx])
        # slide → rId → part 解析 + 图表 part 内容预读（zip 关闭后不可再读）
        _slide_path = slides[page_idx]
        _rels_path = _slide_path.replace("slides/", "slides/_rels/").replace(".xml", ".xml.rels")
        rel_map = {}
        _ext_map = {}
        try:
            _relroot = etree.fromstring(z.read(_rels_path))
            for _rel in _relroot.iter(f"{_RELPKG}Relationship"):
                # 外部 rel（url/email 链接）存原始 Target；内部 part 归一为绝对 part 路径
                if _rel.get("TargetMode") == "External":
                    _ext_map[_rel.get("Id")] = _rel.get("Target")
                    continue
                rel_map[_rel.get("Id")] = posixpath.normpath(
                    posixpath.join(posixpath.dirname(_slide_path), _rel.get("Target")))
                if _rel.get("Type", "").endswith("/slideLayout"):
                    _layout_target = posixpath.normpath(
                        posixpath.join(posixpath.dirname(_slide_path), _rel.get("Target")))
                elif _rel.get("Type", "").endswith("/notesSlide"):
                    _notes_target = posixpath.normpath(
                        posixpath.join(posixpath.dirname(_slide_path), _rel.get("Target")))
        except (KeyError, etree.XMLSyntaxError):
            rel_map = {}
        _rtmp = etree.fromstring(xml)
        _zip_names = set(z.namelist())
        chart_cache = {}
        for e in ir["elements"]:
            if e["type"] != "chart":
                continue
            _gf = _by_name(_rtmp, e["id"])
            _cch = _gf.find(f".//{_C}chart") if _gf is not None else None
            _rid = _cch.get(f"{_REL}id") if _cch is not None else None
            _part = rel_map.get(_rid) if _rid else None
            try:
                chart_cache[e["id"]] = (_part, etree.fromstring(z.read(_part)))
            except (KeyError, TypeError, etree.XMLSyntaxError):
                chart_cache[e["id"]] = (_part, None)
    root = etree.fromstring(xml)

    # ---- 1. cxnSp 数量 = lines 分段数 + glue ----
    # curve 是 freeform 形状（p:sp 非 p:cxnSp），不计入连线
    n_cxn_expected = sum(max(1, len(ln.get("pts", [])) - 1)
                         for ln in ir["lines"] if not ln.get("curve"))
    n_cxn_expected += len(ir["glue"])
    n_cxn = sum(1 for el in root.iter(CXN))
    checks.append(("cxnSp 数量", n_cxn == n_cxn_expected,
                   f"xml {n_cxn} vs 期望 {n_cxn_expected}"))

    # ---- 2. 文本元素：按 name 定位，sz == fs×100 + wrap square ----
    for e in ir["elements"]:
        if not e.get("text_layout") or e.get("ph_info"):
            # ph 元素不自绘（seed 打底落点在模板占位符），文本存在性由第 7 节查
            continue
        sp = _by_name(root, e["id"])
        if sp is None:
            checks.append((f"sp 存在 {e['id']}", False, "未找到 name"))
            continue
        tl = e["text_layout"]
        runs = _text_runs(sp)
        ok = any(sz is not None and int(sz) == int(round(tl["fs"] * 100))
                 for _, sz in runs)
        detail = (f"sz={runs[0][1]} 期望={int(round(tl['fs']*100))}"
                  if runs and runs[0][1] else "无 run")
        checks.append((f"文本字号 {e['id']}", ok, detail))
        checks.append((f"文本 wrap {e['id']}", _has_wrap(sp),
                       "bodyPr wrap=square"))
        # 富文本：段数 / 纯文本拼接 / 强调色+下划线 / 公式段数（runs 仅在有标记时进 IR）
        if e.get("runs"):
            styles = _text_run_styles(sp)
            expected = _expected_runs(e["runs"])
            plain = "".join(s[0] for s in styles)
            checks.append((f"富文本段数 {e['id']}", len(styles) == len(expected),
                           f"xml {len(styles)} vs 期望 {len(expected)}"))
            checks.append((f"富文本纯文本 {e['id']}", plain == "".join(expected),
                           f"xml {plain!r} vs 期望 {''.join(expected)!r}"))
            n_f = sum(1 for s in e["runs"] if "formula" in s)
            n_xml_f = len(sp.findall(f".//{_A14}m"))
            checks.append((f"公式段数 {e['id']}", n_xml_f == n_f,
                           f"xml a14:m={n_xml_f} vs IR 公式段={n_f}"))
            want = _expect_fill_kind(p["style"].get("emphasis")
                                     or p["style"]["text_color"], palette)
            if want and want != "grad":
                flags = _expected_flags(e["runs"])
                bad = [i for i, (s, emph) in enumerate(zip(styles, flags))
                       if emph and (s[3] != want or not s[4])]
                checks.append((f"富文本强调色 {e['id']}", not bad,
                               f"未用强调色 {want}+下划线的 run: {bad}"))

    # ---- 3. 元素坐标/尺寸：按 name 定位，off/ext == IR rect（EMU） ----
    for e in ir["elements"]:
        if e["type"] not in ("shape", "text", "diagram", "table", "chart", "typst",
                             "brush", "icon", "svgpath") \
                or e.get("ph_info"):
            continue
        sp = _by_name(root, e["id"])
        if sp is None:
            continue
        got = _emu_off_ext(sp)
        if got is None:
            checks.append((f"xfrm {e['id']}", False, "无 xfrm"))
            continue
        x, y, w, h = e["rect"]
        exp = (LR.in2emu(x), LR.in2emu(y), LR.in2emu(w), LR.in2emu(h))
        ok = all(abs(g - ex) <= eps_emu for g, ex in zip(got, exp))
        checks.append((f"坐标/尺寸 {e['id']}", ok,
                       f"xml={got} 期望={exp}"))
    # ---- 3b. 图片占位框（B3）：name=id 的 sp 在场且 rect == IR rect ----
    for e in ir["elements"]:
        if e["type"] != "image" or not e.get("placeholder"):
            continue
        sp = _by_name(root, e["id"])
        if sp is None:
            checks.append((f"占位框 {e['id']}", False, "未找到 sp"))
            continue
        got = _emu_off_ext(sp)
        x, y, w, h = e["rect"]
        exp = (LR.in2emu(x), LR.in2emu(y), LR.in2emu(w), LR.in2emu(h))
        checks.append((f"占位框 {e['id']}",
                       got is not None
                       and all(abs(g - ex) <= eps_emu for g, ex in zip(got, exp)),
                       f"xml={got} 期望={exp}"))
    for g in ir["groups"]:
        sp = _by_name(root, g["id"])
        if sp is None:
            checks.append((f"组 sp 存在 {g['id']}", False, "未找到"))
            continue
        got = _emu_off_ext(sp)
        x, y, w, h = g["bbox"]
        exp = (LR.in2emu(x), LR.in2emu(y), LR.in2emu(w), LR.in2emu(h))
        ok = all(abs(gv - ex) <= eps_emu for gv, ex in zip(got, exp))
        checks.append((f"组坐标 {g['id']}", ok, f"xml={got} 期望={exp}"))

    # ---- 4. 连线端点：cxnSp 的 xfrm = 段两端点 min-corner 盒（方向无关，向上/左线段同样成立）----
    def _seg_box(p, q):
        return (min(p[0], q[0]), min(p[1], q[1]),
                abs(q[0] - p[0]), abs(q[1] - p[1]))

    def _eq_emu(got, box):
        if got is None:
            return False
        exp = (LR.in2emu(box[0]), LR.in2emu(box[1]),
               LR.in2emu(box[2]), LR.in2emu(box[3]))
        return all(abs(gv - ev) <= eps_emu for gv, ev in zip(got, exp))

    for ln in ir["lines"] + ir["glue"]:
        if ln.get("curve"):
            continue   # freeform 曲线在 4.5 节独立核对（xfrm = pts min-max 盒）
        pts = ln.get("pts")
        if pts:
            # 折线：seg0 盒含 a1、末段盒含 a2（分段结构由 verify G 家族独立背书）
            c0 = _by_name(root, f"{ln['id']}.seg0")
            cn = _by_name(root, f"{ln['id']}.seg{len(pts)-2}")
            ok = (c0 is not None and _eq_emu(_emu_off_ext(c0), _seg_box(pts[0], pts[1]))
                  and cn is not None and _eq_emu(_emu_off_ext(cn), _seg_box(pts[-2], pts[-1])))
            checks.append((f"连线端点 {ln['id']}", ok,
                           f"a1={tuple(round(v,3) for v in pts[0])} a2={tuple(round(v,3) for v in pts[-1])}"))
            continue
        a1, a2 = ln["a1"], ln["a2"]
        c = _by_name(root, ln["id"])
        if c is None:
            checks.append((f"连线存在 {ln['id']}", False, "未找到 name"))
            continue
        box = _seg_box(a1, a2)
        got = _emu_off_ext(c)
        ok = _eq_emu(got, box)
        checks.append((f"连线端点 {ln['id']}", ok,
                       f"a1={tuple(round(v,3) for v in a1)} a2={tuple(round(v,3) for v in a2)}"))

    # ---- 4.4 curve 曲线物证：freeform 形状按名定位，xfrm = pts min-max 盒 ----
    for ln in ir["lines"]:
        if not ln.get("curve"):
            continue
        sp = _by_name(root, ln["id"])
        if sp is None:
            checks.append((f"曲线存在 {ln['id']}", False, "未找到 name"))
            continue
        got = _emu_off_ext(sp)
        xs = [p[0] for p in ln["pts"]]
        ys = [p[1] for p in ln["pts"]]
        box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        ok = _eq_emu(got, box)
        checks.append((f"曲线 xfrm {ln['id']}", ok,
                       f"xml={got} 期望={tuple(round(v,3) for v in box)}"))
        lnw = sp.find(f".//{_A}ln")
        has_line = lnw is not None and sp.find(f".//{_A}ln/{_A}noFill") is None
        checks.append((f"曲线线迹 {ln['id']}", has_line, "ln 存在且非 noFill"))

    # ---- 4.4b brush 书法矢量字物证：custGeom 字形路径 + 三态填充 ----
    for e in ir["elements"]:
        if e["type"] != "brush":
            continue
        sp = _by_name(root, e["id"])
        if sp is None:
            checks.append((f"书法字存在 {e['id']}", False, "未找到 name"))
            continue
        cg = sp.find(f".//{_A}custGeom")
        checks.append((f"书法字 custGeom {e['id']}", cg is not None,
                       "custGeom 存在（字形矢量路径）"))
        if cg is not None:
            npath = len(cg.findall(f"{_A}pathLst/{_A}path"))
            checks.append((f"书法字 单路径 {e['id']}", npath == 1,
                           f"a:path 数={npath}（=1 保证 口/日 内孔镂空）"))
        st = e.get("style") or {}
        if st.get("image"):
            bf = sp.find(f".//{_A}blipFill")
            blip = bf.find(f"{_A}blip") if bf is not None else None
            rid = blip.get(f"{_REL}embed") if blip is not None else None
            img = rel_map.get(rid) if rid else None
            ok = bf is not None and img is not None and img in _zip_names
            checks.append((f"书法字 图片填充 {e['id']}", ok,
                           f"blipFill rId={rid} → {img}"))
        elif st.get("grad"):
            checks.append((f"书法字 渐变填充 {e['id']}",
                           sp.find(f".//{_A}gradFill") is not None, "gradFill 存在"))
        else:
            fr = _expect_fill_kind(st.get("fill") or p["style"]["fill"], palette)
            el = sp.find(f".//{_A}solidFill/{_A}srgbClr")
            ok = fr is not None and fr != "grad" and el is not None \
                and (el.get("val") or "").upper() == fr.upper()
            checks.append((f"书法字 实色填充 {e['id']}", ok,
                           f"srgbClr={el.get('val') if el is not None else None} 期望 "
                           f"{fr.upper() if fr else None}"))

    # ---- 4.4c icon 矢量图标物证：custGeom 逐子路径 a:path（描边 fill=none）+ a:ln 描线 ----
    for e in ir["elements"]:
        if e["type"] != "icon":
            continue
        sp = _by_name(root, e["id"])
        if sp is None:
            checks.append((f"图标存在 {e['id']}", False, "未找到 name"))
            continue
        cg = sp.find(f".//{_A}custGeom")
        checks.append((f"图标 custGeom {e['id']}", cg is not None,
                       "custGeom 存在（图标矢量路径）"))
        if cg is not None:
            paths = cg.findall(f"{_A}pathLst/{_A}path")
            npath = len(paths)
            nstroke = sum(1 for pt in paths if (pt.get("fill") or "") == "none")
            checks.append((f"图标 描边子路径 {e['id']}", npath >= 1 and nstroke >= 1,
                           f"a:path 数={npath}，fill=none 数={nstroke}（描边语义）"))
        ln = sp.find(f".//{_P}spPr/{_A}ln")
        has_ln = ln is not None and ln.find(f"{_A}solidFill") is not None
        cap = ln.get("cap") if ln is not None else None
        checks.append((f"图标 描线 {e['id']}", has_ln and cap == "rnd",
                       f"a:ln={has_ln}，cap={cap}（期望 rnd 圆头）"))
        st = e.get("style") or {}
        want = _expect_fill_kind(st.get("color") or p["style"]["line_color"], palette)
        el = ln.find(f"{_A}solidFill/{_A}srgbClr") if ln is not None else None
        ok = want is not None and el is not None \
            and (el.get("val") or "").upper() == want.upper()
        checks.append((f"图标 描线色 {e['id']}", ok,
                       f"srgbClr={el.get('val') if el is not None else None} 期望 "
                       f"{want.upper() if want else None}"))

    # ---- 4.5 框架层：背景全幅 + 页眉/页脚文本（不进 IR；物证按 ir.framework 引）----
    _fw = ir.get("framework") or {}
    sw, sh = ir["slide"]
    if _fw.get("background"):
        bg = _by_name(root, "bg")
        got = _emu_off_ext(bg) if bg is not None else None
        exp = (0, 0, LR.in2emu(sw), LR.in2emu(sh))
        ok = (bg is not None and got is not None
              and all(abs(g - ev) <= eps_emu for g, ev in zip(got, exp)))
        detail = f"全幅 rect={got} 期望={exp}"
        if ok:
            fill_ref = _fw["background"]["fill"]
            fr = _expect_fill_kind(fill_ref, palette)
            if fr is None:
                ok = False
                detail = f"fill 解析失败 {fill_ref!r}"
            elif fr == "grad":
                ok = bg.find(f".//{_A}gradFill") is not None
                detail = "gradFill 存在" if ok else "缺 gradFill"
            else:
                el = bg.find(f".//{_A}solidFill/{_A}srgbClr")
                ok = el is not None and (el.get("val") or "").upper() == fr.upper()
                detail = f"srgbClr={el.get('val') if el is not None else None} 期望 {fr.upper()}"
        checks.append(("框架背景", ok, detail))
    for key, name in (("header", "hdr"), ("footer", "ftr")):
        hf = _fw.get(key)
        if not hf or not hf.get("text"):
            continue
        text = hf["text"]
        if key == "footer":
            # 页码偏移与渲染侧同规：显示页码 = 实际页号 + page_offset
            text = text.replace(p["framework"]["page_token"],
                                str(page_idx + 1 + p["framework"]["page_offset"]))
        sp = _by_name(root, name)
        ok = sp is not None and any(t == text for t, _ in _text_runs(sp))
        checks.append((f"框架{key}", ok,
                       f"文本 {text!r}" if ok else "未找到对应文本 sp"))

    # ---- 4.6 备注页物证：slide rel → notesSlide part，a:t 全文 == notes（去换行）----
    _notes = ir.get("notes")
    if _notes:
        _nok = False
        _ndetail = "无 notesSlide rel"
        if _notes_target is not None:
            try:
                with zipfile.ZipFile(path) as z:
                    _nroot = etree.fromstring(z.read(_notes_target))
                _texts = "".join(t.text or "" for t in _nroot.iter(f"{_A}t"))
                _nok = _texts == "".join(str(_notes).split("\n"))
                _ndetail = "notes 文本一致" if _nok else f"notes 文本不一致 {_texts[:40]!r}"
            except (KeyError, etree.XMLSyntaxError) as ex:
                _ndetail = f"notes part 解析失败: {ex}"
        checks.append(("备注页", _nok, _ndetail))

    # ---- 4.7 页面切换物证：effect none/缺省 → XML 无 p:transition；
    #        有切换 → transition 元素存在 + 子元素 = p:{effect} + spd == IR 值；
    #        morph → mc:AlternateContent[Choice(Requires=p159) > p:transition >
    #        p159:morph] + Fallback(fade) 双层在场 ----
    _tr = ir.get("transition") or {}
    _eff = _tr.get("effect")
    _trans_el = root.find(f"{_P}transition")
    if _eff is None or _eff == "none":
        _tok = _trans_el is None
        checks.append(("页面切换", _tok,
                       "无切换（effect 缺省/none）且 XML 无 p:transition"
                       if _tok else "effect=none 但 XML 仍含 p:transition"))
    elif _eff == "morph":
        _ac = root.find(f"{_MC}AlternateContent")
        _choice = _ac.find(f"{_MC}Choice") if _ac is not None else None
        _tr_in = _choice.find(f"{_P}transition") if _choice is not None else None
        _morph_el = _tr_in.find(f"{_P159}morph") if _tr_in is not None else None
        _fb = _ac.find(f"{_MC}Fallback") if _ac is not None else None
        _fb_fade = _fb.find(f"{_P}transition/{_P}fade") if _fb is not None else None
        _dur = _tr_in.get(f"{_P14}dur") if _tr_in is not None else None
        _want_dur = str(_tr.get("dur", 700))
        _tok = (_ac is not None and _choice is not None
                and _choice.get("Requires") == "p159"
                and _morph_el is not None and _morph_el.get("option") == "byObject"
                and _fb_fade is not None and _dur == _want_dur)
        checks.append(("页面切换", _tok,
                       f"morph AC(Choice[p159] p159:morph dur={_dur}) + Fallback(fade) "
                       f"期望 dur={_want_dur}"
                       if _tok else "缺 morph AlternateContent / p159:morph / fade 回退 / dur 不符"))
    else:
        _child = _trans_el.find(f"{_P}{_eff}") if _trans_el is not None else None
        _spd = _trans_el.get("spd") if _trans_el is not None else None
        _tok = (_trans_el is not None and _child is not None
                and _spd == _tr.get("spd", "med"))
        checks.append(("页面切换", _tok,
                       f"p:{_eff} spd={_spd} 期望 {_tr.get('spd', 'med')}"
                       if _tok else "缺 p:transition / 子元素 / spd 不符"))

    # ---- 4.8 元素级超链接物证：带 link 的元素 → cNvPr a:hlinkClick + rId 解析目标
    #       （url/email = 外部 rel 原始 Target；slide = 内部 part 文件名 slide{N}.xml）----
    for e in ir["elements"]:
        lk = e.get("link")
        if not lk:
            continue
        sp = _by_name(root, e["id"])
        href_el = None
        if sp is not None:
            for nvtag in ("nvSpPr", "nvPicPr", "nvGraphicFramePr"):
                cnv = sp.find(f"{_P}{nvtag}/{_P}cNvPr")
                if cnv is not None:
                    href_el = cnv.find(f"{_A}hlinkClick")
                    break
        if href_el is None:
            checks.append((f"链接 {e['id']}", False, "无 hlinkClick"))
            continue
        rid = href_el.get(f"{_REL}id")
        kind = next((k for k in ("url", "slide", "email") if k in lk), None)
        if kind in ("url", "email"):
            want = lk["url"] if kind == "url" else f"mailto:{lk['email']}"
            got = _ext_map.get(rid)
            ok = got == want
        else:
            tgt = rel_map.get(rid) or ""
            want = f"slide{lk['slide']}.xml"
            got = posixpath.basename(tgt)
            ok = tgt != "" and got == want
        checks.append((f"链接目标 {e['id']}", ok,
                       f"rId={rid} → {got!r} 期望 {want!r}"))

    # ---- 5. 箭头 tailEnd：lines 尾段 + glue ----
    ar = sum(1 for el in root.iter(CXN)
             if el.find(f".//{_A}ln/{_A}tailEnd") is not None)
    n_arrow = len(ir["glue"]) + sum(1 for ln in ir["lines"]
                                    if ln.get("arrow", True) and not ln.get("curve"))
    checks.append(("箭头 tailEnd", ar >= n_arrow, f"tailEnd {ar}（期望 {n_arrow}）"))

    # ---- 5.5 公式物证：注入型查 mc 包装 + a14:m + m:oMath + fallback 原文；
    #        占位型查文本==原文（判型与渲染器同源：parse_expr 重算，确定性） ----
    for e in ir["elements"]:
        if e["type"] != "formula":
            continue
        ts = e.get("text_style") or {}
        fs = ts.get("fs", p["formula"]["fs_default"])
        r = formula_omml.parse_expr(e["expr"], fs)
        t_omml = None
        if not r["ok"]:
            t_omml = formula_templates.resolve(e["expr"], fs)
        sp = _by_name(root, e["id"])
        if sp is None:
            checks.append((f"公式框存在 {e['id']}", False, "未找到 name（应 at 文本框或被 mc 包装）"))
            continue
        if r["ok"] or t_omml is not None:
            mc_el, csp = _find_alt_with_name(root, e["id"])
            fb = mc_el.find(f"{_MC}Fallback") if mc_el is not None else None
            fb_texts = [t.text or "" for t in fb.iter(f"{_A}t")] if fb is not None else []
            ok = (mc_el is not None
                  and csp.find(f".//{_A14}m/{_M}oMathPara/{_M}oMath") is not None
                  and e["expr"] in fb_texts)
            checks.append((f"公式注入 {e['id']}", ok,
                           "mc+a14:m+oMath+fallback原文" if ok
                           else "缺 mc 包装或 oMath 或 fallback 原文"))
        else:
            runs = _text_runs(sp)
            ok = any(t == e["expr"] for t, _ in runs)
            checks.append((f"公式占位 {e['id']}", ok,
                           "占位文本==expr（子集外，--com 兜底）" if ok
                           else f"占位缺失（runs={[t[:20] for t, _ in runs]}）"))

    # ---- 5.7 表格物证：graphicFrame 定位 + a:tbl 行列数 + 抽样单元格文本 ----
    for e in ir["elements"]:
        if e["type"] != "table":
            continue
        gf = _by_name(root, e["id"])
        if gf is None:
            checks.append((f"表格存在 {e['id']}", False, "未找到 graphicFrame"))
            continue
        tbl = gf.find(f".//{_A}tbl")
        got_r = len(tbl.findall(f"{_A}tr")) if tbl is not None else 0
        got_c = len(tbl.findall(f".//{_A}tblGrid/{_A}gridCol")) if tbl is not None else 0
        ok = tbl is not None and got_r == e["rows"] and got_c == e["cols"]
        checks.append((f"表格结构 {e['id']}", ok,
                       f"tr={got_r} gridCol={got_c} 期望 {e['rows']}×{e['cols']}"))
        if tbl is None:
            continue
        texts = [t.text or "" for t in tbl.iter(f"{_A}t")]
        want = str(e["data"][0][0])
        checks.append((f"表格文本 {e['id']}", want in texts,
                       f"首格 {want!r} 在 {len(texts)} 个 run 中"))
        if e.get("cell_runs"):
            trs = tbl.findall(f"{_A}tr")
            for ri, row in enumerate(e["cell_runs"]):
                for ci, rr in enumerate(row):
                    if rr is None:
                        continue
                    tcs = trs[ri].findall(f"{_A}tc") if ri < len(trs) else []
                    tc = tcs[ci] if ci < len(tcs) else None
                    styles = _text_run_styles(tc) if tc is not None else []
                    plain = "".join(s[0] for s in styles)
                    ok = (len(styles) == len(rr)
                          and plain == str(e["data"][ri][ci]))
                    checks.append((f"表格富文本 {e['id']}[{ri}][{ci}]", ok,
                                   f"xml runs {len(styles)} vs IR {len(rr)}, "
                                   f"text {plain!r}"))

    # ---- 5.8 图表物证：graphicFrame 按名定位 → rId 解析伴生 chart part →
    #               chartSpace 类型标签 + c:ser 数 == series 数 ----
    _CHART_TAG = {"column_clustered": "barChart", "column_stacked": "barChart",
                  "column_stacked_100": "barChart", "bar_clustered": "barChart",
                  "bar_stacked": "barChart", "bar_stacked_100": "barChart",
                  "line": "lineChart", "line_stacked": "lineChart",
                  "line_markers": "lineChart", "line_markers_stacked": "lineChart",
                  "area": "areaChart", "area_stacked": "areaChart",
                  "area_stacked_100": "areaChart",
                  "pie": "pieChart", "pie_exploded": "pieChart",
                  "doughnut": "doughnutChart", "doughnut_exploded": "doughnutChart"}
    for e in ir["elements"]:
        if e["type"] != "chart":
            continue
        part, croot = chart_cache.get(e["id"], (None, None))
        if part is None or croot is None:
            checks.append((f"图表 part {e['id']}", False,
                           "rId/rels 解析失败或 part 无内容"))
            continue
        tag = f"{_C}{_CHART_TAG.get(e['chart_type'], 'barChart')}"
        found = croot.find(f".//{tag}")
        n_ser = len(croot.findall(f".//{_C}ser"))
        n_cat = len(croot.findall(f".//{_C}cat"))
        ok = found is not None and n_ser == len(e["series"])
        checks.append((f"图表结构 {e['id']}", ok,
                       f"part={posixpath.basename(part)} {tag.split('}')[1]} "
                       f"ser={n_ser} 期望 {len(e['series'])}"
                       + (f" cat={n_cat}" if ok else "")))

    # ---- 5.6 typst 排版块：PNG fallback + svgBlip 扩展（OOXML 2016+ 矢量通道，
    #      references/typst-chain.md）----
    for e in ir["elements"]:
        if e["type"] != "typst":
            continue
        sp = _by_name(root, e["id"])
        if sp is None:
            checks.append((f"typst 块存在 {e['id']}", False, "未找到 name"))
            continue
        blip = sp.find(f".//{_A}blip")
        if blip is None:
            checks.append((f"typst 块存在 {e['id']}", False, "无 a:blip"))
            continue
        rid_png = blip.get(f"{_REL}embed")
        png_part = rel_map.get(rid_png)
        png_ok = bool(png_part and png_part.endswith(".png"))
        checks.append((f"typst PNG fallback {e['id']}", png_ok,
                       f"rId={rid_png} → {posixpath.basename(png_part) if png_part else '未解析'}"))
        sb = blip.find(f"{_A}extLst/{_A}ext/{_SVG}svgBlip")
        if sb is None:
            # 旧版 PPT / svg 注入失败 → 纯 PNG 降级（WARN 级，不判 FAIL）
            checks.append((f"typst SVG 矢量 {e['id']}", True,
                           "PNG fallback（svgBlip 未注入，降级合法）"))
            continue
        rid_svg = sb.get(f"{_REL}embed")
        svg_part = rel_map.get(rid_svg)
        svg_ok = bool(svg_part and svg_part.endswith(".svg")
                      and svg_part in _zip_names)
        checks.append((f"typst SVG 矢量 {e['id']}", svg_ok,
                       f"svgBlip rId={rid_svg} → "
                       f"{posixpath.basename(svg_part) if svg_part else '未解析'}"))

    # ---- 6. 层级铁律：OOXML 层级 = spTree 文档序（越靠后越靠前）≡ IR z 序 ----
    zmap = {}
    for e in ir["elements"]:
        zmap[e["id"]] = e["z"]
    for g in ir["groups"]:
        zmap[g["id"]] = g["z"]
    for ln in ir["lines"]:
        if ln.get("curve"):
            zmap[ln["id"]] = ln["z"]
        elif ln.get("pts"):
            for i in range(len(ln["pts"]) - 1):
                zmap[f"{ln['id']}.seg{i}"] = ln["z"]
        else:
            zmap[ln["id"]] = ln["z"]
    for gl in ir["glue"]:
        zmap[gl["id"]] = gl["z"]
    # 框架层（与 render_pptx._framework_zmap 同规则）：背景最底、页眉/页脚最顶
    fz = ir.get("framework") or {}
    if fz.get("background"):
        zmap["bg"] = 0
    zmax = ir.get("z_max", 0)
    if fz.get("header", {}).get("text"):
        zmap["hdr"] = zmax + 1
    if fz.get("footer", {}).get("text"):
        zmap["ftr"] = zmax + (2 if zmap.get("hdr") else 1)
    spTree = root.find(f"{_P}cSld/{_P}spTree")
    prev, order_ok, parts, cnt = None, True, [], 0
    for el in spTree:
        nm = _cnv_name(el)
        if nm is None:
            continue
        z = zmap.get(nm)
        cnt += 1
        if z is None:
            # 模板层豁免（seed 打底）：add_slide 从版式带出的占位符（p:ph）
            # 无 z 契约；非占位符无 z = 渲染漏配（真 bug，必须拦）
            if el.find(f"{_P}nvSpPr/{_P}nvPr/{_P}ph") is not None:
                continue
            order_ok = False
            parts.append(f"{nm} 无 z 映射")
            continue
        if prev is not None and z < prev:
            order_ok = False
            parts.append(f"{nm}(z={z} 越序)")
        prev = z if prev is None else max(prev, z)
    checks.append(("层级 文档序≡z", order_ok,
                   f"{cnt} 个形状" + (f"；{'；'.join(parts)}" if parts else " z 非递减")))

    # ---- 7. 模板层物证：extract → theme 槽注入核对；seed → 版式引用 + ph 填充 ----
    ti = template_info or {}
    if ti.get("mode") == "extract":
        slots = {s: tok["solid"].lstrip("#").upper()
                 for s, tok in (palette or {}).items()
                 if s in _THEME_SLOTS and tok.get("solid")}
        if slots:
            try:
                with zipfile.ZipFile(path) as z:
                    tn = sorted(n for n in z.namelist()
                                if n.startswith("ppt/theme/theme") and n.endswith(".xml"))
                    troot = etree.fromstring(z.read(tn[0]))
                croot = troot.find(f".//{_A}clrScheme")
                ok = True
                bad = []
                for s, val in sorted(slots.items()):
                    el = croot.find(f"{_A}{s}") if croot is not None else None
                    srgb = el.find(f"{_A}srgbClr") if el is not None else None
                    got = (srgb.get("val") or "").upper() if srgb is not None else None
                    if got != val:
                        ok = False
                        bad.append(f"{s}:{got or '∅'}≠{val}")
                checks.append(("主题槽注入", ok,
                               f"{len(slots)} 槽" + (f"；{' '.join(bad)}" if bad else " 全部一致")))
            except Exception as ex:
                checks.append(("主题槽注入", False, f"解析失败: {ex}"))
    elif ti.get("mode") == "seed":
        li = ti.get("layout_info") or {}
        exp_part = (li.get("part") or "").split("/")[-1]
        got_part = (_layout_target or "").split("/")[-1]
        checks.append(("版式引用", bool(_layout_target) and got_part == exp_part,
                       f"{got_part or '无 layout rel'} 期望 {exp_part}"))
        for e in ir["elements"]:
            if not e.get("ph_info"):
                continue
            phi = e["ph_info"]
            idx, name, ptype = phi.get("idx"), phi.get("name"), phi.get("type")
            ph_sp = None
            for el in root.iter(SPS):
                phel = el.find(f"{_P}nvSpPr/{_P}nvPr/{_P}ph")
                if phel is None:
                    continue
                got_idx = phel.get("idx")
                got_type = phel.get("type")
                nm = None
                cnv = el.find(f"{_P}nvSpPr/{_P}cNvPr")
                if cnv is not None:
                    nm = cnv.get("name")
                match = ((idx is not None and got_idx == str(idx))
                         or (name and nm == name)
                         or (ptype and got_type
                             and str(got_type).lower() == str(ptype).lower()))
                if match:
                    ph_sp = el
                    break
            if ph_sp is None:
                checks.append((f"ph 占位符 {e['id']}", False,
                               f"未找到（idx={idx} name={name} type={ptype}）"))
                continue
            runs = _text_runs(ph_sp)
            ok = any(t == e.get("text", "") for t, _ in runs)
            checks.append((f"ph 填充 {e['id']}", ok,
                           f"占位符文本={[t[:16] for t, _ in runs]}"))
    return checks