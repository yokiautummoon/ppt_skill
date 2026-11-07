# scansci 经验内化实施计划（具名锚点 / 编辑单元 / 排版规则）

> 设计依据：`wiki/decisions/2026-09-30-internalize-scansci-design.md`（已批准）。
> 本计划 **不含 git 提交步骤**：项目目录非 git 仓库（环境说明），每 Task 的
> 收尾以「跑测试 + 记录变更」代替 commit。

**Goal:** 把 scansci-svg 三块经验（具名锚点 / 编辑单元分组 / 排版风格规则）内化到
ppt-builder 全链（SPEC→compile→IR→verify→render→COM→物证），MVP 一次落地。

**Architecture:** 三个内化块按风险递增序实施（块 3 风格规则 → 块 1 具名锚点 → 块 2
编辑单元）。每块保持铁律 1：几何/锚点/z 唯一源 = ir_builder；渲染与 COM 零重算；
verify 用第二实现独立重算；新字段全部可缺省（缺省 = 现状行为零变化）。

**Tech Stack:** 现有管道（spec_compile / spec_validator / ir_builder / verify /
render_pptx / render_check_xml / com_layer / styleguides / attribution），测试套件
（run_mutations / regression / 独立单测），执行器 win_py（Windows Python）。

## Global Constraints

- **铁律 1**：几何/锚点/z 只在 ir_builder 确定；渲染/COM 绝不重算；verify 对锚点/
  z 的检查必须独立重算（第二实现），不读 ir 的现成值断言。
- **缺省不变原则**：新字段（anchors/from_anchor/to_anchor/edit_groups）与 styleguides
  新键（size_fs_floor/labels_follow）不声明时，行为与现状完全一致——现有 115 突变/
  24 回归/46 模板等全部保持绿。
- **文案即契约**：verify 新增 check 名与 attribution 归因子串**同步新增**（本计划
  已含归因配套）——未知 check 名默认归 FIXABLE+manual，进不了任何修链，必须显式归类。
- **测试命令**：一律 `win_py -X utf8 -W ignore tests/<file>.py`（脚本侧无 encode 参数
  时用 `-X utf8` 防 Windows 终端编码崩）。
- **单位换算**（写死在代码里，勿用魔法数变体）：1 in = 914400 EMU = 72 pt；
  EMU→pt 除 12700。
- **元素 id 命名冲突**：新字段不得占用元素 id / glue 字段既有名（anchors 是元素字段，
  an1/an2 是 glue 字段，edit_groups 是 relations 段名——均已核对无冲突）。
- **新语法零历史使用**：已 grep 全 scripts/ + examples/，`anchors`/`from_anchor`/
  `to_anchor`/`edit_groups` 均不存在 → 无既有回归受影响。

---

### Task 1: 块 3 —— 排版/风格规则（size_fs_floor + labels_follow）

**Files:**
- Modify: `scripts/styleguides.py`（模块 docstring 补可选键说明）
- Modify: `scripts/verify.py:424-554`（`_s_family` 内 S1b 之后插 S8/S9）
- Modify: `scripts/attribution.py:48-55`（`_ADVISORY_SUB` 补 2 子串）
- Create: `tests/test_style_rules.py`
- Modify: `tests/run_mutations.py`（对照循环后加规则注入 mutation 段）

**Interfaces:**
- Consumes: `verify._s_family(rep, rules, p, sv)` 既有签名；`ir["edit_groups"]`
  （Task 3 才产出；本 Task 消费 `ir.get("edit_groups") or []`，Task 3 落地前为空 →
  仅"target 无 owner 且无组"场景被判违规，规则缺省不启用故无影响）。
- Produces: `_SMALL_ROLES` 元组（verify.py 函数级常量）；S8/S9 两条新 check；
  `test_style_rules.py` 可独立运行单测。

- [ ] **Step 1: 写失败单测 `tests/test_style_rules.py`**（直接构造 rules 调 `_s_family`）

```python
# -*- coding: utf-8 -*-
"""test_style_rules.py — 块 3 单测：styleguides 可选键 size_fs_floor /
labels_follow 的 verify 消费（不启用 = 零检查；启用 = 按尺寸/组织断言）。

用法：win_py -X utf8 tests/test_style_rules.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import verify as V
from verify import Report

# 最小 IR（2 元素 + 1 glide 骨架；EditGroup 字段由用例自造）
def _mk_ir():
    return {
        "slide": (13.333, 7.5), "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
        "elements": [
            {"id": "big", "type": "text", "rect": (1.0, 1.0, 4.0, 1.0),
             "text": "大", "text_layout": {"fs": 20, "lines": 1, "need_h": 28}},
            {"id": "tiny", "type": "text", "rect": (1.0, 3.0, 0.8, 0.5),
             "text": "小", "text_layout": {"fs": 8, "lines": 1, "need_h": 11}},
            {"id": "chip", "type": "shape", "kind": "rounded_rect",
             "rect": (6.0, 1.0, 2.0, 0.3), "style": {"fill": "#1F2A44"},
             "text": "芯片", "text_layout": {"fs": 7, "lines": 1, "need_h": 10}},
            {"id": "reactor.label", "type": "text", "rect": (9.0, 1.0, 1.0, 0.4),
             "text": "反应器", "text_layout": {"fs": 9, "lines": 1, "need_h": 12}},
        ],
        "lines": [], "glue": [], "groups": [], "z_max": 10,
    }


P = {"verify": {"eps": 0.01}, "text": {"min_fs": 4}, "graph": {},
     "style": {"text_color": "#000000"}}

_fail = []
_pass = []


def check(name, rep, expect_bad):
    bad = bool(rep.violations)
    if bad != expect_bad:
        _fail.append(f"{name}: {'该拦没拦' if expect_bad else '误拦'} "
                     f"violations={[ (f,n,d) for f,n,ok,d in rep.checks if not ok]}")
        print(f"[FAIL!] {name}")
        for fam, n, ok, d in rep.checks:
            if not ok:
                print(f"        ↳ {fam} {n}: {d}")
    else:
        print(f"[OK] {name} {'拦截 ✓' if expect_bad else '通过 ✓'}")
        _pass.append(name)


def _s(rules, ir=None, sv="t"):
    rep = Report(ir or _mk_ir(), {}, P)
    V._s_family(rep, rules, P, sv)
    return rep


def main():
    # 缺省（无 size_fs_floor/labels_follow 键）= 零检查（0 违规）
    ir0 = _mk_ir()
    rep = _s({}, ir0)
    check("缺省规则零检查", rep, expect_bad=False)

    # S8：小尺寸字号下限——rect 短边 < threshold(in) 且非豁免角色 → fs ≥ floor
    rules = {"size_fs_floor": {"threshold": 1.0, "fs": 12}}
    ir = _mk_ir()
    ir["elements"][2]["rect"] = (6.0, 1.0, 2.0, 0.3)   # chip 短边 0.3in < 1.0
    rep = _s(rules, ir)
    names = {n for f, n, ok, d in rep.checks}
    assert "小尺寸字号 chip ≥ 12" in names, f"S8 未产生检查: {names}"
    check("S8 小盒小号拦截", rep, expect_bad=True)    # chip fs=7 < 12 且短边 0.3in

    # S8 放行：同类元素字号已达标
    ir = _mk_ir()
    ir["elements"][2]["text_layout"]["fs"] = 14
    check("S8 小盒达标放行", _s(rules, ir), expect_bad=False)

    # S8 豁免：巨型元素（短边 ≥ threshold）不查
    ir = _mk_ir()
    ir["elements"][2]["rect"] = (6.0, 1.0, 2.0, 1.5)   # 短边 1.5in ≥ 1.0
    rep = _s(rules, ir)
    names = {n for f, n, ok, d in rep.checks}
    check("S8 大盒不查", rep, expect_bad=False)

    # S8 豁免：小字角色 id（lab/caption 等）不查
    ir = _mk_ir()
    ir["elements"].append({"id": "n1.caption", "type": "text",
                           "rect": (1.0, 5.0, 0.6, 0.3), "text": "注",
                           "text_layout": {"fs": 6, "lines": 1, "need_h": 9}})
    check("S8 角色豁免", _s(rules, ir), expect_bad=False)

    # S9：labels_follow——顶层 .label 与顶层目标须同 edit_group（无组 → 违规）
    rules9 = {"labels_follow": True}
    ir = _mk_ir()
    ir["elements"].append({"id": "reactor", "type": "shape",
                           "kind": "rounded_rect", "rect": (10.0, 1.0, 2.0, 1.0),
                           "style": {"fill": "#1F2A44"},
                           "text_layout": {"fs": 14, "lines": 1, "need_h": 20}})
    rep = _s(rules9, ir)
    names = {n for f, n, ok, d in rep.checks}
    assert any("标签组织" in n for n in names), f"S9 未产生检查: {names}"
    check("S9 顶层标签无组拦截", rep, expect_bad=True)

    # S9 放行：同 edit_group 成员（ir 直接注入，Task 3 前即测语义）
    ir = _mk_ir()
    ir["elements"].append({"id": "reactor", "type": "shape",
                           "kind": "rounded_rect", "rect": (10.0, 1.0, 2.0, 1.0),
                           "style": {"fill": "#1F2A44"},
                           "text_layout": {"fs": 14, "lines": 1, "need_h": 20}})
    ir["edit_groups"] = [{"id": "r_eg", "members": ["reactor", "reactor.label"]}]
    check("S9 同编辑组放行", _s(rules9, ir), expect_bad=False)

    # S9 放行：容器派生标签（有 owner）天然合法——graph 边标签语义
    ir = _mk_ir()
    ir["elements"].append({"id": "g.e1.label", "type": "text",
                           "rect": (1.0, 6.0, 1.0, 0.4), "text": "边",
                           "owner": "g", "text_layout": {"fs": 8,
                                                         "lines": 1, "need_h": 11}})
    check("S9 容器标签放行", _s(rules9, ir), expect_bad=False)

    # 汇总
    print(f"---\npass={len(_pass)} fail={len(_fail)}")
    if _fail:
        print("FAILED:", *_fail, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 跑单测确认失败**

Run: `win_py -X utf8 tests/test_style_rules.py`
Expected: FAIL（`AttributeError: module 'verify' has no attribute 'Report'` →
先确认 `Report` 可导入；`_mk_ir` 报 `Report.__init__` 签名不符或 S8/S9 检查未产生）。

> 若 `Report` 签名与 `V.run` 内部不同（本计划假设 `Report(ir, compiled, p)`，
> 见 verify.py:106），以 `verify.py` 实际构造为准——运行后按报错对齐
> （计划撰写时已读 verify.py:106 确认 `Report(ir, compiled, p)`）。

- [ ] **Step 3: 实现 verify.py S8/S9**

在 `_s_family` 开头（`ts = rules.get("type_scale") or {}` 之后、S1 之前）加常量，
并把 S1b 的 `small` 元组替换为复用（行为不变）：

```python
    ts = rules.get("type_scale") or {}
    eps = p["verify"]["eps"]
    # 小字角色豁免词（S1b/S8 共用）：图形标签 lab、图注 caption/note、单位 units、
    # 页脚 foot/hdr/ftr、封面 meta —— 独立于"尺寸"语义的角色豁免
    _SMALL_ROLES = ("lab", "caption", "note", "units", "foot", "hdr", "ftr", "meta")
