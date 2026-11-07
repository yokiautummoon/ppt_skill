# -*- coding: utf-8 -*-
"""render_guards.py — 渲染层默认规则（无 Office，纯 XML 物证断言）：
  ① 对比度守卫（文字↔填充，仅白/黑两族，同层一致）
  ② 表格单元格文字居中（表头与正文均 ctr）
  ③ 左/右对齐文本块居中于框（marL）
  ④ justify + 首行缩进（algn=just + pPr ind）
由批次 A 演练沉淀（撞色/不居中是那轮三个视觉问题之二）。

用法：win_py -X utf8 -W ignore tests/render_guards.py
退出码：0 = 全过；1 = 有断言失败
"""
import io
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from pptx import Presentation

import params as _P
import render_pptx as RP

FAILS = []


def render_one(elements, framework=None):
    p = _P.resolve({})
    prs = Presentation()
    prs.slide_width, prs.slide_height = 12192000, 6858000    # 13.333 × 7.5 in
    sl = prs.slides.add_slide(prs.slide_layouts[6])
    ir = {"slide": (13.333, 7.5), "elements": elements, "lines": [],
          "glue": [], "groups": [], "com_group": [], "z_max": 20,
          "framework": framework or {}, "notes": None}
    used, errors = set(), []
    RP._render_slide(sl, ir, {}, p, used, errors, page_no=1, prs=prs)
    bio = io.BytesIO()
    prs.save(bio)
    z = zipfile.ZipFile(bio)
    return z.read("ppt/slides/slide1.xml").decode("utf-8"), errors


def check(name, cond, detail):
    if cond:
        print(f"[OK] {name} {detail}")
    else:
        print(f"[FAIL!] {name} {detail}")
        FAILS.append(name)


def run_color_guard():
    """① 深色填充 + 默认字 → 白字；浅色填充 + 默认字 → 深字（不被误伤）。"""
    deep = {"id": "s1", "type": "shape", "kind": "rect",
            "rect": [1.0, 1.0, 2.0, 0.6], "z": 0, "style": {"fill": "#1F2A44"},
            "text": "深底文字", "text_style": {"fs": 14, "align": "center"}}
    light = {"id": "s2", "type": "shape", "kind": "rect",
             "rect": [4.0, 1.0, 2.0, 0.6], "z": 1, "style": {"fill": "#DCE9F7"},
             "text": "浅底文字", "text_style": {"fs": 14, "align": "center"}}
    xml, errs = render_one([deep, light])
    assert not errs, errs
    m1 = re.search(r'name="s1".*?<a:r>.*?<a:solidFill><a:srgbClr val="([0-9A-Fa-f]{6})"',
                   xml, re.S)
    m2 = re.search(r'name="s2".*?<a:r>.*?<a:solidFill><a:srgbClr val="([0-9A-Fa-f]{6})"',
                   xml, re.S)
    check("守卫:深底白字", m1 and m1.group(1) == "FFFFFF",
          f"s1(#1F2A44底)={m1.group(1) if m1 else None}")
    check("守卫:浅底深字", m2 and m2.group(1) == "1F2A44",
          f"s2(#DCE9F7底)={m2.group(1) if m2 else None}")


def run_table_center():
    """② 表格单元格（表头+正文）文字居中。"""
    tb = {"id": "tb1", "type": "table", "rect": [1.0, 1.0, 4.0, 1.2], "z": 0,
          "rows": 3, "cols": 2,
          "data": [["表头1", "表头2"], ["A1", "B1"], ["A2", "B2"]],
          "header": {"fs": 12, "bold": True, "fill": "#DCE9F7"},
          "body": {"fs": 11}, "header_fs": 12, "cell_fs": 11,
          "col_widths": [2.0, 2.0]}
    xml, errs = render_one([tb])
    assert not errs, errs
    n_cells = xml.count("<a:tc>")
    n_ctr = len(re.findall(r'<a:pPr[^>]*algn="ctr"', xml))
    check("表格单元格居中", n_cells == 6 and n_ctr >= 6,
          f"cells={n_cells} algn=ctr={n_ctr}")


def run_marL_block_center():
    """③ 左对齐文本块居中：pPr marL = (框宽-文本实测宽)/2。"""
    te = {"id": "t1", "type": "text", "rect": [1.0, 1.0, 4.0, 0.5], "z": 0,
          "text": "左对齐正文", "text_style": {"fs": 14, "align": "left"},
          "text_layout": {"fs": 14, "max_w": 120.0}}
    xml, errs = render_one([te])
    assert not errs, errs
    m = re.search(r'name="t1".*?<a:pPr[^>]*marL="(\d+)"', xml, re.S)
    # 框宽 4in=288pt，文本 120pt → slack/2=84pt → 84*12700=1066800
    check("marL 块居中", m and m.group(1) == "1066800",
          f"marL={m.group(1) if m else None}（期望 1066800）")


def run_justify_indent():
    """④ justify + 首行缩进两字（indent = 2×fs×12700）。"""
    te = {"id": "t2", "type": "text", "rect": [1.0, 1.0, 6.0, 1.0], "z": 0,
          "text": "自然排列：两端对齐，首行缩进两字。",
          "text_style": {"fs": 14, "align": "justify", "indent_chars": 2},
          "text_layout": {"fs": 14, "max_w": 400.0}}
    xml, errs = render_one([te])
    assert not errs, errs
    m = re.search(r'name="t2".*?<a:pPr[^>]*algn="just"[^>]*indent="(\d+)"', xml, re.S)
    check("justify+首行缩进", m and m.group(1) == str(2 * 14 * 12700),
          f"indent={m.group(1) if m else None}（期望 {2 * 14 * 12700}）")


def main():
    run_color_guard()
    run_table_center()
    run_marL_block_center()
    run_justify_indent()
    if FAILS:
        print("== render_guards:", len(FAILS), "项失败 ==")
        sys.exit(1)
    print("== render_guards：全部通过 ==")


if __name__ == "__main__":
    main()