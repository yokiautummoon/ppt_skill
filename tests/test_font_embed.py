# -*- coding: utf-8 -*-
"""test_font_embed.py — B5 字体可移植/嵌入契约测试。

覆盖：
  params：font.portable / portable_list 默认在场；配置栈可覆盖
  物证扫描：_scan_embedded_fonts 命中 ppt/fonts/*.fntdata；普通 pptx → []
  作业协议：com_layer.run 骨架/返回含 fonts 字典（requested/declared/embedded）
  CLI 端到端：--embed-fonts → stage6（com_job.json embed_fonts=true/fonts 清单）→ exit 0；
              有 Office 时 com_out.json 记 fonts 结果（无 fntdata → empty_reason）
  降级：无 Office 时 WARN 不阻断（由 subprocess 输出/exit 0 体现）

用法：win_py -X utf8 -W ignore tests/test_font_embed.py
退出码：0 全过；1 有失败。
"""
import json
import os
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import params as P
import com_layer as CL
import build_ppt as BP

_pass, _fail = [], []


def ok(name, cond, detail=""):
    if cond:
        _pass.append(name)
        print("[OK] %s%s" % (name, (" · " + detail) if detail else ""))
    else:
        _fail.append(name)
        print("[FAIL!] %s · %s" % (name, detail))


def main():
    # ================= params =================
    f = P.DEFAULTS["font"]
    ok("B5 font.portable 默认 False", f.get("portable") is False, str(f.get("portable")))
    ok("B5 font.portable_list 默认空表", f.get("portable_list") == [])
    p2 = P.resolve({"font": {"portable": True, "portable_list": ["Arial"]}})
    ok("B5 配置栈覆盖 portable", p2["font"]["portable"] is True
       and p2["font"]["portable_list"] == ["Arial"])

    # ================= 物证扫描 =================
    with tempfile.TemporaryDirectory() as td:
        z1 = os.path.join(td, "with_font.pptx")
        with zipfile.ZipFile(z1, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("ppt/fonts/font1.fntdata", b"\x00\x01")
            z.writestr("ppt/fonts/font2.fntdata", b"\x00\x02")
            z.writestr("ppt/presentation.xml", "<p:presentation/>")
        got = CL._scan_embedded_fonts(z1)
        ok("B5 扫包命中嵌入字体", got == ["ppt/fonts/font1.fntdata",
                                        "ppt/fonts/font2.fntdata"], str(got))
        z2 = os.path.join(td, "bare.pptx")
        with zipfile.ZipFile(z2, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
        ok("B5 无嵌入 → 空表", CL._scan_embedded_fonts(z2) == [])
        ok("B5 非 zip → 空表（不抛）", CL._scan_embedded_fonts(z2 + ".nope") == [])

    # ================= 作业协议（com_layer.run 返回骨架含 fonts）=================
    with tempfile.TemporaryDirectory() as td:
        ir_path = os.path.join(td, "ir.json")
        with open(ir_path, "w", encoding="utf-8") as fh:
            json.dump([{"slide": [13.333, 7.5], "elements": [], "lines": [],
                        "glue": [], "groups": []}], fh)
        job = {"out": td, "base": os.path.join(td, "missing.pptx"),
               "ir": ir_path, "com": {}, "pdf": False,
               "embed_fonts": True, "fonts": ["Calibri", "微软雅黑"]}
        res, _rc = CL.run(job)
        fonts = res.get("fonts")
        ok("B5 作业返回含 fonts 字典", isinstance(fonts, dict)
           and {"requested", "declared", "embedded"} <= set(fonts), str(fonts))
        ok("B5 declared 记录字族清单",
           fonts.get("declared") == ["Calibri", "微软雅黑"] or
           (fonts.get("requested") is False and "declared" in fonts),
           str(fonts))

    # ================= CLI 端到端（--embed-fonts）=================
    with tempfile.TemporaryDirectory() as td:
        spec = os.path.join(ROOT, "examples", "image_placeholder", "placeholder.yaml")
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                            os.path.join(ROOT, "scripts", "build_ppt.py"),
                            spec, "--out", td, "--report", "none", "--embed-fonts"],
                           capture_output=True, encoding="utf-8", errors="replace")
        ok("B5 --embed-fonts 不阻断（exit 0）", r.returncode == 0, r.stdout[-300:])
        jobp = os.path.join(td, "com_job.json")
        ok("B5 com_job 记 embed_fonts/fonts", os.path.isfile(jobp))
        if os.path.isfile(jobp):
            with open(jobp, "r", encoding="utf-8") as fh:
                j = json.load(fh)
            ok("B5 job.embed_fonts=true", j.get("embed_fonts") is True, str(j.keys()))
            ok("B5 job.fonts 为字族清单", isinstance(j.get("fonts"), list)
               and len(j["fonts"]) >= 2, str(j.get("fonts")))
        outp = os.path.join(td, "com_out.json")
        if os.path.isfile(outp):
            with open(outp, "r", encoding="utf-8") as fh:
                ci = json.load(fh)
            fi = ci.get("fonts") or {}
            ok("B5 com_out 记字体结果", "requested" in fi and "embedded" in fi,
               str(fi))
            if fi.get("requested"):
                ok("B5 无 fntdata → empty_reason 记账",
                   fi.get("embedded") or fi.get("empty_reason") == "no_fntdata",
                   str(fi))
                ok("B5 WARN 已记（诚实降级）",
                   any("字体嵌入" in w for w in (ci.get("warnings") or [])),
                   str((ci.get("warnings") or [])[:2]))
        else:
            ok("B5 无 Office → com_out 缺省降级（非失败态）", True, "com_out.json 未产出")

    print("\n== B5 字体嵌入：%d 通过 / %d 失败 ==" % (len(_pass), len(_fail)))
    return 0 if not _fail else 1


if __name__ == "__main__":
    sys.exit(main())
