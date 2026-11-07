# -*- coding: utf-8 -*-
"""template_analyzer.py — 模板风格卡（stylecard）：只读分析模板 / 成品 .pptx。

母版版式能力的「提炼」侧：不做任何视觉判断，只爬梳模板里可机器阅读的
事实，产出 stylecard.json（机器用：extract 注入 / agent 决策）与
stylecard.md（人读报告）。安全边界：零写入模板、零 COM、零渲染模型改动。

提取事实：
  slide   页面尺寸（presentation.xml sldSz，EMU → 英寸）
  theme   主题色 accent1..6 / bg1,2 / tx1,2（srgbClr 归一为 #RRGGBB，
          sysClr 取 lastClr 同样归一）+ 字族 major/minor 的 latin + ea
          （→ params 字族双轨的原料）
  masters 母版列表：part 名、占位符几何、背景形态（solid/grad/pic/inherit）
  layouts 版式列表：名称、所属母版、占位符几何、背景形态
  pages   成品 deck 场景：逐页实际引用的版式名（模仿输入是"心仪 deck"时用）
  pitfalls 容错项（损坏 part / 图片背景 / 多主题 …），不阻断收卡

CLI：win_py scripts/template_analyzer.py <template.pptx> [--out DIR]
退出码：0 收卡成功（含容错项）；1 IO/参数；2 结构级失败（包不可读）。
"""
import argparse
import json
import os
import zipfile

from lxml import etree

try:
    from pptx import Presentation
except Exception:                       # pragma: no cover
    Presentation = None

EMU_IN = 914400.0

NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


# ---------------------------------------------------------------- 基础工具


def _f(tag):
    """ns 限定名查找（当前用的是 presentationml / drawingml 两域）。"""
    return "{%s}%s" % (NS_P if tag.startswith("p:") else NS_A, tag.split(":")[1])


def _inh(emu):
    """EMU → 英寸（3 位小数）。"""
    return round(emu / EMU_IN, 3) if emu is not None else None


def _color(el):
    """a:srgbClr / a:sysClr 子元素 → '#RRGGBB' 字符串；无法归一 → dict/None。"""
    if el is None:
        return None
    srgb = el.find(_f("a:srgbClr"))
    if srgb is not None:
        v = srgb.get("val")
        return "#%s" % v.upper() if v else None
    sysc = el.find(_f("a:sysClr"))
    if sysc is not None:
        lc = sysc.get("lastClr")
        if lc:
            return "#%s" % lc.upper()
        return {"type": "sysClr", "val": sysc.get("val")}
    return None


def _rels_map(rels_bytes):
    """rels XML → {rId: (Type, Target)}。"""
    out = {}
    if not rels_bytes:
        return out
    root = etree.fromstring(rels_bytes)
    for rel in root.findall("{%s}Relationship" % NS_R):
        out[rel.get("Id")] = (rel.get("Type"), rel.get("Target"))
    return out


def _bg_info(xml_bytes, rels, pitfalls):
    """p:cSld > p:bg → 背景形态 dict。bgRef / 无 bg = 继承母版。"""
    try:
        root = etree.fromstring(xml_bytes)
        cSld = root.find(_f("p:cSld"))
        bg = cSld.find(_f("p:bg")) if cSld is not None else None
        if bg is None:
            return {"kind": "inherit"}
        bgPr = bg.find(_f("p:bgPr"))
        if bgPr is None:
            return {"kind": "inherit"}          # bgRef：引用母版 styleRef
        fill = bgPr[0] if len(bgPr) else None
        if fill is None:
            return {"kind": "none"}
        tag = etree.QName(fill).localname
        if tag == "solidFill":
            return {"kind": "solid", "color": _color(fill)}
        if tag == "gradFill":
            cols = [_color(gs) for gs in fill.findall(_f("a:gs"))
                    if _color(gs) is not None]
            return {"kind": "grad", "colors": cols}
        if tag == "blipFill":
            blip = fill.find(_f("a:blip"))
            rid = blip.get("{%s}embed" % NS_R) if blip is not None else None
            target = rels.get(rid, (None, None))[1] if rid else None
            media = os.path.basename(target) if target else None
            pitfalls.append("图片背景（blipFill%s）——提炼仅记占位，不做裁图" %
                            (": %s" % media if media else ""))
            return {"kind": "pic", "media": media}
        if tag == "pattFill":
            return {"kind": "pattern"}
        if tag == "noFill":
            return {"kind": "none"}
        return {"kind": tag}
    except Exception as ex:
        pitfalls.append("背景解析失败: %s" % ex)
        return {"kind": "unknown"}


