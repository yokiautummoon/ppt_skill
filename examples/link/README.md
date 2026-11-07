# 元素级超链接（link）积木示例

`link.yaml` 演示元素级超链接：任意非容器元素挂 `link: {url|slide|email}`
（三选一），渲染注入 `cNvPr` 下 `a:hlinkClick`（零 COM）。

```bash
win_py -X utf8 -W ignore scripts/build_ppt.py examples/link/link.yaml --out out_link
```

- `url` 外部链接（https://…）；`email` 自动加 `mailto:` 前缀；
  `slide` 页内跳转（1-based 页号）——渲染产 slide part rel + command（
  `action="ppaction://hlinksldjump"`，PowerPoint「本文档中的位置」原生格式）。
- 编译期契约：`slide` 目标越界（> 总页数）或指向本页（恒等自跳，无意义）
  → 编译错 exit 2；`url|slide|email` 必须且仅声明其一。
- 容器（stack/dock/graph）不产形状、无从挂 `hlinkClick` → 编译错；
  children 形状可挂（随容器求解出 rect 后同律注入）；
  seed 打底的 ph 占位符填充不支持 link（文本写入模板占位符）。
- 物证每链接一条「链接目标」：按 `cNvPr/a:hlinkClick@r:id` 解析 rel——
  外部 rel 核对原始 Target == `url` / `mailto:{email}`；内部 rel 核对目标
  part 文件名 == `slide{N}.xml`。