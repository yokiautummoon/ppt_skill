# -*- coding: utf-8 -*-
"""test_svg_doc.py — svg_doc 单测（type: svg 的几何源，无 Office）。

覆盖：图元/defs+use/仿射 transform（含 y 翻转矩阵）/ 紧包围盒 / 按边界+paint
分组 / y-flip 下 bbox 语义 / fail-closed（不支持构造/外链 use/渐变/深嵌套）。
运行：win_py -X utf8 tests/test_svg_doc.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import svg_doc as SD


def _svg(inner, extra=""):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' "
            f"xmlns:xlink='http://www.w3.org/1999/xlink' {extra}>{inner}</svg>")


def test_simple_path():
    """M 指令绝对定位：bbox = 顶点包络；默认 fill=黑。"""
    gs = SD.parse(_svg("<path d='M 0 0 H 10 V 5 H 0 Z' fill='#FF0000'/>"))
    assert len(gs) == 1
    g = gs[0]
    assert g["fill"] == "#FF0000"
    assert g["stroke"] is None
    bb = [round(v, 3) for v in g["bbox"]]
    assert bb == [0.0, 0.0, 10.0, 5.0], bb
    # 默认 fill 为黑（SVG 初值）
    gs2 = SD.parse(_svg("<rect x='1' y='2' width='3' height='4'/>"))
    assert gs2[0]["fill"] == "#000000"


def test_elements_and_types():
    """rect/circle/elipse/line/polyline/polygon 各图元可见。"""
    svg = _svg("""
      <rect x='0' y='0' width='10' height='5' fill='#112233'/>
      <circle cx='20' cy='10' r='4' fill='#445566'/>
      <ellipse cx='30' cy='10' rx='3' ry='2' fill='none' stroke='#778899'
               stroke-width='1.5'/>
      <line x1='40' y1='0' x2='45' y2='10' stroke='#AABBCC' stroke-width='2'/>
      <polyline points='50,0 55,5 60,0' stroke='none' fill='#DDEEFF'/>
      <polygon points='70,0 75,5 80,0' fill='#FFEEDD'/>
    """)
    assert len(SD.parse(svg)) == 6
    # 描边色 + 宽进组弥散
    el = SD.parse(svg)[2]
    assert el["stroke"] == "#778899" and el["stroke_w"] == 1.5


def test_defs_use():
    """symbol 定义 + use 实例化：x/y 附加平移入 bbox。"""
    svg = _svg("""
      <defs><symbol id='dot' overflow='visible'>
        <circle cx='0' cy='0' r='2' fill='#335577'/>
      </symbol></defs>
      <use xlink:href='#dot' x='10' y='5' fill='#335577'/>
    """)
    gs = SD.parse(svg)
    assert len(gs) == 1
    bb = [round(v, 3) for v in gs[0]["bbox"]]
    assert bb == [8.0, 3.0, 12.0, 7.0], bb


def test_transform_translate():
    """g transform=translate 套用到内部图元。"""
    svg = _svg("<g transform='translate(3 4)'><rect x='1' y='1' width='2' "
               "height='2' fill='#FF0000'/></g>")
    bb = [round(v, 3) for v in SD.parse(svg)[0]["bbox"]]
    assert bb == [4.0, 5.0, 6.0, 7.0], bb


def test_transform_scale():
    """scale 放缩：bbox 同比放大。"""
    svg = _svg("<rect x='1' y='2' width='3' height='4' fill='#FF0000' "
               "transform='scale(2 3)'/>")
    bb = [round(v, 3) for v in SD.parse(svg)[0]["bbox"]]
    assert bb == [2.0, 6.0, 8.0, 18.0], bb


def test_transform_yflip():
    """typst/Illustrator 常见 matrix(1 0 0 -1 tx ty)：y 翻转——几何随矩阵。"""
    svg = _svg("<g transform='matrix(1 0 0 -1 30 40)'>"
               "<rect x='0' y='0' width='10' height='5' fill='#FF0000'/></g>")
    bb = [round(v, 3) for v in SD.parse(svg)[0]["bbox"]]
    # y' = ty - y：上缘 40-0=40、下缘 40-5=35
    assert bb == [30.0, 35.0, 40.0, 40.0], bb


def test_transform_rotate():
    """rotate(θ)：绕原点旋转后 bbox 覆盖旋转四边形。"""
    svg = _svg("<g transform='rotate(45 0 0)'>"
               "<rect x='0' y='0' width='4' height='0' fill='#FF0000'/></g>")
    gs = SD.parse(svg)
    assert len(gs) == 1
    x0, y0, x1, y1 = [round(v, 3) for v in gs[0]["bbox"]]
    assert (x0, y0) == (0.0, 0.0)                 # 起始端在原点
    # 4 单位水平段旋 45°：对角线投影 4/√2=2.828，两端点方形包络
    assert (x1, y1) == (round(4 / 2 ** 0.5, 3), round(4 / 2 ** 0.5, 3))


def test_grouping_by_paint():
    """同一边界内按（fill/stroke/width）切分：异色拆形状。"""
    svg = _svg("""
      <g>
        <rect x='0' y='0' width='2' height='2' fill='#FF0000'/>
        <rect x='3' y='0' width='2' height='2' fill='#FF0000'/>
        <rect x='6' y='0' width='2' height='2' fill='#00FF00'/>
        <rect x='0' y='4' width='2' height='2' fill='none' stroke='#0000FF'
              stroke-width='2'/>
      </g>
    """)
    gs = SD.parse(svg)
    assert len(gs) == 3, [(g["fill"], g["stroke"], g["stroke_w"]) for g in gs]
    # 排布：fill #FF0000 ×2 并组、#00FF00 独立、描边组独立
    assert gs[0]["fill"] == "#FF0000" and len(gs[0]["subpaths"]) == 2
    assert gs[1]["fill"] == "#00FF00"
    assert gs[2]["fill"] is None and gs[2]["stroke"] == "#0000FF"


def test_grouping_by_boundary():
    """两个顶层边界各成组（doc_bbox 联合、边界数=2）。"""
    svg = _svg("""
      <rect x='0' y='0' width='10' height='5' fill='#FF0000'/>
      <circle cx='20' cy='20' r='3' fill='#FF0000'/>
    """)
    gs = SD.parse(svg)
    assert len(gs) == 2 and {g["boundary"] for g in gs} == {0, 1}
    db = [round(v, 3) for v in SD.doc_bbox(gs)]
    assert db == [0.0, 0.0, 23.0, 23.0], db


def test_bbox_with_curve_endpoint():
    """三次曲线（C）的 bbox 含控制点近似（@返回扩张）。"""
    svg = _svg("<path d='M 0 0 C 5 -5 15 5 20 0 L 20 10 Z' fill='#FF0000'/>")
    bb = [round(v, 3) for v in SD.parse(svg)[0]["bbox"]]
    # 精确三次贝塞尔极值（非控制点粗框）：y 下探=上端点 + 右端点 + 闭合竖边
    assert bb == [0.0, -5.0, 20.0, 10.0], bb


def test_fail_closed_text():
    try:
        SD.parse(_svg("<text x='5' y='5'>hi</text>"))
        raise AssertionError("text 应 fail-closed")
    except SD.SvgDocError:
        pass


def test_fail_closed_unsupported():
    for tag in ("image", "filter", "clipPath", "mask", "pattern",
                "linearGradient", "radialGradient", "foreignObject", "style"):
        try:
            SD.parse(_svg(f"<{tag}/>"))
            raise AssertionError(f"<{tag}> 应 fail-closed")
        except SD.SvgDocError:
            pass


def test_fail_closed_gradient_url():
    try:
        SD.parse(_svg("<rect x='0' y='0' width='2' height='2' "
                      "fill='url(#g)'/>"))
        raise AssertionError("url() 渐变应 fail-closed")
    except SD.SvgDocError:
        pass


def test_fail_closed_render_affect_attrs():
    """shape 上带 filter/clip-path/mask 属性（引用 defs 定义）= 服用了滤镜/裁剪/
    遮罩 → 须 fail-closed，绝不静默丢效果（对照：<defs> 里的定义本身被容忍）。"""
    probe = [
        ("filter", "<rect x='0' y='0' width='2' height='2' fill='#FF0000' "
                   "filter='url(#f)'/>"),
        ("clip-path", "<path d='M0 0 L2 0 L2 2 Z' fill='#FF0000' "
                      "clip-path='url(#c)'/>"),
        ("clipPath-atom", "<path d='M0 0 L2 0 L2 2 Z' fill='#FF0000' "
                          "clipPath='url(#c)'/>"),
        ("mask", "<rect x='0' y='0' width='2' height='2' fill='#FF0000' "
                 "mask='url(#m)'/>"),
    ]
    wrap = ("<defs><filter id='f'/><clipPath id='c'><circle cx='1' cy='1' r='1'/>"
            "</clipPath><mask id='m'><rect width='2' height='2' fill='#FFF'/></mask>"
            "</defs>{body}")
    for name, body in probe:
        try:
            SD.parse(_svg(wrap.format(body=body)))
            raise AssertionError(f"{name} 属性引用应 fail-closed")
        except SD.SvgDocError:
            pass


def test_defs_contained_unsupported_tolerated():
    """<defs> 内的 filter/clipPath/mask/渐变是惰性定义，未服用即无渲染效果 → 容忍。"""
    svg = _svg("<defs><filter id='f'/><clipPath id='c'/><linearGradient id='g'/>"
               "</defs><rect x='0' y='0' width='2' height='2' fill='#FF0000'/>")
    gs = SD.parse(svg)
    assert len(gs) == 1 and gs[0]["fill"] == "#FF0000"


def test_fail_closed_external_use():
    try:
        SD.parse(_svg("<use href='https://x.com/a.svg'/>"))
        raise AssertionError("外链 use 应 fail-closed")
    except SD.SvgDocError:
        pass


def test_fail_closed_missing_ref():
    try:
        SD.parse(_svg("<use href='#nope'/>"))
        raise AssertionError("缺失引用应 fail-closed")
    except SD.SvgDocError:
        pass


def test_fail_closed_deep_nesting():
    inner = "<rect x='0' y='0' width='1' height='1' fill='#FF0000'/>"
    try:
        SD.parse(_svg("<g>" * 40 + inner + "</g>" * 40))
        raise AssertionError("深嵌套应 fail-closed")
    except SD.SvgDocError:
        pass


def test_fail_closed_bad_root():
    try:
        SD.parse("<html></html>")
        raise AssertionError("非 svg 根应 fail-closed")
    except SD.SvgDocError:
        pass


def test_fail_closed_empty():
    try:
        SD.parse(_svg("<defs><circle id='x' cx='0' cy='0' r='1'/></defs>"))
        raise AssertionError("空/仅 defs 应 fail-closed")
    except SD.SvgDocError:
        pass


def test_radar_structure():
    """端到端样例雷达图：5 组（面板/网格/数据区/描边/圆点）。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "assets", "figures", "radar.svg")
    gs = SD.parse_file(path)
    fills = [g["fill"] for g in gs]
    strokes = [g["stroke"] for g in gs]
    assert len(gs) == 5, [(g.get("fill"), g.get("stroke")) for g in gs]
    # 面板实色填充；网格仅描边（fill=none → None）；数据区实色；描边仅描边；圆点实色
    assert fills[0] == "#EAF1FC"
    assert strokes[1] and fills[1] is None
    assert fills[2] is not None
    assert fills[3] is None and strokes[3]
    assert fills[4] is not None
    # doc_bbox 为先（面板原点附近）后点状末端：联合覆盖数据区+圆点
    db = SD.doc_bbox(gs)
    assert db[2] > db[0] and db[3] > db[1]


if __name__ == "__main__":
    fns = (test_simple_path, test_elements_and_types, test_defs_use,
           test_transform_translate, test_transform_scale, test_transform_yflip,
           test_transform_rotate, test_grouping_by_paint,
           test_grouping_by_boundary, test_bbox_with_curve_endpoint,
           test_fail_closed_text, test_fail_closed_unsupported,
           test_fail_closed_gradient_url, test_fail_closed_external_use,
           test_fail_closed_missing_ref, test_fail_closed_deep_nesting,
           test_fail_closed_bad_root, test_fail_closed_empty, test_radar_structure,
           test_fail_closed_render_affect_attrs,
           test_defs_contained_unsupported_tolerated)
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"[OK] {fn.__name__}")
        except AssertionError as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {ex}")
        except Exception as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {type(ex).__name__}: {ex}")
    print(f"== svg_doc：{len(fns) - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)