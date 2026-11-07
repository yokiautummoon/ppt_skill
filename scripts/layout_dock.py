# -*- coding: utf-8 -*-
"""layout_dock.py — 容器 dock 递归矩形求解（WinForms dock 语义，泛化 probe_dock.solve）。

children 列表内每项声明 dock: top|bottom|left|right|fill + margin + height|width。
侵占顺序固定：top → bottom → left → right → fill（确定性）。
margin 是装配属性：由父容器按分支收缩后传入本盒；容器/叶不再重复收缩。
"""
import layout_rect as LR

KIND_ORDER = ("top", "bottom", "left", "right", "fill")

def layout_dock(node, box, out):
    out[node["id"]] = {"rect": box, "cfg": node}
    pads = node.get("padding", {})
    x, y, w, h = box
    rem_l = x + pads.get("l", 0)
    rem_r = x + w - pads.get("r", 0)
    rem_t = y + pads.get("t", 0)
    rem_b = y + h - pads.get("b", 0)
    kids = node.get("children", [])
    if not kids:
        return
    # 稳定排序：fill 永远最后，其余按声明顺序相对稳定（同 kind 保持声明序）
    order = []
    for kind in KIND_ORDER:
        order += [k for k in kids if k.get("dock", "fill") == kind]
    for sub in order:
        kind = sub.get("dock", "fill")
        m = sub.get("margin", {})
        ml, mt = m.get("l", 0), m.get("t", 0)
        mr, mb = m.get("r", 0), m.get("b", 0)
        if kind == "top":
            hh = float(sub.get("height", 1.0))
            sub_box = (rem_l + ml, rem_t + mt, (rem_r - rem_l) - ml - mr, hh)
            _solve_sub(sub, sub_box, out)
            rem_t += hh + mt + mb
        elif kind == "bottom":
            hh = float(sub.get("height", 1.0))
            sub_box = (rem_l + ml, rem_b - hh - mb, (rem_r - rem_l) - ml - mr, hh)
            _solve_sub(sub, sub_box, out)
            rem_b -= hh + mt + mb
        elif kind == "left":
            ww = float(sub.get("width", 2.0))
            sub_box = (rem_l + ml, rem_t + mt, ww, (rem_b - rem_t) - mt - mb)
            _solve_sub(sub, sub_box, out)
            rem_l += ww + ml + mr
        elif kind == "right":
            ww = float(sub.get("width", 2.0))
            sub_box = (rem_r - ww - mr, rem_t + mt, ww, (rem_b - rem_t) - mt - mb)
            _solve_sub(sub, sub_box, out)
            rem_r -= ww + ml + mr
        else:  # fill
            sub_box = (rem_l + ml, rem_t + mt, (rem_r - rem_l) - ml - mr,
                       (rem_b - rem_t) - mt - mb)
            _solve_sub(sub, sub_box, out)

def _solve_sub(sub, sub_box, out):
    t = sub.get("type")
    if t == "dock":
        layout_dock(sub, sub_box, out)
    elif t == "stack":
        from layout_stack import layout_stack
        layout_stack(sub, sub_box, out)
    else:
        out[sub["id"]] = {"rect": sub_box, "cfg": sub, "parent": None}