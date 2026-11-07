---
tags: [module]
module: animation_recipes
depends_on: []
updated: 2026-09-10
---

# animation_recipes — 安逸动画库 35 宏配方

RECIPES 数据集：enter 15 / persist 5 / emphasize 3 / exit 12，含 category/desc/dur/repeat/timing/behaviors（set·filter·property·scale·rotation·motion 六类）/delete_first/text_unit/notes。截断宏 `退出动画_先淡入后淡出_fanbal`（source_truncated=True）。selfcheck() 静态自检（字段白名单、property 必须 points）——`win_py scripts/animation_recipes.py` 直跑。

PRESET_BASE：35 宏 → 预设基座表（enter→fade/zoom/bounce/spin、persist→grow_shrink/spin、emphasize→grow_shrink/spin、exit→fade；白名单 {fade, zoom, bounce, grow_shrink, spin, pulse}）。com_layer AddEffect 用预设而非 Custom=0——**WPS 只播 presetID≠0**（插件版产物即预设基座 + set + 叠加，2026-09 根因定位，见 references/animation.md）；selfcheck 校验键数与白名单。