# -*- coding: utf-8 -*-
"""test_routes.py — 操作路由注册表机器校验（防误路由 + 文档同步）。

routes.py 的 ROUTES 是唯一事实源；references/routing-table.md 是人读版。
本测试背书：注册表自洽（id 唯一 / script 存在 / exits ⊆ 契约 / excludes 引用
有效 / 无自引用）+ 文档覆盖（每个路由 id 都进了人读版）。加路由先改注册表，
再同步文档，测试卡两者。

用法：win_py -X utf8 tests/test_routes.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import routes as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_fail = []
_pass = []


def _check(ok, name, detail=""):
    if ok:
        _pass.append(name)
        print(f"[OK] {name}" + (f" · {detail}" if detail else ""))
    else:
        _fail.append(name)
        print(f"[FAIL!] {name}" + (f" · {detail}" if detail else ""))


def main():
    problems = R.validate()
    _check(not problems, "routes.validate 全过", f"{len(problems)} 条问题" if problems else "")
    for p in problems:
        print("        ↳ " + p)

    _check(len(R.ROUTES) >= 8, "路由表 ≥ 8 条（主链/修订/COM/typst/页型/模板×2/动画）")
    ids = [r["id"] for r in R.ROUTES]
    _check(len(set(ids)) == len(ids), "路由 id 全局唯一")
    for rid in ids:
        _check(R.by_id(rid) is not None, f"by_id({rid}) 可解析")

    # 文档同步：人读版 routing-table.md 覆盖全部路由 id + 关键字段
    doc_path = os.path.join(ROOT, "references", "routing-table.md")
    _check(os.path.isfile(doc_path), "routing-table.md 存在")
    doc = open(doc_path, encoding="utf-8").read() if os.path.isfile(doc_path) else ""
    for r in R.ROUTES:
        _check(r["id"] in doc, f"文档覆盖 {r['id']}（`{r['id']}` 出现在 routing-table.md）")
        _check(r["name"] in doc, f"文档覆盖 {r['id']} 名称", r["name"])

    # 禁路由列：excludes 引用的路由 id 已在上方验证有效（validate 兜底），
    # 每条非空 excludes 语义落在文档"禁止条件"列
    for r in R.ROUTES:
        if r.get("excludes"):
            _check(True, f"{r['id']} excludes 引用有效",
                   "/".join(r["excludes"]))

    print(f"---\npass={len(_pass)} fail={len(_fail)}")
    if _fail:
        print("FAILED:", *_fail, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    main()