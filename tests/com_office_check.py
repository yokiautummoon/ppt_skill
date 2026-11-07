# -*- coding: utf-8 -*-
"""com_office_check.py — 需真实 Office 的 COM 自检（可选）。

覆盖 COM 作业路径的产物验收：
  glue  → com_out.glue ok + follow.ok（随动自检）
  group → com_out.groups ok（Range().Group() 组合）
  ole   → com_out.ole ok（AddOLEObject 嵌入 .vsdx，双击可编辑）
  pdf   → --pdf 导出 base.pdf（ExportAsFixedFormat，落盘且非空）

无 Office 环境：win32com ImportError → com_layer 返回 WARN（glue/ole 空）→ 本脚本
判 FAIL 并提示需 Office（在有 Office 的 win 机器上跑才有意义）。

用法：win_py -X utf8 -W ignore tests/com_office_check.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "scripts", "build_ppt.py")
# OLE 用例需要一个真实的 .vsdx；未提供时跳过（不伪造通过）
VSDX = os.environ.get("PPT_OLE_VSDX", "")


def run_spec(name, rel, expect):
    spec = os.path.join(ROOT, rel)
    with tempfile.TemporaryDirectory() as td:
        text = open(spec, encoding="utf-8").read()
        if "__VSDX__" in text:
            # OLE：把夹具占位符换成真实 vsdx 路径后再编译
            tmp_spec = os.path.join(td, "spec.yaml")
            open(tmp_spec, "w", encoding="utf-8").write(
                text.replace("__VSDX__", VSDX))
            spec = tmp_spec
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                            BUILD, spec, "--out", td, "--com", "--com-strict",
                            "--report", "none"], capture_output=True, text=True)
        com_path = os.path.join(td, "com_out.json")
        if r.returncode != 0 or not os.path.exists(com_path):
            print(f"[FAIL] {name}: exit={r.returncode} 无 com_out.json\n{r.stdout[-1500:]}")
            return False
        com = json.load(open(com_path, encoding="utf-8"))

        def _ok(k):
            v = com.get(k)
            if isinstance(v, list):
                return bool(v) and all(g.get("ok") for g in v)
            return bool(v) and v.get("ok")   # follow 是 dict

        ok = all(_ok(k) for k in expect)
        detail = {k: ([g.get("id") for g in com[k]] if isinstance(com.get(k), list)
                      else com.get(k)) for k in expect}
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
        return ok


def run_pdf(name, rel):
    """PDF 导出验收：--pdf（隐含 COM）→ exit 0 + com_out.pdf 落盘且非空。

    base.pdf 非空断言防"PowerPoint 静默产出 0 字节"（ExportAsFixedFormat
    失败多半伴随异常 → warnings，但落盘文件仍可能存在）。"""
    spec = os.path.join(ROOT, rel)
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                            BUILD, spec, "--out", td, "--pdf", "--com-strict",
                            "--report", "none"], capture_output=True, text=True)
        com_path = os.path.join(td, "com_out.json")
        ok = False
        detail = f"exit={r.returncode}"
        if r.returncode == 0 and os.path.exists(com_path):
            com = json.load(open(com_path, encoding="utf-8"))
            pdf = com.get("pdf")
            ok = isinstance(pdf, str) and os.path.isfile(pdf) \
                and os.path.getsize(pdf) > 0
            detail = (f"pdf={'落盘' if ok else pdf!r} warnings="
                      f"{len(com.get('warnings') or [])}")
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            print(r.stdout[-1200:])
        return ok


def run_template_com(name, rel):
    """模板模式（meta.template）COM 验收：exit 0 + warnings 空 + PNG 产出。

    warnings 空 = PowerPoint.Presentations.Open 未报错（0x80070570 文档损坏类
    会写 warnings）；png 是字符串路径且落盘 → 打开+导出全链真实通过。"""
    spec = os.path.join(ROOT, rel)
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                            BUILD, spec, "--out", td, "--com", "--com-strict",
                            "--report", "none"], capture_output=True, text=True)
        com_path = os.path.join(td, "com_out.json")
        ok = False
        detail = f"exit={r.returncode}"
        if r.returncode == 0 and os.path.exists(com_path):
            com = json.load(open(com_path, encoding="utf-8"))
            w = com.get("warnings") or []
            png = com.get("png")
            ok = not w and isinstance(png, str) and os.path.isfile(png)
            detail = f"warnings={len(w)} png={'是' if isinstance(png, str) else png}"
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            print(r.stdout[-1200:])
        return ok


def main():
    results = []
    results.append(run_spec("glue 绑定+随动", "_probe/glue.yaml", ["glue", "follow"]))
    results.append(run_spec("group 组合", "examples/flowchart/chart.yaml", ["groups"]))
    if VSDX and os.path.isfile(VSDX):
        results.append(run_spec("OLE vsdx", "_probe/ole_vsdx.yaml", ["ole"]))
    else:
        print("[SKIP] OLE vsdx: 未设置 PPT_OLE_VSDX（本地 .vsdx 路径）")
    results.append(run_spec("动画 COM 构造", "examples/animation/chart.yaml", ["anim"]))
    results.append(run_template_com("extract COM 真打开", "examples/template/extract.yaml"))
    results.append(run_template_com("seed COM 真打开", "examples/template/seed.yaml"))
    results.append(run_pdf("PDF 导出", "examples/deck/deck.yaml"))
    good = sum(results)
    print(f"\n== COM 自检：{good}/{len(results)} 通过（需 Office）==")
    return 0 if good == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())