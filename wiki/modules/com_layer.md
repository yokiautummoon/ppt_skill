---
tags: [module]
module: com_layer
parent: build_ppt
depends_on:
  - formula_omml
  - formula_templates
  - animation_constants
  - animation_recipes
  - anim_group
  - omml_engine
updated: 2026-09-30
---

# com_layer — COM 后处理

win_py 子进程（JSON job in/out，cwd=scripts/，路径全绝对）：glue BeginConnect/EndConnect 随动（站点表 SITE_BY_KIND）、Group 组合、OLE .vsdx 嵌入、动画时间轴实时构造（_apply_anims：AddEffect **PRESET_BASE 预设基座**/Custom 兜底 level=0 → behaviors → delete_first 删预设 set → text_unit）、公式 Word 批量兜底、PDF SaveAs 32、PNG 预览。失败 WARN 降级；--com-strict 才 exit 5。早退路径补满键骨架。

- **动画编排组（性质①）**：`_apply_anims` 按 `ir.anim_sequence`（AddEffect 全局
  按 start 稳定排序序）逐叶构造效果，锚定触发（with_previous → TriggerDelay 前驱
  start；after_previous → 前驱 end）；构造后 `_check_timeline_after` COM 回读比对
  `EffectInformation.TriggerDelayTime`（绝对秒）与 `ir.anim_timeline` 叶 start，
  超 0.02s → WARN（时间轴确定性回读背书）。
- **具名锚点偏移披露（scansci 内化块 1）**：具名锚点 glue（IR 含 `an1`）绑定
  就近站点后，把锚点绝对位（英寸 ×72 → pt，与 COM Shape 坐标同单位）与 from
  端站点中点比对，偏差 >0.25in=18pt → WARN（披露性，不阻断——绑定仍走就近站点）。
- **编辑单元组（scansci 内化块 2）**：组循环泛化为读 `ir.edit_groups`（显式
  relations.edit_groups + 容器 group:true 并组同源），逐组
  `Shapes.Range([...]).Group()` 命名 `{id}.group`，组区间 z_lo/z_hi 记入
  com_out；跑完披露「spTree 结构变更，XML 物证以组为单位复核」（不阻断）。
- **文本溢出真实回读（B4，第二来源）**：逐页对带文本形状读 `TextFrame2.TextRange.BoundHeight`
  （PowerPoint 实高）vs `TextFrame2.BoundHeight`（框内高），超 `com.overflow_tol_pt`（默认 1.0pt）
  → 记 `overflow:[{id,page,text_h,frame_h,over_pt}]` + WARN（不阻断）。离线 textmesh 估算是
  第一来源（渲染期 autofit），此处为 PowerPoint 自身度量的实证背书。
- **字体嵌入请求（B5）**：job.embed_fonts=true 时置位 `pres.EmbedTrueTypeFonts=True`
  并记 declared 字族清单；Save 后 `_scan_embedded_fonts` 扫包 `ppt/fonts/*.fntdata`。
  实测自动化路径不产嵌入字体（Save/SaveAs 位置参/WithWindow/SaveSubsetFonts 变体均无效，
  见 references/ooxml-notes.md §15）→ 无产物则记 `fonts.empty_reason="no_fntdata"` + WARN
  （不阻断；--com-strict 升级 exit 5）。语义 = 请求 + 诚实核对，跨机可移植靠通用字族 +
  `font.portable_list` 人工确认清单。输出 `fonts:{requested,declared,embedded,empty_reason}`。
- 公式兜底（omml_engine Word 批量）与动画时间轴同属 COM 作业，JSON job 键骨架
  缺省补满（早退路径不泄漏 None）。