# -*- coding: utf-8 -*-
"""typst_compile.py — typst 复杂精美排版链路：SPEC type:typst → SVG/PNG 双产物。

设计要点（详见 references/typst-chain.md）：
  1. 自动围切最小边界盒（trim）：rect 只定**宽**（决定换行与 100% 宽填充语义），
     页面高 `auto`（typst 依内容生长，杜绝顶部裁剪与下部空白）；编译后扫 PNG
     求内容 bbox → 裁 PNG + 重写 SVG viewBox → 元素实际尺寸 = 内容 bbox，位置 =
     rect 原点 + 内容偏移。渲染期零重算（排版块版铁律 1 的对应物）。
     用户 preamble 自带 `#set page` 时让用户自控画布（跳过硬切，尺寸不符 → WARN）。
  2. 双产物（OOXML 2016+ svgBlip 规范要求栅格 fallback）：
       svg — 矢量通道：typst 字形输出即轮廓 path，自包含无字体依赖；
       png — 栅格 fallback：全版本 PPT 兼容，ppi 控清晰度。
  3. 编译器 = scripts/typst-cli/typst.exe（官方 typst 二进制，无 Office 依赖）。
     编译失败 → TypstCompileError（stage1.5 编译闸门 → exit 2）。

产物落 <out_dir>/typst_cache/<page>_<id>.{typ,png,svg}；源码同落（.typ）供审计。
"""
import os
import re
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(_HERE, "typst-cli", "typst.exe")
PNG_PPI = 300
TRIM_TOL = 12          # PNG 背景差阈值（0-255）：滤掉抗锯齿轮廓噪声
DEFAULT_FONTS = ("Microsoft YaHei", "SimSun", "Times New Roman")
DEFAULT_FS_PT = 11.0
_VB_RE = re.compile(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"')


class TypstCompileError(Exception):
    pass


def cli_available():
    return os.path.isfile(CLI)


def _fonts_literal():
    return "(" + ", ".join('"%s"' % f for f in DEFAULT_FONTS) + ")"


def _typst_lit(v):
    """vars 值 → typst 字面量（字符串加引号；数值/布尔原样透传）。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return '"%s"' % str(v).replace("\\", "\\\\").replace('"', '\\"')


def build_source(e, rect, base_dir=None):
    """元素 → 完整 typst 源码（默认前导 + 用户 preamble + vars + 正文）。

    正文源三选一（spec_compile 已背书互斥）：inline `typst` 或外链 `typst_src`。
    """
    w_pt = round(float(rect[2]) * 72.0, 3)
    pre = (e.get("preamble") or "").strip("\n")
    parts = []
    if "#set page" not in pre:
        # rect 只定宽（换行/100% 宽填充语义），高 auto → 页面依内容生长，
        # 再经 _trim_bbox 围切最小边界盒（见 module docstring）。
        parts.append("#set page(width: %gpt, height: auto, margin: 0pt)" % (w_pt,))
    parts.append("#set text(font: %s, size: %gpt)" % (_fonts_literal(), DEFAULT_FS_PT))
    if pre:
        parts.append(pre)
    for k, v in (e.get("vars") or {}).items():
        parts.append("#let %s = %s" % (k, _typst_lit(v)))
    src = e.get("typst")
    if src is None:
        src = _read_external(e, base_dir)
    parts.append(src)
    return "\n".join(parts) + "\n"


def _read_external(e, base_dir):
    rel = e["typst_src"]
    path = rel if os.path.isabs(rel) else os.path.join(base_dir or ".", rel)
    if not os.path.isfile(path):
        raise TypstCompileError(f"typst_src 不存在：{rel!r}（解析为 {path}）")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _run_cli(typ_path, out_path, fmt, ppi=None):
    cmd = [CLI, "compile", "-f", fmt]
    if ppi is not None:
        cmd += ["--ppi", str(ppi)]
    cmd += [typ_path, out_path]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip() or f"exit {r.returncode}"
        raise TypstCompileError(detail)


def compile_one(src, base_path):
    """源码 → (svg_path, png_path)。base_path 为无扩展名的产物前缀。"""
    typ_path = base_path + ".typ"
    with open(typ_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    svg_path = base_path + ".svg"
    png_path = base_path + ".png"
    _run_cli(typ_path, svg_path, "svg")
    _run_cli(typ_path, png_path, "png", ppi=PNG_PPI)
    return svg_path, png_path


def _svg_size_pt(svg_path):
    """从 SVG viewBox 读产物尺寸（pt，因 typst 输出 width/height 以 pt 记）。"""
    with open(svg_path, "r", encoding="utf-8") as f:
        m = _VB_RE.search(f.read(2048))
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def _explicit_page(e):
    """用户 preamble 自带 #set page → 用户自控画布，跳过自动围切。"""
    return "#set page" in (e.get("preamble") or "")


def _content_bbox_px(png_path):
    """PNG 内容 bbox（像素）。白底合成 → 与角落背景差 > TRIM_TOL 的像素 bbox。

    返回 (l, t, r, b) px（±1px 保护边：不裁掉抗锯齿轮廓极浅像素）或 None。"""
    from PIL import Image, ImageChops
    with Image.open(png_path) as src:
        rgba = src.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(white, rgba).convert("RGB")
    bg = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, bg).convert("L").point(
        lambda v: 255 if v > TRIM_TOL else 0)
    bb = diff.getbbox()
    if not bb:
        return None
    l, t, r, b = bb
    return max(0, l - 1), max(0, t - 1), min(rgb.size[0], r + 1), min(rgb.size[1], b + 1)


