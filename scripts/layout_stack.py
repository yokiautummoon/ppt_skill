# -*- coding: utf-8 -*-
"""layout_stack.py — 容器 stack（垂直/水平）分配器。

语义（agent 可操控）：
  - children 尺寸：width/height 数值（英寸）或 "100%"（撑满容器该轴）。
  - 垂直 stack：align=left|center|right 控制 children 水平对齐（默认 center）；
                v_align=top|center|bottom 控制整体块垂直位置（默认 top）。
  - 水平 stack：align=top|middle|bottom 控制 children 垂直对齐（默认 middle）；
                h_align=left|center|right 控制整体块水平位置（默认 center）。
  - gap：相邻 child 间距（英寸，数值接口）。
规则：尺寸/gap 由声明决定；整体块超容器 → 由 G 家族"stack 账目"断言拦截（不在此抛出）。
"""
import layout_rect as LR

def _dim(child, key, container_dim):
    raw = child.get(key, "100%")
    if isinstance(raw, str) and raw.endswith("%"):
        return float(raw.rstrip("%")) / 100.0 * container_dim
    return float(raw)

def layout_stack(node, rect, out):
    """node: {id, orientation, align, v_align|h_align, gap, children:[...]}
       out[id] = {"rect": (x,y,w,h), "cfg": child, "parent": node_id} 累积。"""
    x, y, w, h = rect
    out[node["id"]] = {"rect": rect, "cfg": node}
    vert = node.get("orientation", "vertical") != "horizontal"
    gap = node.get("gap", 0.0)
    kids = node.get("children", [])
    if vert:
        dims = [_dim(k, "height", h) for k in kids]
        total = sum(dims) + gap * max(0, len(kids) - 1)
        va = node.get("v_align", "top")
        y0 = y + (0.0 if va == "top" else (h - total) if va == "bottom" else (h - total) / 2)
        al = node.get("align", "center")
        cy = y0
        for k, kd in zip(kids, dims):
            kw = _dim(k, "width", w)
            kx = x + (0.0 if al == "left" else (w - kw) if al == "right" else (w - kw) / 2)
            out[k["id"]] = {"rect": (kx, cy, kw, kd), "cfg": k, "parent": node["id"]}
            cy += kd + gap
    else:
        dims = [_dim(k, "width", w) for k in kids]
        total = sum(dims) + gap * max(0, len(kids) - 1)
        ha = node.get("h_align", "center")
        x0 = x + (0.0 if ha == "left" else (w - total) if ha == "right" else (w - total) / 2)
        al = node.get("align", "middle")
        cx = x0
        for k, kd in zip(kids, dims):
            kh = _dim(k, "height", h)
            ky = y + (0.0 if al == "top" else (h - kh) if al == "bottom" else (h - kh) / 2)
            out[k["id"]] = {"rect": (cx, ky, kd, kh), "cfg": k, "parent": node["id"]}
            cx += kd + gap