```

S1b 内 `small = (...)` 行改为 `small = _SMALL_ROLES`（其余不动）。

S1b 块结束（"正文字号" rep.add 之后）追加 S8/S9：

```python
    # S8 小尺寸字号下限（size_fs_floor，scansci「复杂度预算/识别性优先」内化）：
    # 元素 rect 短边 < threshold(in) 时 fs ≥ floor——"缩小后保留辨识特征"转为
    # 可断言规则（区别于 min_fs 硬底：本规则按尺寸生效）。豁免：容器部件（owner）
    # 与 S1b 小字角色同律。
    sff = rules.get("size_fs_floor")
    if sff:
        thr_in = sff.get("threshold", 1.0)
        thr_emu = int(round(thr_in * 914400))
        floor = sff.get("fs", 12)
        for e in ir["elements"]:
            if e.get("type") not in ("text", "shape") or "text_layout" not in e:
                continue
            if e.get("owner"):
                continue
            if any(k in e["id"] for k in _SMALL_ROLES):
                continue
            r = e["rect"]
            short_in = min(r[2], r[3]) / 914400.0
            if short_in < thr_in:
                rep.add("S", f"小尺寸字号 {e['id']} ≥ {floor}",
                        e["text_layout"]["fs"] >= floor,
                        f"rect短边={short_in:.2f}in fs={e['text_layout']['fs']} 规范≥{floor}")

    # S9 标签组织（labels_follow，scansci「标签随部件 vs 图例独立」内化）：
    # .label 后缀文本须与其目标同 owner 或同 edit_group——graph 边/组标签有
    # owner（容器组织）天然满足；约束自由（顶层）标签与顶层目标的组织。
    lf = rules.get("labels_follow")
    if lf:
        eg_members = set()
        for g in (ir.get("edit_groups") or []):
            eg_members.update(g.get("members") or [])
        for e in ir["elements"]:
            if not (e["id"].endswith(".label") and "text" in e):
                continue
            if e.get("owner"):
                continue                     # 容器派生的标签：已随部件组织
            target = elems.get(e["id"][:-len(".label")])
            if target is None or target.get("owner"):
                continue                     # 目标不可比/目标在容器内：无约束
            ok = e["id"] in eg_members and target["id"] in eg_members
            if not ok:
                rep.add("S", f"标签组织 {e['id']}", False,
                        f"目标 {target['id']} 与标签须同 edit_group（同部件组织）"
                        if not eg_members else
                        f"目标 {target['id']} 与标签须同 edit_group")
```

- [ ] **Step 4: attribution.py 归因配套**

`_ADVISORY_SUB` 元组追加（S8/S9 是审美/结构偏好，不机械修）：

```python
    "小尺寸字号", "标签组织",        # scansci 内化规则：按尺寸/组织偏好，人工/LLM 裁定
```

- [ ] **Step 5: run_mutations.py 加规则注入 mutation**

在 `main()` 的 compiled 层 S 家族段（ladder 用例之后）追加——用临时 style key 注入
规则，验证「启用规则时违规必被拦」（该拦没拦 = FAIL！）。位置：`# S4 必需构件缺失`
用例之后、M12 之前任意处：

```python
    # ---- scansci 内化块 3：size_fs_floor 规则注入突变（缺省不启用；启用必拦）----
    import styleguides as _SG
    _k8 = "__scan_s8__"
    _SG.RULE_SETS[_k8] = {"size_fs_floor": {"threshold": 1.0, "fs": 30}}
    try:
        m = copy.deepcopy(c0)
        m["meta"]["style_guide"] = _k8
        mir, mp = ir_of(m)
        # flowchart 节点 fs 多 < 30 且节点短边 < 1.0in → 必违规
        check("S8 注入规则拦截", m, mir, mp, expect_ok=True,
              mutate_desc="size_fs_floor fs=30：小尺寸节点 fs 未达标")
    finally:
        del _SG.RULE_SETS[_k8]
```

> 注：`c0` 在 M1 段之后已从 flow 加载（见 run_mutations.py:113），此处直接复用。

- [ ] **Step 6: 跑全套确认绿**

Run:
```
win_py -X utf8 tests/test_style_rules.py
win_py -X utf8 -W ignore tests/run_mutations.py
```
Expected: 两者 exit 0，无 `[FAIL!]`。

> 本 Task 无端到端 regression 示例（规则缺省不启用→无可验行为；启用场景由单测
> + 突变背书）。设计文档「regression 示例」要求由块 1/2 的 _probe 示例承担。

- [ ] **Step 7: 变更记录（本目录非 git，无提交）**

