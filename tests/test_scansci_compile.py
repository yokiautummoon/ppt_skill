# -*- coding: utf-8 -*-
"""test_scansci_compile.py — 块 1/2 编译期拦截单测：新语法（anchors /
from_anchor / to_anchor / edit_groups）白名单与存在性校验。

用法：win_py -X utf8 tests/test_scansci_compile.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import spec_compile as SC

_fail = []
_pass = []


def _yaml(extra_elems, extra_relations):
    """把元素/关系 dict 列表组装成 SPEC YAML 文本（双引号 JSON 风格序列化，
    与 spec_compile 可解析的 YAML 子集兼容）。"""
    lines = [
        "meta: {title: t, style_guide: flowchart, slide: {w: 13.333, h: 7.5},"
        " margin: {l: 0.5, t: 0.5, r: 0.5, b: 0.5}}",
        "palette: {p: '#1F2A44'}",
    ]
    lines.append("elements:")
    for e in extra_elems:
        lines.append("- " + _d(e))
    lines.append("relations:")
    for r in extra_relations:
        lines.append("  " + r)
    return "\n".join(lines)


def _d(obj):
    """dict → YAML 流式内联（JSON 双引号风格；None/True/False 用 null/true/false）。"""
    import json
    return json.dumps(obj, ensure_ascii=False)


def _compile(extra_elems, extra_relations, expect_raise, name, detail):
    import yaml
    data = yaml.safe_load(_yaml(extra_elems, extra_relations))
    try:
        SC.compile_spec(data)
    except SC.SpecCompileError as ex:
        if expect_raise:
            print(f"[OK] {name} 编译拦截 ✓ · {detail} :: {str(ex)[:90]}")
            _pass.append(name)
        else:
            _fail.append(f"{name}: 误拦（{str(ex)[:120]}）")
            print(f"[FAIL!] {name} 误拦 · {str(ex)[:120]}")
        return
    except Exception as ex:
        # 非 SpecCompileError 的崩溃也视为失败（应报告而非静默）
        _fail.append(f"{name}: 非 SpecCompileError 异常 {type(ex).__name__}（{str(ex)[:100]}）")
        print(f"[FAIL!] {name} 异常 {type(ex).__name__} · {str(ex)[:100]}")
        return
    if expect_raise:
        _fail.append(f"{name}: 漏拦（未抛 SpecCompileError）")
        print(f"[FAIL!] {name} 漏拦 · {detail}")


def base_elems():
    return [
        {"id": "pump", "type": "shape", "kind": "rounded_rect",
         "rect": [1.0, 1.0, 2.0, 1.0], "style": {"fill": "p"},
         "anchors": {"outlet": [1.0, 0.5]}},
        {"id": "reactor", "type": "shape", "kind": "rounded_rect",
         "rect": [5.0, 1.0, 2.0, 1.0], "style": {"fill": "p"},
         "anchors": {"inlet": [0.0, 0.5], "outlet": [1.0, 0.5]}},
    ]


def main():
    # ---- 块 1：具名锚点编译拦截 ----
    # 合法：锚点在 [0..1]² 且有端点元素声明
    _compile(base_elems(),
             ["glue:",
              "  - {from: pump, to: reactor, from_anchor: outlet, to_anchor: inlet}"],
             False, "合法具名锚点", "锚点坐标/引用全合规")

    # 漏拦检查 1：锚点坐标越界
    e = base_elems()
    e[1]["anchors"] = {"inlet": [1.5, 0.5]}
    _compile(e,
             ["glue:",
              "  - {from: pump, to: reactor, to_anchor: inlet}"],
             True, "锚点越界拦截", "inlet x=1.5 超出 [0,1]²")

    # 漏拦检查 2：glue 引用不存在的锚点名（成对声明，先过成对检查再命中名称存在性）
    _compile(base_elems(),
             ["glue:",
              "  - {from: pump, to: reactor, from_anchor: outlet, to_anchor: nosuch}"],
             True, "锚点名缺失拦截", "reactor 无 anchors.nosuch")

    # 漏拦检查 3：端点无 anchors 却引用
    _compile(base_elems(),
             ["glue:",
              "  - {from: pump, to: reactor, from_anchor: outlet}"],
             True, "端点无锚点拦截", "pump 未声明 anchors 却用 from_anchor")

    # 漏拦检查 4：anchors 值非 [x,y] 数值
    e = base_elems()
    e[1]["anchors"] = {"inlet": "oops"}
    _compile(e,
             ["glue:",
              "  - {from: pump, to: reactor, to_anchor: inlet}"],
             True, "锚点值类型拦截", "inlet 非 [nx,ny] 数值对")

    # 漏拦检查 5：from_anchor/to_anchor 单边声明（不变量：具名锚点成对）
    _compile(base_elems(),
             ["glue:",
              "  - {from: pump, to: reactor, from_anchor: outlet}"],
             True, "锚点单边声明拦截", "只有 from_anchor 无 to_anchor")

    # ---- 块 2：edit_groups 编译拦截 ----
    _edit_elems = [
        {"id": "glass", "type": "shape", "kind": "rounded_rect",
         "rect": [1.0, 1.0, 2.0, 1.0], "style": {"fill": "p"}},
        {"id": "frame", "type": "shape", "kind": "rounded_rect",
         "rect": [1.0, 1.0, 2.0, 1.0], "style": {"fill": "p"}},
        {"id": "pump", "type": "shape", "kind": "rounded_rect",
         "rect": [4.0, 1.0, 2.0, 1.0], "style": {"fill": "p"}},
    ]
    # 合法：成员为顶层元素
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {id: window, members: [glass, frame]}"],
             False, "合法编辑组", "成员为顶层元素")
    # 漏拦 1：成员引用不存在元素
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {id: window, members: [glass, nosuch]}"],
             True, "编辑组悬空成员拦截", "nosuch 不在 elements")
    # 漏拦 2：跨组重复成员
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {id: g1, members: [glass, frame]}",
              "  - {id: g2, members: [glass, pump]}"],
             True, "编辑组跨组重复拦截", "glass 分属 g1/g2")
    # 漏拦 3：容器成员（不产形状）
    _compile([{"id": "box", "type": "stack", "rect": [1.0, 1.0, 4.0, 2.0],
               "children": [{"id": "k1", "type": "shape", "kind": "rounded_rect",
                             "width": 1.0, "height": 1.0}]},
              {"id": "a", "type": "shape", "kind": "rounded_rect",
               "rect": [6.0, 1.0, 1.0, 1.0], "style": {"fill": "p"}}],
             ["edit_groups:",
              "  - {id: g, members: [box, a]}"],
             True, "编辑组容器成员拦截", "stack 不产单形状")
    # 漏拦 4：组缺 id 或 members 非列表
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {members: [glass, frame]}"],
             True, "编辑组缺 id 拦截", "无 id")
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {id: g, members: glass}"],
             True, "编辑组 members 非列表拦截", "members 为字符串")

    print(f"---\npass={len(_pass)} fail={len(_fail)}")
    if _fail:
        print("FAILED:", *_fail, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    main()