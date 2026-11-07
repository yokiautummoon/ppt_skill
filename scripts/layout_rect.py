# -*- coding: utf-8 -*-
"""layout_rect.py — 纯几何工具：矩形/AABB/单位换算/端口模型磁吸锚点/越界。

端口模型（磁吸定位）：每个节点有 4 个端口 N/S/E/W，坐标为形状边界在上下左右
方向上的点。对全部常见 shape 族（rounded_rect/can/proc/diamond/oval）该点
即 AABB 边中点：椭圆在 0/90/180/270° 的边界点恰好是 AABB 中点，菱形顶点亦然。
故端口坐标统一 = AABB 边中点，无需按 shape 分支。
"""
import math

# ---- 单位换算（EMU/PT/IN）----
IN_EMU = 914400      # EMU per inch
PT_EMU = 12700       # EMU per point
IN_PT = 72.0

def in2emu(v): return int(round(v * IN_EMU))
def pt2emu(v): return int(round(v * PT_EMU))
def in2pt(v):  return v * IN_PT

# ---- 矩形工具（rect = (x, y, w, h) 英寸）----
def center(rect):       x, y, w, h = rect; return (x + w / 2, y + h / 2)
def aabb_nodes(rect):
    """端口坐标 dict：N/S/E/W = AABB 边中点。"""
    x, y, w, h = rect
    cx, cy = x + w / 2, y + h / 2
    return {"N": (cx, y), "S": (cx, y + h), "E": (x + w, cy), "W": (x, cy)}

def rects_intersect(a, b, eps=1e-9):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    return (ax < bx + bw - eps and bx < ax + aw - eps and
            ay < by + bh - eps and by < ay + ah - eps)

def rect_contains(outer, inner, eps=1e-9):
    """outer 包含 inner（贴边合法：±eps 对称容差，outer 不必严格多出 eps）。"""
    ox, oy, ow, oh = outer; ix, iy, iw, ih = inner
    return (ox - eps <= ix and oy - eps <= iy and
            ix + iw <= ox + ow + eps and iy + ih <= oy + oh + eps)

def segment_rect_overlap(p, q, rect, eps=1e-6):
    """线段 pq 是否深入矩形内部（纯贴边/擦角/沿边重合不算；端点落在边上不算）。

    对内缩 eps 后的矩形做 Liang-Barsky 参数裁剪：相交参数区间长度 > eps 才算
    穿越（沿边重合线的退化裁剪会被内缩框排除）。布局器（回边是否需绕行）与
    校验器（连线不穿节点）共用，见 2026-10-09 连线治理决策。"""
    # 内缩 2×eps：沿原始边缘重合的线段（正交拐点贴列边缘是标准画法）会被
    # 裁出；真正深入内部的穿越（深度 > 2×eps）保留
    inner = (rect[0] + 2 * eps, rect[1] + 2 * eps, rect[2] - 4 * eps, rect[3] - 4 * eps)
    if inner[2] <= 0 or inner[3] <= 0:
        return False
    x0, y0, w, h = inner
    xmin, ymin, xmax, ymax = x0, y0, x0 + w, y0 + h
    px, py = p
    qx, qy = q
    dx, dy = qx - px, qy - py
    u1, u2 = 0.0, 1.0
    for pl, ql in ((-dx, px - xmin), (dx, xmax - px),
                   (-dy, py - ymin), (dy, ymax - py)):
        if abs(pl) <= eps:
            if ql < -eps:
                return False          # 平行且在矩形外（同一侧）
            continue
        r = ql / pl
        if pl < 0:
            if r > u2:
                return False
            if r > u1:
                u1 = r
        else:
            if r < u1:
                return False
            if r < u2:
                u2 = r
    return (u2 - u1) > eps

def pad_rect(rect, pad):
    """pad: 标量或 dict(l/t/r/b)；内缩。"""
    if isinstance(pad, dict):
        l, t = pad.get("l", 0), pad.get("t", 0)
        r, b = pad.get("r", 0), pad.get("b", 0)
    else:
        l = t = r = b = pad
    x, y, w, h = rect
    return (x + l, y + t, w - l - r, h - t - b)

# ---- 磁吸锚点（端口模型）----
def snap_anchor(self_rect, other_center):
    """从 self 出发指向 other 的锚点：主轴选择 → 端口坐标。

    |dx| >= |dy| → 水平接入（E/W 端口）；否则垂直（N/S 端口）。
    返回 (side, (x, y))；side ∈ N/S/E/W（供校验断言"锚点贴某端口"）。"""
    sx, sy = center(self_rect)
    ox, oy = other_center
    dx, dy = ox - sx, oy - sy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return "C", (sx, sy)
    ports = aabb_nodes(self_rect)
    if abs(dx) >= abs(dy):
        side = "E" if dx >= 0 else "W"
    else:
        side = "S" if dy >= 0 else "N"     # y 向下：目标在下侧 → 走 S 端口
    p = ports[side]
    return side, (round(p[0], 3), round(p[1], 3))

def anchor_pair(ra, rb):
    """a→b 与 b→a 双向磁吸锚点（布局器与校验器共用此实现；校验另附独立重算）。"""
    ca, cb = center(ra), center(rb)
    side_a, a1 = snap_anchor(ra, cb)
    side_b, a2 = snap_anchor(rb, ca)
    return side_a, a1, side_b, a2

def edge_anchor(c1, dim1, c2, dim2):
    """probe 版兼容签名：两中心+尺寸 → 起锚点（直线端）。供独立第二实现比对。"""
    ra = (c1[0] - dim1[0] / 2, c1[1] - dim1[1] / 2, dim1[0], dim1[1])
    rb = (c2[0] - dim2[0] / 2, c2[1] - dim2[1] / 2, dim2[0], dim2[1])
    _, a1, _, _ = anchor_pair(ra, rb)
    return a1

# ---- 越界 / 数值审计 ----
def is_finite_pos(v, eps=1e-9):
    return isinstance(v, (int, float)) and math.isfinite(v) and v > eps

def audit_rect_inside(rect, slide, pad=0.0, eps=1e-3):
    """rect ⊆ slide（含内缩 pad）；越界返回 (False, 超界方向描述)。"""
    sw, sh = slide
    x, y, w, h = rect
    ok = (x >= pad - eps and y >= pad - eps and
          x + w <= sw - pad + eps and y + h <= sh - pad + eps)
    return ok, None if ok else "out_of_slide"