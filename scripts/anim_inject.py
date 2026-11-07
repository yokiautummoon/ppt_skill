# -*- coding: utf-8 -*-
"""anim_inject.py — 页级元素动画批量注入（批次—接续编排，幂等，保留 CRLF）。

由批次 A 演练提炼的官方工具：按"每页递进逻辑"给页级元素挂 animation
（effect 引用 animation_recipes 的 35 宏），容器/children 不注入（编译层
对容器挂动画本就会拦截，此处双重防护）。

批次语义（PowerPoint 时序）：
  批首 trigger=after_previous（承接上批，delay=批间隔）；
  批内其余 trigger=with_previous（与批首同刻）——同批同入、批间接续。
  批 0（title）用 with_previous（页首同刻）。

四段划分（默认，可 --xx-sub 覆盖）：
  批 0 title        — id == "title"
  批 1 主体         — title 之外的非小注/非结论元素（image/table/formula/chart
                      用 --implicit-eff，默认快速淡入；其余 --body-eff）
  批 2 小注         — id 含 note/units/fnote/lab/impacts → --note-eff
  批 3 结论         — id 含 take/warn/sum/qa/recall → --concl-eff

用法：
  win_py -X utf8 scripts/anim_inject.py --spec spec.yaml
  win_py -X utf8 scripts/anim_inject.py --spec spec.yaml --seed \
      --layout 空白 --body-delay 0.25 --concl-eff 进入动画_安逸Q弹

默认同时把 meta.template 切到 seed 模式（inherits 母版样式）；
--no-seed 跳过切换（spec 已是 seed 或单形状场景）。
"""
import argparse
import io
import re
import sys

import yaml

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULTS = {
    "title_eff": "\u8fdb\u5165\u52a8\u753b_\u81ea\u4e0a\u6d6e\u5165_\u6539",  # 进入动画_自上浮入_改
    "body_eff": "\u8fdb\u5165\u52a8\u753b_\u81ea\u4e0b\u6d6e\u5165_\u6539",    # 进入动画_自下浮入_改
    "implicit_eff": "\u8fdb\u5165\u52a8\u753b_\u5feb\u901f\u6de1\u5165",      # 进入动画_快速淡入
    "note_eff": "\u8fdb\u5165\u52a8\u753b_\u5feb\u901f\u6de1\u5165",
    "concl_eff": "\u8fdb\u5165\u52a8\u753b_\u5b89\u9038Q\u5f39",              # 进入动画_安逸Q弹
    "note_sub": ("note", "units", "fnote", "lab", "impacts"),
    "concl_sub": ("take", "warn", "sum", "qa", "recall"),
    "delays": {1: 0.25, 2: 0.2, 3: 0.4},
}
IMPLICIT_SP = {"image", "table", "formula", "chart"}
CONT = {"stack", "dock", "graph"}


def classify(e, cfg):
    """返回 (批次, 效果宏)。0=title / 1=主体 / 2=小注 / 3=结论。"""
    i = e.get("id", "")
    if i == "title":
        return 0, cfg["title_eff"]
    if any(s in i for s in cfg["concl_sub"]):
        return 3, cfg["concl_eff"]
    if any(s in i for s in cfg["note_sub"]):
        return 2, cfg["note_eff"]
    t = e.get("type")
    return 1, (cfg["implicit_eff"] if t in IMPLICIT_SP else cfg["body_eff"])


def build_plan(doc, cfg):
    """每页 → [(id, batch, eff, trigger, delay)]；容器与 children 跳过。"""
    plan = {}
    for s in doc["meta"]["slides"]:
        title = s.get("title", "")
        top = [e for e in (s.get("elements") or []) if not e.get("parent")
               and e.get("type") not in CONT]
        by_batch = {}
        for e in top:
            b, eff = classify(e, cfg)
            by_batch.setdefault(b, []).append((e["id"], eff))
        rows = []
        for b in (0, 1, 2, 3):
            grp = by_batch.get(b)
            if not grp:
                continue
            for k, (i, eff) in enumerate(grp):
                if k == 0:
                    tr = "with_previous" if b == 0 else "after_previous"
                    dl = None if b == 0 else cfg["delays"][b]
                else:
                    tr, dl = "with_previous", None
                rows.append((i, b, eff, tr, dl))
        plan[title] = rows
    return plan