在 `wiki/_log.md` 追加一行：
`2026-09-30 块3 落地：styleguides 可选键 size_fs_floor/labels_follow + verify S8/S9 + attribution 归因 + test_style_rules.py 单测（scansci 内化）`

---

### Task 2: 块 1 —— 具名锚点（elements.anchors + glue from_anchor/to_anchor）

**Files:**
- Modify: `scripts/spec_compile.py`（`_check_elem` shape 分支 640-650；页级 glue
  校验 867-875；全局 glue 校验 1272-1280）
- Modify: `scripts/spec_validator.py:23`（`PER_TYPE["shape"]` 加 `"anchors"`）
- Modify: `scripts/ir_builder.py`（build_ir 主循环 anchors 绝对化；`_emit_glue`
  589-599 具名分支 + `_side_of` 辅助）
- Modify: `scripts/verify.py`（G5/G6 循环 187-207 豁免带 an1 的 glue；其后加 G10）
- Modify: `scripts/attribution.py:38-46`（`_INTERNAL_SUB` 加 `"端点一致"`）
- Modify: `scripts/com_layer.py`（354-382 glue 绑定后具名锚点偏移 WARN）
- Create: `tests/test_scansci_compile.py`
- Modify: `tests/run_mutations.py`（对照加 `_probe/anchors.yaml` + G10 突变段）
- Create: `_probe/anchors.yaml`
- Modify: `tests/regression.py`（CASES 增例）

**Interfaces:**
- Consumes: `all_rects`（ir_builder 既有）；glue 现状结构（`from_id/to_id/z/a1/a2/
  side1/side2/label`）；`p["verify"]["eps"]`。
- Produces: IR 元素 `anchors`（绝对坐标 dict）；glue 新键 `an1/an2`（锚点名）+
  既有 `a1/a2`（= 锚点绝对位）+ `side1/side2`（由 `_side_of` 推导）。
  `spec_compile` 编译期拦截锚点范围 [0..1]²、锚点名存在性。

- [ ] **Step 1: 写失败单测 `tests/test_scansci_compile.py`**（编译期拦截）

```python
# -*- coding: utf-8 -*-
"""test_scansci_compile.py — 块 1/2 编译期拦截单测：新语法（anchors /
from_anchor / to_anchor / edit_groups）白名单与存在性校验。

用法：win_py -X utf8 tests/test_scansci_compile.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))

import spec_compile as SC

_fail = []
_pass = []


def _yaml(extra_elems, extra_relations):
    lines = [
        "meta: {title: t, style_guide: flowchart, slide: {w: 13.333, h: 7.5},"
        " margin: {l: 0.5, t: 0.5, r: 0.5, b: 0.5}}",
        "palette: {p: '#1F2A44'}",
    ]
    lines.append("elements:")
    for e in extra_elems:
        lines.append("- " + repr(e).replace("'", '"').replace('"', '"') if False else
                     "- " + str(e).replace("'", '"'))
    lines.append("relations:")
    for r in extra_relations:
        lines.append("  " + r)
    return "\n".join(lines)


def _compile(extra_elems, extra_relations, expect_raise, name, detail):
    import yaml
    data = yaml.safe_load(_yaml(extra_elems, extra_relations))
    try:
        SC.compile_spec(data)
    except SC.SpecCompileError as ex:
        if expect_raise:
            print(f"[OK] {name} 编译拦截 ✓ · {detail} :: {str(ex)[:90]}")
            _pass.append(name)
        else:
            _fail.append(f"{name}: 误拦（{str(ex)[:120]}）")
            print(f"[FAIL!] {name} 误拦 · {str(ex)[:120]}")
        return
    if expect_raise:
        _fail.append(f"{name}: 漏拦（未抛 SpecCompileError）")
        print(f"[FAIL!] {name} 漏拦 · {detail}")


def base_elems():
    return [
        {"id": "pump", "type": "shape", "kind": "rounded_rect",
         "rect": [1.0, 1.0, 2.0, 1.0], "style": {"fill": "p"}},
        {"id": "reactor", "type": "shape", "kind": "rounded_rect",
         "rect": [5.0, 1.0, 2.0, 1.0], "style": {"fill": "p"},
         "anchors": {"inlet": [0.0, 0.5], "outlet": [1.0, 0.5]}},
    ]


def main():
    # 合法：锚点在 [0..1]² 且有端点元素声明
    _compile(base_elems(),
             ["glue:",
              "  - {from: pump, to: reactor, from_anchor: outlet, to_anchor: inlet}"],
             False, "合法具名锚点", "锚点坐标/引用全合规")

    # 漏拦检查 1：锚点坐标越界
    e = base_elems()
    e[1]["anchors"] = {"inlet": [1.5, 0.5]}
    _compile(e,
             ["glue:",
              "  - {from: pump, to: reactor, to_anchor: inlet}"],
             True, "锚点越界拦截", "inlet y=1.5 超出 [0,1]²")

    # 漏拦检查 2：glue 引用不存在的锚点名
    _compile(base_elems(),
             ["glue:",
              "  - {from: pump, to: reactor, to_anchor: nosuch}"],
             True, "锚点名缺失拦截", "reactor 无 anchors.nosuch")

    # 漏拦检查 3：锚点名声明在端点（pump 无 anchors）却引用
    _compile(base_elems(),
             ["glue:",
              "  - {from: pump, to: reactor, from_anchor: outlet}"],
             True, "端点无锚点拦截", "pump 未声明 anchors 却用 from_anchor")

    # 漏拦检查 4：anchors 非 dict 或值非 [x,y] 数值
    e = base_elems()
    e[1]["anchors"] = {"inlet": "oops"}
    _compile(e,
             ["glue:",
              "  - {from: pump, to: reactor, to_anchor: inlet}"],
             True, "锚点值类型拦截", "inlet 非 [nx,ny] 数值对")

    print(f"---\npass={len(_pass)} fail={len(_fail)}")
    if _fail:
        print("FAILED:", *_fail, sep="\n  ")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

> `_yaml`/`_compile` 用 `str(dict)` 序列化（引号统一双引号）——若 YAML 解析边界
> 有问题（字典值含引号），此测试骨架会在首次运行时报错，届时把 `repr` 序列化改
> 为显式 yaml 模板字符串（本计划骨架已给；块 2 Task 复用同一 helper）。

- [ ] **Step 2: 跑单测确认失败**

Run: `win_py -X utf8 tests/test_scansci_compile.py`
Expected: FAIL（4 个"漏拦检查"全 FAIL！—— 现无 anchors 校验；「合法具名锚点」
可能因 spec_validator 未知字段 `anchors` 报 violation → 编译不 raise，
本测试文件只查 SpecCompileError raise，故也 PASS。关键失败 = 漏拦检查 1-4）。

- [ ] **Step 3: spec_compile.py 编译校验**

`_check_elem` 的 `etype == "shape"` 分支（`if "text" in e ...` 之后，
`if kind == "cylinder"` 之前）插入：

```python
        if "anchors" in e:
            if not isinstance(e["anchors"], dict) or not e["anchors"]:
                raise SpecCompileError(f"{path}.anchors: 必须为非空 dict（name → [nx, ny]）")
            for an, val in e["anchors"].items():
                if not isinstance(an, str) or not an:
                    raise SpecCompileError(f"{path}.anchors: 锚点名必须为非空字符串")
                if (not isinstance(val, (list, tuple)) or len(val) != 2
                        or not all(isinstance(v, (int, float))
                                   and not isinstance(v, bool) and 0.0 <= v <= 1.0
                                   for v in val)):
                    raise SpecCompileError(f"{path}.anchors.{an}: 必须为 [nx, ny] 且 nx,ny ∈ [0,1]")
