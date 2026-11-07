# -*- coding: utf-8 -*-
"""textmesh.py — 文本测量 / 断行 / autofit（确定性排版期定字号）。

测量模型（实测微软雅黑/Calibri，参考文献 references/text-measurement.md）：
  - CJK em 宽 = 1.00×fs，ASCII em 宽 = 0.54×fs
  - 行高 = line_h × fs
  - 断行阈值 = 框宽（与渲染端 word_wrap 一致）；margin_w 3% 只用于断言兜底
三段式：segment_text(空白折叠/CJK 逐字/ASCII 整词) → measure_prepare(逐段测量) → wrap_layout(贪心断行)
"""
import params as _P   # 内部绝对导入（build_ppt 保证 scripts 在 sys.path）

def segment_text(text):
    """CJK 逐字、ASCII 按词分段；空白折叠（多个空白 → 无）。"""
    segs, buf = [], ""
    for ch in text:
        if ch.isspace():
            if buf:
                segs.append(("ascii", buf)); buf = ""
        elif ord(ch) > 0x2E80:
            if buf:
                segs.append(("ascii", buf)); buf = ""
            segs.append(("cjk", ch))
        else:
            buf += ch
    if buf:
        segs.append(("ascii", buf))
    return segs

def measure_prepare(text, fs, em_cjk=None, em_asc=None):
    """(prepare) 分段并测量每段宽度(pt)，按字号线性缩放，可缓存。"""
    em_cjk = em_cjk or _P.DEFAULTS["text"]["em_cjk"]
    em_asc = em_asc or _P.DEFAULTS["text"]["em_asc"]
    return [(t, tok, (len(tok) * (em_cjk if t == "cjk" else em_asc) * fs))
            for t, tok in segment_text(text)]

def wrap_layout(segs, box_w_pt):
    """(layout) 贪心断行：CJK 段可断、ASCII 词整词不可断；返回 (lines, max_w)。"""
    lines, cur, cur_w, max_w = [], [], 0.0, 0.0
    for seg in segs:
        if cur and cur_w + seg[2] > box_w_pt:
            lines.append(cur); max_w = max(max_w, cur_w)
            cur, cur_w = [], 0.0
        cur.append(seg); cur_w += seg[2]
    if cur:
        lines.append(cur); max_w = max(max_w, cur_w)
    return lines, max_w

def autofit_text(text, fs0, box_w_pt, box_h_pt, min_fs=None, iters=None,
                 margin_w=None, line_h=None):
    """排版期定字号：迭代收缩直到水平/垂直均合框；返回 text_layout dict。

    min_fs 为硬底：缩到硬底仍超框则返回超框状态（由 T 家族断言拦截），不静默降到不可读。"""
    p = _P.DEFAULTS["text"]
    min_fs = min_fs if min_fs is not None else p["min_fs"]
    iters = iters if iters is not None else p["autofit_iters"]
    margin_w = margin_w if margin_w is not None else p["margin_w"]
    line_h = line_h if line_h is not None else p["line_h"]
    fs, lines, max_w, need_h = fs0, [], 0.0, 0.0
    for _ in range(iters):
        lines, max_w = wrap_layout(measure_prepare(text, fs), box_w_pt)
        need_h = len(lines) * line_h * fs
        if max_w <= box_w_pt * margin_w and need_h <= box_h_pt:
            break
        r = 1.0
        if max_w > box_w_pt * margin_w:
            r = min(r, box_w_pt * margin_w / max_w)
        if need_h > box_h_pt:
            r = min(r, box_h_pt / need_h)
        fs = max(min_fs, fs * r)
    return dict(fs=round(fs, 2), lines=len(lines), max_w=round(max_w, 1),
                need_h=round(need_h, 1), chars=len(text), overflow=False)

def autofit_node(text, box_w_in, box_h_in, fs0=None, min_fs=None, p=None):
    """节点文本 autofit 便捷封装（英寸入参）。"""
    p = p or _P.DEFAULTS
    fs0 = fs0 if fs0 is not None else p["text"]["fs0_node"]
    return autofit_text(text, fs0, box_w_in * 72, box_h_in * 72, min_fs=min_fs)