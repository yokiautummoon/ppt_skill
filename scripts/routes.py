# -*- coding: utf-8 -*-
"""routes.py — 操作路由注册表（防误路由 + 协议显式化）。

借鉴 EasySlides workflow registry 的 Trigger / Preconditions / Route-exclusion /
Output-contract 四列：本的每次操作入口在此**显式声明**何时该走、前置条件、
**禁止条件（Route-exclusion）**与产出契约。agent 与 CLI 双层消费：人读版见
references/routing-table.md，机器校验见 tests/test_routes.py。

禁止条件列的意义（EasySlides 的核心教训）：只写"何时可以走"不够——还要写明
"何时**不许**走这条"，防止把错误的问题伸进错误的管道后，靠后续门禁兜底。
"""
import os

ROUTE_EXITS = (0, 2, 3, 4, 5, 6)   # build_ppt 出口码契约（0 成功 / 2 编译 / 3 校验
                                   # / 4 渲染物证 / 5 COM 严格 / 6 LLM 稳态暂停）
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 每条路由四列（+ script/exits 机器校验字段）：
#   trigger      何时走这条（用户意图/产物信号）
#   preconditions 必须为真的前置（不满足 → 换路由或先补前置）
#   excludes     禁止条件（路由 id 引用 + 自由文本条件；拿去接"什么时候不许走"）
#   outputs      Route-output contract：本条路由承诺的产物
ROUTES = [
    dict(
        id="main_generation",
        name="主生成链（SPEC → base.pptx）",
        trigger="从零生成/给定 SPEC YAML 出可编辑 pptx",
        preconditions=["SPEC 存在且 style_guide 合法", "产物须原生可编辑（铁律：不手改产物）"],
        excludes=["fix_loop"],
        exclude_conditions=["源是幻灯片截图/AI 稿 → 本项目不做图片重建（EasySlides 才做）",
                            "已有成品只补备注/音频/时间 → 改 SPEC 重跑全链（不手改产物）",
                            "批注动画 → 走 anim_inject（原子性四段批次）"],
        outputs=["out/base.pptx", "out/ir.json", "out/report.md", "out/evidence/ 物证"],
        exits=(0, 2, 3, 4),
        script="scripts/build_ppt.py",
        entry="win_py -X utf8 scripts/build_ppt.py spec.yaml",
    ),
    dict(
        id="fix_loop",
        name="--fix 自优修订链",
        trigger="校验违规需自动收敛（R1–R4 机械动作 / LLM 语义修订）",
        preconditions=["build_ppt 可运行", "违规归因非 internal（算法 bug → 停机 exit 4）"],
        excludes=[],
        exclude_conditions=["internal 归因（引擎 bug）：不修 SPEC 不喂 LLM",
                            "数据字段无据可溯：数据红线整批拒绝（CHECK_OUT 强制）"],
        outputs=["out/llm_job.json / llm_out.json", "fix.diff", ".snap.N 快照"],
        exits=(0, 3, 4, 6),
        script="scripts/build_ppt.py",
        entry="win_py -X utf8 scripts/build_ppt.py spec.yaml --fix [--llm]",
    ),
    dict(
        id="com_postprocess",
        name="COM 后处理（glue/Group/OLE/动画/PDF/PNG）",
        trigger="需 COM 真能力（连线/Office Group/动画时间轴/导出）",
        preconditions=["Windows + Office 安装",
                       "POWERPNT.EXE 无驻留 GUI 实例（瞬态 Dispatch 失败先 taskkill 重试）"],
        excludes=["main_generation"],
        exclude_conditions=["chart/formula 有零 COM 路径 → 不必要不加 --com",
                            "仅纯文本/表格/图表 → 不需要 COM，直接主生成链"],
        outputs=["pptx 增强（动画/分组/连线）", "out/*.pdf / *.png"],
        exits=(0, 5),
        script="scripts/com_layer.py",
        entry="win_py -X utf8 scripts/build_ppt.py spec.yaml --com [--com-strict]",
    ),
    dict(
        id="typst_block",
        name="typst 复杂精美排版块（type:typst）",
        trigger="示意图/复杂排版：多栏、表格、数学、ceTZ 矢量图",
        preconditions=["typst.exe 0.15.x 在场（scripts/typst-cli/）", "块须顶层声明（不进 children）"],
        excludes=["main_generation"],
        exclude_conditions=["需要逐字可编辑的纯文本 → 用 Office 原生形状（typst 整块为图）",
                            "需要数据图 → 用 chart（原生图表零 COM）；typst 不做数据可视化"],
        outputs=["out/typst/*.svg（OOXML 2016+ 矢量）+ *.png（全版本回退）"],
        exits=(0, 2),
        script="scripts/typst_compile.py",
        entry="（build_ppt stage1.5 自动；手动验证 win_py -X utf8 scripts/typst_compile.py …）",
    ),
    dict(
        id="page_intent",
        name="页型意图破格版式（cover/section/problem/versus/route）",
        trigger="多页 deck 需破格封面/节标题/科研页（审定菜单：agent 只选 intent token）",
        preconditions=["meta.slides 多页序列",
                       "intent ∈ implemented（cover/section/problem/versus/route/content）"],
        excludes=["com_postprocess"],
        exclude_conditions=["单页模式声明 page_intent → 编译拒（意图是多页版面语义）",
                            "planned 页型（data/compare/conclusion/quote）→ 编译拒（fail-closed）"],
        outputs=["cov_* / sec_* / prb_* / vsv_* / rte_* 引擎展开元素（IR + verify S6 断言背书）"],
        exits=(0, 2, 3),
        script="scripts/ir_builder.py",
        entry="（页级 slides[i].page_intent；语法见 references/page-intents.md）",
    ),
    dict(
        id="template_extract",
        name="模板风格卡提炼（extract）",
        trigger="有模板 pptx，提炼风格卡（尺寸/主题色/字族/母版占位符）",
        preconditions=["模板 pptx 文件在场"],
        excludes=["template_seed"],
        exclude_conditions=["只想沿用模板母版直接出图 → 走 seed 打底，不必先 extract"],
        outputs=["templates/stylecards/<name>.json"],
        exits=(0, 2),
        script="scripts/template_analyzer.py",
        entry="win_py -X utf8 scripts/template_analyzer.py extract <pptx> --out …",
    ),
    dict(
        id="template_seed",
        name="模板打底生成（seed）",
        trigger="用模板母版样式作为画布垫底出图",
        preconditions=["模板/风格卡在场（seed 打底在编译期注入 params.font 双轨）"],
        excludes=["template_extract"],
        exclude_conditions=["seed + 全局 framework.background → 全画布遮挡母版背景（告警，特例页用页级覆盖）"],
        outputs=["out/base.pptx（带母版占位符落点）"],
        exits=(0, 2, 3, 4),
        script="scripts/build_ppt.py",
        entry="win_py -X utf8 scripts/build_ppt.py spec.yaml --seed <template>",
    ),
    dict(
        id="anim_inject",
        name="页级动画批量注入",
        trigger="已有 SPEC/pptx，原子性批量注动画（幂等/CRLF 保留/四段批次）",
        preconditions=["SPEC YAML 在场"],
        excludes=[],
        exclude_conditions=["容器（stack/dock/graph）不产单形状 → 跳过（脚本内建）"],
        outputs=["回写 SPEC（动画段注入）"],
        exits=(0,),
        script="scripts/anim_inject.py",
        entry="win_py -X utf8 scripts/anim_inject.py --spec X.yaml --seed",
    ),
]

