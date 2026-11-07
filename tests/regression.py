# -*- coding: utf-8 -*-
"""regression.py — 端到端回归：examples 全链 CLI（--no-com）断言 exit 0 + 物证数。

确定性证据链的守护：任何引擎改动后跑一遍，防"修 A 坏 B"。
用法：win_py -X utf8 -W ignore tests/regression.py
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "scripts", "build_ppt.py")

CASES = [
    # 每页基数含「页面切换」物证一条（无切换也断言 XML 无 p:transition）
    ("flowchart", "examples/flowchart/chart.yaml", 39),   # 35 + 框架背景/页眉/页脚 3 项 + 切换
    ("ladder", "examples/ladder/ladder.yaml", 10),
    ("formula", "examples/formula/formula.yaml", 13),
    ("formula-inline", "examples/formula/inline.yaml", 23),  # 文本内公式：
    #  同行 {{…}} → m:oMath 行内式；独占一段 → m:oMathPara 显示式（物证 23 条）
    ("table", "examples/table/table.yaml", 12),
    ("orgchart", "examples/orgchart/orgchart.yaml", 64),
    ("chart", "examples/chart/chart.yaml", 17),
    ("chart-style", "examples/chart/chart_style.yaml", 57),  # 原生图表样式全键：5 页（柱/环/折/堆/条+面积）
    ("deck", "examples/deck/deck.yaml", 54),   # 多页序列：3 页逐页物证
    ("notes", "examples/notes/notes.yaml", 35),  # 备注页：3 页基数 + 页2/3 备注物证
    ("transition", "examples/transition/transition.yaml", 44),  # 切换：4 页逐页（框架页脚 + transition 物证）
    ("link", "examples/link/link.yaml", 45),   # 超链接：3 页（目录 3 链接物证）
    ("pageoffset", "examples/pageoffset/pageoffset.yaml", 43),  # 页码偏移：封面无页脚(10) + 正文 3 页各 11
    ("closure", "examples/closure/closure.yaml", 141),  # 交付闭环总验收：6 页五件套全在场
    ("animation", "examples/animation/chart.yaml", 31),  # 动画积木 9 元素（动画不进 stage5 物证：
    #                                                        时间轴语义，仅 stage6 COM 有动态形）
    ("anim-group", "examples/animation/anim_group.yaml", 28),  # 动画编排组：succession/aligned/group
    #                                                        时间轴引擎展开（成员 trigger/delay 改写）
    ("template-extract", "examples/template/extract.yaml", 15),
    ("template-seed", "examples/template/seed.yaml", 8),
    ("glue-com", "_probe/glue.yaml", 11),
    ("anchors", "_probe/anchors.yaml", 11),   # 具名锚点：2 元素 + glue + label 物证（证据 11/11）
    ("edit-groups", "_probe/edit_groups.yaml", 10),  # 编辑单元：3 件套 + pump + 组区间物证
    ("pageintent", "examples/pageintent/cover.yaml", 27),  # 页型意图：cover 破格封面引擎展开 + 内容页
    ("section", "examples/pageintent/section.yaml", 25),  # 页型意图：section 破格节标题引擎展开 + 内容页
    ("method", "examples/method/cylinder.yaml", 40),  # cylinder/curve 积木：复合展开物证 40 条
    ("typst", "examples/typst/typst.yaml", 7),  # typst 复杂排版整页简历：PNG fallback + svgBlip 双通道
    #                                              物证（1 块 ×（存在+PNG+SVG）3 + 基础 4）
    ("research-sci", "examples/research/sci.yaml", 63),  # 科研三件套（C1）：
    #   problem 问题页 + versus 对照页 + route 路线页引擎展开逐页物证
    ("image-placeholder", "examples/image_placeholder/placeholder.yaml", 12),  # B3 占位框：
    #                                              2 占位框物证 + 基础 8 + 页面切换
    ("ink", "examples/ink/ink.yaml", 41),  # C3 书法矢量字（brush）+ Morph：
    #  2 页逐页物证（字形 custGeom/单路径/三态填充 + morph AlternateContent）
    ("icon", "examples/icon/icon.yaml", 110),  # B1 矢量图标库（icon）：
    #  2 页逐页物证（图标 custGeom/逐子路径描边 fill=none/a:ln 圆头描线）
    ("svg", "examples/svg/svg.yaml", 18),  # 矢量图内化（type: svg）：
    #  SVG→原生 custGeom 5 片形状物证（面板/网格描边/数据区/描边/圆点 defs-use）
    ("svg-ratio", "examples/svg/ratio.yaml", 16),  # 相对坐标层（rect_kind: ratio）：
    #  content/slide 相对定位解绝对 rect + svg 组合 + 文字适配
    ("showcase", "examples/showcase/showcase.yaml", 150),  # 设计编排示范：
    #  6 页零重复骨架（cover/section/图标卡/图表KPI/versus/route）逐页物证
    ("pageintent-variants", "examples/pageintent/variants.yaml", 100),  # 变体家族：
    #  cover split + 三 section 自动轮换（num_left→num_giant→band）+ 内容对照页
    # 内容页结构生成（P3）：5 样板版式各 2 页逐页物证
    ("layout-panels", "examples/layouts/panels.yaml", 60),
    ("layout-columns", "examples/layouts/columns.yaml", 49),
    ("layout-kpis", "examples/layouts/kpis.yaml", 59),
    ("layout-cards", "examples/layouts/cards.yaml", 80),
    ("layout-figure-text", "examples/layouts/figure_text.yaml", 23),
    ("pageintent-theme", "examples/pageintent/theme.yaml", 75),  # 设计语言层：
    #  meta.theme 预设（角色色 token + 类型尺度）+ text_style.scale + 3 页逐页物证
    ("pageintent-theme-deep", "examples/pageintent/theme_deep.yaml", 111),  # 设计语言补强：
    #  跨色相预设 coral_energy + structure=sandwich + motif=circle_icon + font_pair=serif_sans
    ("bad-spec", "_probe/bad.yaml", None),      # 编译期失败 → exit 2
    ("overlap", "_probe/overlap.yaml", None),   # 校验期失败 → exit 3
]


def run_case(name, rel, expected_evidence):
    spec = os.path.join(ROOT, rel)
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore",
                            BUILD, spec, "--out", td, "--report", "none"],
                           capture_output=True, encoding="utf-8", errors="replace")
        out = r.stdout
        if expected_evidence is None:
            expect_rc = 2 if "bad" in name else 3
            ok = r.returncode == expect_rc
            print(f"[{'OK' if ok else 'FAIL'}] {name}: exit={r.returncode}（期望 {expect_rc}）")
            return ok
        ev = re.search(r"evidence: OK (\d+)/(\d+)", out)
        n = int(ev.group(1)) if ev else 0
        ok = r.returncode == 0 and ev and n == expected_evidence
        print(f"[{'OK' if ok else 'FAIL'}] {name}: exit={r.returncode} evidence={n}/{expected_evidence}")
        if not ok:
            print(out[-2000:])
        return ok


def main():
    results = [run_case(*c) for c in CASES]
    # 编译期结构错误负例：rect 非四元组 → 契约 exit 2（stage0/1 拆分后）
    with tempfile.TemporaryDirectory() as td:
        bad = os.path.join(td, "bad_rect.yaml")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("meta: {title: t, style_guide: flowchart, slide: {w: 13.333, h: 7.5},"
                    " margin: {l: 0.5, t: 0.5, r: 0.5, b: 0.5}}\n"
                    "palette: {p: '#1F2A44'}\n"
                    "elements:\n- {id: a, type: shape, kind: rounded_rect,"
                    " rect: [0.6, 0.5, 6.0], style: {fill: p}}\n")
        r = subprocess.run([sys.executable, "-X", "utf8", "-W", "ignore", BUILD,
                            bad, "--out", td, "--report", "none"],
                           capture_output=True, encoding="utf-8", errors="replace")
        ok = r.returncode == 2
        results.append(ok)
        print(f"[{'OK' if ok else 'FAIL'}] bad-rect: exit={r.returncode}（期望 2）")
    total = len(results)
    good = sum(results)
    print(f"\n== 回归：{good}/{total} 通过 ==")
    return 0 if good == total else 1


if __name__ == "__main__":
    sys.exit(main())