def apply_text(txt, plan, crlf):
    """在页级元素 `- id: X` 行之后插 animation 行（跟随元素缩进 +2）。
    页级判定：`- title:` 行重置页边界，页内首个 `- id:` 行的缩进即顶层缩进，
    更深的行（容器 children）跳过。CRLF 文件行内带 \r（split("\n") 保留），
    注入的新行按 crlf 补 \r，join("\n") 原样拼接——行尾风格与源文件一致。"""
    lines = txt.split("\n")
    anim_of = {}
    for rows in plan.values():
        for i, b, eff, tr, dl in rows:
            anim_of[i] = (eff, tr, dl)
    out, inserted, top_indent = [], 0, -1
    for ln in lines:
        out.append(ln)
        if re.match(r"^ *- title: ", ln):
            top_indent = -1          # 页边界：重置顶层缩进
            continue
        m = re.match(r"^( +)- id: ", ln)
        if not m:
            continue
        indent = len(m.group(1))
        if top_indent < 0:
            top_indent = indent      # 页首元素即顶层（build_plan 保证每页有 title）
        if indent != top_indent:
            continue                 # children 缩进更深 → 跳过
        i = ln.strip()[len("- id: "):].strip().strip("\"'").strip("\r")
        if i in anim_of:
            eff, tr, dl = anim_of[i]
            s = "animation: {effect: %s, trigger: %s" % (eff, tr)
            if dl:
                s += ", delay: %0.2f" % dl
            out.append(" " * (indent + 2) + s + "}" + ("\r" if crlf else ""))
            inserted += 1
    return "\n".join(out), inserted


def seed_switch(txt):
    """extract → seed（幂等：已 seed 跳过）。layout 取自 --layout。
    正则定位整块替换，兼容 CRLF/LF 行尾与 keys 列表的项目差异。"""
    pat = re.compile(r"^ {2}template:\s*\r?\n"
                     r"(?:^ {4}[^\r\n]*\r?\n)+?", re.M)
    m = pat.search(txt)
    if m is None:
        raise AssertionError("meta.template 块缺失")
    if "mode: seed" in txt:
        return txt, "已是 seed 模式，跳过"
    src_m = re.search(r"^ {4}src:\s*(\S+)\s*$", m.group(0), re.M)
    src = src_m.group(1) if src_m else "../ppt\u6a21\u677f.pptx"
    new = ("  template:\r\n    src: %s\r\n    mode: seed\r\n"
           "    layout: %s\r\n" % (src, _LAYOUT))
    return txt.replace(m.group(0), new, 1), "extract → seed 已切换（layout: %s）" % _LAYOUT


def main():
    ap = argparse.ArgumentParser(description="页级动画批量注入（批次—接续，幂等，CRLF 保留）")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--seed", action="store_true",
                    help="切换 meta.template 到 seed 模式（继承母版）")
    ap.add_argument("--layout", default="\u7a7a\u767d")
    ap.add_argument("--title-eff", default=DEFAULTS["title_eff"])
    ap.add_argument("--body-eff", default=DEFAULTS["body_eff"])
    ap.add_argument("--implicit-eff", default=DEFAULTS["implicit_eff"])
    ap.add_argument("--note-eff", default=DEFAULTS["note_eff"])
    ap.add_argument("--concl-eff", default=DEFAULTS["concl_eff"])
    ap.add_argument("--note-sub", default=",".join(DEFAULTS["note_sub"]))
    ap.add_argument("--concl-sub", default=",".join(DEFAULTS["concl_sub"]))
    ap.add_argument("--body-delay", type=float, default=DEFAULTS["delays"][1])
    ap.add_argument("--note-delay", type=float, default=DEFAULTS["delays"][2])
    ap.add_argument("--concl-delay", type=float, default=DEFAULTS["delays"][3])
    a = ap.parse_args()
    global _LAYOUT
    _LAYOUT = a.layout
    cfg = {"title_eff": a.title_eff, "body_eff": a.body_eff,
           "implicit_eff": a.implicit_eff, "note_eff": a.note_eff,
           "concl_eff": a.concl_eff, "note_sub": tuple(a.note_sub.split(",")),
           "concl_sub": tuple(a.concl_sub.split(",")),
           "delays": {1: a.body_delay, 2: a.note_delay, 3: a.concl_delay}}

    with io.open(a.spec, encoding="utf-8", newline="") as f:
        txt = f.read()
    crlf = txt.count("\r\n") > txt.count("\n") * 0.5
    doc = yaml.safe_load(txt)
    if a.seed:
        txt, msg = seed_switch(txt)
        print("[seed]", msg)
    # 幂等：清历史注入行 → 重注入
    # 行尾容忍 \r\n（CRLF：$ 前 \r 挡路会失配，须 \r? 显式消费）与任意缩进
    txt = re.sub(r"(?m)^ *animation: \{.*\}\r?(?:\n)?", "", txt)
    doc = yaml.safe_load(txt)
    plan = build_plan(doc, cfg)
    total = sum(len(r) for r in plan.values())
    assert all(any(b == 0 for _, b, _, _, _ in r) for r in plan.values()), \
        "存在无标题批次的页"
    txt2, inserted = apply_text(txt, plan, crlf)
    assert inserted == total, f"注入数 {inserted} ≠ 计划 {total}（页级 id 未命中？）"
    with io.open(a.spec, "w", encoding="utf-8", newline="") as f:
        f.write(txt2)
    print("页数:", len(plan), "| 元素总数:", total, "| 注入:", inserted)
    print("每页动画数:", sorted(len(r) for r in plan.values()))
    print("anim_inject OK（批次—接续编排，seed=%s，CRLF=%s）" % (a.seed, crlf))


if __name__ == "__main__":
    main()