```

glue 校验（页级 867-875 与全局 1272-1280 两处同构追加）。页级原文：

```python
    for i, gl in enumerate(rel.get("glue", [])):
        gp = f"{pp}.relations.glue[{i}]"
        if not isinstance(gl, dict) or "from" not in gl or "to" not in gl:
            raise SpecCompileError(f"{gp}: 必须声明 from 与 to")
        for k in ("from", "to"):
            if gl[k] not in seen:
                raise SpecCompileError(f"{gp}.{k}: 引用不存在的元素 {gl[k]!r}")
        if "label" in gl and not isinstance(gl["label"], str):
            raise SpecCompileError(f"{gp}.label: 必须为字符串")
```

在 `label` 检查后追加：

```python
        # 具名锚点（scansci 内化）：from_anchor/to_anchor 可缺省（省略 → 回退
        # AABB 边中点现状）；声明则须成对（消除"单端具名"混合 glue——G5/G6 豁免
        # 与 G10 覆盖的前提不变量），且锚点名必须存在于端点元素 anchors
        if ("from_anchor" in gl) != ("to_anchor" in gl):
            raise SpecCompileError(f"{gp}: from_anchor/to_anchor 须成对声明"
                                   "（具名锚点连接，双向指定端点）")
        for at_key in ("from_anchor", "to_anchor"):
            if at_key not in gl:
                continue
            end_id = gl["from"] if at_key == "from_anchor" else gl["to"]
            anchors = next((x.get("anchors") or {})
                           for x in elems if x["id"] == end_id)
            if gl[at_key] not in anchors:
                raise SpecCompileError(
                    f"{gp}.{at_key}: 锚点名 {gl[at_key]!r} 不在元素 {end_id!r} "
                    f"anchors（可选 {sorted(anchors)}）")
```

> `elems` 即 `_check_slide` 的 `elems` 列表（line 836）。全局段（`compile_spec`
> 单页路径）里 glue 校验块前的元素列表变量名为 `elems`（line 1245 附近循环已
> 建 `seen`；`data["elements"]` 可作来源）——全局段用 `data["elements"]` 替代
> `elems` 名称，写法同构。

- [ ] **Step 4: spec_validator.py 白名单**

`PER_TYPE["shape"]`（line 23）追加 `"anchors"`：

```python
    "shape": COMMON_FIELDS | {"kind", "text", "text_style", "style", "slice", "opacity",
                              "anchors"},
```

> glow 字段 `from_anchor/to_anchor` 不属元素白名单（glue 段结构检查归
> spec_compile，validator 只查 glue 的 style token 引用）——无需改。

- [ ] **Step 5: ir_builder.py —— anchors 绝对化 + _emit_glue 具名分支**

`_emit_basic` 是**选择性复制字段**（text/shape/image… 各分支明列字段，见
ir_builder.py:265-280）——不会透传 `anchors`。在 `_emit_basic` 的
`elif t == "shape":` 分支（line 275）追加（顶层 shape 与容器 children shape 共用
此函数；child 带 anchors 已被 CHILD_PER_TYPE 白名单拦掉，不会走到此）：

```python
    elif t == "shape":
        el["kind"] = cfg.get("kind", "rounded_rect")
        el["style"] = _style(cfg.get("style"), p)
        if cfg.get("anchors"):
            el["anchors"] = _abs_anchors(rect, cfg["anchors"])
        if "text" in cfg:
            _apply_text(el, cfg, rect, p)
            el["text"] = cfg["text"]
```

新增模块级辅助 + 主循环接线（放在 `_expanded_cover` 之后、主循环之前）：

```python
def _abs_anchors(rect, anchors):
    """归一锚点 → 绝对坐标（EMU 输出，round 3 位与 glue a1/a2 同规）。"""
    x, y, w, h = rect
    out = {}
    for an, (nx, ny) in anchors.items():
        out[an] = (round(x + nx * w, 3), round(y + ny * h, 3))
    return out


def _side_of(rect, pt):
    """锚点所在边推导：归一化半径比 |nx|≥|ny| → E/W；否则 N/S（角点取横向，
    确定性优先序——verify G10 与渲染零重算，COM 站点就近绑定的降级哲学背书）。"""
    cx, cy = rect[0] + rect[2] / 2.0, rect[1] + rect[3] / 2.0
    nx = (pt[0] - cx) / (rect[2] / 2.0) if rect[2] else 0.0
    ny = (pt[1] - cy) / (rect[3] / 2.0) if rect[3] else 0.0
    return "E" if nx >= abs(ny) else ("W" if -nx >= abs(ny) else
                                      ("S" if ny >= 0 else "N"))
```

> 简化：`return "E" if nx >= abs(ny) else "W" if abs(nx) < abs(ny) and nx < 0 ... `
> 上式为稳妥写法（E 右、W 左、S 下、N 上）。若觉得绕，用等价分支：
> `if abs(nx) >= abs(ny): return "E" if nx >= 0 else "W"; return "S" if ny >= 0 else "N"`。

`_emit_glue`（line 589-599）——现实现读：

```python
def _emit_glue(compiled, out, p, alloc, all_rects):
    ...
    for gl in compiled.get("relations", {}).get("glue", []):
        ...
        sa = _side_of_rect(ra, rb)      # 现状 LR.anchor_pair 的边推导逻辑
        ...
        out["glue"].append(dict(id=..., from_id=ra_id, to_id=rb_id, z=..., a1=..., a2=...,
                                side1=sa, side2=sb, label=gl.get("label")))
```

`_emit_glue` 循环体（line 591-599）整体改为（现状 `sa/a1/sb/a2` 由
`LR.anchor_pair(ra, rb)` 一次解出——未声明锚点 glue 输出字节级等价；具备名
锚点时用 `_abs_anchors` 覆盖 a1/a2 并以 `_side_of` 推导 side。编译期已成对
强制 → `an1` 存在 ⟹ `an2` 存在，无混合 glue）：

```python
    for i, gl in enumerate((compiled.get("relations") or {}).get("glue", [])):
        ra, rb = all_rects.get(gl["from"]), all_rects.get(gl["to"])
        if ra is None or rb is None:
            raise ValueError(f"glue 端点 rect 缺失: {gl['from']}→{gl['to']}（编译期应已拦截）")
        sa, a1, sb, a2 = LR.anchor_pair(ra, rb)
        fa, ta = gl.get("from_anchor"), gl.get("to_anchor")
        ra_el = next((e for e in compiled["elements"] if e["id"] == gl["from"]), None)
        rb_el = next((e for e in compiled["elements"] if e["id"] == gl["to"]), None)
        if fa and ra_el and ra_el.get("anchors"):
            a1, sa = _abs_anchors(ra, {fa: ra_el["anchors"][fa]})[fa], \
                     _side_of(ra, _abs_anchors(ra, {fa: ra_el["anchors"][fa]})[fa])
        if ta and rb_el and rb_el.get("anchors"):
            a2, sb = _abs_anchors(rb, {ta: rb_el["anchors"][ta]})[ta], \
                     _side_of(rb, _abs_anchors(rb, {ta: rb_el["anchors"][ta]})[ta])
        gid = gl.get("id") or f"glue.{gl['from']}->{gl['to']}"
        rec = dict(id=gid, from_id=gl["from"], to_id=gl["to"],
                   z=alloc(z=out["z_max"] + 1 + i), a1=a1, a2=a2,
                   side1=sa, side2=sb, label=gl.get("label"))
        if fa:
            rec["an1"] = fa
        if ta:
            rec["an2"] = ta
        out["glue"].append(rec)
```

> 现状 `a1/a2/side1/side2` 语义在未声明锚点路径字节级保留（`LR.anchor_pair`
> 结果原样走）；具名路径绝对坐标 round 3 位（`_abs_anchors` 与 IR rect 同规）。

- [ ] **Step 6: verify.py —— G5/G6 豁免 + G10**

G5/G6 循环（line 187-207）开头插入豁免：

```python
    for ln in ir["lines"] + ir["glue"]:
        if ln.get("an1"):
            continue   # 具名锚点 glue：端点=锚点绝对位由 G10 独立重算（豁免 AABB 边中点判据）
        ra = elems.get(...)   # 原逻辑不动
