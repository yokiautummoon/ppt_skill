---
tags: [module]
module: build_ppt
parent: root
depends_on:
  - spec_compile
  - spec_validator
  - typst_compile
  - params
  - ir_builder
  - verify
  - attribution
  - spec_fixer
  - revisioner
  - llm_fixer
  - report
  - render_pptx
  - render_check_xml
  - com_layer
updated: 2026-09-14
---

# build_ppt — 管道编排 CLI

stage0 load → stage1 compile+validate（exit 2）→ **stage1.5 typst 编译**（有 `type:typst` 元素时调 typst_compile.compile_all，语法错误 → exit 2）→ stage2 ir_builder → stage3 verify（exit 3）→ stage4 render_pptx（exit 4）→ stage5 render_check_xml 物证（exit 4）→ stage6 可选 com_layer（--com / --com-strict exit 5）。出口码契约即 skill 铁证链的闸门。

`--fix` 修订循环（`_check` 抽取 + `_fix_loop`）：校验失败 → attribution 归因 →
spec_fixer 机械 R1–R4 / llm_fixer 作业模式 → 事务快照 → 写回 → 回环重跑。
出口 **0 收敛 / 3 不可修·超限 / 4 internal 停机 / 6 需 LLM 稳态暂停**（写
llm_job.json，回填 llm_out.json 后重跑同命令）；`--revert` 恢复最近 `.snap.N`。
详见 wiki/runbooks/fix-loop.md。

- **配置栈（性质③）**：`build_pages(compiled, overrides)` 统一完成全局→页级合并
  （margin/framework 键级 dict 合并，framework 段用宽松 `_fw_merge`——内部键集
  由 spec_compile 白名单守）+ 逐页 `shim["_p"] =
  params.resolve(全局 meta.params, 页级 slides[i].params, overrides)`；
  p 的 page 级穿透全链路：ir_builder/verify/render_pptx(pps)/render_check_xml
  逐页取 p。CLI `--param key=value`（可重复，last-wins）经 `_parse_param_overrides`
  解析为嵌套 dict，YAML 类型化；页级 params 是参数旋钮的页级化（字号硬底/
  table pad/eps 逐页可调）。详见 wiki/modules/params.md。
- render 逐页 p 列表 `pps = [pg["_p"] for pg in pages]` 传给 render_pptx；
  stage5 物证按 `zip(irs, pages)` 逐页核对（ir / p / 页级 anim 编排组时间轴）。