_ROUTE_IDS = [r["id"] for r in ROUTES]


def by_id(rid):
    return next((r for r in ROUTES if r["id"] == rid), None)


def validate():
    """机器校验：id 唯一 / script 存在 / exits ∈ 契约 / excludes 引用有效路由 /
    无自引用 / 关键字段非空。返回问题列表（空 = 全部通过）。"""
    problems = []
    seen = set()
    for r in ROUTES:
        rid = r["id"]
        if rid in seen:
            problems.append(f"路由 id 重复: {rid}")
        seen.add(rid)
        if not all(r.get(k) for k in ("id", "name", "trigger", "outputs", "script")):
            problems.append(f"{rid}: 关键字段（id/name/trigger/outputs/script）缺失")
        for ex in r.get("excludes") or []:
            if ex == rid:
                problems.append(f"{rid}: excludes 自引用 {ex}")
            elif ex not in _ROUTE_IDS:
                problems.append(f"{rid}: excludes 引用未知路由 {ex!r}")
        if not set(r.get("exits") or ()) <= set(ROUTE_EXITS):
            problems.append(f"{rid}: exits 越出契约 {ROUTE_EXITS}")
        script = os.path.join(_REPO_ROOT, r["script"])
        if not os.path.isfile(script):
            problems.append(f"{rid}: script 不存在 {r['script']}")
    return problems


if __name__ == "__main__":
    import sys
    problems = validate()
    if problems:
        print("routes.py 校验失败:")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print(f"routes.py 校验通过（{len(ROUTES)} 条路由）")