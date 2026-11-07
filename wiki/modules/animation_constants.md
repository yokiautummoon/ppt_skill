---
tags: [module]
module: animation_constants
depends_on: []
updated: 2026-09-10
---

# animation_constants — 动画 COM 常量

MsoAnimType/Effect/Property/FilterEffectType/TriggerType/AnimateByLevel/MsoTriState 实测值（PowerPoint 16.0）。取常量策略：win32com 类型库 constants 按名取优先（版本精确），缺名回退硬编码表；com_layer 经 C("type.set") 短名取值，配方数据不碰 COM 名。无 Office 环境导入不炸。

预设基座（MsoAnimEffect，2026-09 COM 批测 7 候选全接受）：Appear=1 Fade=10 Zoom=23 Bounce=27 GrowShrink=29 Spin=31 Pulse=34——AddEffect 用预设而非 Custom=0（presetID≠0 才被 WPS 认，见 references/animation.md「预设基座」节）；自带 behaviors 均以 set 可见开头（com_layer delete_first 删之）。OOXML presetID ≠ 枚举值：PowerPoint 语义化映射（本机：fade→10、bounce→26、grow_shrink→6、spin→8），产物只要求非零 + presetClass 正确。