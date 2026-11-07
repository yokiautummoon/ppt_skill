# -*- coding: utf-8 -*-
"""test_images.py — B3 图片占位契约测试（无需 Office）。

覆盖：
  编译期：placeholder 字符串/布尔放行；缺 src 无 placeholder 拒；
          placeholder 空串/类型错拒；diagram+placeholder 拒；caption 类型错拒
  白名单：image 接受 placeholder/caption；未知字段仍拒
  清单：_image_prompts 命中占位与缺文件两类；_write_img_prompts 内容（尺寸/提示词/路径）
  闸门：--strict-images → exit 2（CLI 端到端）
  降级：src 指向不存在文件 → exit 0 + 占位框渲染 + 物证在场（占位框 sp）
  params：images.* 键与默认值在场

用法：win_py -X utf8 -W ignore tests/test_images.py
退出码：0 全过；1 有失败。
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import spec_compile as SC
import spec_validator as SV
import params as P
import build_ppt as BP
import render_pptx as RP
import render_check_xml as RC

_pass, _fail = [], []


def ok(name, cond, detail=""):
    if cond:
        _pass.append(name)
        print("[OK] %s%s" % (name, (" · " + detail) if detail else ""))
    else:
        _fail.append(name)
        print("[FAIL!] %s · %s" % (name, detail))


def _title():
    return {"id": "title", "type": "text", "rect": [0.8, 0.6, 11.7, 0.6],
            "text": "t", "text_style": {"fs": 16, "align": "left"}}


def _build(elements, meta=None):
    m = {"title": "t", "style_guide": "deck", "slide": {"w": 13.333, "h": 7.5},
         "margin": {"l": 0.5, "r": 0.5, "t": 0.5, "b": 0.5}}
    m.update(meta or {})
    return SC.compile_spec({"meta": m, "palette": {"deep": "#1F2A44"},
                            "elements": elements})


def _reject(elements, meta=None):
    try:
        _build(elements, meta)
        return None
    except SC.SpecCompileError as ex:
        return str(ex)


IMG = {"id": "fig", "type": "image", "rect": [0.8, 1.6, 5.0, 3.0]}


def main():
    # ================= 编译期放行/拒绝 =================
    ok("B3 placeholder 字符串放行",
       _reject([_title(), dict(IMG, placeholder="流程示意图，扁平图标风")]) is None)
    ok("B3 placeholder 布尔 + caption 放行",
       _reject([_title(), dict(IMG, placeholder=True, caption="结果对比照")]) is None)
    ok("B3 placeholder 空串拒",
       _reject([_title(), dict(IMG, placeholder="   ")]) is not None)
    ok("B3 placeholder 类型错拒",
       _reject([_title(), dict(IMG, placeholder=12)]) is not None)
    ok("B3 缺 src 无 placeholder 拒",
       _reject([_title(), dict(IMG)]) is not None)
    ok("B3 diagram+placeholder 拒",
       _reject([_title(), {"id": "d", "type": "diagram",
                           "rect": [0.8, 1.6, 5.0, 3.0], "placeholder": True}]) is not None)
    ok("B3 caption 类型错拒",
       _reject([_title(), dict(IMG, placeholder=True, caption=5)]) is not None)

    # ================= 白名单 =================
    comp = _build([_title(), dict(IMG, placeholder="图", caption="c")])
    ok("B3 白名单 placeholder/caption", not SV.validate(comp),
       str(SV.validate(comp)))
    bad = _build([_title(), dict(IMG, placeholder="图", foo=1)])
    ok("B3 白名单 未知字段拒", SV.validate(bad) != [])

    # ================= 缺图清单 =================
    p = P.resolve(None)
    items = BP._image_prompts(p, comp)
    ok("B3 清单命中占位", len(items) == 1 and items[0]["id"] == "fig",
       str(items))
    ok("B3 清单提示词取自 placeholder", items[0]["prompt"] == "图")
    with tempfile.TemporaryDirectory() as td:
        ph = os.path.join(td, "img_prompts.md")
        BP._write_img_prompts(ph, items)
        with open(ph, "r", encoding="utf-8") as f:
            md = f.read()
        ok("B3 清单内容", "fig" in md and "目标尺寸" in md and "5.00 × 3.00 in" in md
           and "未声明" in md, md[:80])

    # ================= src 缺文件降级 =================
    missing = _build([_title(), dict(IMG, src=os.path.join("nope", "x.png"))])
    mitems = BP._image_prompts(p, missing)
    ok("B3 缺文件进清单", len(mitems) == 1 and "nope" in (mitems[0]["src"] or ""),
       str(mitems))
    ok("B3 缺文件提示词兜底", mitems[0]["prompt"] == p["images"]["missing_key"])

    # ================= params 键 =================
    im = P.DEFAULTS["images"]
    ok("B3 params 键完整",
       {"strict", "prompt_file", "placeholder_fill", "placeholder_border",
        "placeholder_fs", "missing_key"} <= set(im), str(sorted(im)))
    ok("B3 strict 默认关", im["strict"] is False)

    # ================= CLI 端到端（strict / 缺文件降级 + 物证）=================
    with tempfile.TemporaryDirectory() as td:
        spec = os.path.join(td, "ph.yaml")
        with open(spec, "w", encoding="utf-8") as f:
            f.write("""meta:
  title: 图片占位
  style_guide: deck
  slide: {w: 13.333, h: 7.5}
  margin: {l: 0.5, t: 0.5, r: 0.5, b: 0.5}
