# 页码偏移（page_offset）积木示例

`pageoffset.yaml` 演示页脚页码偏移 + 页级 footer 清空：封面不计页码、正文
从「第 1 页」起编号。

```bash
win_py -X utf8 -W ignore scripts/build_ppt.py examples/pageoffset/pageoffset.yaml --out out_pageoffset
```

- 显示页码 = 实际页号 + `params.framework.page_offset`。示例 `offset=-1`：
  实际第 2/3/4 页的页脚显示「第 1/2/3 页」，封面不占号。
- 页级 `framework: {footer: {text: ""}}` 清空该页页脚（封面无页脚）——
  框架层按页合并（build_pages 语义），全局 footer 声明 + 页级覆盖。
- `page_offset` 必须是整数（可正可负）：正数前移、负数后移页码。
  非整数（如 `0.5`）或布尔 → 编译错 exit 2（页码是整数语义，不让出
  「第 2.5 页」这类怪象）。
- 全局页脚声明在 `meta.framework.footer`，`{page}` 占位符逐页展开；
  渲染与物证同规（同一表达式），物证按页核对展开后的文本。

参考 `examples/deck/`：多页序列 + 全局框架层 + 页级覆盖的完整用法。