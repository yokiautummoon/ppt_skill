# -*- coding: utf-8 -*-
"""alpha_math.py — 半透明层叠加反解（JAnim apart_alpha / merge_alpha 移植）。

复合形状（cylinder 拆侧壁/端面/弧线等部件）与 JAnim 把曲线切 n 段是同一个
数学问题：n 个半透明层叠加的合成不透明度 = 1 − ∏(1−αi)。若默认每层都用
声明值，叠区必然过度深色；正确做法是**反解每层 alpha**，使"任一层数组合的
合成值 = 声明目标"（叠区保真）。

  merge_alpha(alphas)      n 层合成：1 − ∏(1−αi)                      （正向）
  apart_alpha(target, n)   n 段切分等价反解：α = 1−(1−target)^(1/n)    （闭式）
  face_alpha(fg, bg)       端面反解：端面叠于侧壁之上合成 = fg
                           → α_face = (fg − bg)/(1 − bg)；fg ≤ bg 无解 → None

注：JAnim 用 bisection（ε=1e-3）解反演；1−(1−α)^n 的逆有闭式解，本模块用闭式
（等价、无迭代漂移），断言容差仍取 ε=1e-3（合成值与目标的偏差阈值）。
α 语义 = 不透明度（0 透明 ~ 1 不透明），与 SPEC cylinder `opacity` 一致；
渲染层 a:alpha val = α × 100000。
"""
EPS = 1e-3


def merge_alpha(alphas):
    """n 层半透叠加的合成不透明度：1 − ∏(1−αi)。"""
    a = 1.0
    for x in alphas:
        a *= 1.0 - x
    return 1.0 - a


def apart_alpha(target, n):
    """n 段切分的每段 alpha：全部叠加后恰还原 target。
    闭式解 1−(1−target)^(1/n)（JAnim bisection 解的解析等价）。"""
    if n <= 1:
        return float(target)
    return 1.0 - (1.0 - target) ** (1.0 / n)


def face_alpha(face_target, side_alpha):
    """端面 alpha 反解：端面绘制于侧壁之上（2 层叠），使合成 = face_target。
    face_target ≤ side_alpha 时端面无法比底层更透（叠区不可能到达目标）→
    返回 None（调用方报错：face_opacity 须 > opacity）。"""
    if face_target <= side_alpha + EPS:
        return None
    return (face_target - side_alpha) / (1.0 - side_alpha)


def check_merge(alphas, target):
    """合成断言：merge(alphas) ≈ target（ε=EPS）。返回 None 或偏差。"""
    got = merge_alpha(alphas)
    return got if abs(got - target) <= EPS else None