```

循环后（G7 之前）加 G10：

```python
    # G10 具名锚点解析一致（scansci 连接配方内化）：glue 端点 = 元素 anchors
    # 绝对位 ±eps（第二实现：从 compiled 归一坐标重算，不读 IR 现成值）
    comp_anchors = {}
    for ce in (compiled.get("elements") or []):
        if ce.get("anchors"):
            comp_anchors[ce["id"]] = _abs_compiled_anchors(ce)
    for gl in ir["glue"]:
        if not gl.get("an1"):
            continue
        want1 = comp_anchors.get(gl["from_id"], {}).get(gl["an1"])
        want2 = comp_anchors.get(gl["to_id"], {}).get(gl["an2"])
        ok1 = want1 is not None and abs(gl["a1"][0] - want1[0]) <= eps \
            and abs(gl["a1"][1] - want1[1]) <= eps
        ok2 = want2 is not None and abs(gl["a2"][0] - want2[0]) <= eps \
            and abs(gl["a2"][1] - want2[1]) <= eps
        rep.add("G", f"锚点一致 {gl['id']}", ok1 and ok2,
                f"a1={tuple(round(v,3) for v in gl['a1'])} 期望"
                f"{tuple(round(v,3) for v in want1) if want1 else '∅'} · "
                f"a2={tuple(round(v,3) for v in gl['a2'])} 期望"
                f"{tuple(round(v,3) for v in want2) if want2 else '∅'}")
```

`_abs_compiled_anchors`（verify 模块级，独立实现）：

```python
def _abs_compiled_anchors(ce):
    x, y, w, h = ce["rect"]
    return {an: (x + nx * w, y + ny * h) for an, (nx, ny) in ce["anchors"].items()}
```

- [ ] **Step 7: attribution.py**

`_INTERNAL_SUB` 追加 `"锚点一致"`（G10 = ir_builder 锚点算法 bug，停机报 bug）：

```python
    "锚点一致",              # 具名锚点解析一致（布局层算法 bug）
```

- [ ] **Step 8: run_mutations.py —— 对照 + G10 突变**

EX dict 加键 `"anchors"`（line 27-33 区域）：

```python
      "anchors": os.path.join(ROOT, "_probe", "anchors.yaml"),
```

对照循环 `("flow", "ladder", "glue", "org", "chart", "method")` 改为追加
`"anchors"`（对照：具名锚点合法 SPEC 0 违规）。

主循环（M12 之后）加 G10 突变——篡改 IR glue 端点，期望 G10 + G5 豁免成立：

```python
    # ---- scansci 内化块 1：G10 具名锚点端点一致（篡改 a1 必须被拦）----
    ca, ia, pa = base_pair("anchors")
    m = copy.deepcopy(ia)
    for gl in m["glue"]:
        if gl.get("an1"):
            gl["a1"] = (gl["a1"][0] + 0.2, gl["a1"][1])   # 挪离锚点绝对位
    check("IR 具名锚点端点偏离", ca, m, pa, expect_ok=True,
          mutate_desc="具名锚点 glue a1 右移 0.2（≠ 元素 anchors 绝对位）")
```

> `check(..., expect_ok=True, ...)` = 期望有违规（该拦没拦 = FAIL！）。
> 若篡改后 G5 豁免生效 + G10 起拦，则通过。

- [ ] **Step 9: regression 示例 `_probe/anchors.yaml`**

```yaml
meta:
  title: 具名锚点示例
  style_guide: flowchart
  slide: {w: 13.333, h: 7.5}
  margin: {l: 0.5, t: 0.5, r: 0.5, b: 0.5}
palette:
  p: '#1F2A44'
  q: '#4C9BE8'
elements:
  - id: pump
    type: shape
    kind: rounded_rect
    rect: [1.0, 3.0, 2.0, 1.0]
    style: {fill: p, border: q}
    text: 泵
  - id: reactor
    type: shape
    kind: rounded_rect
    rect: [5.0, 3.0, 2.0, 1.0]
    style: {fill: p, border: q}
    text: 反应器
    anchors:
      inlet: [0.0, 0.35]      # 左缘偏上——具名锚点：连接位精确可控
      outlet: [1.0, 0.8]      # 右缘偏下
relations:
  glue:
    - from: pump
      to: reactor
      from_anchor: outlet
      to_anchor: inlet
      label: 进料
```

> 运行前验证：`win_py -X utf8 scripts/build_ppt.py _probe/anchors.yaml --out /tmp/x
> --report none` → exit 0（compile → ir → verify → render → 物证全过）。
> 物证断言走既有 4 节（cxnSp xfrm = a1/a2 min-corner 盒）——a1/a2 已是锚点
> 绝对位，自动成立，无需改 render_check_xml。
> 若 verify 报"标签字号"超 type_scale.edge_label（label 文本进查），把 label fs
> 调整为规范内或删 label 走纯锚点验证——以实际报错为准微调。

- [ ] **Step 10: regression.py 增例**

CASES 追加：

```python
    ("anchors", "_probe/anchors.yaml", 11),   # 具名锚点：2 元素 + glue + label 物证
```

> 物证计数以实际 `--report` 输出为准：跑一次 `build_ppt.py` 读 `evidence: OK n/m`
> 再回填精确 n（骨架先写 11 占位，验收 Task 校准）。

- [ ] **Step 11: com_layer.py 具名锚点偏移 WARN**

glue 绑定循环（`rec.update(ok=True, site1=s1, site2=s2)` 之后）追加：

```python
                    # 具名锚点（scansci 内化）：绑定就近站点的同时披露锚点绝对位
                    # 与站点位置偏差（>0.25in 即 WARN；不阻断——降级哲学背书）
                    if gl.get("an1"):
                        try:
                            shp1 = find_shape_by_name(slide, gl["from_id"])
                            x, y, w_, h_ = shp1.Left, shp1.Top, shp1.Width, shp1.Height
                            mid = {"N": (x + w_ / 2, y), "S": (x + w_ / 2, y + h_),
                                   "E": (x + w_, y + h_ / 2), "W": (x, y + h_ / 2)}[gl["side1"]]
                            ax, ay = gl["a1"][0] / 12700.0, gl["a1"][1] / 12700.0
                            if abs(mid[0] - ax) > 18 or abs(mid[1] - ay) > 18:
                                out["warnings"].append(
                                    f"glue {gl['id']} 锚点 {gl['an1']} 绝对位"
                                    f"({ax:.1f},{ay:.1f}) 偏离侧 {gl['side1']} 站点中点"
                                    f"({mid[0]:.1f},{mid[1]:.1f})—绑定就近站点")
                        except Exception:
                            pass
