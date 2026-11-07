# 操作路由表（Route Registry）—— 防误路由 + 协议显式化

> 借鉴 EasySlides workflow registry 的四列：**Trigger / Preconditions /
> Route-exclusion / Output-contract**。本表声明每种操作入口"何时该走、前置、
> **何时不许走**、承诺产出"。机器校验：`scripts/routes.py validate()`（唯一
> 事实源）；本表是人读同步版，`tests/test_routes.py` 卡两者一致。

## 总则（所有路由共享的禁止条件）

- **不手改产物 pptx/XML**——一下动 z/锚点就改 SPEC 重跑（铁律）。
- **不静默降级**——能力不支持就让编译期拒绝（capabilities.py fail-closed），
  不靠"字段合法却什么也没发生"糊弄。
- **数据红线**——LLM 改 data/categories/series 须溯源 brief 原文或标 `[占位]`，
  禁止编造（CHECK_OUT 强制，exit 3 整批拒绝）。
- **internal 归因停机**——引擎算法 bug 不修 SPEC、不喂 LLM（exit 4）。

## 路由一览

| id | 名称 | 出口码 | 脚本 |
|---|---|---|---|
| `main_generation` | 主生成链（SPEC → base.pptx） | 0/2/3/4 | build_ppt.py |
| `fix_loop` | --fix 自优修订链 | 0/3/4/6 | build_ppt.py |
| `com_postprocess` | COM 后处理 | 0/5 | com_layer.py |
| `typst_block` | typst 复杂排版块 | 0/2 | typst_compile.py |
| `page_intent` | 页型意图破格版式（cover/section/problem/versus/route） | 0/2/3 | ir_builder.py |
| `template_extract` | 模板风格卡提炼 | 0/2 | template_analyzer.py |
| `template_seed` | 模板打底生成 | 0/2/3/4 | build_ppt.py |
| `anim_inject` | 页级动画批量注入 | 0 | anim_inject.py |

---

### main_generation —— 主生成链（SPEC → base.pptx）

- **Trigger**：从零生成 / 给定 SPEC YAML 出可编辑 pptx。
- **Preconditions**：SPEC 存在且 style_guide 合法；产物须原生可编辑。
- **禁止条件（Route-exclusion）**：
  - 源是幻灯片截图/AI 稿 → 本项目不做图片重建（EasySlides 才做）。
  - 已有成品只补备注/音频/时间 → 改 SPEC 重跑全链（不手改产物）。
  - 批注动画 → 走 `anim_inject`（原子性四段批次）。
- **Output-contract**：out/base.pptx、out/ir.json、out/report.md、out/evidence/ 物证。

### fix_loop —— --fix 自优修订链

- **Trigger**：校验违规需自动收敛（R1–R4 机械动作 / LLM 语义修订）。
- **Preconditions**：build_ppt 可运行；违规归因非 internal。
- **禁止条件**：internal 归因（引擎 bug）停机不修；数据字段无据可溯 → 数据红线整批拒绝。
- **Output-contract**：out/llm_job.json / llm_out.json、fix.diff、.snap.N 快照。
- **出口码**：0 收敛 / 3 建议人工 / 4 internal 停机 / 6 LLM 稳态暂停（回填 llm_out.json 后重跑同命令继续）。

### com_postprocess —— COM 后处理（glue/Group/OLE/动画/PDF/PNG）

- **Trigger**：需 COM 真能力（连线/Office Group/OLE/动画时间轴/PDF/PNG）。
- **Preconditions**：Windows + Office 安装；POWERPNT.EXE 无驻留 GUI 实例（瞬态 Dispatch 失败先 taskkill 重试）。
- **禁止条件**：chart/formula 有零 COM 路径 → 不必要不加 --com；仅纯文本/表格/图表 → 不需要 COM。
- **Output-contract**：pptx 增强（动画/分组/连线）、out/*.pdf / *.png。WARN 降级仅 --com-strict 才 exit 5。

### typst_block —— typst 复杂精美排版块（type:typst）

- **Trigger**：示意图/复杂排版：多栏、表格、数学、ceTZ 矢量图。
- **Preconditions**：typst.exe 0.15.x 在场（scripts/typst-cli/）；块须顶层声明（不进 children）。
- **禁止条件**：需要逐字可编辑的纯文本 → 用 Office 原生形状（typst 整块为图）；需要数据图 → 用 chart（原生图表零 COM）。
- **Output-contract**：out/typst/*.svg（OOXML 2016+ 矢量）+ *.png（全版本回退）；页面尺寸 = 元素 rect 1:1（铁律 1 的排版块对应物）。

### page_intent —— 页型意图破格版式（cover/section/problem/versus/route）

- **Trigger**：多页 deck 需破格封面/节标题/科研页（审定菜单：agent 只选 intent token）。
- **Preconditions**：meta.slides 多页序列；intent ∈ implemented（cover/section/problem/versus/route/content）。
- **禁止条件**：单页模式声明 page_intent → 编译拒（意图是多页版面语义）；planned 页型（data/compare/conclusion/quote）→ 编译拒（fail-closed，防静默 no-op）。
- **Output-contract**：cov_* / sec_* / prb_* / vsv_* / rte_* 引擎展开元素（IR + verify S6 断言背书）。
- 落地协议：references/page-intents.md §扩展新原型（每原型 = 布局代码 + verify 断言）。

### template_extract —— 模板风格卡提炼（extract）

- **Trigger**：有模板 pptx，提炼风格卡（尺寸/主题色/字族/母版占位符）。
- **Preconditions**：模板 pptx 文件在场。
- **禁止条件**：只想沿用模板母版直接出图 → 走 `template_seed`，不必先 extract。
- **Output-contract**：templates/stylecards/<name>.json。

### template_seed —— 模板打底生成（seed）

- **Trigger**：用模板母版样式作为画布垫底出图。
- **Preconditions**：模板/风格卡在场（seed 打底在编译期注入 params.font 双轨）。
- **禁止条件**：seed + 全局 framework.background → 全画布遮挡母版背景（告警；特例页用页级覆盖）。
- **Output-contract**：out/base.pptx（带母版占位符落点）。

### anim_inject —— 页级动画批量注入

- **Trigger**：已有 SPEC/pptx，原子性批量注动画（幂等/CRLF 保留/四段批次）。
- **Preconditions**：SPEC YAML 在场（官方工具，不手改）。
- **禁止条件**：容器（stack/dock/graph）不产单形状 → 跳过（脚本内建）。
- **Output-contract**：回写 SPEC（动画段注入）。

---

## 加新路由

1. `scripts/routes.py` 加条目（四列 + script/exits）；
2. 本表加同名小节（id 一字不差）；
3. `win_py -X utf8 tests/test_routes.py` 卡两者一致。