palette: {deep: "#1F2A44"}
elements:
  - id: title
    type: text
    rect: [0.8, 0.6, 11.7, 0.6]
    text: "图片占位"
    text_style: {fs: 16, align: left}
  - id: fig_a
    type: image
    rect: [0.8, 1.6, 5.0, 3.0]
    placeholder: "示意图 A"
  - id: fig_b
    type: image
    rect: [6.5, 1.6, 5.0, 3.0]
    src: "definitely_missing.png"
""")
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                            os.path.join(ROOT, "scripts", "build_ppt.py"),
                            spec, "--out", td, "--report", "none"],
                           capture_output=True, encoding="utf-8", errors="replace")
        ok("B3 缺图默认不阻断（exit 0）", r.returncode == 0, r.stdout[-300:])
        prompts = os.path.join(td, "img_prompts.md")
        ok("B3 清单文件落 out_dir", os.path.isfile(prompts))
        if os.path.isfile(prompts):
            with open(prompts, "r", encoding="utf-8") as f:
                md = f.read()
            ok("B3 清单含两类缺图", "fig_a" in md and "fig_b" in md
               and "definitely_missing.png（当前缺失）" in md, md[:120])
        r2 = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                             os.path.join(ROOT, "scripts", "build_ppt.py"),
                             spec, "--out", td, "--report", "none",
                             "--strict-images"],
                            capture_output=True, encoding="utf-8", errors="replace")
        ok("B3 --strict-images → exit 2", r2.returncode == 2,
           "rc=%d %s" % (r2.returncode, r2.stdout[-200:]))

        # 渲染 + 物证（对缺图 SPEC 重跑一次取 IR 做物证核对）
        rc, *rest = BP._check(spec, td)
        ok("B3 _check 编译通过", rc == 0, str(rest[0] if rc else ""))
        if rc == 0:
            compiled, pages, pg_p, irs, reps = rest
            out = os.path.join(td, "base.pptx")
            used, errs = RP.render(irs, compiled, pg_p, out,
                                  pps=[pg["_p"] for pg in pages])
            ok("B3 占位框渲染不报错", not errs, str(errs))
            ok("B3 组件银行记占位", "image_placeholder" in used, str(used))
            checks = RC.check(out, irs[0], pages[0]["_p"], compiled["palette"])
            bad_ev = [(n, d) for n, ok_, d in checks if not ok_]
            ok("B3 物证全过", not bad_ev, str(bad_ev[:3]))
            ok("B3 物证含占位框", any(n.startswith("占位框") for n, _, _ in checks),
               "checks=%d" % len(checks))

    print("\n== B3 图片占位：%d 通过 / %d 失败 ==" % (len(_pass), len(_fail)))
    return 0 if not _fail else 1


if __name__ == "__main__":
    sys.exit(main())