```

- [ ] **Step 12: 变更记录**

`wiki/_log.md` 追加：
`2026-09-30 块1 落地：elements.anchors + glue from_anchor/to_anchor（spec_compile/
validator/ir_builder/verify G10/com WARN）+ test_scansci_compile.py + _probe/anchors.yaml`

---

### Task 3: 块 2 —— 编辑单元分组（relations.edit_groups）

**Files:**
- Modify: `scripts/spec_compile.py`（两处 relations 白名单 858/1261 + edit_groups
  校验块）
- Modify: `scripts/ir_builder.py`（`_coalesce_edit_groups` + `out["edit_groups"]`）
- Modify: `scripts/verify.py`（G4 第三源 + G11）
- Modify: `scripts/attribution.py`（`_INTERNAL_SUB` 加 `"编辑组"`）
- Modify: `scripts/com_layer.py:402-416`（组循环泛化 edit_groups）
- Modify: `tests/test_scansci_compile.py`（edit_groups 编译拦截用例）
- Modify: `tests/run_mutations.py`（对照加 `_probe/edit_groups.yaml` + G11/G4 突变）
- Create: `_probe/edit_groups.yaml`
- Modify: `tests/regression.py`（CASES 增例）

**Interfaces:**
- Produces: IR `edit_groups` = `[{id, members, z_lo, z_hi}]`（显式组 + group:true
  容器并组）；z 不变量「组内连续、组间不交叠、参与全局序」由 `_coalesce_edit_groups`
  保证，verify G11 独立重算。
- Consumes: `out["com_group"]`（既有容器 group:true 列表）；`seen`/`elems`（编译期）。

- [ ] **Step 1: 编译期拦截用例（并入 test_scansci_compile.py）**

`main()` 末尾追加（复用既有 helper `_compile`）：

```python
    # ---- 块 2：edit_groups 编译拦截 ----
    # 合法：成员为顶层产生形状的元素；组名/成员合规
    _edit_elems = [
        {"id": "glass", "type": "shape", "kind": "rounded_rect",
         "rect": [1.0, 1.0, 2.0, 1.0], "style": {"fill": "p"}},
        {"id": "frame", "type": "shape", "kind": "rounded_rect",
         "rect": [1.0, 1.0, 2.0, 1.0], "style": {"fill": "p"}},
        {"id": "pump", "type": "shape", "kind": "rounded_rect",
         "rect": [4.0, 1.0, 2.0, 1.0], "style": {"fill": "p"}},
    ]
    _compile(_edit_elems + [_edit_elems[2]],
             ["edit_groups:",
              "  - {id: window, members: [glass, frame]}"],
             False, "合法编辑组", "成员为顶层元素")
    # 漏拦 1：成员引用不存在元素
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {id: window, members: [glass, nosuch]}"],
             True, "编辑组悬空成员拦截", "nosuch 不在 elements")
    # 漏拦 2：跨组重复成员
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {id: g1, members: [glass, frame]}",
              "  - {id: g2, members: [glass, pump]}"],
             True, "编辑组跨组重复拦截", "glass 分属 g1/g2")
    # 漏拦 3：容器成员（不产形状）
    _compile([{"id": "box", "type": "stack", "rect": [1.0, 1.0, 4.0, 2.0],
               "children": [{"id": "k1", "type": "shape", "kind": "rounded_rect",
                             "width": 1.0, "height": 1.0}]},
              {"id": "a", "type": "shape", "kind": "rounded_rect",
               "rect": [6.0, 1.0, 1.0, 1.0], "style": {"fill": "p"}}],
             ["edit_groups:",
              "  - {id: g, members: [box, a]}"],
             True, "编辑组容器成员拦截", "stack 不产单形状")
    # 漏拦 4：组缺 id 或 members 非列表
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {members: [glass, frame]}"],
             True, "编辑组缺 id 拦截", "无 id")
    _compile(_edit_elems,
             ["edit_groups:",
              "  - {id: g, members: glass}"],
             True, "编辑组 members 非列表拦截", "members 为字符串")
```

- [ ] **Step 2: 跑单测失败确认**

Run: `win_py -X utf8 tests/test_scansci_compile.py`
Expected: 块 2 用例「漏拦检查」FAIL！（relations 白名单尚无 edit_groups → 未知
关系段错误会抛 SpecCompileError——注意：**258/1261 白名单先不拦反而报"未知关系
段"会拦截**——正确预期是：edit_groups 未加白名单前，`_compile` 报 SpecCompileError
"未知关系段"→ 漏拦用例反而 PASS（误拦合法？不——合法用例「合法编辑组」会 FAIL！
因为它也报"未知关系段"）。**Step 2 预期 = 「合法编辑组」FAIL（误拦）**，确认
白名单缺失。实现后转绿。）

- [ ] **Step 3: spec_compile.py —— 白名单 + 校验块**

两处 relations 白名单（line 858 与 1261）改为：

```python
        if k not in ("edges", "glue", "overlap", "z_override", "edit_groups"):
            raise SpecCompileError(f"{pp}.relations.{k}: 未知关系段"
                                   "（edges/glue/overlap/z_override/edit_groups）")
```

页级（`_check_slide`，overlap 校验块之后、`if "margin"` 之前）加：

```python
    for i, eg in enumerate(rel.get("edit_groups", [])):
        ep = f"{pp}.relations.edit_groups[{i}]"
        if not isinstance(eg, dict) or "id" not in eg or not isinstance(eg.get("id"), str) \
                or not eg["id"]:
            raise SpecCompileError(f"{ep}: 必须声明非空 id")
        mems = eg.get("members")
        if not isinstance(mems, list) or not mems:
            raise SpecCompileError(f"{ep}.members: 必须为非空列表（顶层元素 id）")
        for mk in mems:
            if mk not in seen:
                raise SpecCompileError(f"{ep}.members: 引用不存在的元素 {mk!r}")
            mtype = next((x["type"] for x in elems if x["id"] == mk), None)
            if mtype in ("stack", "dock", "graph"):
                raise SpecCompileError(f"{ep}.members: {mk!r} 为容器（{mtype}）"
                                       "不产单形状，不能为编辑组成员"
                                       "（group:true 容器自动并入，无需声明）")
    # 跨组重复成员（编辑单元原子性：一个元素只属一个组）
    member_owner = {}
    for i, eg in enumerate(rel.get("edit_groups", [])):
        for mk in eg.get("members", []):
            if mk in member_owner:
                raise SpecCompileError(
                    f"{pp}.relations.edit_groups[{i}].members: {mk!r} 已属"
                    f"编辑组 {member_owner[mk]!r}（跨组重复成员不允许）")
            member_owner[mk] = eg.get("id")
```

全局段（`compile_spec`，overlap 校验块 line 1282-1289 之后）同构追加——把 `pp`
换为空串、`elems` 换 `data["elements"]`、错误消息前缀 `pp.` 去掉：

```python
    for i, eg in enumerate(rel.get("edit_groups", [])):
        ep = f"relations.edit_groups[{i}]"
        if not isinstance(eg, dict) or "id" not in eg or not isinstance(eg.get("id"), str) \
                or not eg["id"]:
            raise SpecCompileError(f"{ep}: 必须声明非空 id")
        mems = eg.get("members")
        if not isinstance(mems, list) or not mems:
            raise SpecCompileError(f"{ep}.members: 必须为非空列表（顶层元素 id）")
        for mk in mems:
            if mk not in seen:
                raise SpecCompileError(f"{ep}.members: 引用不存在的元素 {mk!r}")
            mtype = next((x["type"] for x in data["elements"] if x["id"] == mk), None)
            if mtype in ("stack", "dock", "graph"):
                raise SpecCompileError(f"{ep}.members: {mk!r} 为容器（{mtype}）"
                                       "不产单形状，不能为编辑组成员"
                                       "（group:true 容器自动并入，无需声明）")
    member_owner = {}
    for i, eg in enumerate(rel.get("edit_groups", [])):
        for mk in eg.get("members", []):
            if mk in member_owner:
                raise SpecCompileError(
                    f"relations.edit_groups[{i}].members: {mk!r} 已属"
                    f"编辑组 {member_owner[mk]!r}（跨组重复成员不允许）")
            member_owner[mk] = eg.get("id")
```

- [ ] **Step 4: ir_builder.py —— _coalesce_edit_groups + out["edit_groups"]**

build_ir 主循环收尾（`_emit_glue(compiled, out, p, alloc, all_rects)` 之后）追加：

```python
    _coalesce_edit_groups(compiled, out)
