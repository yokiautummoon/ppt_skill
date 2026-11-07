# -*- coding: utf-8 -*-
"""run_template.py — meta.template 两模式（extract/seed）契约测试（无 COM，确定性）。

三层契约：
  A compile 契约   直接 import spec_compile，断言注入语义：
                   extract = slide/palette(frame)/framework/params 的 fill-only 合并
                   （agent 显式声明优先），accent1..6+dk1/lt1/dk2/lt2 注入、
                   framework.background ← 母版 bg、params.font 双轨；
                   seed = 版式选择（按名/索引/默认）+ ph 占位符解析（ph_info）。
  B 渲染契约       CLI 子进程跑 extract/seed 官方案例 → zip 解包断言：
                   seed 剥离模板自带页 → 仅 SPEC 页；ph 文本落在模板占位符；
                   footer {page} 展开；版式引用于 slide rel；
                   extract 渲染后 theme1.xml clrScheme 槽 == palette token。
  C 模板素材契约   防止 gen_brand.py 回归：母版 cSld 恰一 p:bg 且居首
                   （双 bg 曾致 0x80070570 文档损坏）、全 XML part 可解析、
                   theme accent1 品牌蓝、无默认色残留。

用法：win_py -X utf8 -W ignore tests/run_template.py
退出码：0 全过；1 有失败；2 其他错误。
"""
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import yaml
from lxml import etree

import spec_compile as SC

_pass, _fail = [], []


def check(name, ok, detail=""):
    ( _pass if ok else _fail).append(name)
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" —— {detail}" if detail else ""))


