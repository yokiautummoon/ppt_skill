---
tags: [module]
module: params
depends_on: []
updated: 2026-09-14
---

# params — 参数合并数值接口（配置栈）

文本/边/组/公式/表格/遮挡/COM（dispatch 重试）等数值接口全在 DEFAULTS——
单一事实源、无散落硬编码（数值接口铁律）。合并为**配置栈**（性质③：JAnim
utils/config.py 分层回退移植），统一链：

```
DEFAULTS → meta.params（全局层）→ slides[i].params（页级层）→ --param 覆盖（CLI 层）
```

- `resolve(meta_params, page_params, overrides)`：逐层深覆盖已存在键、未知键报错
  （同一 `_merge` 原语，无手写分支）；返回 DEFAULTS 深拷贝，层间不污染。
- `layer_merge(base, override, path)`：层级间统一深覆盖原语（margin/framework
  的『全局打底 + 页级覆盖』也走此，消除 build_ppt 手写浅 merge——页级只覆盖
  部分键时其余显式值保留，而非静默回退默认）。framework 段（background/
  header/footer）是可新增配置单元，build_pages 对其用宽松深合并（段内键集合
  由 spec_compile 白名单守住）。
- **页级 p 贯穿全链路**：build_pages 存 `shim["_p"]`，ir_builder 布局、
  verify 断言、render_pptx 渲染、render_check_xml 物证按页取 p（页级 params
  是"参数旋钮"的页级化：字号硬底/表格 pad/eps 等逐页可调）。
- **CLI `--param key=value`**（可重复，last-wins）：值按 YAML 类型化
  （true/false/数字/字符串），路径 `font.latin=Times New Roman` 拆为嵌套；
  临时调参不改 SPEC。
- **修订器覆盖** = 修订链写回 SPEC：meta.params 本属 revisioner 可改结构，
  自然生效于上游层（无需单独覆盖层）。
- template extract 在编译期注入 params.font（模板字族双轨，fill-only）——
  注入发生在全局层之前。
- **排版/版式阈值**（批次 1 A1/A2/A3 内化）：`verify.typography`
  （`max_emphasis` / `max_title_cjk` / `body_chars_max` / `body_chars_min` /
  `title_fs_min`）与 `verify.layout_variety`（`min_pages` / `min_distinct` /
  `distinct_ratio` / `max_same` / `grid` / `min_area_ratio`）同属数值接口，
  可经配置栈逐页/全局覆盖；推荐值见 `styleguides.QUANTITATIVE` 与
  references/design-norms.md。`style.emphasis`（行内 `[[强调]]` 色）亦在此层。
- **图片占位**（批次 2 B3）：`images.*`（`strict` / `prompt_file` /
  `placeholder_fill` / `placeholder_border` / `placeholder_fs` / `missing_key`）
  控制缺图降级与提示清单；`--strict-images` 等价 `--param images.strict=true`。
- **文本溢出回读容差**（批次 2 B4）：`com.overflow_tol_pt`（默认 1.0pt）——COM
  TextFrame2 实高超出文本框内高超过此值即记 overflow + WARN（第二来源实证）。
- **字体可移植**（批次 2 B5）：`font.portable`（bool，请求 COM 端嵌入，隐含进入
  stage6）+ `font.portable_list`（交付前需人工确认在目标机可用的字族清单）；
  `--embed-fonts` 等价 `--param font.portable=true`。实测自动化路径不产 fntdata →
  WARN 诚实降级（见 references/ooxml-notes.md §15、wiki/modules/com_layer.md）。

单测 tests/test_params_stack.py（10 项）+ tests/test_deck_rules.py（A1/A2/A3
契约 41 项）+ tests/test_images.py（B3 契约 25 项）+ tests/test_font_embed.py
（B5 契约 15 项）+ tests/test_overflow_readback.py（B4 契约 9 项）；语法见
references/spec-v2-language.md `meta.params` 行与 CLAUDE.md 「配置栈」概念。