```

模块级实现（放 `_emit_glue` 之后）：

```python
def _coalesce_edit_groups(compiled, out):
    """编辑单元 z 收拢（scansci「三种组织分开判断」内化）。

    不变量：组内成员 z 连续区间、组间区间互不交叠、组区间参与全局序
    （容器 group:true 现状语义——children 阶梯 base_z+10*(i+1)——的泛化）。

    确定性算法（一次扫描）：
      1) 显式组 + 容器并组（group:true → 派生物 owner==cid）合成统一组表。
      2) 组按成员当前 min_z 升序（组间相对序 = 现状序的稳定投影）。
      3) 按原 z 升序遍历全元素：首次遇某组员 → 从游标连续分配整组（组内按
         原 z 保序）；非组员 → 原 z 未被占则保留、被占则顺延游标。
    """
    # 1) 组表：显式组（成员已在编译期校验为顶层产生形状的元素）+ 容器并组
    eg_spec = (compiled.get("relations") or {}).get("edit_groups", [])
    groups = [dict(id=g["id"], members=list(g["members"])) for g in eg_spec]
    now_z = {e["id"]: e["z"] for e in out["elements"]}
    for cid in out.get("com_group", []):
        mems = sorted((e["id"] for e in out["elements"] if e.get("owner") == cid),
                      key=lambda i: now_z.get(i, 0))
        if len(mems) >= 2:      # 单成员组无组合收益，跳过（与 COM len<2 拒合同律）
            groups.append(dict(id=cid, members=mems))

    ordered = sorted(out["elements"], key=lambda e: e["z"])
    by_id = {e["id"]: e for e in out["elements"]}
    group_of = {}
    for g in groups:
        for m in g["members"]:
            group_of[m] = g["id"]
        g["_minz"] = min((now_z.get(m, 0) for m in g["members"]), default=0)
    groups.sort(key=lambda g: g["_minz"])

    # 2) 组按 min_z 升序 → 分配序（组块整体分配，组内保原 z 序）
    new_z = {}
    cursor = 0
    for e in ordered:
        eid = e["id"]
        if eid in new_z:
            continue
        gid = group_of.get(eid)
        if gid is not None and gid not in new_z:
            members = sorted([m for m in next(g["members"] for g in groups
                                              if g["id"] == gid)],
                             key=lambda m: now_z.get(m, 0))
            for m in members:
                new_z[m] = cursor
                cursor += 1
            continue
        # 非组员（或组已分配完）：保留原 z；被占则顺延
        z = now_z[eid]
        if z < cursor:
            z = cursor
        while z in set(new_z.values()):
            z += 1
        new_z[eid] = z
        cursor = max(cursor, z + 1)

    # 3) 回写 z + 组区间
    for e in out["elements"]:
        e["z"] = new_z[e["id"]]
    out["z_max"] = max(new_z.values(), default=0)
    _groups_map = []
    for g in groups:
        zs = [new_z[m] for m in g["members"]]
        _groups_map.append({"id": g["id"], "members": list(g["members"]),
                            "z_lo": min(zs), "z_hi": max(zs)})
    out["edit_groups"] = _groups_map
```

> 注意 `new_z.values()` 的 `set` 每次重建 O(n²)——MVP 元素量小（<50），可接受；
> 若嫌之，维护递增集合。算法确定性：排序键全为现值，无随机。

- [ ] **Step 5: verify.py —— G4 第三源 + G11**

G4（line 160-180）——`overlap_decl` 构建之后追加 edit_group 索引，并在合法判定
并入：

```python
    # scansci 内化：编辑单元（relations.edit_groups）成员互遮 = 合法源第三类
    eg_of = {}
    for g in (ir.get("edit_groups") or []):
        for m in g["members"]:
            eg_of[m] = g["id"]
```

判定处改为：

```python
            same_owner = a.get("owner") is not None and a.get("owner") == b.get("owner")
            declared = pair in overlap_decl
            same_eg = eg_of.get(a["id"]) is not None and eg_of.get(a["id"]) == eg_of.get(b["id"])
            rep.add("G", f"遮挡 {a['id']}↔{b['id']} 合法来源",
                    same_owner or declared or same_eg,
                    "同容器兄弟" if same_owner
                    else ("overlap 声明" if declared
                          else ("同编辑组" if same_eg else "未声明 ×")))
```

G9 之后加 G11（独立重算 z 区间，不读 ir 的 z_lo/z_hi 现成值）：

```python
    # G11 编辑单元区间（scansci 内化）：组成员 z 连续区间且在区间内无外部元素
    for g in (ir.get("edit_groups") or []):
        ids = set(g["members"])
        zs = [e["z"] for e in ir["elements"] if e["id"] in ids]
        if len(zs) != len(ids):
            rep.add("G", f"编辑组 {g['id']} 成员齐备", False,
                    f"IR 缺成员（有 {len(zs)}/{len(ids)}）")
            continue
        lo, hi = min(zs), max(zs)
        contiguous = (hi - lo + 1 == len(ids))
        outsider = [e["id"] for e in ir["elements"]
                    if lo <= e["z"] <= hi and e["id"] not in ids]
        rep.add("G", f"编辑组 {g['id']} z 区间", contiguous and not outsider,
                f"z 范围[{lo},{hi}] 连续={contiguous} 区间外来客={outsider or '∅'}")
```

- [ ] **Step 6: attribution.py**

`_INTERNAL_SUB` 追加 `"编辑组"`（G11 = 布局器 z 分配 bug，停机报 bug）：

```python
    "编辑组",              # 编辑单元 z 区间（布局器收拢算法 bug）
```

- [ ] **Step 7: com_layer.py —— 组循环泛化**

既有组循环（line 402-416，`for cid in ir.get("com_group", [])`）替换为：

```python
            # ---- 3. 组（编辑单元 + SPEC group:true 容器：统一 COM 入口）----
            # 编辑单元（relations.edit_groups）与容器 group:true 在 IR 统一为
            # edit_groups（成员已含容器派生物）；Office Group 改变 spTree 结构
            # → 组内元素后续 XML 物证须以组为单位复核（WARN 级提示，不阻断）。
            _eg = ir.get("edit_groups") or []
            if _eg and ir.get("edit_groups_pack"):
                out["warnings"].append(
                    "编辑组已 Office Group：spTree 结构变更，XML 物证以组为单位复核")
            for g in _eg:
                try:
                    shapes = [find_shape_by_name(slide, m) for m in g["members"]]
                    shapes = [s for s in shapes if s is not None]
                    if len(shapes) < 2:
                        raise ValueError(
                            f"成员 <2（members={g['members']}，已 Group={len(shapes)}）")
                    grp = slide.Shapes.Range([s.Name for s in shapes]).Group()
                    grp.Name = f"{g['id']}.group"
                    out["groups"].append({"id": g["id"], "ok": True,
                                          "name": grp.Name, "n": len(shapes),
                                          "z_lo": g.get("z_lo"), "z_hi": g.get("z_hi")})
                    _log(f"[com] group {_page_tag}{g['id']}: OK n={len(shapes)}")
                except Exception as ex:
                    out["groups"].append({"id": g["id"], "ok": False,
                                          "detail": str(ex)[:120]})
```

> `ir.get("edit_groups_pack")` 为可选披露位（ir_builder 里设 `out["edit_groups_pack"]`
> = True，供 COM 提示）；若不需要额外键，改判 `if _eg:` 直接提示（组结构调整
> 必然因 COM Group 发生，仅当实际跑了 Group 才提示——上述用 `edit_groups_pack`
> 语义 = ir 层确认收拢过/含组）。MVP 简化：`_eg` 非空即提示。

- [ ] **Step 8: run_mutations.py —— 对照 + G11/G4 突变**

EX dict 加键（line 33 后）：

```python
      "egroups": os.path.join(ROOT, "_probe", "edit_groups.yaml"),
```

对照循环追加 `"egroups"`。

主循环（M12 之后）加突变：

```python
    # ---- scansci 内化块 2：G11 编辑单元区间（打散组内 z 必须被拦）----
    ce, ie, pe = base_pair("egroups")
    m = copy.deepcopy(ie)
    _eg0 = m.get("edit_groups") or []
    if _eg0:
        wid = _eg0[0]["id"]
        mems = _eg0[0]["members"]
        # 把组内某成员 z 抬到组区间外（插别的元素原 z 位置）
        for e in m["elements"]:
            if e["id"] == mems[-1]:
                e["z"] = max(e["z"] for e in m["elements"]) + 5
    check("IR 编辑组 z 打散", ce, m, pe, expect_ok=True,
          mutate_desc="编辑组成员 z 抬出组区间（G11 起拦）")

    # G4 第三源对照：同编辑组成员互遮 = 合法（不误拦）
    m = copy.deepcopy(ie)
    # 找同组两成员并让它们重叠（若原本不重叠）
    if _eg0:
        a = next(e for e in m["elements"] if e["id"] == _eg0[0]["members"][0])
        b = next(e for e in m["elements"] if e["id"] == _eg0[0]["members"][1])
        b["rect"] = (a["rect"][0] + 0.05, a["rect"][1] + 0.05,
                     a["rect"][2], a["rect"][3])
    check("IR 同编辑组互遮合法", ce, m, pe, expect_ok=False,
          mutate_desc="同编辑组成员重叠（G4 第三源，不得误拦）")