def _ph_list(placeholders, pitfalls):
    """python-pptx placeholders → [{idx, type, name, rect}]；无几何的记 None。"""
    out = []
    for ph in placeholders:
        try:
            pf = ph.placeholder_format
            rect = None
            if ph.left is not None:
                rect = [_inh(ph.left), _inh(ph.top), _inh(ph.width), _inh(ph.height)]
            out.append({"idx": pf.idx, "type": str(pf.type), "name": ph.name,
                        "rect": rect})
        except Exception as ex:
            pitfalls.append("占位符解析失败: %s" % ex)
    return out


def _theme_info(zparts, pitfalls):
    """zip 里 ppt/theme/themeN.xml → {colors, fonts}。解析失败 → None + pitfalls。"""
    names = sorted(n for n in zparts if n.startswith("ppt/theme/theme") and n.endswith(".xml"))
    if not names:
        pitfalls.append("无主题 part（ppt/theme/theme1.xml 缺失）")
        return None
    if len(names) > 1:
        pitfalls.append("多主题 part（%d 个，取 %s）" % (len(names), names[0]))
    try:
        root = etree.fromstring(zparts[names[0]])
        te = root.find(_f("a:themeElements"))
        info = {"colors": {}, "fonts": {}}
        cs = te.find(_f("a:clrScheme")) if te is not None else None
        # clrScheme 色槽 = XML 实际名：dk1/lt1（深/浅 1，语义 ≈ 文本/背景基色）
        # + dk2/lt2（语义 ≈ 强调底/浅底）+ accent1..6
        for key in ("dk1", "lt1", "dk2", "lt2",
                    "accent1", "accent2", "accent3", "accent4",
                    "accent5", "accent6"):
            if cs is not None:
                info["colors"][key] = _color(cs.find(_f("a:" + key)))
        fs = te.find(_f("a:fontScheme")) if te is not None else None
        for role in ("majorFont", "minorFont"):
            rn = fs.find(_f("a:" + role)) if fs is not None else None
            if rn is None:
                continue
            for tag, key in (("latin", "latin"), ("ea", "ea")):
                el = rn.find(_f("a:" + tag))
                val = el.get("typeface") if el is not None else None
                if val:
                    info["fonts"]["%s_%s" % (role[:-4], key)] = val
        return info
    except Exception as ex:
        pitfalls.append("主题解析失败: %s" % ex)
        return None


# ---------------------------------------------------------------- 设计 DNA


def _top(counter, n=8):
    """Counter → [{"key": K, "count": N}]（按数量降序，稳定取前 n）。"""
    return [{"key": k, "count": v}
            for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))[:n]]


def _design_dna(zparts, pitfalls):
    """成品 deck 的设计 DNA：逐页统计字号/字族/文字色/形状构成。

    只读 DrawingML：a:rPr（sz/b/solidFill/latin/ea）与 p:sp 的
    a:prstGeom@prst。用于模仿既有 deck 的观感（stylecard 消费），不做审美
    判断。纯模板（无 slide）→ 空统计，不报错。"""
    import re
    from collections import Counter
    slide_parts = sorted(
        (n for n in zparts if re.match(r"ppt/slides/slide\d+\.xml$", n)),
        key=lambda n: int(re.search(r"slide(\d+)\.xml$", n).group(1)))
    dna = {"pages": [], "fonts": {"latin": [], "ea": []},
           "sizes": [], "colors": [], "shape_mix": [],
           "pages_with_picture": 0, "size_range": None}
    agg_sz, agg_col, agg_prst = Counter(), Counter(), Counter()
    agg_latin, agg_ea = Counter(), Counter()
    for pi, sp_name in enumerate(slide_parts):
        try:
            root = etree.fromstring(zparts[sp_name])
        except Exception as ex:
            pitfalls.append("slide %s 解析失败: %s" % (sp_name, ex))
            continue
        sz, col, prst = Counter(), Counter(), Counter()
        latin, ea = Counter(), Counter()
        n_runs = n_bold = 0
        for r in root.iter(_f("a:r")):
            n_runs += 1
            rpr = r.find(_f("a:rPr"))
            if rpr is None:
                continue            # 无 rPr = 完全继承主题/版式（run 仍计数）
            if rpr.get("b") in ("1", "true"):
                n_bold += 1
            szv = rpr.get("sz")
            if szv and szv.isdigit():
                key = round(int(szv) / 100.0, 1)
                sz[key] += 1
                agg_sz[key] += 1
            sf = rpr.find(_f("a:solidFill"))
            c = _color(sf) if sf is not None else None
            if isinstance(c, str):
                col[c] += 1
                agg_col[c] += 1
            for tag, bucket in (("a:latin", latin), ("a:ea", ea)):
                el = rpr.find(_f(tag))
                face = el.get("typeface") if el is not None else None
                if face:
                    bucket[face] += 1
        for sp in root.iter(_f("p:sp")):
            geom = sp.find("%s/%s" % (_f("p:spPr"), _f("a:prstGeom")))
            if geom is not None and geom.get("prst"):
                prst[geom.get("prst")] += 1
                agg_prst[geom.get("prst")] += 1
        for k, v in latin.items():
            agg_latin[k] += v
        for k, v in ea.items():
            agg_ea[k] += v
        n_pic = sum(1 for _ in root.iter(_f("p:pic")))
        n_tbl = sum(1 for _ in root.iter(_f("a:tbl")))
        n_chart = sum(1 for gd in root.iter(_f("a:graphicData"))
                      if (gd.get("uri") or "").endswith("/chart"))
        if n_pic:
            dna["pages_with_picture"] += 1
        dna["pages"].append({
            "n": pi + 1, "runs": n_runs, "bold_runs": n_bold,
            "pictures": n_pic, "tables": n_tbl, "charts": n_chart,
            "sizes": _top(sz, 5), "colors": _top(col, 5),
            "fonts": {"latin": _top(latin, 3), "ea": _top(ea, 3)},
            "shape_mix": _top(prst, 5)})
    dna["sizes"] = _top(agg_sz, 8)
    dna["colors"] = _top(agg_col, 8)
    dna["shape_mix"] = _top(agg_prst, 8)
    dna["fonts"] = {"latin": _top(agg_latin, 8), "ea": _top(agg_ea, 8)}
    if agg_sz:
        dna["size_range"] = [min(agg_sz), max(agg_sz)]
    return dna


