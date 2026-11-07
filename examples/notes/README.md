# 备注页（speaker notes）积木示例

`notes.yaml` 演示页级备注：渲染器把 `slides[i].notes`（或单页模式 `meta.notes`）
写入 notes_slide 部件——演讲者视图可见，纯渲染零 COM。

```bash
win_py -X utf8 -W ignore scripts/build_ppt.py examples/notes/notes.yaml --out out_notes
```

- 多行备注用 YAML 块标量（`|`），渲染为 notes 多段（每行一段 run）+ 字号走
  `params.text.notes_fs`（默认 12pt，`meta.params` 可覆盖）。
- 无备注的页不建 notes part（本例页 1）；物证每页一条「备注页」核对
  slide rel → notesSlide part 文本 == SPEC notes（去换行）。
- 备注页不进 IR 几何（不占 spTree、不参与 G/T/D 校验）——与 framework 同地位，
  只是内容而非布局。