```

- [ ] **Step 9: regression 示例 `_probe/edit_groups.yaml`**

```yaml
meta:
  title: 编辑单元示例
  style_guide: flowchart
  slide: {w: 13.333, h: 7.5}
  margin: {l: 0.5, t: 0.5, r: 0.5, b: 0.5}
palette:
  d: '#2D6CDF'
  p: '#1F2A44'
  h: '#F2EFE9'
elements:
  # 玻璃/边框/高光三件套必然互遮 → 编辑单元声明使其合法（G4 第三源）+ COM 组
  - id: frame
    type: shape
    kind: rounded_rect
    rect: [2.0, 1.5, 4.0, 3.0]
    style: {fill: p, border: d, border_w: 2}
  - id: glass
    type: shape
    kind: rounded_rect
    rect: [2.3, 1.8, 3.4, 2.4]
    style: {fill: h, opacity: 0.4, border: None}
  - id: highlight
    type: shape
    kind: rounded_rect
    rect: [2.6, 2.1, 1.2, 0.5]
    style: {fill: d, opacity: 0.6, border: None}
  - id: pump
    type: shape
    kind: rounded_rect
    rect: [8.0, 2.0, 2.0, 1.0]
    style: {fill: p}
    text: 泵
relations:
  edit_groups:
    - id: window
      members: [frame, glass, highlight]
```

> 校验：互遮对 frame↔glass、frame↔highlight、glass↔highlight 全属 window 组 →
> G4 合法；z 收拢后组内连续（G11）；pump 不遮任何组员。
> `opacity` 仅 cylinder 支持（spec_compile 拦：shape 带 opacity 且非 cylinder
> 报错！）——**玻璃/高光改为用 style.fill 直接浅色表达**（去掉 opacity 键），
> 或用半透明表达的需求留给 cylinder。修订：把 glass/highlight 的 opacity 删掉，
> fill 用浅色 token。

修订后元素：

```yaml
  - id: glass
    type: shape
    kind: rounded_rect
    rect: [2.3, 1.8, 3.4, 2.4]
    style: {fill: '#D8E6F7', border: None}   # 浅蓝玻璃（调色板外 hex 合法）
  - id: highlight
    type: shape
    kind: rounded_rect
    rect: [2.6, 2.1, 1.2, 0.5]
    style: {fill: '#9DC3F2', border: None}
```

- [ ] **Step 10: regression.py 增例**

```python
    ("edit-groups", "_probe/edit_groups.yaml", 11),  # 编辑单元：3 件套 + pump + 组区间物证
```

（物证计数同样以实际跑批校准。）

- [ ] **Step 11: 变更记录**

`wiki/_log.md` 追加：
`2026-09-30 块2 落地：relations.edit_groups（spec_compile 拦截/ir _coalesce z 收拢/
verify G4 第三源+G11/com 组泛化）+ _probe/edit_groups.yaml`

---

### Task 4: 文档与全量回归验收

**Files:**
- Modify: `wiki/modules/spec_compile.md`、`wiki/modules/spec_validator.md`、
  `wiki/modules/ir_builder.md`、`wiki/modules/verify.md`、
  `wiki/modules/com_layer.md`、`wiki/modules/styleguides.md`
- Modify: `references/copyediting.md`（scansci 经验条目）
- Modify: `wiki/decisions/2026-09-30-internalize-scansci-design.md`（状态：approved→done）

- [ ] **Step 1: 模块页更新**

按各模块现风格追加小节（不要重写既有内容）：
- `spec_compile.md`：元素字段 `anchors`（[nx,ny]∈[0,1]²）+ glue `from_anchor`/
  `to_anchor`（省略回退 AABB）+ relations 段 `edit_groups`（成员须顶层产生形状/
  禁跨组重复）校验点。
- `spec_validator.md`：shape 白名单含 `anchors`。
- `ir_builder.md`：anchors 归一→绝对（铁律 1 内）；`_side_of` 边推导优先序
  （角点取横向）；`_coalesce_edit_groups` z 收拢算法与不变量。
- `verify.md`：G10（锚点一致，具名 glue 豁免 G5/G6）、G11（编辑组 z 区间）、
  G4 第三合法源（同编辑组）、S8/S9（size_fs_floor/labels_follow）——注明第二
  实现独立重算。
- `com_layer.md`：组入口统一 edit_groups（Group 改 spTree → WARN 提示）；
  具名锚点 glue 偏移 >0.25in → WARN 披露。
- `styleguides.md`：可选键 size_fs_floor / labels_follow（缺省不启用）。

- [ ] **Step 2: copyediting.md scansci 经验条目**

追加：复杂度预算原则（每视觉单元 ≤ 语义色上限 + 字号层级下限）、识别性优先
（小尺寸元素字号下限 size_fs_floor）、图例/标签组织（labels_follow——标签随
部件移动，独立图例才可游离）、连接锚点使用指引（具名锚点从属形态，不自动吸附）、
编辑单元语义（成员共同移动、可互遮为合法）。

- [ ] **Step 3: 全量回归**

Run（全部必须 exit 0）：

```
win_py -X utf8 tests/test_style_rules.py
win_py -X utf8 tests/test_scansci_compile.py
win_py -X utf8 -W ignore tests/run_mutations.py
win_py -X utf8 -W ignore tests/regression.py
win_py -X utf8 -W ignore tests/render_guards.py
win_py -X utf8 tests/test_anim_group.py
win_py -X utf8 tests/test_alpha_math.py
win_py -X utf8 tests/test_params_stack.py
win_py -X utf8 tests/test_typst_compile.py
win_py -X utf8 tests/run_fixer.py
```

Expected: 0 失败；regression 里新增 anchors / edit-groups 两例证据计数与实际
`evidence: OK n/m` 对齐（首跑若 n≠占位值，回填 CASES 精确 n 再跑）。

- [ ] **Step 4: 设计文档状态收尾**

`wiki/decisions/2026-09-30-internalize-scansci-design.md` frontmatter
`status: approved` → `status: done`，追加一行「落地回执：MVP 已实现（见
wiki/plans/2026-09-30-internalize-scansci-plan.md），测试全绿」。

- [ ] **Step 5: 变更记录**

`wiki/_log.md` 追加：
`2026-09-30 scansci 内化 MVP 验收：块3/块1/块2 全落地，全测试绿（run_mutations+
regression+render_guards+全部单测+run_fixer）；COM 组/锚点偏移披露待 Office 环境复核`

---

## 自检（self-review）

- **Spec 覆盖**：设计文档三块全部映射到 Task 1/2/3；实施顺序（块3→块1→块2）保持；
  每块含单测 + 突变 + regression 示例（块 3 规则缺省不启用 → 单测/突变背书）+
  wiki 页更新（Task 4）。
- **占位符扫描**：无 TBD/TODO；所有代码块可直接落盘。唯一已知校准点 = regression
  物证计数 n（Step 10 注明首跑回填）与 `Report.__init__` 签名（Task 1 Step 2 注明若
  不符以 verify.py 为准微调）。
- **类型一致性**：`an1/an2`（glue）与 `from_anchor/to_anchor`（SPEC）全链同名；
  `edit_groups` 段名 / IR 键 / com 消费一致；`_side_of` 输出 N/S/E/W 与 SITE_BY_KIND
  键一致；`z_lo/z_hi` 在 IR 与 com 记录一致。