# 模板风格卡（stylecard）——母版版式「提炼」侧的基石

## 定位

只读分析模板 / 成品 .pptx 的机器可读事实：产出 `stylecard.json`（机器用：
后续 extract 注入 / agent 决策）+ `stylecard.md`（人读报告）。
零写入模板、零 COM、零渲染模型改动；母版版式的「提炼 / 模仿」两条能力
都从这里起步（analyzer → 事实；agent + 用户 → 取舍；extract/seed → 落地）。

## 命令

```bash
win_py scripts/template_analyzer.py <模板|成品.pptx> [--out DIR]
# 默认输出到模板所在目录：<名>.stylecard.json + <名>.stylecard.md
# exit 0 收卡成功（容错项不阻断）；1 IO/参数；2 包不可读
```

## 提取事实

| 域 | 内容 | 用途 |
|---|---|---|
| `slide` | 页面尺寸（EMU→英寸） | meta.slide 原料 |
| `theme.colors` | clrScheme 色槽：`dk1/lt1/dk2/lt2` + `accent1..6`，归一 `#RRGGBB` | palette 原料 |
| `theme.fonts` | 字族 major/minor 的 latin + ea（双轨原料） | params 字族 |
| `masters / layouts` | 母版与版式：占位符 idx/type/name/几何、背景形态 solid/grad/pic/inherit | seed 打底、framework 参考 |
| `pages` | 成品 deck 逐页引用的版式名 | 模仿场景（用户给心仪 deck） |
| `pitfalls` | 容错项：损坏 part、图片背景、多主题… 不阻断收卡 | agent 取舍信号 |

## 用途（后续批次）

1. **提炼（extract）**：stylecard 的 slide/colors/fonts → 自动灌进
   meta.framework / palette / params（agent 显式覆盖优先）。
2. **打底（seed）**：layout 占位符几何 + 页映射 → 以模板为渲染基底，
   SPEC 元素覆盖到具体页（模板层豁免校验，SPEC 层照常）。
3. **agent 决策**：用户给一份心仪的 deck？先 analyzer 收卡 → 摘要给用户看
   → 按意愿把事实写进 SPEC。

## 边界

- 不做视觉判断：只爬梳可机器阅读的事实；审美取舍归 agent + 用户。
- 图片背景只记占位（`kind: pic` + media 名），不做裁图。
- `sysClr` 用 `lastClr` 归一；无 lastClr 的保留 `{type, val}` 由 agent 决策。
- 多主题 part / 无主题 / 图片背景等均降级记录，不阻断收卡。