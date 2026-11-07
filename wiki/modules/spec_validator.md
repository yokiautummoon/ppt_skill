---
tags: [module]
module: spec_validator
parent: build_ppt
depends_on:
  - params
updated: 2026-09-30
---

# spec_validator — 白名单静态校验

PER_TYPE/COMMON_FIELDS 白名单：未知字段、未声明 palette token、非法 rect、动画字段、framework 键、`meta.brief`（意图上下文）、`type:typst`（`typst`/`typst_src`/`design`/`preamble`/`vars`）等。返回 violation 列表；不炸则给 verify 兜底。

- **scansci 内化**：`PER_TYPE["shape"]` 白名单新增 `anchors`（具名锚点
  [nx,ny]∈[0,1]²，块 1）；glue `from_anchor`/`to_anchor` 属 relations 语义由
  spec_compile 收紧，validator 不重复检查。