def _trim_products(svg_path, png_path, l, t, r, b):
    """按内容 bbox（像素，单一来源）围切双产物：重写 SVG viewBox + 裁 PNG。"""
    k = 72.0 / PNG_PPI                         # px → pt
    bx, by, bw, bh = l * k, t * k, (r - l) * k, (b - t) * k
    with open(svg_path, "r", encoding="utf-8") as f:
        head = f.read().split(">", 1)[0]
    head = re.sub(r'viewBox="[^"]*"', 'viewBox="%g %g %g %g"' % (bx, by, bw, bh), head)
    head = re.sub(r'width="[^"]*"', 'width="%gpt"' % bw, head)
    head = re.sub(r'height="[^"]*"', 'height="%gpt"' % bh, head)
    with open(svg_path, "r", encoding="utf-8") as f:
        rest = f.read().split(">", 1)[1]
    with open(svg_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(head + ">" + rest)
    from PIL import Image
    with Image.open(png_path) as src:
        src.crop((l, t, r, b)).save(png_path)  # 句柄关闭后再写同名文件（Windows 锁）


def compile_all(compiled, out_dir, base_dir=None):
    """编译全部 type:typst 元素；写回 e["_typst"] = {svg,png,typ,size,offset,page}。

    size/offset 均为 pt（围切后内容 bbox 与其在 rect 页内的偏移；用户 preamble
    自设 page 时 size=画布尺寸、offset=(0,0)，跳过硬切）。返回 warnings 列表
    （自设画布与 rect 不符等，不阻断）。编译失败抛 TypstCompileError，消息含
    元素定位（stage1.5 编译闸门 → exit 2）。"""
    if not cli_available():
        raise TypstCompileError(
            f"typst CLI 未安装：{CLI}（typst 排版链路需官方二进制，见 references/typst-chain.md）")
    pages = compiled.get("slides") or []
    n = sum(1 for pg in pages for e in (pg.get("elements") or [])
            if e.get("type") == "typst")
    if n == 0:
        return []
    cache = os.path.join(os.path.abspath(out_dir), "typst_cache")
    os.makedirs(cache, exist_ok=True)
    warnings = []
    for pi, page in enumerate(pages):
        for e in page.get("elements") or []:
            if e.get("type") != "typst":
                continue
            path = f"page{pi + 1}.elements[{e['id']}]"
            try:
                src = build_source(e, e["rect"], base_dir)
                base = os.path.join(cache, f"{pi + 1}_{e['id']}")
                svg_path, png_path = compile_one(src, base)
            except TypstCompileError as ex:
                raise TypstCompileError(f"{path}: typst 编译失败\n{ex}")
            page_size = _svg_size_pt(svg_path)
            if page_size and not _explicit_page(e):
                # 自动围切最小边界盒：内容 bbox 定元素尺寸，偏移定落版起点
                bb = _content_bbox_px(png_path)
                if bb:
                    _trim_products(svg_path, png_path, *bb)
                    k = 72.0 / PNG_PPI
                    size = ((bb[2] - bb[0]) * k, (bb[3] - bb[1]) * k)
                    offset = (bb[0] * k, bb[1] * k)
                else:
                    size, offset = page_size, (0.0, 0.0)
            else:
                size, offset = page_size, (0.0, 0.0)
            e["_typst"] = {"svg": os.path.abspath(svg_path),
                           "png": os.path.abspath(png_path),
                           "typ": os.path.abspath(base + ".typ"),
                           "size": size, "offset": offset, "page": page_size}
            if size and _explicit_page(e):
                rw, rh = float(e["rect"][2]) * 72.0, float(e["rect"][3]) * 72.0
                if abs(size[0] - rw) > 0.5 or abs(size[1] - rh) > 0.5:
                    warnings.append(
                        f"{path}: typst 画布 {size[0]:.1f}×{size[1]:.1f}pt ≠ "
                        f"rect {rw:.1f}×{rh:.1f}pt（preamble 自设 page）——"
                        f"按画布尺寸落版于 rect 原点")
    return warnings
