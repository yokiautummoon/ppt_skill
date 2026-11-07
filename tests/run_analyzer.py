# -*- coding: utf-8 -*-
"""run_analyzer.py — 风格卡分析器契约测试（只需 python-pptx，无需 Office）。

三层契约：
  A 自产模板契约  python-pptx 造两页模板（10×5 in：Title Slide + Blank）
                  反解析断言：尺寸 10×5、版式名、title 占位符、页映射、主题结构。
  B zip 一致性    analyzer 的 slide/theme 输出 == 直接 lxml 解析 zip 的结果。
  C 损坏容错      垃圾 theme1.xml 的合法包 → pitfalls 记录、theme 降级、不崩，
                  其余项（尺寸/母版/版式）仍可用。

用法：win_py -X utf8 -W ignore tests/run_analyzer.py
退出码：0 全过；1 有失败；2 其他错误。
"""
import os
import re
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from lxml import etree
from pptx import Presentation
from pptx.util import Inches

import template_analyzer as TA

_pass, _fail = [], []


def ok(name, cond, detail=""):
    if cond:
        _pass.append(name)
        print("[OK] %s%s" % (name, (" · " + detail) if detail else ""))
    else:
        _fail.append(name)
        print("[FAIL!] %s · %s" % (name, detail))


def build_two_page(path):
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5)
    s1 = prs.slides.add_slide(prs.slide_layouts[0])   # Title Slide
    s1.shapes.title.text = "T"
    prs.slides.add_slide(prs.slide_layouts[6])        # Blank
    prs.save(path)


def rewrite_zip(src, dst, replace):
    """复制 zip，按名替换部分内容（损坏容错测试用）。"""
    with zipfile.ZipFile(src) as zr:
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zw:
            for item in zr.infolist():
                data = replace.get(item.filename, zr.read(item.filename))
                zw.writestr(item, data)


def main():
    with tempfile.TemporaryDirectory() as td:
        tpl = os.path.join(td, "mini.pptx")
        build_two_page(tpl)
        card = TA.analyze(tpl)

        # ---- A 自产模板契约 ----
        ok("A 尺寸", card["slide"] == {"w": 10.0, "h": 5.0},
           "card=%s" % card["slide"])
        names = [ly["name"] for ly in card["layouts"]]
        ok("A 版式名", "Title Slide" in names and "Blank" in names,
           "共 %d 版式" % len(names))
        tsl = next(ly for ly in card["layouts"] if ly["name"] == "Title Slide")
        phs = tsl["ph"]
        ok("A title 占位符",
           any(p["idx"] == 0 or "title" in p["type"].lower() for p in phs),
           "ph=%s" % [(p["idx"], p["type"]) for p in phs])
        ok("A 页映射", card["pages"] == [{"n": 1, "layout": "Title Slide"},
                                          {"n": 2, "layout": "Blank"}],
           "pages=%s" % card["pages"])
        ok("A 母版", len(card["masters"]) >= 1, "母版 %d" % len(card["masters"]))
        t = card["theme"]
        ok("A 主题结构", bool(t and t["colors"].get("accent1")),
           "accent1=%s" % (t["colors"].get("accent1") if t else "theme=None"))
        hex_ok = bool(t and t["colors"].get("accent1")
                      and re.match(r"^#[0-9A-F]{6}$", t["colors"]["accent1"]))
        ok("A 色归一", hex_ok,
           "accent1=%s" % (t["colors"]["accent1"] if t else None))
        dna = card.get("design_dna") or {}
        ok("A 设计DNA 结构", isinstance(dna.get("pages"), list)
           and len(dna["pages"]) == 2
           and set(("fonts", "sizes", "colors", "shape_mix")) <= set(dna),
           "pages=%d" % len(dna.get("pages") or []))
        ok("A 设计DNA 页统计", dna["pages"][0]["n"] == 1
           and dna["pages"][0]["runs"] >= 1,
           "p1 runs=%s" % (dna["pages"][0]["runs"] if dna.get("pages") else "—"))

        # ---- B zip 一致性 ----
        with zipfile.ZipFile(tpl) as z:
            pr = etree.fromstring(z.read("ppt/presentation.xml"))
            sz = pr.find("{%s}sldSz" % TA.NS_P)
            expect_slide = {"w": round(int(sz.get("cx")) / TA.EMU_IN, 3),
                            "h": round(int(sz.get("cy")) / TA.EMU_IN, 3)}
        ok("B slide 一致", card["slide"] == expect_slide,
           "%s vs %s" % (card["slide"], expect_slide))
        with zipfile.ZipFile(tpl) as z:
            troot = etree.fromstring(z.read("ppt/theme/theme1.xml"))
        acc = troot.find(".//{%s}accent1" % TA.NS_A)
        srgb = acc.find("{%s}srgbClr" % TA.NS_A) if acc is not None else None
        sysc = acc.find("{%s}sysClr" % TA.NS_A) if acc is not None else None
        if srgb is not None:
            expect_c = "#%s" % srgb.get("val").upper()
        elif sysc is not None and sysc.get("lastClr"):
            expect_c = "#%s" % sysc.get("lastClr").upper()
        else:
            expect_c = None
        ok("B theme 一致", expect_c is not None
           and card["theme"]["colors"]["accent1"] == expect_c,
           "expect %s got %s" % (expect_c, card["theme"]["colors"]["accent1"]))

        # ---- C 损坏容错：垃圾 theme1.xml ----
        bad = os.path.join(td, "bad_theme.pptx")
        rewrite_zip(tpl, bad, {"ppt/theme/theme1.xml": b"<oops not xml"})
        try:
            c2 = TA.analyze(bad)
            ok("C 不崩", True)
        except Exception as ex:
            ok("C 不崩", False, "analyze 抛错: %s" % ex)
            return 1
        ok("C theme 降级", c2["theme"] is None
           and any("主题" in p for p in c2["pitfalls"]),
           "pitfalls=%s" % [p[:30] for p in c2["pitfalls"]])
        ok("C 其他项可用", c2["slide"] is not None and c2["layouts"],
           "slide=%s layouts=%d" % (c2["slide"], len(c2["layouts"])))

    print("\n== 风格卡契约：%d 通过 / %d 失败 ==" % (len(_pass), len(_fail)))
    return 0 if not _fail else 1


if __name__ == "__main__":
    sys.exit(main())