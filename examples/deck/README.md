# 多页序列示例（meta.slides）

演示/课件/宣讲/汇报的长页制作能力：一个 SPEC 产出多张 slide 的 base.pptx。

## 本示例 3 页

| 页 | 标题 | 图面积木 |
|---|---|---|
| 1 | 封面 | text（大标题/副标题/日期）+ 装饰色带 shape |
| 2 | 议程 | 原生表格（table，data 推导行列） |
| 3 | 关键指标 | 原生图表（chart column_clustered）+ 指标卡片（stack 容器） |

## 多页语法要点

```yaml
meta:
  margin: {l: 0.6, t: 0.6, r: 0.6, b: 0.6}        # 全局打底
  framework:                                     # 全局框架层（三页共用）
    background: {fill: {grad: [...]}}
    header: {text: "...", align: right}
    footer: {text: "机密 · 第 {page} 页", ...}    # {page} 逐页展开
  slides:                                        # 每个元素一页
    - title: 封面                                 # 可选页标题（报告里显示）
      elements: [...]                            # 该页元素
      relations: {...}                           # 可选；页内引用自洽
      margin: {...}                              # 可选页级覆盖
      framework: {...}                           # 可选页级覆盖（dict 合并）
```

- 顶层 `elements`/`relations` 在多页模式须移入各页（编译期拦截）。
- `palette` 全局共享；元素 id 唯一作用域 = 页内（跨页互不感知）。
- 遮挡/安全区校验按页隔离：页 3 的面板与页 2 的表格互不干扰。
- footer 的 `{page}` 占位符按实际页号展开（第 1 页 = 1 …），渲染与 XML 物证同规则。

## 运行

```bash
win_py scripts/build_ppt.py examples/deck/deck.yaml --out examples/deck/out
# exit 0；out/base.pptx 含 3 页；out/report.md 逐页校验清单
win_py scripts/build_ppt.py examples/deck/deck.yaml --out examples/deck/out --com
# 追加 COM：逐页导出 preview.png / preview-2.png / preview-3.png
```

## 跟你自己的 SPEC 对照

- 页数上限无硬性限制；每页独立通过 G/D/T/S 校验，任一页违规 → exit 3。
- ir.json 多页时写为列表（com_layer 按页遍历 Slides(i+1)）；单页仍写 dict。