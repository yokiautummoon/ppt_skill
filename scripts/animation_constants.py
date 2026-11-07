# -*- coding: utf-8 -*-
"""animation_constants.py — PowerPoint 动画 COM 常量（probe 实测背书）。

取常量策略：先尝试 win32com 类型库 constants 按名取（版本精确）；
类型库未加载/缺名 → 回退硬编码表（PowerPoint 16.0 + win32com 实测，
见 _probe/anim_const_probe.py）。com_layer 在 EnsureDispatch 后调 resolve()
一次缓存。无 Office 的 CI/测试环境导入本模块不炸（win32com import 包 try），
可确定性断言回退表值。

实测值（PowerPoint 16.0）：
  MsoAnimType   Set=8 Filter=7 Property=5 Rotation=4 Scale=3 Motion=1 None=0
  MsoAnimEffect Custom=0；预设基座（AddEffect 用 presetID≠0 才被 WPS 认）：
                Appear=1 Fade=10 Zoom=23 Bounce=27 GrowShrink=29 Spin=31
                Pulse=34（COM 批测全接受；自带 behaviors 均以 set 可见开头）
  MsoAnimProperty Visibility=8 X=1 Y=2 Width=3 Height=4 Rotation=6
  MsoAnimFilterEffectType Fade=8
  MsoAnimTriggerType WithPrevious=2
  MsoAnimateByLevel Paragraph=0 Character=2
  MsoTriState   msoTrue=-1 msoFalse=0（在 Office 共享类型库，PowerPoint
                typelib 不含 → 恒走硬编码）
"""
try:
    from win32com.client import constants as _TYPELIB
except Exception:                       # 无 win32com（Linux CI / 精简环境）
    _TYPELIB = None

# 硬编码回退表（键 = COM 常量名；值 = 实测）
_FALLBACK = {
    "msoAnimTypeSet": 8, "msoAnimTypeFilter": 7, "msoAnimTypeProperty": 5,
    "msoAnimTypeRotation": 4, "msoAnimTypeScale": 3, "msoAnimTypeMotion": 1,
    "msoAnimTypeNone": 0,
    "msoAnimEffectCustom": 0,
    # 预设基座（WPS 只认 presetID≠0 的效果——根因见 animation.md）
    "msoAnimEffectAppear": 1, "msoAnimEffectFade": 10,
    "msoAnimEffectZoom": 23, "msoAnimEffectBounce": 27,
    "msoAnimEffectGrowShrink": 29, "msoAnimEffectSpin": 31,
    "msoAnimEffectPulse": 34,
    "msoAnimVisibility": 8, "msoAnimX": 1, "msoAnimY": 2,
    "msoAnimWidth": 3, "msoAnimHeight": 4, "msoAnimRotation": 6,
    "msoAnimFilterEffectTypeFade": 8,
    "msoAnimTriggerOnPageClick": 1,
    "msoAnimTriggerWithPrevious": 2,
    "msoAnimTriggerAfterPrevious": 3,
    "ppAnimateByParagraph": 0, "ppAnimateByCharacter": 2,
    # MsoTriState（Office 共享类型库，标准值）
    "msoTrue": -1, "msoFalse": 0, "msoCTrue": 1, "msoTriStateMixed": -2,
}

# 内部名 → COM 常量名（com_layer 用短名，配方数据不碰 COM 名）
_ALIAS = {
    "type.set": "msoAnimTypeSet", "type.filter": "msoAnimTypeFilter",
    "type.property": "msoAnimTypeProperty", "type.rotation": "msoAnimTypeRotation",
    "type.scale": "msoAnimTypeScale", "type.motion": "msoAnimTypeMotion",
    "type.none": "msoAnimTypeNone",
    "effect.custom": "msoAnimEffectCustom",
    "effect.appear": "msoAnimEffectAppear", "effect.fade": "msoAnimEffectFade",
    "effect.zoom": "msoAnimEffectZoom", "effect.bounce": "msoAnimEffectBounce",
    "effect.grow_shrink": "msoAnimEffectGrowShrink",
    "effect.spin": "msoAnimEffectSpin", "effect.pulse": "msoAnimEffectPulse",
    "prop.visibility": "msoAnimVisibility", "prop.x": "msoAnimX",
    "prop.y": "msoAnimY", "prop.width": "msoAnimWidth",
    "prop.height": "msoAnimHeight", "prop.rotation": "msoAnimRotation",
    "filter.fade": "msoAnimFilterEffectTypeFade",
    "trigger.on_click": "msoAnimTriggerOnPageClick",
    "trigger.with_previous": "msoAnimTriggerWithPrevious",
    "trigger.after_previous": "msoAnimTriggerAfterPrevious",
    "level.paragraph": "ppAnimateByParagraph",
    "level.character": "ppAnimateByCharacter",
    "tri.true": "msoTrue", "tri.false": "msoFalse",
    "tri.ctrue": "msoCTrue", "tri.mixed": "msoTriStateMixed",
}

_VALUES = None


def resolve():
    """返回 {COM 常量名: int} 全表（首次惰性探测，此后缓存）。"""
    global _VALUES
    if _VALUES is None:
        _VALUES = {}
        for n, fb in _FALLBACK.items():
            v = fb
            if _TYPELIB is not None:
                try:
                    v = int(getattr(_TYPELIB, n))
                except Exception:
                    pass
            _VALUES[n] = v
    return _VALUES


def C(name):
    """内部短名取常量：C("type.set") / C("prop.visibility")…"""
    return resolve()[_ALIAS.get(name, name)]