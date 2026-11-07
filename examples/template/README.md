# 模板素材示例（meta.template —— 母版版式的「提炼 / 打底」两条腿）

场景：手里有一份心仪的模板 / 成品 deck，想让新产物继承它的设计语言。

素材说明：本示例的 `brand.pptx`（10×5 in · 主题 accent1 #2D6CDF · 母版背景
#EAF1F9 · 母版 5 占位符 + 11 版式）由 `examples/template/gen_brand.py` 生成，
可随时再生成/改名复刻自己的品牌基底（改底色/品牌色/尺寸/版式）；模板自带的
两页示例仅用于演示 seed 的剥页行为。生成器内含一条实证坑的防御：母版 `p:bg`
必须唯一（默认模板自带 bgRef，硬插第二个 bg → 0x80070570 文档损坏）。

1. 先收集风格卡（只读，零写入模板，无 Office 亦可）：

   ```bash
   win_py -X utf8 -W ignore scripts/template_analyzer.py brand.pptx
   ```

   产出 `brand.stylecard.json`（机器用）+ `brand.stylecard.md`（人读摘要）。

2. **extract —— 提炼**：样式卡事实按 `meta.template.keys` 注入
   （slide/palette/framework/params，fill-only：agent 显式声明优先）：

   ```bash
   win_py -X utf8 -W ignore scripts/build_ppt.py examples/template/extract.yaml --out out_extract --com
   ```

   - slide ← 模板尺寸（10×5）；palette 注入 accent1..6/dk1/lt1/dk2/lt2；
   - framework.background ← 母版底色（solid 取色 / grad 取两色 / 否则主题 lt1）；
   - params.font ← 模板字族双轨（latin + ea）；主题槽在渲染后写回 theme1.xml，
     新建形状 / 图表默认色 / 取色器即品牌色（物证「主题槽注入」背书）。

3. **seed —— 打底**：以模板为渲染基底，元素级 `ph` 字段填充模板占位符：

   ```bash
   win_py -X utf8 -W ignore scripts/build_ppt.py examples/template/seed.yaml --out out_seed --com
   ```

   - 渲染器 `add_slide(选中版式)`；`ph: 0` / `ph: "Title 1"` 匹配占位符
     （仅 text 元素；不进 glue/overlap/z_override；rect 仍必须声明，仅作文本测量）；
   - 模板层（母版/版式几何、占位符样式）豁免 G/D/T 校验——不进 IR；
     SPEC 层（text 测量/文本校验）照常。

验收：exit 0 + 物证全过；`out_*/preview.png` 请用户目视复核品牌一致性。

新版式先跑 `scripts/template_analyzer.py` 收卡，边界见 references/stylecard.md。