# ---------------------------------------------------------------- 主流程


def analyze(path):
    """模板/成品 pptx → stylecard dict。损坏容错：能读多少给多少。"""
    card = {"source": path, "slide": None, "theme": None,
            "masters": [], "layouts": [], "pages": [], "pitfalls": []}
    pitfalls = card["pitfalls"]
    try:
        with zipfile.ZipFile(path) as z:
            zparts = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    except Exception as ex:
        raise ValueError("模板包不可读（非 zip? %s）" % ex)

    # ---- 页面尺寸（presentation.xml sldSz）----
    try:
        pr = etree.fromstring(zparts["ppt/presentation.xml"])
        sz = pr.find(_f("p:sldSz"))
        if sz is not None:
            card["slide"] = {"w": _inh(int(sz.get("cx"))), "h": _inh(int(sz.get("cy")))}
    except Exception as ex:
        pitfalls.append("页面尺寸解析失败: %s" % ex)

    card["theme"] = _theme_info(zparts, pitfalls)
    card["design_dna"] = _design_dna(zparts, pitfalls)

    # ---- python-pptx 结构视图（母版/版式/占位符/页映射）----
    if Presentation is None:
        pitfalls.append("python-pptx 不可用——无母版/版式/页映射信息")
        return card
    try:
        prs = Presentation(path)
    except Exception as ex:
        pitfalls.append("python-pptx 打开失败（关系损坏?）——仅 zip 层信息: %s" % ex)
        return card

    for master in prs.slide_masters:
        pn = str(master.part.partname).lstrip("/")
        rels = _rels_map(zparts.get(pn.replace("slideMasters/", "slideMasters/_rels/")
                                       .replace(".xml", ".xml.rels")))
        bg = _bg_info(zparts.get(pn, b""), rels, pitfalls)
        card["masters"].append({"part": pn, "ph": _ph_list(master.placeholders, pitfalls),
                                "bg": bg})
        for layout in master.slide_layouts:
            lp = str(layout.part.partname).lstrip("/")
            lrels = _rels_map(zparts.get(lp.replace("slideLayouts/", "slideLayouts/_rels/")
                                           .replace(".xml", ".xml.rels")))
            lbg = _bg_info(zparts.get(lp, b""), lrels, pitfalls)
            card["layouts"].append({"name": layout.name, "master": pn, "part": lp,
                                    "ph": _ph_list(layout.placeholders, pitfalls),
                                    "bg": lbg})
    try:
        card["pages"] = [{"n": i + 1, "layout": s.slide_layout.name}
                         for i, s in enumerate(prs.slides)]
        if not card["pages"]:
            pitfalls.append("模板无页面（纯模板场景）——pages 空")
    except Exception as ex:
        pitfalls.append("页映射解析失败: %s" % ex)

    return card


