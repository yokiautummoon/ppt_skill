# -*- coding: utf-8 -*-
"""build_formula_templates.py — 离线构建公式模板库（需 Word）。

对清单里每个表达式跑一次 Word 批量引擎；**只有 Word 真产出 m:nary
结构才收录**（其余 skip 并打印，留给运行时 Word 兜底）。产物 =
scripts/formula_templates.json（随包分发）→ 无 Office 环境直接命中注入。

用法：win_py scripts/build_formula_templates.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import formula_templates  # noqa: E402
import omml_engine  # noqa: E402

# 模板清单：高频"子集外但字符式可达"写法。收录门槛 = Word BuildUp 产出真
# m:nary 且带明确 chr（∑/∏ 实测 OK；\sum{} 花括号式、∫ 不收录——∫ 产 nary
# 但 chr/limLoc 缺省，渲染语义未机器可证，留 Word 兜底；构建对未达门槛的
# 自动 skip 并打印，运行时照常走 Word 兜底/占位降级）。
TEMPLATE_EXPRS = [
    "∑_(i=1)^n x_i",
    "∑_(i=1)^n a_i",
    "∑_(i=0)^n x_i",
    "∑_(k=1)^m x_k",
    "∑_(j=1)^n a_j",
    "∏_(i=1)^n x_i",
    "∏_(i=1)^n a_i",
]


def main():
    results = omml_engine.word_batch_omml(TEMPLATE_EXPRS)
    lib = {}
    for expr, r in zip(TEMPLATE_EXPRS, results):
        omml = r.get("omml", "") if r.get("ok") else ""
        if "<m:nary" in omml:
            # 归一化到 PowerPoint 原生基准（w:rPr → a:rPr + 清 xmlns）后才可注入
            lib[expr] = {"omml": formula_templates.normalize(omml, 18), "fs": 18}
            print(f"[OK]   收录 {expr}（nary）")
        else:
            print(f"[skip] {expr}: {r.get('reason') or 'Word 未产出 m:nary'}")
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "formula_templates.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print(f"== 模板库 {len(lib)}/{len(TEMPLATE_EXPRS)} 条 → {out} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())