def sc_compile(rel_yaml):
    """读 examples/template/<rel>.yaml → compile_spec（base_dir=examples/template）。"""
    base = os.path.join(ROOT, "examples", "template")
    with open(os.path.join(base, rel_yaml), encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SC.compile_spec(data, base_dir=base)


def mk_micro(template=None, elements=None, relations=None, palette=None, ph=None):
    """最小 SPEC dict（compile 负例用）。"""
    return {"meta": {"title": "t", "style_guide": "flowchart",
                     **({"template": template} if template else {})},
            "palette": palette or {},
            "elements": elements or [{"id": "a", "type": "text", "rect": [0.5, 0.5, 3, 1],
                                      "text": "x",
                                      **({"ph": ph} if ph is not None else {})}],
            "relations": relations or {}}


# ================= A. compile 契约 =================

def test_extract_compile():
    c = sc_compile("extract.yaml")
    pal = c["palette"]
    meta = c["meta"]
    exp_slots = {"accent1": "#2D6CDF", "accent2": "#C0504D", "accent3": "#9BBB59",
                 "accent4": "#8064A2", "accent5": "#4BACC6", "accent6": "#F79646",
                 "dk1": "#000000", "lt1": "#FFFFFF", "dk2": "#1F497D", "lt2": "#EEECE1"}
    for s, v in exp_slots.items():
        check(f"extract 注入 palette.{s}", pal.get(s) == {"solid": v},
              f"got={pal.get(s)}")
    check("extract slide 尺寸", meta.get("slide") == {"w": 10.0, "h": 5.0}, str(meta.get("slide")))
    bg = (meta.get("framework") or {}).get("background")
    check("extract 框架背景 ← 母版 bg", bg == {"fill": "#EAF1F9"}, str(bg))
    f = (meta.get("params") or {}).get("font") or {}
    check("extract 字族 latin ← minor", f.get("latin") == "Calibri", str(f.get("latin")))
    check("extract 字族 title ← major", f.get("title_latin") == "Calibri", str(f.get("title_latin")))
    check("extract 字族 ea 无注入轨留默认", f.get("ea") is None, str(f.get("ea")))
    ti = c.get("_template") or {}
    check("extract tinfo mode", ti.get("mode") == "extract" and bool(ti.get("card")),
          str(ti.get("mode")))
    check("extract 注记非空", any("[extract]" in n for n in ti.get("notes", [])), "")


def test_extract_fill_only():
    base = os.path.join(ROOT, "examples", "template")
    with open(os.path.join(base, "extract.yaml"), encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["palette"]["deep"] = "#AABBCC"          # agent 显式声明（应压过 any）
    data["meta"]["framework"] = {"background": {"fill": "#112233"}}
    c = SC.compile_spec(data, base_dir=base)
    check("extract fill-only 显式 token 保留",
          c["palette"].get("deep") == {"solid": "#AABBCC"}, str(c["palette"].get("deep")))
    check("extract fill-only 显式背景不覆盖",
          (c["meta"].get("framework") or {}).get("background") == {"fill": "#112233"},
          str(c["meta"].get("framework", {}).get("background")))
    check("extract fill-only 模板 token 仍注入",
          c["palette"].get("accent1") == {"solid": "#2D6CDF"}, str(c["palette"].get("accent1")))


def test_seed_compile():
    c = sc_compile("seed.yaml")
    ti = c["_template"]
    check("seed 模式", ti.get("mode") == "seed", str(ti.get("mode")))
    li = ti.get("layout_info") or {}
    check("seed 版式按名选中", li.get("name") == "Title Slide", str(li.get("name")))
    check("seed 版式 part 锚定", li.get("part") == "ppt/slideLayouts/slideLayout1.xml",
          str(li.get("part")))
    check("seed slide 尺寸 setdefault 自模板", c["meta"].get("slide") == {"w": 10.0, "h": 5.0},
          str(c["meta"].get("slide")))
    es = c["slides"][0]["elements"]
    by_id = {e["id"]: e for e in es}
    check("seed ph:0 → idx0", (by_id["title"].get("ph_info") or {}).get("idx") == 0,
          str(by_id["title"].get("ph_info")))
    check("seed ph:1 → idx1", (by_id["subtitle"].get("ph_info") or {}).get("idx") == 1,
          str(by_id["subtitle"].get("ph_info")))
    # ph 元素本身不进元素几何校验：rect 保留（仅作文本测量）；render 侧将其跳过
    check("seed ph 元素 rect 仍声明", "rect" in by_id["title"], "")


def test_seed_negatives():
    base = os.path.join(ROOT, "examples", "template")
    tpl = {"src": "brand.pptx", "mode": "seed", "layout": "Title Slide"}

    def expect_err(name, d, frag):
        try:
            SC.compile_spec(d, base_dir=base)
            check(name, False, "未抛错")
        except SC.SpecCompileError as ex:
            check(name, frag in str(ex), str(ex).split("\n")[0])

    d = mk_micro(template=None, ph=0)
    expect_err("负例 无 template 声明 ph", d, "ph 字段仅")
    d3 = mk_micro(template=tpl, ph=0)
    d3["elements"] = [{"id": "a", "type": "shape", "kind": "rounded_rect",
                       "rect": [0.5, 0.5, 3, 1], "ph": 0}]
    expect_err("负例 ph 非 text", d3, "ph 仅支持 text")
    d4 = mk_micro(template=tpl, ph=99)
    expect_err("负例 ph 不存在", d4, "版式无占位符")
    d5 = mk_micro(template=tpl, ph=0,
                  relations={"glue": [{"from": "a", "to": "b"}]},
                  elements=[{"id": "a", "type": "text", "rect": [0.5, 0.5, 3, 1],
                             "text": "x", "ph": 0},
                            {"id": "b", "type": "text", "rect": [2, 2, 3, 1], "text": "y"}])
    expect_err("负例 ph 进 glue", d5, "不走关系")
    d6 = mk_micro(template={"src": "brand.pptx", "mode": "extract", "layout": "x"})
    expect_err("负例 extract 带 layout", d6, "仅 seed")
    d7 = mk_micro(template={"src": "brand.pptx", "mode": "extract", "keys": ["bad"]})
    expect_err("负例 keys 未知键", d7, "未知键")


# ================= B. 渲染契约（CLI + zip） =================

def _build(rel_yaml, td):
    spec = os.path.join(ROOT, rel_yaml)
    r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                        os.path.join(ROOT, "scripts", "build_ppt.py"),
                        spec, "--out", td, "--report", "none"],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, os.path.join(td, "base.pptx")


def test_render_extract():
    with tempfile.TemporaryDirectory() as td:
        rc, out, pptx = _build("examples/template/extract.yaml", td)
        check("extract CLI exit 0", rc == 0, f"rc={rc}")
        if rc != 0:
            print(out[-1500:])
            return
        with zipfile.ZipFile(pptx) as z:
            tn = [n for n in z.namelist() if n.startswith("ppt/theme/theme") and n.endswith(".xml")]
            root = etree.fromstring(z.read(tn[0]))
        A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        acc = root.find(f".//{A}clrScheme/{A}accent1/{A}srgbClr")
        check("extract 主题槽写回 accent1", acc is not None
              and (acc.get("val") or "").upper() == "2D6CDF",
              f"val={acc.get('val') if acc is not None else None}")
        # slide 尺寸 10×5 = 9144000×4572000 EMU
        with zipfile.ZipFile(pptx) as z:
            pr = z.read("ppt/presentation.xml").decode("utf-8")
        m = re.search(r'<p:sldSz cx="(\d+)" cy="(\d+)"', pr)
        check("extract sldSz 10×5", m is not None
              and (int(m.group(1)), int(m.group(2))) == (9144000, 4572000),
              m.groups() if m else "无 sldSz")


def test_render_seed():
    with tempfile.TemporaryDirectory() as td:
        rc, out, pptx = _build("examples/template/seed.yaml", td)
        check("seed CLI exit 0", rc == 0, f"rc={rc}")
        if rc != 0:
            print(out[-1500:])
            return
        with zipfile.ZipFile(pptx) as z:
            slides = sorted(n for n in z.namelist()
                            if n.startswith("ppt/slides/slide") and n.endswith(".xml"))
            check("seed 剥离模板页 → 仅 SPEC 页", len(slides) == 1, f"{len(slides)} slides")
            s1 = z.read(slides[0]).decode("utf-8")
            rels = z.read(slides[0].replace("slides/", "slides/_rels/").replace(".xml", ".xml.rels")).decode("utf-8")
        # footer {page} 展开（framework.footer → "机密 · 第 1 页"）
        check("seed footer 页号展开", "机密 · 第 1 页" in s1, "")
        # ph 填充落点：文本出现在 slide（含模板占位符 run）
        check("seed ph 文本落点", "品牌模板打底页" in s1, "")
        check("seed ph 副标题落点", "标题 / 副标题填入模板占位符" in s1, "")
        # 版式引用：slide rel → slideLayout part == 排版 part
        m = re.search(r'Type="[^"]*slideLayout"[^>]*Target="([^"]+)"', rels)
        got = None
        if m:
            got = posixpath.normpath(posixpath.join(posixpath.dirname(slides[0]), m.group(1)))
        check("seed 版式引用", got == "ppt/slideLayouts/slideLayout1.xml",
              str(got) if got else "无 slideLayout rel")


# ================= C. 模板素材契约（brand.pptx 防回归） =================

def test_brand_integrity():
    path = os.path.join(ROOT, "examples", "template", "brand.pptx")
    with zipfile.ZipFile(path) as z:
        P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
        root = etree.fromstring(z.read("ppt/slideMasters/slideMaster1.xml"))
        cSld = root.find(f"{P}cSld")
        kids = [etree.QName(ch).localname for ch in cSld]
        check("素材 母版 bg 唯一且居首",
              kids.count("bg") == 1 and kids[0] == "bg", str(kids))
        bad = []
        for n in z.namelist():
            if n.endswith(".xml") or n.endswith(".rels"):
                try:
                    etree.fromstring(z.read(n))
                except Exception as ex:
                    bad.append((n, str(ex)))
        check("素材 全 XML part 可解析", not bad, str(bad[:3]))
        tx = z.read("ppt/theme/theme1.xml").decode("utf-8")
        check("素材 theme accent1 品牌蓝", tx.count("2D6CDF") == 1, "")
        check("素材 无默认色残留", "4F81BD" not in tx, "")


def main():
    test_extract_compile()
    test_extract_fill_only()
    test_seed_compile()
    test_seed_negatives()
    test_render_extract()
    test_render_seed()
    test_brand_integrity()
    total = len(_pass) + len(_fail)
    print(f"\n== 模板契约：{len(_pass)}/{total} 通过 ==")
    return 0 if not _fail else 1


if __name__ == "__main__":
    sys.exit(main())