# ---------------------------------------------------------------- 输出


def _md(card):
    L = ["# 风格卡：%s" % os.path.basename(card["source"]), ""]
    s = card["slide"]
    L.append("- 页面尺寸: %s" % ("%.3f × %.3f in" % (s["w"], s["h"]) if s else "—"))
    t = card["theme"]
    if t and t["colors"]:
        row = " · ".join("%s %s" % (k, v) for k, v in sorted(t["colors"].items())
                         if isinstance(v, str))
        L.append("- 主题色: %s" % (row or "全部为系统色（sysClr）"))
    if t and t["fonts"]:
        f = t["fonts"]
        L.append("- 字族: 正文 latin=%s · ea=%s；标题 latin=%s · ea=%s" % (
            f.get("minor_latin", "—"), f.get("minor_ea", "—"),
            f.get("major_latin", "—"), f.get("major_ea", "—")))
    L += ["", "### 母版 / 版式"]
    if not card["masters"]:
        L.append("- （无）")
    for m in card["masters"]:
        L.append("- 母版 %s · 背景 %s · 占位符 %d 项" % (
            m["part"], m["bg"].get("kind"), len(m["ph"])))
        for ph in m["ph"]:
            L.append("  - idx %s %s %s %s" % (
                ph["idx"], ph["type"], ph["name"],
                ph["rect"] if ph["rect"] else "(无几何)"))
    for ly in card["layouts"]:
        L.append("- 版式「%s」（%s）· 背景 %s · 占位符 %d 项" % (
            ly["name"], ly["master"].split("/")[-1], ly["bg"].get("kind"), len(ly["ph"])))
        for ph in ly["ph"]:
            L.append("  - idx %s %s %s %s" % (
                ph["idx"], ph["type"], ph["name"],
                ph["rect"] if ph["rect"] else "(无几何)"))
    if card["pages"]:
        L += ["", "### 页映射（成品 deck 场景）"]
        L.append(", ".join("%d → %s" % (p["n"], p["layout"]) for p in card["pages"]))
    dna = card.get("design_dna") or {}
    if dna.get("pages"):
        L += ["", "### 设计 DNA（成品页面统计）"]
        L.append("- 页面数: %d · 含图页: %d · 字号区间: %s" % (
            len(dna["pages"]), dna["pages_with_picture"],
            ("%s–%spt" % tuple(dna["size_range"])) if dna.get("size_range") else "—"))

        def _mix(items, unit):
            return " · ".join("%s%s×%d" % (i["key"], unit, i["count"]) for i in items)
        if dna["sizes"]:
            L.append("- 字号分布: %s" % _mix(dna["sizes"], "pt"))
        if dna["fonts"]["latin"] or dna["fonts"]["ea"]:
            L.append("- 字族: latin %s · ea %s" % (
                _mix(dna["fonts"]["latin"], "") or "—",
                _mix(dna["fonts"]["ea"], "") or "—"))
        if dna["colors"]:
            L.append("- 文本色: %s" % _mix(dna["colors"], ""))
        if dna["shape_mix"]:
            L.append("- 形状构成: %s" % _mix(dna["shape_mix"], ""))
        bold = sum(p["bold_runs"] for p in dna["pages"])
        runs = sum(p["runs"] for p in dna["pages"])
        if runs:
            L.append("- 加粗 run 占比: %.0f%%（%d/%d）" % (100.0 * bold / runs, bold, runs))
    if card["pitfalls"]:
        L += ["", "### 容错项（不阻断，注意取舍）"]
        for pp in card["pitfalls"]:
            L.append("- %s" % pp)
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="模板风格卡：只读分析模板/成品 pptx → stylecard.json/md")
    ap.add_argument("template", help="模板或成品 .pptx 路径")
    ap.add_argument("--out", default=None, help="输出目录（默认 = 模板所在目录）")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.template):
        print("template_analyzer: 文件不存在: %s" % args.template)
        return 1
    try:
        card = analyze(args.template)
    except ValueError as ex:
        print("template_analyzer: %s" % ex)
        return 2
    out_dir = args.out or os.path.dirname(os.path.abspath(args.template))
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.template))[0]
    jp = os.path.join(out_dir, base + ".stylecard.json")
    mp = os.path.join(out_dir, base + ".stylecard.md")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    with open(mp, "w", encoding="utf-8") as f:
        f.write(_md(card))
    print("stylecard: %s" % jp)
    print("stylecard: %s" % mp)
    if card["pitfalls"]:
        print("容错项 %d 条（见 stylecard.md）" % len(card["pitfalls"]))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())