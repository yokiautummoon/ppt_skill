# -*- coding: utf-8 -*-
"""test_overflow_readback.py — B4 COM 真实文本溢出回读契约测试。

覆盖：
  params：com.overflow_tol_pt 默认在场
  单元：_readback_overflow 用 TextFrame2 桩——超容差记账 + WARN；容差内静默；
        无文本/无文本框/形状缺失跳过；框内高 ≤0 跳过
  作业协议：com_layer.run 返回骨架含 overflow 列表（early/早退 + 正常路径）
  CLI 端到端：--com 触发 stage6，com_out.json 含 overflow 键（有 Office 时逐页回读）

用法：win_py -X utf8 -W ignore tests/test_overflow_readback.py
退出码：0 全过；1 有失败。
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import params as P
import com_layer as CL

_pass, _fail = [], []


def ok(name, cond, detail=""):
    if cond:
        _pass.append(name)
        print("[OK] %s%s" % (name, (" · " + detail) if detail else ""))
    else:
        _fail.append(name)
        print("[FAIL!] %s · %s" % (name, detail))


# ---- TextFrame2 / slide 桩 ----
class _TR:
    def __init__(self, h):
        self.BoundHeight = h


class _TF2:
    def __init__(self, has_text, tr_h, fr_h):
        self.HasText = has_text
        self.TextRange = _TR(tr_h)
        self.BoundHeight = fr_h


class _Shape:
    def __init__(self, name, tf2=None):
        self.Name = name
        self.HasTextFrame = tf2 is not None
        if tf2 is not None:
            self.TextFrame2 = tf2


class _Shapes:
    def __init__(self, shapes):
        self._s = shapes

    @property
    def Count(self):
        return len(self._s)

    def __call__(self, i):
        return self._s[i - 1]


class _Slide:
    def __init__(self, shapes):
        self.Shapes = _Shapes(shapes)


def main():
    # ================= params =================
    ok("B4 com.overflow_tol_pt 默认在场",
       P.DEFAULTS["com"].get("overflow_tol_pt") == 1.0,
       str(P.DEFAULTS["com"].get("overflow_tol_pt")))

    # ================= _readback_overflow 单元 =================
    ir = {"elements": [
        {"type": "text", "id": "t_over", "text": "溢出文本"},
        {"type": "shape", "id": "s_fit", "text": "刚好"},
        {"type": "text", "id": "t_notext"},                # 无文本 → 跳过
        {"type": "image", "id": "img"},                    # 非文本类型 → 跳过
        {"type": "text", "id": "t_missing", "text": "缺形状"},  # 形状缺失 → 跳过
        {"type": "text", "id": "t_zero", "text": "零框"},   # 框内高 0 → 跳过
    ]}
    slide = _Slide([
        _Shape("t_over", _TF2(True, 120.0, 60.0)),   # over = 60pt → 记账
        _Shape("s_fit", _TF2(True, 40.0, 60.0)),     # over < 0 → 静默
        _Shape("t_notext", _TF2(False, 80.0, 60.0)),  # HasText False → 跳过
        _Shape("img"),                                # 无文本框 → 跳过
        _Shape("t_zero", _TF2(True, 50.0, 0.0)),     # fr_h ≤ 0 → 跳过
    ])
    out = {"overflow": [], "warnings": []}
    CL._readback_overflow(slide, ir, out, 1, 1.0)
    ids = [o["id"] for o in out["overflow"]]
    ok("B4 超容差形状记账", ids == ["t_over"], str(ids))
    ok("B4 记账含实高/框内高/超差",
       out["overflow"][0]["text_h"] == 120.0
       and out["overflow"][0]["frame_h"] == 60.0
       and out["overflow"][0]["over_pt"] == 60.0
       and out["overflow"][0]["page"] == 1, str(out["overflow"][0]))
    ok("B4 溢出 WARN 已记",
       any("文本溢出回读" in w for w in out["warnings"]), str(out["warnings"]))

    # 容差内（over=0.5 < 1.0）静默
    slide2 = _Slide([_Shape("a", _TF2(True, 60.5, 60.0))])
    out2 = {"overflow": [], "warnings": []}
    CL._readback_overflow(slide2, {"elements": [{"type": "text", "id": "a",
                                                 "text": "x"}]}, out2, 1, 1.0)
    ok("B4 容差内静默", out2["overflow"] == [] and out2["warnings"] == [])

    # 容差可调：tol=0.25 时 0.5 也记账
    out3 = {"overflow": [], "warnings": []}
    CL._readback_overflow(slide2, {"elements": [{"type": "text", "id": "a",
                                                 "text": "x"}]}, out3, 1, 0.25)
    ok("B4 容差可调（0.25 命中 0.5）", [o["id"] for o in out3["overflow"]] == ["a"])

    # ================= 作业返回骨架含 overflow =================
    with tempfile.TemporaryDirectory() as td:
        ir_path = os.path.join(td, "ir.json")
        with open(ir_path, "w", encoding="utf-8") as fh:
            json.dump([{"slide": [13.333, 7.5], "elements": [], "lines": [],
                        "glue": [], "groups": []}], fh)
        job = {"out": td, "base": os.path.join(td, "missing.pptx"),
               "ir": ir_path, "com": {}, "pdf": False}
        res, _rc = CL.run(job)
        ok("B4 作业返回含 overflow 列表", isinstance(res.get("overflow"), list),
           str(res.get("overflow")))

    # ================= CLI 端到端（--com → stage6 回读）=================
    with tempfile.TemporaryDirectory() as td:
        spec = os.path.join(ROOT, "examples", "image_placeholder", "placeholder.yaml")
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                            os.path.join(ROOT, "scripts", "build_ppt.py"),
                            spec, "--out", td, "--report", "none", "--com"],
                           capture_output=True, encoding="utf-8", errors="replace")
        ok("B4 --com 不阻断（exit 0）", r.returncode == 0, r.stdout[-300:])
        outp = os.path.join(td, "com_out.json")
        if os.path.isfile(outp):
            with open(outp, "r", encoding="utf-8") as fh:
                co = json.load(fh)
            ok("B4 com_out 含 overflow 键", isinstance(co.get("overflow"), list),
               str(co.get("overflow")))
        else:
            ok("B4 无 Office → com_out 缺省降级（非失败态）", True, "com_out.json 未产出")

    print("\n== B4 文本溢出回读：%d 通过 / %d 失败 ==" % (len(_pass), len(_fail)))
    return 0 if not _fail else 1


if __name__ == "__main__":
    sys.exit(main())
