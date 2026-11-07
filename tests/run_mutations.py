# -*- coding: utf-8 -*-
"""run_mutations.py — 突变套件：篡改合法 SPEC/IR 的各处不变式，确认校验器逐一拦下。

铁律：没有突变被"放过" = 校验器非橡皮图章。三层覆盖：
  IR 层     改 ir_builder 产物（几何/锚点/文本/层级相关不变式）→ G/D/T 家族
  compiled 层 改编译产物（ladder 语义：单调/色数/账目/构件）→ S 家族
  编译层    改 SPEC 白名单（未知字段/未声明 token/非法 rect）→ spec_validator

对照：三份合法 SPEC 全过（flowchart / ladder / glue）。

用法：win_py -X utf8 -W ignore tests/run_mutations.py
退出码：0 = 全部突变被拦且对照全过；1 = 有突变漏拦（FAIL!）；2 = 其他错误
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import ir_builder
import params as _P
import spec_compile as SC
import spec_validator as SV
import verify as V

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = {"flow": os.path.join(ROOT, "examples", "flowchart", "chart.yaml"),
      "ladder": os.path.join(ROOT, "examples", "ladder", "ladder.yaml"),
      "glue": os.path.join(ROOT, "_probe", "glue.yaml"),
      "org": os.path.join(ROOT, "examples", "orgchart", "orgchart.yaml"),
      "chart": os.path.join(ROOT, "examples", "chart", "chart.yaml"),
      "deck": os.path.join(ROOT, "examples", "deck", "deck.yaml"),
      "method": os.path.join(ROOT, "examples", "method", "cylinder.yaml"),
      "anchors": os.path.join(ROOT, "_probe", "anchors.yaml"),
      "egroups": os.path.join(ROOT, "_probe", "edit_groups.yaml")}

_fail = []
_pass = []


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return SC.compile_spec(SC.load_yaml(f.read()))


def ir_of(compiled):
    p = _P.resolve((compiled.get("meta") or {}).get("params"))
    return ir_builder.build_ir(compiled, p), p


def check(name, compiled, ir, p, expect_ok, mutate_desc):
    """expect_ok=True = 期望校验器拦下（有违规）；False = 期望通过（无违规）。"""
    rep = V.run(ir, compiled, p)
    bad = bool(rep.violations)
    if bad != expect_ok:
        _fail.append(f"{name}: {'漏拦（该拦没拦）' if expect_ok else '误拦（该过没过）'} · {mutate_desc}")
        print(f"[FAIL!] {name} · {mutate_desc}")
        for fam, cname, cok, cdetail in rep.checks:
            if not cok:
                print(f"        ↳ {fam} {cname}: {cdetail}")
    else:
        tag = "拦截 ✓" if expect_ok else "通过 ✓"
        print(f"[OK] {name} {tag} · {mutate_desc}")
        _pass.append(name)


def base_pair(key):
    c = load(EX[key])
    ir, p = ir_of(c)
    return c, ir, p


def main():
    # ---- 对照：合法 SPEC 必须 0 违规 ----
    for key in ("flow", "ladder", "glue", "org", "chart", "method", "anchors", "egroups"):
        c, ir, p = base_pair(key)
        check(f"对照 {key}", c, ir, p, expect_ok=False, mutate_desc="合法 SPEC 全过")

    # ---- 多页序列（meta.slides）契约 ----
    def page_shims(compiled):
        """多页 compiled → 逐页 shim（与 build_ppt.build_pages 同语义）。"""
        shims, globale = [], compiled.get("meta") or {}
        for page in compiled["slides"]:
            meta = dict(globale)
            gm = dict(meta.get("margin") or {})
            gm.update(page.get("margin") or {})
            meta["margin"] = gm
            gf = dict(meta.get("framework") or {})
            for k, v in (page.get("framework") or {}).items():
                gf[k] = v
            meta["framework"] = gf
            shims.append({"meta": meta, "palette": compiled["palette"],
                          "elements": page["elements"],
                          "relations": page.get("relations") or {}})
        return shims

    # 对照：deck 3 页逐页合法全过（id 唯一域 = 页内、遮挡/安全区校验按页隔离）
    cd = load(EX["deck"])
    shims_d = page_shims(cd)
    for pi, sh in enumerate(shims_d):
        ir, pp = ir_of(sh)
        check(f"对照 deck S{pi + 1}", sh, ir, pp, expect_ok=False,
              mutate_desc=f"deck 页 {pi + 1}/{len(shims_d)} 合法全过")

    # M13 多页校验按页隔离：页 3 chart 移出安全区——仅该页被拦
    _bad = copy.deepcopy(shims_d[2])
    for e in _bad["elements"]:
        if e["type"] == "chart":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y + 5.0, w, h)
    ir, pp = ir_of(_bad)
    check("IR 多页页级隔离", _bad, ir, pp, expect_ok=True,
          mutate_desc="deck 页 3 chart 下移 5.0 越界（页 1/2 不受影响）")

    c0, ir0, p0 = base_pair("flow")
    E = {e["id"]: e for e in ir0["elements"]}
    L = ir0["lines"]

    # ---- IR 层：G 几何核心 ----
    # M1 节点重叠未声明：pay 移入 start 所在区域（owner 相同 → 兄弟合法，须改成跨 owner）
    m = copy.deepcopy(ir0)
    start, pay = E["start"], E["pay"]
    m["elements"] = [e for e in m["elements"] if e["id"] != "pay"]
    pay2 = copy.deepcopy(pay)
    pay2["rect"] = (start["rect"][0] + 0.05, start["rect"][1] + 0.05,
                    start["rect"][2], start["rect"][3])
    pay2["owner"] = None  # 取消同容器身份 → 未声明顶层重叠
    m["elements"].append(pay2)
    check("IR 未声明重叠", c0, m, p0, expect_ok=True, mutate_desc="pay 无声明叠 start")

    # M2 锚点挪出端口
    m = copy.deepcopy(ir0)
    m["lines"][0]["a1"] = (m["lines"][0]["a1"][0] + 0.35, m["lines"][0]["a1"][1])
    check("IR 锚点出界", c0, m, p0, expect_ok=True, mutate_desc="edge a1 右移 0.35")

    # M3 边端点缺失：引用不存在的节点
    m = copy.deepcopy(ir0)
    m["elements"] = [e for e in m["elements"] if e["id"] != "fail"]
    check("IR 边引用缺失", c0, m, p0, expect_ok=True, mutate_desc="删节点 fail，边仍引用")

    # M4 orth 折线结构破坏：水平段 y 偏移
    m = copy.deepcopy(ir0)
    for ln in m["lines"]:
        if ln.get("pts") and ln.get("way") == "orth":
            ln["pts"] = [ln["pts"][0], (ln["pts"][1][0], ln["pts"][1][1] + 0.5),
                         ln["pts"][2], ln["pts"][3]]
    check("IR orth 折线破坏", c0, m, p0, expect_ok=True, mutate_desc="折线中段 y+0.5")

    # M5 同层不同高：某节点高改 0.6（G8 同层同高）
    m = copy.deepcopy(ir0)
    for e in m["elements"]:
        if e["id"] == "ok":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w, 0.55)
    check("IR 同层不同高", c0, m, p0, expect_ok=True, mutate_desc="节点 ok 高改 0.55")

    # M6 组包络不 ⊇ 成员：bbox 缩小 0.7（> group_pad 0.3，成员必飞出）
    m = copy.deepcopy(ir0)
    b = m["groups"][0]["bbox"]
    m["groups"][0]["bbox"] = (b[0] + 0.35, b[1] + 0.35, b[2] - 0.7, b[3] - 0.7)
    check("IR 组包络漏成员", c0, m, p0, expect_ok=True, mutate_desc="g_main bbox 缩 0.7 超 pad")

    # M7 节点出图面板内容区
    m = copy.deepcopy(ir0)
    for e in m["elements"]:
        if e["id"] == "chk":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y + 5.0, w, h)   # 移出 graph 面板
    check("IR 节点出内容区", c0, m, p0, expect_ok=True, mutate_desc="chk 下移 5.0")

    # M8 顶层元素出安全区：title 越 margin.t
    m = copy.deepcopy(ir0)
    for e in m["elements"]:
        if e["id"] == "title":
            x, y, w, h = e["rect"]
            e["rect"] = (x, -0.3, w, h)
    check("IR 元素出安全区", c0, m, p0, expect_ok=True, mutate_desc="title y=-0.3 < margin.t")

    # ---- IR 层：T 文本 ----
    # M9 空文本
    m = copy.deepcopy(ir0)
    for e in m["elements"]:
        if e["id"] == "start":
            e["text"] = "   "
    check("IR 空文本", c0, m, p0, expect_ok=True, mutate_desc="start 文本空白")

    # M10 text_layout 与框矛盾：框缩到装不下原文本（fs/lines 保持）
    m = copy.deepcopy(ir0)
    for e in m["elements"]:
        if e["id"] == "chk":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w * 0.28, h)
    check("IR 文本溢出", c0, m, p0, expect_ok=True, mutate_desc="chk 框宽缩 0.28")

    # ---- IR 层：glue ----
    cg, ig, pg = base_pair("glue")
    m = copy.deepcopy(ig)
    m["elements"] = [e for e in m["elements"] if e["id"] != "s1"]
    check("IR glue 端点缺失", cg, m, pg, expect_ok=True, mutate_desc="删 glue 起点 s1")

    # M12 合法遮挡对照（顶层层叠 + overlap 声明）：不得误拦
    m = copy.deepcopy(ig)
    m["elements"].append({"id": "ov1", "type": "shape", "kind": "rounded_rect",
                          "z": 40, "rect": (9.2, 3.0, 2.0, 1.0),
                          "style": {"fill": "#2D6CDF"}})
    m["elements"].append({"id": "ov2", "type": "shape", "kind": "rounded_rect",
                          "z": 50, "rect": (9.6, 3.2, 2.0, 1.0),
                          "style": {"fill": "#2D6CDF"}})
    m["elements"][-1]["owner"] = None
    _ov = (compiled_from := copy.deepcopy(cg))
    _ov["relations"] = _ov.get("relations") or {}
    _ov["relations"]["overlap"] = [{"id": "ov1", "with": "ov2"}]
    check("IR 声明重叠合法", _ov, m, pg, expect_ok=False, mutate_desc="ov1/ov2 重叠 + overlap 声明")

    # M13 具名锚点端点偏离：篡改 IR glue a1 绝对位（≠ 元素 anchors 绝对位）——
    # G5/G6 对具名锚点 glue 豁免（an1 存在），须由 G10 独立重算起拦
    ca, ia, pa = base_pair("anchors")
    m = copy.deepcopy(ia)
    for gl in m["glue"]:
        if gl.get("an1"):
            gl["a1"] = (gl["a1"][0] + 0.2, gl["a1"][1])   # 挪离锚点绝对位
    check("IR 具名锚点端点偏离", ca, m, pa, expect_ok=True,
          mutate_desc="具名锚点 glue a1 右移 0.2（≠ 元素 anchors 绝对位）")

    # ---- scansci 内化块 2：编辑单元 ----
    ce, ie, pe = base_pair("egroups")
    eg0 = (ie.get("edit_groups") or [{}])[0]

    # M14 z 打散：把组内末成员 z 抬出组区间 → G11 独立重算起拦
    m = copy.deepcopy(ie)
    if eg0.get("members"):
        last = eg0["members"][-1]
        for e in m["elements"]:
            if e["id"] == last:
                e["z"] = max(e["z"] for e in m["elements"]) + 5
    check("IR 编辑组 z 打散", ce, m, pe, expect_ok=True,
          mutate_desc="编辑组成员 z 抬出组区间（G11 起拦）")

    # M15 G4 第三源对照：同编辑组成员互遮 = 合法（不得误拦）
    m = copy.deepcopy(ie)
    if eg0.get("members"):
        a = next(e for e in m["elements"] if e["id"] == eg0["members"][0])
        b = next(e for e in m["elements"] if e["id"] == eg0["members"][1])
        b["rect"] = (a["rect"][0] + 0.05, a["rect"][1] + 0.05,
                     a["rect"][2], a["rect"][3])
    check("IR 同编辑组互遮合法", ce, m, pe, expect_ok=False,
          mutate_desc="同编辑组成员重叠（G4 第三源，不得误拦）")

    # ---- compiled 层：S 规范（ladder）----
    cl, il, pl = base_pair("ladder")

    # S1 梯形宽度非严格递减：s3 改宽于 s2
    m = copy.deepcopy(cl)
    for ch in m["elements"][1]["children"]:   # elements[1] = stack1
        if ch["id"] == "s3":
            ch["width"] = 6.0
    mir, mp = ir_of(m)
    check("S 宽度不递减", m, mir, mp, expect_ok=True, mutate_desc="s3 width 3.0→6.0")

    # S2 色数超限：加第 4 级阶梯用新色（原 3 色保留，单调/账目仍合规 → 唯一违规 = 色数）
    m = copy.deepcopy(cl)
    m["elements"][1]["children"].append({"id": "s4", "type": "shape",
                                         "kind": "rounded_rect", "width": 2.0,
                                         "height": 0.95, "style": {"fill": "#E8B8B8"}})
    mir, mp = ir_of(m)
    check("S 色数超限", m, mir, mp, expect_ok=True, mutate_desc="新增 s4 第 4 色（> 3）")

    # S3 stack 账目不符：step 高度超标
    m = copy.deepcopy(cl)
    for ch in m["elements"][1]["children"]:
        ch["height"] = 1.9
    mir, mp = ir_of(m)
    check("S 栈账目超容", m, mir, mp, expect_ok=True, mutate_desc="step 高 0.95→1.9 溢出容器")

    # S4 必需构件缺失：删 title
    m = copy.deepcopy(cl)
    m["elements"] = [e for e in m["elements"] if e["id"] != "title"]
    mir, mp = ir_of(m)
    check("S 必需构件缺失", m, mir, mp, expect_ok=True, mutate_desc="删 title")

    # ---- scansci 内化块 3：size_fs_floor 规则注入突变（缺省不启用；启用必拦）----
    import styleguides as _SG
    _k8 = "__scan_s8__"
    _SG.RULE_SETS[_k8] = {"size_fs_floor": {"threshold": 1.2, "fs": 30}}
    try:
        # 用 glue 样例（顶层形状无 owner，不会被 S8 的 owner 豁免跳过；
        # 短边 1.0in < 1.2in 且默认 fs < 30 → 必违规）
        m = copy.deepcopy(cg)
        m["meta"]["style_guide"] = _k8
        mir, mp = ir_of(m)
        check("S8 注入规则拦截", m, mir, mp, expect_ok=True,
              mutate_desc="size_fs_floor fs=30：小尺寸顶层形状 fs 未达标")
    finally:
        del _SG.RULE_SETS[_k8]

    # ---- 编译层：白名单（spec_validator）----
    # C1 未声明 palette token
    m = copy.deepcopy(c0)
    m["elements"][0]["text_style"] = {"color": "ghost"}
    v = SV.validate(m)
    print(f"[OK] 编译 未声明 token 拦截 ✓" if v else f"[FAIL!] 编译 未声明 token 漏拦")
    (_pass if v else _fail).append("编译 未声明 token")

    # C2 未知字段
    m = copy.deepcopy(c0)
    m["elements"][1]["extra"] = 1
    v = SV.validate(m)
    print(f"[OK] 编译 未知字段拦截 ✓" if v else "[FAIL!] 编译 未知字段漏拦")
    (_pass if v else _fail).append("编译 未知字段")

    # C3 非法 rect（负宽）—— 编译期静态错误，走 spec_compile 断言抛错
    base_text = open(EX["flow"], "r", encoding="utf-8").read()
    bad_text = base_text.replace("rect: [0.5, 1.6, 12.33, 5.4]", "rect: [0.5, 1.6, -12.33, 5.4]")
    try:
        SC.compile_spec(SC.load_yaml(bad_text))
        ok, why = False, "负宽 rect 竟编译通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 非法 rect 拦截 ✓ ({why})" if ok else f"[FAIL!] 编译 非法 rect 漏拦")
    (_pass if ok else _fail).append("编译 非法 rect")

    # C4 formula 缺 expr —— 编译期抛错（exit 2 契约）
    bad_fx = {"meta": {"title": "t", "style_guide": "flowchart", "slide": {"w": 13.333, "h": 7.5},
                       "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
              "palette": {"p": "#1F2A44"},
              "elements": [{"id": "fx", "type": "formula", "rect": [0.6, 1.0, 5.0, 1.0]}]}
    try:
        SC.compile_spec(bad_fx)
        ok, why = False, "formula 缺 expr 竟编译通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 formula 缺 expr 拦截 ✓ ({why})" if ok else f"[FAIL!] 编译 formula 缺 expr 漏拦")
    (_pass if ok else _fail).append("编译 formula 缺 expr")

    # C5 formula expr 空白 —— 同 C4
    bad_fx["elements"][0]["expr"] = "   "
    try:
        SC.compile_spec(bad_fx)
        ok, why = False, "formula 空白 expr 竟编译通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 formula 空白 expr 拦截 ✓ ({why})" if ok else f"[FAIL!] 编译 formula 空白 expr 漏拦")
    (_pass if ok else _fail).append("编译 formula 空白 expr")

    # C6 formula 未知字段 —— spec_validator 白名单拦截
    bad_fx = {"meta": {"title": "t", "style_guide": "flowchart", "slide": {"w": 13.333, "h": 7.5},
                       "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
              "palette": {"p": "#1F2A44"},
              "elements": [{"id": "fx", "type": "formula", "rect": [0.6, 1.0, 5.0, 1.0],
                            "expr": "a/b", "expr2": "x^2"}]}
    v = SV.validate(bad_fx)
    print(f"[OK] 编译 formula 未知字段拦截 ✓" if v else "[FAIL!] 编译 formula 未知字段漏拦")
    (_pass if v else _fail).append("编译 formula 未知字段")

    # ---- framework 框架层契约（背景/页眉/页脚：不进 IR → 校验天然豁免；
    #      编译层拦 fill 语义/未知键/保留名）----
    _FW_BASE = {"meta": {"title": "t", "style_guide": "flowchart",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
                "palette": {"p": "#1F2A44"},
                "elements": [{"id": "t1", "type": "shape", "kind": "rounded_rect",
                              "rect": [1.0, 1.0, 3.0, 1.0], "style": {"fill": "p"}}]}
    _FW_OK = copy.deepcopy(_FW_BASE)
    _FW_OK["meta"]["framework"] = {"background": {"fill": {"grad": ["#FFFFFF", "#EAF1F9"]}},
                                   "header": {"text": "白皮书", "align": "right", "fs": 10},
                                   "footer": {"text": "机密 · {page}", "color": "p"}}
    compiled_fw = SC.compile_spec(copy.deepcopy(_FW_OK))
    ir_fw, p_fw = ir_of(compiled_fw)
    check("对照 framework", compiled_fw, ir_fw, p_fw, expect_ok=False,
          mutate_desc="合法框架层（grad 背景+页眉+页脚）全过")
    # C7 framework fill 非法（grad 外键）
    _fwe = copy.deepcopy(_FW_BASE)
    _fwe["meta"]["framework"] = {"background": {"fill": {"oops": 1}}}
    try:
        SC.compile_spec(_fwe)
        ok, why = False, "fill dict 仅 grad 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 framework fill 非法拦截 ✓ ({why})" if ok else "[FAIL!] 编译 framework fill 非法漏拦")
    (_pass if ok else _fail).append("编译 framework fill 非法")

    # C8 framework 未知键
    _fwe = copy.deepcopy(_FW_BASE)
    _fwe["meta"]["framework"] = {"sidebar": {"text": "x"}}
    try:
        SC.compile_spec(_fwe)
        ok, why = False, "sidebar 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 framework 未知键拦截 ✓ ({why})" if ok else "[FAIL!] 编译 framework 未知键漏拦")
    (_pass if ok else _fail).append("编译 framework 未知键")

    # C9 framework 保留名 id
    _fwe = copy.deepcopy(_FW_BASE)
    _fwe["elements"][0]["id"] = "bg"
    try:
        SC.compile_spec(_fwe)
        ok, why = False, "id=bg 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 framework 保留名拦截 ✓ ({why})" if ok else "[FAIL!] 编译 framework 保留名漏拦")
    (_pass if ok else _fail).append("编译 framework 保留名")

    # ---- notes 备注页契约（单页 meta.notes / 多页 slides[i].notes；纯渲染层）----
    _NT_BASE = {"meta": {"title": "t", "style_guide": "flowchart",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
                "palette": {"p": "#1F2A44"},
                "elements": [{"id": "t1", "type": "shape", "kind": "rounded_rect",
                              "rect": [1.0, 1.0, 3.0, 1.0], "style": {"fill": "p"}}]}
    _nt = copy.deepcopy(_NT_BASE)
    _nt["meta"]["notes"] = "演讲要点：先讲背景，再讲方案"
    compiled_nt = SC.compile_spec(_nt)
    ir_nt, p_nt = ir_of(compiled_nt)
    if ir_nt.get("notes") != "演讲要点：先讲背景，再讲方案":
        _fail.append("notes IR 直通：meta.notes 未进 IR")
        print("[FAIL!] notes IR 直通")
    check("对照 notes 单页", compiled_nt, ir_nt, p_nt, expect_ok=False,
          mutate_desc="单页 meta.notes 合法全过")
    _ntb = copy.deepcopy(_NT_BASE)
    _ntb["meta"]["notes"] = 123
    try:
        SC.compile_spec(_ntb)
        ok, why = False, "meta.notes=123 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 notes 类型拦截 ✓ ({why})" if ok else "[FAIL!] 编译 notes 类型漏拦")
    (_pass if ok else _fail).append("编译 notes 类型")
    _ntb = {"meta": {"title": "t", "style_guide": "deck",
                     "slide": {"w": 13.333, "h": 7.5}, "notes": "全局备注",
                     "slides": [{"elements": [{"id": "a", "type": "text",
                                               "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}]}]},
            "palette": {"p": "#1F2A44"}}
    try:
        SC.compile_spec(_ntb)
        ok, why = False, "多页 meta.notes 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 多页全局 notes 拦截 ✓ ({why})" if ok else "[FAIL!] 编译 多页全局 notes 漏拦")
    (_pass if ok else _fail).append("编译 多页全局 notes")
    _ntb = {"meta": {"title": "t", "style_guide": "deck",
                     "slide": {"w": 13.333, "h": 7.5},
                     "slides": [{"elements": [{"id": "a", "type": "text",
                                               "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}],
                                 "notes": ["not", "list"]}]},
            "palette": {"p": "#1F2A44"}}
    try:
        SC.compile_spec(_ntb)
        ok, why = False, "slides[0].notes 列表竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 页级 notes 类型拦截 ✓ ({why})" if ok else "[FAIL!] 编译 页级 notes 类型漏拦")
    (_pass if ok else _fail).append("编译 页级 notes 类型")

    # ---- transition 页面切换契约（全局默认 meta.transition + 页级覆盖 slides[i].transition；----
    #      编译期解析每页有效值；effect=none 显式关闭；单页模式禁全局切换）----
    _TR_BASE = {"meta": {"title": "t", "style_guide": "deck",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                         "transition": {"effect": "fade", "spd": "slow"},
                         "slides": [
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "页一",
                                            "text_style": {"fs": 32}}]},
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "页二",
                                            "text_style": {"fs": 32}}],
                              "transition": {"effect": "push"}},
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "页三",
                                            "text_style": {"fs": 32}}],
                              "transition": {"effect": "none"}}]},
                "palette": {"p": "#1F2A44"}}
    compiled_tr = SC.compile_spec(copy.deepcopy(_TR_BASE))
    got_tr = [s.get("transition") for s in compiled_tr["slides"]]
    want_tr = [{"effect": "fade", "spd": "slow"},      # 继承全局默认
               {"effect": "push", "spd": "med"},       # 页覆盖（spd 缺省 med）
               {"effect": "none", "spd": "med"}]       # 显式关闭（none）
    if got_tr == want_tr:
        print("[OK] 编译 transition 继承解析 ✓ 全局默认/页覆盖/显式关闭")
        _pass.append("编译 transition 继承解析")
    else:
        _fail.append(f"transition 继承解析: {got_tr}")
        print("[FAIL!] 编译 transition 继承解析")
    shim_tr = {"meta": dict(_TR_BASE["meta"]), "palette": {"p": "#1F2A44"},
               "elements": compiled_tr["slides"][0]["elements"], "relations": {}}
    shim_tr["meta"]["transition"] = compiled_tr["slides"][0]["transition"]
    ir_tr, p_tr = ir_of(shim_tr)
    if ir_tr.get("transition") != {"effect": "fade", "spd": "slow"}:
        _fail.append("transition IR 直通：页级有效值未进 IR")
        print("[FAIL!] transition IR 直通")
    check("对照 transition 页", shim_tr, ir_tr, p_tr, expect_ok=False,
          mutate_desc="transition 页合法全过（切换不进 IR 几何）")
    _trb = copy.deepcopy(_TR_BASE)
    _trb["meta"]["slides"][0]["transition"] = {"effect": "blinds"}
    try:
        SC.compile_spec(_trb)
        ok, why = False, "effect=blinds 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 transition 非法 effect 拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 transition 非法 effect 漏拦")
    (_pass if ok else _fail).append("编译 transition 非法 effect")
    _trb = copy.deepcopy(_TR_BASE)
    _trb["meta"]["transition"] = {"effect": "fade", "spd": "ultra"}
    try:
        SC.compile_spec(_trb)
        ok, why = False, "spd=ultra 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 transition 非法 spd 拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 transition 非法 spd 漏拦")
    (_pass if ok else _fail).append("编译 transition 非法 spd")
    _trb = copy.deepcopy(_TR_BASE)
    _trb["meta"]["slides"][0]["transition"] = "fade"
    try:
        SC.compile_spec(_trb)
        ok, why = False, "transition 字符串竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 transition 非 dict 拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 transition 非 dict 漏拦")
    (_pass if ok else _fail).append("编译 transition 非 dict")
    _trb = {"meta": {"title": "t", "style_guide": "flowchart",
                     "slide": {"w": 13.333, "h": 7.5},
                     "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                     "transition": {"effect": "fade"}},
            "palette": {"p": "#1F2A44"},
            "elements": [{"id": "t1", "type": "shape", "kind": "rounded_rect",
                          "rect": [1.0, 1.0, 3.0, 1.0], "style": {"fill": "p"}}]}
    try:
        SC.compile_spec(_trb)
        ok, why = False, "单页 meta.transition 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 单页全局 transition 拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 单页全局 transition 漏拦")
    (_pass if ok else _fail).append("编译 单页全局 transition")

    # ---- link 元素级超链接契约（{url|slide|email} 三选一；slide 边界/自跳编译期拦）----
    _LK_BASE = {"meta": {"title": "t", "style_guide": "deck",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                         "slides": [
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "目录",
                                            "text_style": {"fs": 32}},
                                           {"id": "l1", "type": "shape", "kind": "rounded_rect",
                                            "rect": [1.0, 2.2, 3.0, 0.8],
                                            "link": {"url": "https://example.com"}},
                                           {"id": "l2", "type": "shape", "kind": "rounded_rect",
                                            "rect": [1.0, 3.2, 3.0, 0.8],
                                            "link": {"slide": 2}},
                                           {"id": "l3", "type": "shape", "kind": "rounded_rect",
                                            "rect": [1.0, 4.2, 3.0, 0.8],
                                            "link": {"email": "a@b.c"}}]},
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "正文",
                                            "text_style": {"fs": 32}}]}]},
                "palette": {"p": "#1F2A44", "soft": "#EAF1F9"}}
    compiled_lk = SC.compile_spec(copy.deepcopy(_LK_BASE))
    l0 = compiled_lk["slides"][0]["elements"]
    if next(e["link"] for e in l0 if e["id"] == "l2") != {"slide": 2}:
        _fail.append("link IR 直通：slides[i].elements link 未保留")
        print("[FAIL!] link IR 直通")
    shim_lk = {"meta": _LK_BASE["meta"], "palette": {"p": "#1F2A44", "soft": "#EAF1F9"},
               "elements": list(l0), "relations": {}}
    ir_lk, p_lk = ir_of(shim_lk)
    check("对照 link 页", shim_lk, ir_lk, p_lk, expect_ok=False,
          mutate_desc="link 元素合法全过（超链接不进 IR 几何）")
    _lkb = copy.deepcopy(_LK_BASE)
    _lkb["meta"]["slides"][0]["elements"][1]["link"] = {}
    try:
        SC.compile_spec(_lkb)
        ok, why = False, "空 link 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 link 空 dict 拦截 ✓ ({why})" if ok else "[FAIL!] 编译 link 空 dict 漏拦")
    (_pass if ok else _fail).append("编译 link 空 dict")
    _lkb = copy.deepcopy(_LK_BASE)
    _lkb["meta"]["slides"][0]["elements"][1]["link"] = {"url": "https://x", "slide": 2}
    try:
        SC.compile_spec(_lkb)
        ok, why = False, "url+slide 并存竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 link 多 target 拦截 ✓ ({why})" if ok else "[FAIL!] 编译 link 多 target 漏拦")
    (_pass if ok else _fail).append("编译 link 多 target")
    _lkb = copy.deepcopy(_LK_BASE)
    _lkb["meta"]["slides"][0]["elements"][1]["link"] = {"slide": 9}
    try:
        SC.compile_spec(_lkb)
        ok, why = False, "slide: 9（越界）竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 link slide 越界拦截 ✓ ({why})" if ok else "[FAIL!] 编译 link slide 越界漏拦")
    (_pass if ok else _fail).append("编译 link slide 越界")
    _lkb = copy.deepcopy(_LK_BASE)
    _lkb["meta"]["slides"][1]["elements"].append(
        {"id": "back", "type": "shape", "kind": "rounded_rect",
         "rect": [1.0, 2.5, 3.0, 0.8], "link": {"slide": 2}})
    try:
        SC.compile_spec(_lkb)
        ok, why = False, "页 2 自跳 slide:2 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 link 自跳拦截 ✓ ({why})" if ok else "[FAIL!] 编译 link 自跳漏拦")
    (_pass if ok else _fail).append("编译 link 自跳")
    _lkb = copy.deepcopy(_LK_BASE)
    _lkb["meta"]["slides"][1]["elements"].append(
        {"id": "st", "type": "stack", "orientation": "vertical",
         "rect": [1.0, 2.5, 4.0, 2.0], "link": {"url": "https://x"},
         "children": [{"id": "c1", "type": "text", "text": "x",
                       "width": 3.0, "height": 0.6}]})
    try:
        SC.compile_spec(_lkb)
        ok, why = False, "容器挂 link 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 link 容器拦截 ✓ ({why})" if ok else "[FAIL!] 编译 link 容器漏拦")
    (_pass if ok else _fail).append("编译 link 容器")
    _lkb = copy.deepcopy(_LK_BASE)
    _lkb["meta"]["slides"][0]["elements"][1]["link"] = "https://x"
    try:
        SC.compile_spec(_lkb)
        ok, why = False, "link 字符串竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 link 非 dict 拦截 ✓ ({why})" if ok else "[FAIL!] 编译 link 非 dict 漏拦")
    (_pass if ok else _fail).append("编译 link 非 dict")

    # ---- animation 动效契约（{effect 配方 | behaviors 直写} 二选一；配方名/字段/容器 ----
    #      编译期拦；合法元素 animation 原样进 IR，渲染/verify 不消费）----
    _AB_BASE = {"meta": {"title": "t", "style_guide": "deck",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                         "slides": [
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "动效页",
                                            "text_style": {"fs": 32}},
                                           {"id": "c1", "type": "shape", "kind": "rounded_rect",
                                            "rect": [1.0, 2.2, 3.0, 0.8],
                                            "animation": {"effect": "进入动画_自上浮入_改"}}]},
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "正文",
                                            "text_style": {"fs": 32}}]}]},
                "palette": {"p": "#1F2A44"}}
    compiled_ab = SC.compile_spec(copy.deepcopy(_AB_BASE))
    ab0 = compiled_ab["slides"][0]["elements"]
    if next(e["animation"] for e in ab0 if e["id"] == "c1") != {"effect": "进入动画_自上浮入_改"}:
        _fail.append("编译 animation 合法保留")
        print("[FAIL!] 编译 animation 合法 FAIL")
    shim_ab = {"meta": _AB_BASE["meta"], "palette": {"p": "#1F2A44"},
               "elements": list(ab0), "relations": {}}
    ir_ab, p_ab = ir_of(shim_ab)
    check("对照 animation 页", shim_ab, ir_ab, p_ab, expect_ok=False,
          mutate_desc="animation 元素合法全过（动画不进 IR 几何）")
    el_ab = next(e for e in ir_ab["elements"] if e["id"] == "c1")
    if el_ab.get("animation") != {"effect": "进入动画_自上浮入_改"}:
        _fail.append("animation IR 原样透传")
        print("[FAIL!] animation IR 原样透传")
    _abb = copy.deepcopy(_AB_BASE)
    _abb["meta"]["slides"][0]["elements"][1]["animation"] = \
        {"effect": "进入动画_不存在的宏"}
    try:
        SC.compile_spec(_abb)
        ok, why = False, "未注册 effect 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 animation 未注册 effect 拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 animation 未注册 effect 漏拦")
    (_pass if ok else _fail).append("编译 animation 未注册 effect")
    _abb = copy.deepcopy(_AB_BASE)
    _abb["meta"]["slides"][0]["elements"][1]["animation"] = \
        {"behaviors": [{"type": "zoom", "dur": 0.3}]}
    try:
        SC.compile_spec(_abb)
        ok, why = False, "非法 behavior 类型竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 animation behaviors 非法类型拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 animation behaviors 非法类型漏拦")
    (_pass if ok else _fail).append("编译 animation behaviors 非法类型")
    _abb = copy.deepcopy(_AB_BASE)
    _abb["meta"]["slides"][0]["elements"][1]["animation"] = \
        {"behaviors": [{"type": "scale", "from_x": 100, "to_x": 110}]}
    try:
        SC.compile_spec(_abb)
        ok, why = False, "缺 dur 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 animation behaviors 缺 dur 拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 animation behaviors 缺 dur 漏拦")
    (_pass if ok else _fail).append("编译 animation behaviors 缺 dur")
    _abb = copy.deepcopy(_AB_BASE)
    _abb["meta"]["slides"][1]["elements"].append(
        {"id": "st", "type": "stack", "orientation": "vertical",
         "rect": [1.0, 2.5, 4.0, 2.0],
         "animation": {"effect": "进入动画_快速淡入"},
         "children": [{"id": "c2", "type": "text", "text": "x",
                       "width": 3.0, "height": 0.6,
                       "animation": {"effect": "进入动画_快速淡入"}}]})
    try:
        SC.compile_spec(_abb)
        ok, why = False, "容器挂 animation 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 animation 容器拦截（children 允许）✓ ({why})" if ok
          else "[FAIL!] 编译 animation 容器漏拦")
    (_pass if ok else _fail).append("编译 animation 容器")
    _abb = copy.deepcopy(_AB_BASE)
    _abb["meta"]["slides"][0]["elements"][1]["animation"] = \
        {"effect": "进入动画_自上浮入_改", "behaviors": [{"type": "set", "dur": 0.1}]}
    try:
        SC.compile_spec(_abb)
        ok, why = False, "effect+behaviors 并存竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 animation effect+behaviors 并存拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 animation effect+behaviors 并存漏拦")
    (_pass if ok else _fail).append("编译 animation 并存")
    _abb = copy.deepcopy(_AB_BASE)
    _abb["meta"]["slides"][0]["elements"][1]["animation"] = \
        {"behaviors": [{"type": "property", "dur": 0.5, "attrib": "x",
                        "points": [["0", "#ppt_x"]]}]}
    try:
        SC.compile_spec(_abb)
        ok, why = False, "points 时间非数值竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 animation points 时间非数值拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 animation points 时间非数值漏拦")
    (_pass if ok else _fail).append("编译 animation points 时间类型")

    # ---- page_offset 页码偏移契约（meta.params.framework.page_offset 整数可负；----
    #      渲染/物证同规：显示页码 = 实际页号 + offset）----
    _PO_BASE = {"meta": {"title": "t", "style_guide": "deck",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                         "params": {"framework": {"page_offset": -1}},
                         "slides": [
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "封面",
                                            "text_style": {"fs": 32}}],
                              "framework": {"footer": {"text": ""}}},
                             {"elements": [{"id": "title", "type": "text",
                                            "rect": [1.0, 1.0, 6.0, 1.0], "text": "正文",
                                            "text_style": {"fs": 32}}]}]},
                "palette": {"p": "#1F2A44"}}
    compiled_po = SC.compile_spec(copy.deepcopy(_PO_BASE))
    p_po = _P.resolve(compiled_po["meta"].get("params"))
    if p_po["framework"]["page_offset"] != -1:
        _fail.append(f"page_offset 解析: {p_po['framework']['page_offset']}")
        print("[FAIL!] 编译 page_offset 解析")
    shim_po = {"meta": dict(compiled_po["meta"]), "palette": {"p": "#1F2A44"},
               "elements": compiled_po["slides"][1]["elements"], "relations": {}}
    ir_po, p_po2 = ir_of(shim_po)
    check("对照 page_offset 页", shim_po, ir_po, p_po2, expect_ok=False,
          mutate_desc="offset 整数可负、IR 几何不受影响")
    _pob = copy.deepcopy(_PO_BASE)
    _pob["meta"]["params"]["framework"]["page_offset"] = 0.5
    try:
        SC.compile_spec(_pob)
        ok, why = False, "page_offset=0.5 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 page_offset 浮点拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 page_offset 浮点漏拦")
    (_pass if ok else _fail).append("编译 page_offset 浮点")
    _pob = copy.deepcopy(_PO_BASE)
    _pob["meta"]["params"]["framework"]["page_offset"] = True
    try:
        SC.compile_spec(_pob)
        ok, why = False, "page_offset=true 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 page_offset 布尔拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 page_offset 布尔漏拦")
    (_pass if ok else _fail).append("编译 page_offset 布尔")

    # ---- table 表格积木契约（data 矩阵账目 / col_widths 和 / 单元格溢出 T 拦）----
    _TB_BASE = {"meta": {"title": "t", "style_guide": "flowchart",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
                "palette": {"p": "#1F2A44"},
                "elements": [{"id": "tb", "type": "table", "rect": [1.0, 1.0, 8.0, 3.0],
                              "data": [["指标", "数值"], [1, 2]],
                              "header": {"fs": 12, "fill": "p"}}]}
    compiled_tb = SC.compile_spec(copy.deepcopy(_TB_BASE))
    ir_tb, p_tb = ir_of(compiled_tb)
    check("对照 table", compiled_tb, ir_tb, p_tb, expect_ok=False,
          mutate_desc="合法表格（data 推导行列）全过")
    _bad = copy.deepcopy(_TB_BASE)
    _bad["elements"][0]["data"] = [["a", "b"], ["c"]]
    try:
        SC.compile_spec(_bad)
        ok, why = False, "非矩形 data 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 table 非矩形 data 拦截 ✓ ({why})" if ok else "[FAIL!] 编译 table 非矩形 data 漏拦")
    (_pass if ok else _fail).append("编译 table 非矩形 data")
    _bad = copy.deepcopy(_TB_BASE)
    _bad["elements"][0]["col_widths"] = [3.0, 3.0]      # 和 6 ≠ rect 宽 8
    try:
        SC.compile_spec(_bad)
        ok, why = False, "col_widths 和≠rect.w 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 table col_widths 账目拦截 ✓ ({why})" if ok else "[FAIL!] 编译 table col_widths 账目漏拦")
    (_pass if ok else _fail).append("编译 table col_widths 账目")
    _bad = copy.deepcopy(_TB_BASE)
    _bad["elements"][0]["data"] = [["很长很长很长的单元格文本内容" * 12, "b"], [1, 2]]
    compiled_tb2 = SC.compile_spec(_bad)                # 结构合法 →
    ir_tb2, p_tb2 = ir_of(compiled_tb2)                 # 单元格溢出应由 T 家族拦
    check("T 表格格溢出", compiled_tb2, ir_tb2, p_tb2, expect_ok=True,
          mutate_desc="单元格文本远超列宽")

    # ---- graph orientation 垂直（组织树）契约 ----
    # G6 vertical 重算：垂直跨层边 a1 改成同轴对侧端口（贴端口但非重算期望）
    c_v, ir_v, p_v = base_pair("org")
    m = copy.deepcopy(ir_v)
    for ln in m["lines"]:
        if ln["id"] == "org.ceo->rd":
            ceo = next(e for e in m["elements"] if e["id"] == "ceo")
            x, y, w, h = ceo["rect"]
            ln["a1"] = (round(x + w / 2, 3), round(y, 3))   # N 端口（对侧，重算期望 S）
    check("G6 vertical 重算", c_v, m, p_v, expect_ok=True,
          mutate_desc="垂直跨层边 a1 改对侧端口")
    _bad = copy.deepcopy(c_v)
    for e in _bad["elements"]:
        if e["type"] == "graph":
            e["orientation"] = "radial"
    try:
        SC.compile_spec(_bad)
        ok, why = False, "orientation=radial 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 graph orientation 非法值拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 graph orientation 非法值漏拦")
    (_pass if ok else _fail).append("编译 graph orientation 非法值")

    # ---- chart 图表积木契约（数据账目 / pie 单序列 / chart_type / colors token）----
    _CH_BASE = {"meta": {"title": "t", "style_guide": "deck",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
                "palette": {"p": "#1F2A44"},
                "elements": [{"id": "ch", "type": "chart", "rect": [1.0, 1.0, 8.0, 4.0],
                              "chart_type": "column_clustered",
                              "categories": ["A", "B"],
                              "series": [{"name": "s1", "values": [1, 2]},
                                         {"name": "s2", "values": [3, 4]}]}]}
    _ch_bad = copy.deepcopy(_CH_BASE)
    _ch_bad["elements"][0]["series"][0]["values"] = [1]      # 1 ≠ 2 类别
    try:
        SC.compile_spec(_ch_bad)
        ok, why = False, "values 数≠categories 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 chart 数据账目拦截 ✓ ({why})" if ok else "[FAIL!] 编译 chart 数据账目漏拦")
    (_pass if ok else _fail).append("编译 chart 数据账目")
    _ch_bad = copy.deepcopy(_CH_BASE)
    _ch_bad["elements"][0]["chart_type"] = "pie"
    _ch_bad["elements"][0]["series"].append({"name": "s3", "values": [5, 6]})
    try:
        SC.compile_spec(_ch_bad)
        ok, why = False, "pie 双序列竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 chart pie 单序列拦截 ✓ ({why})" if ok else "[FAIL!] 编译 chart pie 单序列漏拦")
    (_pass if ok else _fail).append("编译 chart pie 单序列")
    _ch_bad = copy.deepcopy(_CH_BASE)
    _ch_bad["elements"][0]["chart_type"] = "radar"
    try:
        SC.compile_spec(_ch_bad)
        ok, why = False, "chart_type=radar 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 chart 未知类型拦截 ✓ ({why})" if ok else "[FAIL!] 编译 chart 未知类型漏拦")
    (_pass if ok else _fail).append("编译 chart 未知类型")
    _ch_bad = copy.deepcopy(_CH_BASE)
    _ch_bad["elements"][0]["style"] = {"colors": ["nostalf"]}   # 未声明 token
    try:
        SC.compile_spec(_ch_bad)
        ok, why = False, "colors 未声明 token 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 chart colors token 拦截 ✓ ({why})" if ok else "[FAIL!] 编译 chart colors token 漏拦")
    (_pass if ok else _fail).append("编译 chart colors token")

    # ---- 多页（meta.slides）编译/白名单契约 ----
    def _mk_slides(scfg):
        base = {"meta": {"title": "t", "style_guide": "deck",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
                "palette": {"p": "#1F2A44"}}
        if scfg is not None:
            base["meta"]["slides"] = scfg
        return base

    # C10 slides 非列表
    try:
        SC.compile_spec(_mk_slides("x"))
        ok, why = False, "slides 字符串竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 slides 非列表拦截 ✓ ({why})" if ok else "[FAIL!] 编译 slides 非列表漏拦")
    (_pass if ok else _fail).append("编译 slides 非列表")

    # C11 多页 + 顶层 elements 并存 → 拦截（页面元素归属歧义）
    bad = _mk_slides([{"elements": [{"id": "a", "type": "text",
                                     "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}]}])
    bad["elements"] = [{"id": "t1", "type": "shape", "kind": "rounded_rect",
                        "rect": [1.0, 1.0, 3.0, 1.0], "style": {"fill": "p"}}]
    try:
        SC.compile_spec(bad)
        ok, why = False, "顶层 elements 与 slides 并存竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 多页+顶层elements 拦截 ✓ ({why})" if ok else "[FAIL!] 编译 多页+顶层elements 漏拦")
    (_pass if ok else _fail).append("编译 多页+顶层elements")

    # C12 页级未知键
    try:
        SC.compile_spec(_mk_slides([{"bad_key": 1}]))
        ok, why = False, "页级未知键竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 页级未知键拦截 ✓ ({why})" if ok else "[FAIL!] 编译 页级未知键漏拦")
    (_pass if ok else _fail).append("编译 页级未知键")

    # C13 页内 id 重复
    try:
        SC.compile_spec(_mk_slides([{"elements": [
            {"id": "a", "type": "text", "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"},
            {"id": "a", "type": "text", "rect": [1.0, 2.0, 2.0, 1.0], "text": "y"}]}]))
        ok, why = False, "页内 id 重复竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 页内 id 重复拦截 ✓ ({why})" if ok else "[FAIL!] 编译 页内 id 重复漏拦")
    (_pass if ok else _fail).append("编译 页内 id 重复")

    # C14 页级 palette token 未声明 → 白名单拦（slides 元素引用全局 palette；
    #   raw dict 直测 validate：若经 compile_spec 结构层 _check_color 已先拦截，
    #   则测不到白名单的页级路径）
    bad = {"meta": {"title": "t", "style_guide": "deck",
                    "slide": {"w": 13.333, "h": 7.5},
                    "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                    "slides": [{"elements": [{"id": "a", "type": "text",
                                              "rect": [1.0, 1.0, 2.0, 1.0],
                                              "text": "x",
                                              "text_style": {"color": "ghost"}}]}]},
           "palette": {"p": "#1F2A44"}}
    ok = bool(SV.validate(bad))
    print(f"[OK] 编译 页级 token 未声明拦截 ✓" if ok else "[FAIL!] 编译 页级 token 未声明漏拦")
    (_pass if ok else _fail).append("编译 页级 token 未声明")

    # ---- formula parser 契约（确定性判型同源：render 注入 / com 兜底分界的唯一依据）----
    import formula_omml as FO
    cases_ok = ["a/b + x^2 + c_i", "√(a+b)", "E=mc^2", "λ_n = α/β", "(a+1)/(b-1)", "a_i^2"]
    cases_fb = ["∑_(i=1)^n x_i", "\\sum_{i=1}^{n}", "∫_0^1 x dx", "|x|", "{a,b}"]
    p_ok = all(FO.parse_expr(e, 18)["ok"] for e in cases_ok)
    p_fb = all(not FO.parse_expr(e, 18)["ok"] for e in cases_fb)
    if p_ok and p_fb:
        print("[OK] 公式 parser 契约 ✓ 子集内 6 例注入 / 子集外 5 例兜底")
        _pass.append("公式 parser 契约")
    else:
        _fail.append("公式 parser 契约：子集判定与预期不符")
        print("[FAIL!] 公式 parser 契约")
        for e in cases_ok + cases_fb:
            r = FO.parse_expr(e, 18)
            want = e in cases_ok
            if r["ok"] != want:
                print(f"        ↳ {'期望注入但 not ok' if want else '期望兜底但 ok'}: {e} → {r.get('reason', r['ok'])}")

    # 行内/显示两种承载形态：同一 OMML 体，wrapper 决定 m:oMath vs m:oMathPara
    _body = FO.parse_expr("a/b + x^2", 18)["omml"]
    _in = FO.omath_inline(_body)
    _disp = FO.omath_paragraph(_body)
    t_in = "<m:oMath>" in _in and "oMathPara" not in _in
    t_disp = "<m:oMathPara>" in _disp and "<m:oMath>" in _disp
    if t_in and t_disp:
        print("[OK] 公式承载形态 ✓ 行内 m:oMath / 显示 m:oMathPara")
        _pass.append("公式承载形态")
    else:
        _fail.append(f"公式承载形态：in={t_in} disp={t_disp}")
        print("[FAIL!] 公式承载形态")

    # ---- formula 模板库契约（辅助手段：离线模板命中 / 归一化 / resolve 应用）----
    import formula_templates as FT
    t1 = FT.resolve("∑_(i=1)^n x_i", 18, None) is not None
    t2 = FT.resolve("∫_0^1 x dx", 18, None) is None          # 未收录的表达式不命中
    t3 = "w:rPr" not in FT.load()["∑_(i=1)^n x_i"]["omml"]    # 归一化：无 Word 命名空间残留
    t4 = 'sz="2400"' in FT.resolve("∑_(i=1)^n x_i", 24, None)   # resolve 应用 SPEC fs
    t5 = 'srgbClr val="2D6CDF"' in FT.resolve("∑_(i=1)^n x_i", 18, "2D6CDF")
    t6 = FT.supported("∑_(i=1)^n x_i", 18) and not FT.supported("∫_0^1 x dx", 18)
    t7 = FT.resolve("∏_(i=1)^n x_i", 18, None) is not None   # ∏ 也在模板库
    if t1 and t2 and t3 and t4 and t5 and t6 and t7:
        print("[OK] 公式模板库契约 ✓ 命中/未命中/归一化/fs/颜色/supported/∏收")
        _pass.append("公式模板库契约")
    else:
        _fail.append(f"公式模板库契约：t1={t1} t2={t2} t3={t3} t4={t4} t5={t5} t6={t6} t7={t7}")
        print("[FAIL!] 公式模板库契约")

    # ---- 文本排版契约（规则2：justify 对齐 / indent_chars 首行缩进字符串）----
    _TS_BASE = {"meta": {"title": "t", "style_guide": "flowchart",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
                "palette": {"p": "#1F2A44"},
                "elements": [{"id": "t1", "type": "text", "rect": [1.0, 1.0, 6.0, 1.0],
                              "text": "自然排列", "text_style": {"fs": 14}}]}
    _ts = copy.deepcopy(_TS_BASE)
    _ts["elements"][0]["text_style"] = {"fs": 14, "align": "justify", "indent_chars": 2}
    try:
        SC.compile_spec(_ts)
        ok, why = True, "justify+indent_chars 合法通过"
    except Exception as ex:
        ok, why = False, str(ex)[:80]
    print(f"[OK] 编译 justify+indent_chars 合法 ✓" if ok
          else f"[FAIL!] 编译 justify+indent_chars 合法: {why}")
    (_pass if ok else _fail).append("编译 justify+indent_chars 合法")
    _tsb = copy.deepcopy(_TS_BASE)
    _tsb["elements"][0]["text_style"] = {"fs": 14, "indent_chars": 2.5}
    try:
        SC.compile_spec(_tsb)
        ok, why = False, "indent_chars=2.5 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 indent_chars 非整数拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 indent_chars 非整数漏拦")
    (_pass if ok else _fail).append("编译 indent_chars 非整数")

    # ---- cylinder/curve 积木契约（编译层：slice/opacity 语义 + points 归一化 +
    #      style/dash 白名单；合法样例全链通过）----
    _CY_PAL = {"p": "#1F2A44", "blue": "#2D6CDF", "accent": "#E8590C"}

    def _cy_spec(elems):
        return {"meta": {"title": "t", "style_guide": "flowchart",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}},
                "palette": dict(_CY_PAL), "elements": elems}

    # 对照：合法 cylinder（slice/opacity）+ curve（归一化点 + 线 style）+ 虚线 line 全过
    _cy_ok = _cy_spec([
        {"id": "cyl", "type": "shape", "kind": "cylinder", "rect": [1.0, 1.0, 4.0, 2.5],
         "slice": 1.0, "opacity": 0.3, "style": {"fill": "blue"}},
        {"id": "cv", "type": "curve", "rect": [1.0, 4.0, 4.0, 1.5],
         "points": [[0.0, 0.5], [0.5, 0.2], [1.0, 0.6]],
         "style": {"color": "accent", "weight": 2.0, "dash": "dot"}},
        {"id": "dn", "type": "line", "rect": [1.0, 6.0, 4.0, 0.0],
         "x1": 1.0, "y1": 6.0, "x2": 5.0, "y2": 6.0,
         "color": "blue", "weight": 1.25, "dash": "dot"}])
    c_ok = SC.compile_spec(copy.deepcopy(_cy_ok))
    v_ok = SV.validate(c_ok)
    if v_ok:
        _fail.append(f"cylinder/curve 对照白名单误拦: {v_ok}")
        print(f"[FAIL!] cylinder/curve 对照白名单: {v_ok}")
    else:
        _pass.append("cylinder/curve 对照白名单")
        print("[OK] cylinder/curve 对照白名单 ✓")
    ir_cy, p_cy = ir_of(c_ok)
    check("对照 cylinder/curve", c_ok, ir_cy, p_cy, expect_ok=False,
          mutate_desc="合法 cylinder/curve/虚线 line 全过")

    def _cy_bad(elems, desc):
        """编译负例 helper：期望 SpecCompileError（其他异常 = 引擎 bug 亦判 fail）。"""
        try:
            SC.compile_spec(_cy_spec(elems))
            _fail.append(f"编译 {desc} 漏拦")
            print(f"[FAIL!] 编译 {desc} 漏拦")
        except SC.SpecCompileError:
            _pass.append(f"编译 {desc}")
            print(f"[OK] 编译 {desc} 拦截 ✓")
        except Exception as ex:
            _fail.append(f"编译 {desc} 误抛 {type(ex).__name__}")
            print(f"[FAIL!] 编译 {desc} 误抛 {type(ex).__name__}: {ex}")

    _cv_pt = {"id": "cv", "type": "curve", "rect": [1.0, 1.0, 4.0, 2.0]}
    _cy_bad([dict(_cv_pt, points=[[0.0, 0.5], [1.0, 0.6]])], "curve points<3")
    _cy_bad([dict(_cv_pt, points=[[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]])],
            "curve 全同点退化")
    _cy_bad([dict(_cv_pt, points=[[0.0, 0.5], [0.5, 1.2], [1.0, 0.6]])], "curve 归一化越界")
    _cy_bad([dict(_cv_pt, points=[[0.0, 0.5], [0.5, 0.2], [1.0, 0.6]],
                  style={"color": "accent", "fill": "blue"})], "curve style 未知键")
    _cy_bad([dict(_cv_pt, points=[[0.0, 0.5], [0.5, 0.2], [1.0, 0.6]],
                  style={"color": "accent", "weight": 0})], "curve weight≤0")
    _cy_bad([dict(_cv_pt, points=[[0.0, 0.5], [0.5, 0.2], [1.0, 0.6]],
                  style={"color": "accent", "dash": "solid"})], "curve dash 非法")
    _cy_bad([{"id": "cyl", "type": "shape", "kind": "cylinder",
              "rect": [1.0, 1.0, 4.0, 2.5], "slice": 1.5}], "cylinder slice>1")
    _cy_bad([{"id": "cyl", "type": "shape", "kind": "cylinder",
              "rect": [1.0, 1.0, 4.0, 2.5], "slice": 0}], "cylinder slice=0")
    _cy_bad([{"id": "cyl", "type": "shape", "kind": "cylinder",
              "rect": [1.0, 1.0, 4.0, 2.5], "opacity": 1.5}], "cylinder opacity 越界")
    _cy_bad([{"id": "rr", "type": "shape", "kind": "rounded_rect",
              "rect": [1.0, 1.0, 4.0, 2.0], "slice": 1.0,
              "style": {"fill": "blue"}}], "slice 仅 cylinder")
    _cy_bad([{"id": "dn", "type": "line", "rect": [1.0, 1.0, 4.0, 0.0],
              "x1": 1.0, "y1": 1.0, "x2": 5.0, "y2": 1.0,
              "color": "blue", "dash": "solid"}], "line dash 非法")

    # ---- page_intent 页型意图契约（审定菜单：agent 只选 intent token，引擎确定性
    #      展开版式；编译期拦 intent 枚举/字段归属/保留 id；verify 断言背书展开质量）----
    _PI_PAL = {"p": "#1F2A44", "acc": "#D08770"}   # acc 故意 ≠ 全局 accent，验证 token 解析
    _PI_COVER = {"title": "封面", "page_intent": "cover",
                 "cover": {"title": "2026 上半年经营分析报告",
                           "subtitle": "聚焦增长 · 控制风险",
                           "meta": "财务部 · 2026-09-09",
                           "accent": "acc"}}
    _PI_BODY = {"title": "议程",
                "elements": [{"id": "title", "type": "text",
                              "rect": [1.0, 1.0, 6.0, 1.0], "text": "汇报议程",
                              "text_style": {"fs": 28}}]}
    _PI_SECTION = {"title": "节页", "page_intent": "section",
                   "section": {"num": "02", "title": "预算执行与偏差分析",
                               "accent": "acc"}}

    def _pi_spec(slides):
        return {"meta": {"title": "t", "style_guide": "deck",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                         "slides": slides},
                "palette": dict(_PI_PAL)}

    _pi_glob = _pi_spec([_PI_COVER, _PI_BODY, _PI_SECTION])

    def _pi_shim(page):
        """页 shim（与 build_ppt.build_pages 同语义：透传 page_intent + intent 字段）。"""
        meta = copy.deepcopy(_pi_glob["meta"])
        gm = dict(meta.get("margin") or {})
        gm.update(page.get("margin") or {})
        meta["margin"] = gm
        gf = dict(meta.get("framework") or {})
        for k, v in (page.get("framework") or {}).items():
            gf[k] = v
        meta["framework"] = gf
        meta["page_intent"] = page.get("page_intent")
        if page.get("page_intent"):
            meta[page["page_intent"]] = page.get(page["page_intent"])
        return {"meta": meta, "palette": dict(_PI_PAL),
                "elements": page.get("elements") or [],
                "relations": page.get("relations") or {}}

    compiled_pi = SC.compile_spec(copy.deepcopy(_pi_glob))
    # 对照 cover 页：引擎展开在场 + accent token 解析 + 破格断言全过
    shim_cover = _pi_shim(compiled_pi["slides"][0])
    ir_cover, p_cover = ir_of(shim_cover)
    if ir_cover.get("page_intent") != "cover":
        _fail.append("page_intent IR 直通：页面意图未进 IR")
        print("[FAIL!] page_intent IR 直通")
    got_ids = {e["id"] for e in ir_cover["elements"]}
    need_ids = {"cov_deco", "cov_title", "cov_sub", "cov_meta"}
    if not need_ids <= got_ids:
        _fail.append(f"page_intent cover 展开缺失: {need_ids - got_ids}")
        print("[FAIL!] page_intent cover 展开缺失")
    deco = next(e for e in ir_cover["elements"] if e["id"] == "cov_deco")
    if deco["style"]["fill"] != "#D08770":
        _fail.append(f"page_intent accent token 解析: {deco['style']['fill']!r} ≠ #D08770")
        print("[FAIL!] page_intent accent token 解析")
    check("对照 page_intent cover", shim_cover, ir_cover, p_cover, expect_ok=False,
          mutate_desc="cover 引擎展开（deco/标题/副题/落款）合法全过")
    shim_body = _pi_shim(compiled_pi["slides"][1])
    ir_body, p_body = ir_of(shim_body)
    check("对照 page_intent body", shim_body, ir_body, p_body, expect_ok=False,
          mutate_desc="意图序列的内容对照页合法全过")
    # 对照 section 页：引擎展开在场 + 贯穿/层级断言全过
    shim_sec = _pi_shim(compiled_pi["slides"][2])
    ir_sec, p_sec = ir_of(shim_sec)
    if ir_sec.get("page_intent") != "section":
        _fail.append("page_intent IR 直通：section 意图未进 IR")
        print("[FAIL!] page_intent section IR 直通")
    sec_ids = {e["id"] for e in ir_sec["elements"]}
    if not {"sec_deco", "sec_num", "sec_title", "sec_guide"} <= sec_ids:
        _fail.append(f"page_intent section 展开缺失: {sec_ids}")
        print("[FAIL!] page_intent section 展开缺失")
    check("对照 page_intent section", shim_sec, ir_sec, p_sec, expect_ok=False,
          mutate_desc="section 引擎展开（数字/节名/强调条/引导线）合法全过")

    def _pi_bad(slides, desc):
        """编译负例 helper（同 _cy_bad：期望 SpecCompileError）。"""
        try:
            SC.compile_spec(_pi_spec(slides))
            _fail.append(f"编译 {desc} 漏拦")
            print(f"[FAIL!] 编译 {desc} 漏拦")
        except SC.SpecCompileError:
            _pass.append(f"编译 {desc}")
            print(f"[OK] 编译 {desc} 拦截 ✓")
        except Exception as ex:
            _fail.append(f"编译 {desc} 误抛 {type(ex).__name__}")
            print(f"[FAIL!] 编译 {desc} 误抛 {type(ex).__name__}: {ex}")

    _pi_bad([dict(_PI_BODY, page_intent="custom")], "page_intent 非法枚举")
    _pi_bad([dict(_PI_BODY, page_intent="content", cover={"title": "x"})],
            "intent 字段归属（content 挂 cover 字段）")
    _pi_bad([dict(_PI_COVER, cover=dict(_PI_COVER["cover"], oops=1))], "cover 未知字段")
    _pi_bad([dict(_PI_COVER, cover={"subtitle": "x"})], "cover 缺 title")
    _pi_bad([dict(_PI_COVER, elements=[
        {"id": "cov_title", "type": "text", "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}])],
        "cover 保留 id 冲突")
    _pi_bad([dict(_PI_SECTION, section={"title": "x"})], "section 缺 num")
    _pi_bad([dict(_PI_SECTION, section={"num": "02"})], "section 缺 title")
    _pi_bad([dict(_PI_SECTION, section=dict(_PI_SECTION["section"], oops=1))],
            "section 未知字段")
    _pi_bad([dict(_PI_SECTION, elements=[
        {"id": "sec_num", "type": "text", "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}])],
        "section 保留 id 冲突")
    try:
        SC.compile_spec({"meta": {"title": "t", "style_guide": "deck",
                                  "slide": {"w": 13.333, "h": 7.5},
                                  "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                                  "page_intent": "cover"},
                         "palette": dict(_PI_PAL),
                         "elements": [{"id": "t1", "type": "text",
                                       "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}]})
        ok, why = False, "单页 meta.page_intent 竟通过"
    except Exception as ex:
        ok, why = True, type(ex).__name__
    print(f"[OK] 编译 单页 meta.page_intent 拦截 ✓ ({why})" if ok
          else "[FAIL!] 编译 单页 meta.page_intent 漏拦")
    (_pass if ok else _fail).append("编译 单页 meta.page_intent")

    # ---- 设计语言层契约（meta.theme 三键：structure/motif/font_pair）----
    def _th_spec(theme):
        return {"meta": {"title": "t", "style_guide": "deck",
                         "slide": {"w": 13.333, "h": 7.5},
                         "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5},
                         "theme": theme},
                "palette": dict(_PI_PAL),
                "elements": [{"id": "title", "type": "text",
                              "rect": [1.0, 1.0, 6.0, 1.0], "text": "标题"}]}

    def _th_bad(theme, desc):
        try:
            SC.compile_spec(_th_spec(theme))
            _fail.append(f"编译 {desc} 漏拦")
            print(f"[FAIL!] 编译 {desc} 漏拦")
        except SC.SpecCompileError:
            _pass.append(f"编译 {desc}")
            print(f"[OK] 编译 {desc} 拦截 ✓")
        except Exception as ex:
            _fail.append(f"编译 {desc} 误抛 {type(ex).__name__}")
            print(f"[FAIL!] 编译 {desc} 误抛 {type(ex).__name__}: {ex}")

    # 正例：三键合法且组合（sandwich + circle_icon + serif_sans）可编译
    try:
        _c = SC.compile_spec(_th_spec({"name": "coral_energy", "structure": "sandwich",
                                       "motif": "circle_icon", "font_pair": "serif_sans"}))
        print("[OK] 编译 theme 三键组合合法 ✓")
        _pass.append("编译 theme 三键组合")
    except Exception as ex:
        print(f"[FAIL!] 编译 theme 三键组合误抛 {type(ex).__name__}: {ex}")
        _fail.append("编译 theme 三键组合")
    _th_bad({"name": "coral_energy", "motif": "bogus"}, "theme.motif 非法枚举")
    _th_bad({"name": "coral_energy", "structure": "bogus"}, "theme.structure 非法枚举")
    _th_bad({"name": "coral_energy", "font_pair": "bogus"}, "theme.font_pair 非法枚举")
    _th_bad({"primary": "#124CAD", "structure": "dark"},
            "theme.structure=dark 缺 mode=dark")

    # ---- IR 层：verify 页型断言（破格度 / 必需构件）----
    m = copy.deepcopy(ir_cover)
    for e in m["elements"]:
        if e["id"] == "cov_title":
            w = e["rect"][2]
            e["rect"] = (13.333 / 2 - w / 2, e["rect"][1], w, e["rect"][3])
    check("IR cover 破格度破坏", shim_cover, m, p_cover, expect_ok=True,
          mutate_desc="cov_title 水平中心对准 slide 中心（破格度→0）")
    m = copy.deepcopy(ir_cover)
    m["elements"] = [e for e in m["elements"] if e["id"] != "cov_deco"]
    check("IR cover 必需构件缺失", shim_cover, m, p_cover, expect_ok=True,
          mutate_desc="删 cov_deco（破格封面必需构件）")
    m = copy.deepcopy(ir_sec)
    for e in m["elements"]:
        if e["id"] == "sec_num":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w, 2.0)     # 大数字贯穿 → 普通文本行
    check("IR section 贯穿度破坏", shim_sec, m, p_sec, expect_ok=True,
          mutate_desc="sec_num 高 3.25→2.0（< 版心 40%）")
    m = copy.deepcopy(ir_sec)
    for e in m["elements"]:
        if e["id"] == "sec_num":
            e["text_layout"]["fs"] = 24    # 数字降为普通标题字号（层级消失）
    check("IR section 字号层级破坏", shim_sec, m, p_sec, expect_ok=True,
          mutate_desc="sec_num fs 96→24（≤ title fs 40）")

    # ---- 科研三件套页型（C1）：problem / versus / route（references/page-intents.md §8）----
    _PI_PROBLEM = {"title": "问题", "page_intent": "problem",
                   "problem": {"title": "高噪声长序列上误差累积",
                               "items": ["异常点敏感", "在线延迟超标", "标注稀疏"],
                               "accent": "acc"}}
    _PI_VERSUS = {"title": "对照", "page_intent": "versus",
                  "versus": {"left_title": "基线：卡尔曼滤波",
                             "right_title": "本方法：鲁棒滤波",
                             "left_items": ["高斯假设敏感"], "right_items": ["重尾降权"],
                             "vs": "VS", "accent": "acc"}}
    _PI_ROUTE = {"title": "路线", "page_intent": "route",
                 "route": {"title": "四阶段路线",
                           "stages": ["问题建模", "鲁棒滤波", "在线推理", "实证验证"],
                           "accent": "acc"}}
    _sci_glob = _pi_spec([_PI_PROBLEM, _PI_VERSUS, _PI_ROUTE])
    _sci_comp = SC.compile_spec(copy.deepcopy(_sci_glob))
    _sci_ir = {}
    for si, (intent, need) in enumerate((
            ("problem", {"prb_badge", "prb_title", "prb_items"}),
            ("versus", {"vsv_panel_l", "vsv_panel_r", "vsv_divider", "vsv_tag",
                        "vsv_title_l", "vsv_body_r"}),
            ("route", {"rte_title", "rte_stage1", "rte_stage4"}))):
        shim = _pi_shim(_sci_comp["slides"][si])
        ir_, p_ = ir_of(shim)
        _sci_ir[intent] = (shim, ir_, p_)
        if ir_.get("page_intent") != intent:
            _fail.append(f"科研页型 IR 直通: {intent}")
            print(f"[FAIL!] 科研页型 IR 直通 {intent}")
        got = {e["id"] for e in ir_["elements"]}
        if not need <= got:
            _fail.append(f"科研页型 {intent} 展开缺失: {need - got}")
            print(f"[FAIL!] 科研页型 {intent} 展开缺失")
        check(f"对照科研页型 {intent}", shim, ir_, p_, expect_ok=False,
              mutate_desc=f"{intent} 引擎展开合法全过")
    # accent token 解析（route 阶段条填色 = palette acc）
    _rs0 = next(e for e in _sci_ir["route"][1]["elements"] if e["id"] == "rte_stage1")
    if _rs0["style"]["fill"] != "#D08770":
        _fail.append(f"科研页型 accent token 解析: {_rs0['style']['fill']!r} ≠ #D08770")
        print("[FAIL!] 科研页型 accent token 解析")
    # route 箭头连线在场（N 阶段 → N-1 箭头）
    _rlinks = [ln for ln in _sci_ir["route"][1]["lines"] if ln["id"].startswith("rte_lnk")]
    if len(_rlinks) != 3:
        _fail.append(f"科研页型 route 箭头数: {len(_rlinks)} ≠ 3")
        print("[FAIL!] 科研页型 route 箭头数")
    # 编译负例
    _pi_bad([dict(_PI_PROBLEM, problem={"items": ["a"]})], "problem 缺 title")
    _pi_bad([dict(_PI_PROBLEM, problem={"title": "T", "items": "not-list"})],
            "problem items 非列表")
    _pi_bad([dict(_PI_VERSUS, versus={"right_title": "B"})], "versus 缺 left_title")
    _pi_bad([dict(_PI_VERSUS, versus={"left_title": "A", "right_title": "B",
                                      "left_items": [1, 2]})], "versus items 含非字符串")
    _pi_bad([dict(_PI_ROUTE, route={"stages": ["唯一"]})], "route stages < 2")
    _pi_bad([dict(_PI_ROUTE, route={"stages": "not-list"})], "route stages 非列表")
    _pi_bad([dict(_PI_ROUTE, elements=[
        {"id": "rte_stage9", "type": "text", "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}])],
        "route 保留前缀 rte_ 冲突")
    _pi_bad([dict(_PI_PROBLEM, problem=dict(_PI_PROBLEM["problem"], oops=1))],
            "problem 未知字段")
    # IR 层：verify 科研页型断言（破格/均衡/等步距）
    _sh, _ir, _pp = _sci_ir["problem"]
    _m = copy.deepcopy(_ir)
    for e in _m["elements"]:
        if e["id"] == "prb_badge":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w, 1.2)      # 纵向贯穿 → 矮块
    check("IR problem 贯穿度破坏", _sh, _m, _pp, expect_ok=True,
          mutate_desc="prb_badge 高→1.2（< 版心×0.32）")
    _m = copy.deepcopy(_ir)
    for e in _m["elements"]:
        if e["id"] == "prb_title":
            e["text_style"]["align"] = "center"
    check("IR problem 左对齐破坏", _sh, _m, _pp, expect_ok=True,
          mutate_desc="prb_title align → center（破格消失）")
    _sh, _ir, _pp = _sci_ir["versus"]
    _m = copy.deepcopy(_ir)
    for e in _m["elements"]:
        if e["id"] == "vsv_panel_r":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w + 1.5, h)   # 右栏加宽 → 失衡
    check("IR versus 均衡破坏", _sh, _m, _pp, expect_ok=True,
          mutate_desc="右栏宽 +1.5（差 > balance_tol）")
    _m = copy.deepcopy(_ir)
    for e in _m["elements"]:
        if e["id"] == "vsv_panel_r":
            e["style"]["fill"] = e["style"].get("fill")
        if e["id"] == "vsv_panel_l":
            e["style"]["fill"] = "#F2F5FA"   # 与右栏同色 → 分色消失
    check("IR versus 分色破坏", _sh, _m, _pp, expect_ok=True,
          mutate_desc="左右面板同色（对立着色消失）")
    _sh, _ir, _pp = _sci_ir["route"]
    _m = copy.deepcopy(_ir)
    _m["elements"] = [e for e in _m["elements"] if e["id"] != "rte_stage3"]
    check("IR route 必需构件缺失", _sh, _m, _pp, expect_ok=True,
          mutate_desc="删 rte_stage3（阶段数 ≠ stages）")
    _m = copy.deepcopy(_ir)
    for e in _m["elements"]:
        if e["id"] == "rte_stage4":
            x, y, w, h = e["rect"]
            e["rect"] = (x + 1.2, y, w, h)   # 末阶段右移 → 等步距破坏
    check("IR route 等步距破坏", _sh, _m, _pp, expect_ok=True,
          mutate_desc="rte_stage4 右移 1.2（间距极差 > even_tol）")

    # ---- 变体家族（anti-刻板）：显式变体展开 + 每变体反破格断言（堵"引擎展开
    #      逐页相同却无人拦"的盲区；选型：SPEC variant 优先，否则轮换）----
    _VAR_COVER_BAND = {"title": "封面", "page_intent": "cover",
                       "cover": {"title": "色带贯穿封面", "subtitle": "副题",
                                 "meta": "ppt-builder", "accent": "acc",
                                 "variant": "band"}}
    _VAR_COVER_SPLIT = {"title": "封面", "page_intent": "cover",
                        "cover": {"title": "色块纵贯封面", "subtitle": "副题",
                                  "meta": "ppt-builder", "accent": "acc",
                                  "variant": "split"}}
    _VAR_SEC_GIANT = {"title": "节页", "page_intent": "section",
                      "section": {"num": "02", "title": "巨型序号贴右",
                                  "accent": "acc", "variant": "num_giant"}}
    _VAR_SEC_BAND = {"title": "节页", "page_intent": "section",
                     "section": {"num": "03", "title": "序号节名同嵌色带",
                                 "accent": "acc", "variant": "band"}}
    _var_comp = SC.compile_spec(copy.deepcopy(_pi_spec(
        [_VAR_COVER_BAND, _VAR_COVER_SPLIT, _VAR_SEC_GIANT, _VAR_SEC_BAND])))
    _var_ir = {}
    for _vi, (_key, _var, _need_ids) in enumerate((
            ("cover_band", "band", {"cov_deco", "cov_title", "cov_sub", "cov_meta"}),
            ("cover_split", "split", {"cov_deco", "cov_title"}),
            ("sec_giant", "num_giant", {"sec_num", "sec_title", "sec_guide"}),
            ("sec_band", "band", {"sec_deco", "sec_num", "sec_title"}))):
        _sh = _pi_shim(_var_comp["slides"][_vi])
        _ir, _p = ir_of(_sh)
        _var_ir[_key] = (_sh, _ir, _p)
        if _ir.get("page_intent_variant") != _var:
            _fail.append(f"变体 IR 记录 {_key}: {_ir.get('page_intent_variant')!r} ≠ {_var!r}")
            print(f"[FAIL!] 变体 IR 记录 {_key}")
        _got = {e["id"] for e in _ir["elements"]}
        if not _need_ids <= _got:
            _fail.append(f"变体 {_key} 展开缺失: {_need_ids - _got}")
            print(f"[FAIL!] 变体 {_key} 展开缺失")
        check(f"对照变体 {_key}", _sh, _ir, _p, expect_ok=False,
              mutate_desc=f"{_var} 变体引擎展开合法全过")
    # 每变体反破格：把"破格点"改回刻板形态，必须被拦
    _m = copy.deepcopy(_var_ir["cover_band"][1])
    for e in _m["elements"]:
        if e["id"] == "cov_deco":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w * 0.5, h)      # 横贯色带 → 半宽条
    check("IR cover band 横贯破坏", _var_ir["cover_band"][0], _m,
          _var_ir["cover_band"][2], expect_ok=True,
          mutate_desc="cov_deco 宽 ×0.5（< 版心×0.90，横贯消失）")
    _m = copy.deepcopy(_var_ir["cover_split"][1])
    for e in _m["elements"]:
        if e["id"] == "cov_deco":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w, h * 0.4)      # 纵贯色块 → 矮块
    check("IR cover split 纵贯破坏", _var_ir["cover_split"][0], _m,
          _var_ir["cover_split"][2], expect_ok=True,
          mutate_desc="cov_deco 高 ×0.4（< 版心×0.70，纵贯消失）")
    _m = copy.deepcopy(_var_ir["sec_giant"][1])
    for e in _m["elements"]:
        if e["id"] == "sec_num":
            x, y, w, h = e["rect"]
            e["rect"] = (x - 1.5, y, w, h)      # 贴右 → 左移
    check("IR section num_giant 贴右破坏", _var_ir["sec_giant"][0], _m,
          _var_ir["sec_giant"][2], expect_ok=True,
          mutate_desc="sec_num 左移 1.5（右缘偏离 > right_tol）")
    _m = copy.deepcopy(_var_ir["sec_band"][1])
    for e in _m["elements"]:
        if e["id"] == "sec_deco":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w * 0.5, h)      # 横贯色带 → 半宽条
    check("IR section band 横贯破坏", _var_ir["sec_band"][0], _m,
          _var_ir["sec_band"][2], expect_ok=True,
          mutate_desc="sec_deco 宽 ×0.5（< 版心×0.90，横贯消失）")
    # 编译负例：未知变体 / 跨 intent 误用变体
    _pi_bad([dict(_PI_COVER, cover=dict(_PI_COVER["cover"], variant="nope"))],
            "cover 未知变体")
    _pi_bad([dict(_PI_SECTION, section=dict(_PI_SECTION["section"], variant="nope"))],
            "section 未知变体")
    _pi_bad([dict(_PI_COVER, cover=dict(_PI_COVER["cover"], variant="num_giant"))],
            "cover 误用 section 变体名")

    # ---- 内容页结构生成五样板（references/page-intents.md §10）：panels/columns/
    #      kpis/cards/figure_text——agent 只给结构化内容，网格/分栏/指标行/卡网格/
    #      图文由引擎确定性展开；编译期拦字段/变体/保留前缀，verify 反破格断言背书 ----
    _PI_PANELS = {"title": "面板", "page_intent": "panels",
                  "panels": {"title": "三条并行要点", "cols": 3, "accent": "acc",
                             "items": [{"head": "选题", "body": "收敛核心问题"},
                                       {"head": "方法", "body": "双路径互证"},
                                       {"head": "证据", "body": "逐页物证核对"}]}}
    _PI_COLUMNS = {"title": "分栏", "page_intent": "columns",
                   "columns": {"title": "两栏对照", "accent": "acc",
                               "cols": [{"head": "现状", "items": ["手工排版", "版式重复"]},
                                        {"head": "目标", "items": ["引擎生成", "变体防刻板"]}]}}
    _PI_KPIS = {"title": "指标", "page_intent": "kpis",
                "kpis": {"title": "关键指标", "accent": "acc",
                         "items": [{"value": "100%", "label": "物证通过率"},
                                   {"value": "184", "label": "突变用例"}]}}
    _PI_CARDS = {"title": "卡片", "page_intent": "cards",
                 "cards": {"title": "能力卡", "cols": 3, "accent": "acc",
                           "items": [{"icon": "palette", "head": "设计语言",
                                      "body": "deck 级角色色"},
                                     {"icon": "layout-grid", "head": "结构生成",
                                      "body": "引擎解版式"},
                                     {"icon": "shield-check", "head": "物证背书",
                                      "body": "逐页机器可证"}]}}
    _PI_FIGTEXT = {"title": "图文", "page_intent": "figure_text",
                   "figure_text": {"title": "图文并置", "accent": "acc",
                                   "caption": "图 1 · 占位示意",
                                   "blocks": ["左侧正文块一。", "左侧正文块二。"]}}
    _lay_comp = SC.compile_spec(copy.deepcopy(_pi_spec(
        [_PI_PANELS, _PI_COLUMNS, _PI_KPIS, _PI_CARDS, _PI_FIGTEXT])))
    _lay_ir = {}
    for _li, (_intent, _need) in enumerate((
            ("panels", {"pnl_title", "pnl_panel0"}),
            ("columns", {"col_title", "col_head0"}),
            ("kpis", {"kpi_title", "kpi_card0"}),
            ("cards", {"crd_title", "crd_card0"}),
            ("figure_text", {"fgt_title", "fgt_fig", "fgt_body"}))):
        _sh = _pi_shim(_lay_comp["slides"][_li])
        _ir, _p = ir_of(_sh)
        _lay_ir[_intent] = (_sh, _ir, _p)
        if _ir.get("page_intent") != _intent:
            _fail.append(f"内容页型 IR 直通: {_intent}")
            print(f"[FAIL!] 内容页型 IR 直通 {_intent}")
        _got = {e["id"] for e in _ir["elements"]}
        if not _need <= _got:
            _fail.append(f"内容页型 {_intent} 展开缺失: {_need - _got}")
            print(f"[FAIL!] 内容页型 {_intent} 展开缺失")
        check(f"对照内容页型 {_intent}", _sh, _ir, _p, expect_ok=False,
              mutate_desc=f"{_intent} 引擎展开合法全过")
    # accent token 解析（panels 面板头文字色 = palette acc）
    _pn0 = next(e for e in _lay_ir["panels"][1]["elements"] if e["id"] == "pnl_head0")
    if _pn0["text_style"]["color"] != "#D08770":
        _fail.append(f"内容页型 accent token 解析: {_pn0['text_style']['color']!r} ≠ #D08770")
        print("[FAIL!] 内容页型 accent token 解析")
    # 编译负例：未知字段 / 未知变体 / 保留前缀冲突
    _pi_bad([dict(_PI_PANELS, panels=dict(_PI_PANELS["panels"], oops=1))],
            "panels 未知字段")
    _pi_bad([dict(_PI_PANELS, panels=dict(_PI_PANELS["panels"], variant="nope"))],
            "panels 未知变体")
    _pi_bad([dict(_PI_COLUMNS, columns=dict(_PI_COLUMNS["columns"], oops=1))],
            "columns 未知字段")
    _pi_bad([dict(_PI_KPIS, kpis=dict(_PI_KPIS["kpis"], variant="nope"))],
            "kpis 未知变体")
    _pi_bad([dict(_PI_CARDS, cards=dict(_PI_CARDS["cards"], oops=1))],
            "cards 未知字段")
    _pi_bad([dict(_PI_FIGTEXT, figure_text=dict(_PI_FIGTEXT["figure_text"], oops=1))],
            "figure_text 未知字段")
    _pi_bad([dict(_PI_PANELS, elements=[
        {"id": "pnl_x", "type": "text", "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}])],
        "panels 保留前缀 pnl_ 冲突")
    _pi_bad([dict(_PI_CARDS, elements=[
        {"id": "crd_x", "type": "text", "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}])],
        "cards 保留前缀 crd_ 冲突")
    _pi_bad([dict(_PI_FIGTEXT, elements=[
        {"id": "fgt_x", "type": "text", "rect": [1.0, 1.0, 2.0, 1.0], "text": "x"}])],
        "figure_text 保留前缀 fgt_ 冲突")
    # IR 层反破格：把版式改回刻板形态 → verify 必须拦
    _sh, _ir, _pp = _lay_ir["panels"]
    _m = copy.deepcopy(_ir)
    for e in _m["elements"]:
        if e["id"] == "pnl_panel0":
            x, y, w, h = e["rect"]
            e["rect"] = (x, y, w * 0.4, h)   # 面板缩窄 → 网格不贯穿
    check("IR panels 网格贯穿破坏", _sh, _m, _pp, expect_ok=True,
          mutate_desc="pnl_panel0 宽 ×0.4（网格跨 < 版心×比）")
    _sh, _ir, _pp = _lay_ir["kpis"]
    _m = copy.deepcopy(_ir)
    for e in _m["elements"]:
        if e["id"] == "kpi_val0":
            e["text_layout"]["fs"] = 12      # 数值降为标签同号 → 尺度对比消失
    check("IR kpis 数值层级破坏", _sh, _m, _pp, expect_ok=True,
          mutate_desc="kpi_val0 fs → 12（≤ 标签 fs×比）")
    _sh, _ir, _pp = _lay_ir["cards"]
    _m = copy.deepcopy(_ir)
    _m["elements"] = [e for e in _m["elements"]
                      if not e["id"].startswith("crd_badge")]
    check("IR cards 顶饰缺失", _sh, _m, _pp, expect_ok=True,
          mutate_desc="删 crd_badge*（顶饰不在场）")
    _sh, _ir, _pp = _lay_ir["figure_text"]
    _m = copy.deepcopy(_ir)
    for e in _m["elements"]:
        if e["id"] == "fgt_body":
            fr = next(x["rect"] for x in _m["elements"] if x["id"] == "fgt_fig")
            e["rect"] = (fr[0] + 0.5, fr[1], 2.0, fr[3])   # 文侧压到图上 → 分栏破坏
    check("IR figure_text 图文重叠", _sh, _m, _pp, expect_ok=True,
          mutate_desc="fgt_body 移入图区（图文不重叠破坏）")
    # columns arrow 变体：删栏间箭头 → 断言拦
    _arr_comp = SC.compile_spec(copy.deepcopy(_pi_spec(
        [dict(_PI_COLUMNS, columns=dict(_PI_COLUMNS["columns"], variant="arrow"))])))
    _sh = _pi_shim(_arr_comp["slides"][0])
    _ir, _pp = ir_of(_sh)
    _m = copy.deepcopy(_ir)
    _m["lines"] = [ln for ln in _m["lines"] if not ln["id"].startswith("col_arrow")]
    check("IR columns 箭头缺失", _sh, _m, _pp, expect_ok=True,
          mutate_desc="删 col_arrow*（arrow 变体箭头不在场）")

    # ---- 能力档案 fail-closed（EasySlides capability profile 内化；
    #      scripts/capabilities.py 是唯一事实源）----
    # 编译期拒：planned 页型（防"字段合法却无展开"的静默 no-op）/ 缺字段 dict /
    # 字段 dict 无 intent / 非锚定类型声明 anchors / top_level_only 进 children
    _pi_bad([dict(_PI_BODY, page_intent="data")], "planned 页型 data")
    _pi_bad([dict(_PI_BODY, page_intent="quote")], "planned 页型 quote")
    _pi_bad([{"title": "c", "page_intent": "cover"}], "cover 缺字段 dict")
    _pi_bad([{"title": "c", "cover": {"title": "T"}}], "cover 字段 dict 无 intent")

    _cap_meta = {"title": "t", "style_guide": "deck",
                 "slide": {"w": 13.333, "h": 7.5},
                 "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}}

    def _cap_bad(elems, desc):
        try:
            SC.compile_spec({"meta": dict(_cap_meta), "palette": dict(_PI_PAL),
                             "elements": elems})
            _fail.append(f"编译 {desc} 漏拦")
            print(f"[FAIL!] 编译 {desc} 漏拦")
        except SC.SpecCompileError:
            _pass.append(f"编译 {desc}")
            print(f"[OK] 编译 {desc} 拦截 ✓")

    def _cap_ok(elems, desc):
        try:
            SC.compile_spec({"meta": dict(_cap_meta), "palette": dict(_PI_PAL),
                             "elements": elems})
            _pass.append(desc)
            print(f"[OK] {desc} ✓")
        except Exception as ex:
            _fail.append(f"{desc} 误拦 {type(ex).__name__}: {ex}")
            print(f"[FAIL!] {desc} 误拦 {type(ex).__name__}: {ex}")

    _cap_bad([{"id": "s", "type": "stack", "rect": [1, 1, 4, 2],
               "anchors": {"a": [.5, .5]},
               "children": [{"id": "k", "type": "shape", "kind": "rounded_rect",
                             "width": 1, "height": 1}]}], "容器声明 anchors")
    _cap_bad([{"id": "ln", "type": "line", "rect": [1, 1, 2, 0],
               "x1": 1, "y1": 1, "x2": 3, "y2": 1, "anchors": {"a": [.5, .5]}}],
             "线声明 anchors")
    _cap_bad([{"id": "s", "type": "stack", "rect": [1, 1, 6, 4],
               "children": [{"id": "tb", "type": "table", "data": [["a"]]}]}],
             "top_level_only table 进 children")
    _cap_ok([{"id": "t1", "type": "text", "rect": [1, 1, 2, 1], "text": "x",
              "anchors": {"a": [.9, .9]}}], "能力档案 合法 anchors 放行")

    # ---- typst 排版块契约（references/typst-chain.md）----
    # 编译期：三源互斥 / design 未落地 / 外链缺失 / vars 键非法 / children 顶层限制
    t_spec = ("meta:\n  title: t\n  slide: {w: 13.333, h: 7.5}\n"
              "elements:\n  - id: t1\n    type: typst\n    rect: [0.5, 0.5, 6.0, 3.0]\n")

    def _tneg(field):
        try:
            SC.compile_spec(SC.load_yaml(t_spec + field))
            return None
        except SC.SpecCompileError as ex:
            return str(ex)

    if (_tneg("    typst_src: x.typ\n    typst: x\n")
            and _tneg("    design: 落地方案待作业\n")
            and _tneg("    typst_src: missing.typ\n")
            and _tneg("    typst: x\n    vars: {1bad: 1}\n")):
        print("[OK] typst 编译期契约 ✓ 三源互斥 / design 未落地 / 外链缺失 / vars 键非法")
        _pass.append("typst 编译期契约")
    else:
        _fail.append("typst 编译期契约")
        print("[FAIL!] typst 编译期契约")

    # IR 守护：typst 元素无 stage1.5 编译产物（_typst）→ 明确拦截（不得静默出空图）
    try:
        c = SC.compile_spec(SC.load_yaml(t_spec + "    typst: x\n"))
        ir_builder.build_ir(c["slides"][0], _P.resolve(None))
        _fail.append("typst 产物缺失未拦")
        print("[FAIL!] IR typst 产物缺失拦截")
    except ValueError as ex:
        if "typst 产物缺失" in str(ex):
            print("[OK] IR typst 产物缺失拦截 ✓ stage1.5 未跑的守护")
            _pass.append("IR typst 产物缺失")
        else:
            _fail.append(f"typst 产物缺失：{ex}")
            print(f"[FAIL!] typst 产物缺失（异样错误 {ex}）")

    # ---- seed 背景遮挡告警（规则1：seed 模式 + 全局 framework.background → warnings）----
    w1 = SC._seed_bg_warning({"framework": {"background": {"fill": "#FFF"}}},
                             {"mode": "seed"})
    w2 = SC._seed_bg_warning({"framework": {}}, {"mode": "seed"})
    w3 = SC._seed_bg_warning({"framework": {"background": {"fill": "#FFF"}}},
                             {"mode": "extract"})
    if w1 and w2 is None and w3 is None:
        print("[OK] seed 背景遮挡告警契约 ✓ seed+background→警告 / 无背景→静默 / extract→静默")
        _pass.append("seed 背景遮挡告警")
    else:
        _fail.append(f"seed 背景遮挡告警：w1={bool(w1)} w2={w2} w3={w3}")
        print("[FAIL!] seed 背景遮挡告警")

    # ---- C3 契约：morph 平滑切换 + brush 书法矢量字 ----
    _C3_META = {"title": "t", "style_guide": "deck",
                "slide": {"w": 13.333, "h": 7.5},
                "margin": {"l": 0.5, "t": 0.5, "r": 0.5, "b": 0.5}}

    def _c3_bad(spec, desc):
        try:
            SC.compile_spec(spec)
            _fail.append(f"编译 {desc} 漏拦")
            print(f"[FAIL!] 编译 {desc} 漏拦")
        except SC.SpecCompileError:
            _pass.append(f"编译 {desc}")
            print(f"[OK] 编译 {desc} 拦截 ✓")

    def _c3_ok(spec, desc):
        try:
            SC.compile_spec(spec)
            _pass.append(desc)
            print(f"[OK] {desc} ✓")
        except Exception as ex:
            _fail.append(f"{desc} 误拦 {type(ex).__name__}: {ex}")
            print(f"[FAIL!] {desc} 误拦 {type(ex).__name__}: {ex}")

    def _tr_spec(tr):
        return {"meta": dict(_C3_META, slides=[
            {"title": "a", "transition": tr,
             "elements": [{"id": "title", "type": "text", "rect": [1, 1, 4, 1],
                           "text": "x", "text_style": {"fs": 24}}]}]),
            "palette": {"p": "#1F2A44"}}

    _c3_ok(_tr_spec({"effect": "morph"}), "morph 缺省 dur 放行")
    _c3_ok(_tr_spec({"effect": "morph", "dur": 1200}), "morph 带 dur 放行")
    _c3_bad(_tr_spec({"effect": "morph", "dur": 50}), "morph dur < 100")
    _c3_bad(_tr_spec({"effect": "morph", "dur": 6000}), "morph dur > 5000")
    _c3_bad(_tr_spec({"effect": "fade", "dur": 900}), "非 morph 声明 dur")
    _c3_bad(_tr_spec({"effect": "zoom"}), "未知切换效果")

    def _br_spec(elems):
        return {"meta": dict(_C3_META), "palette": {"p": "#1F2A44"}, "elements": elems}

    _bs = {"id": "b", "type": "brush", "rect": [1, 1, 3, 3], "text": "永",
           "font": "kai"}
    _c3_ok(_br_spec([dict(_bs)]), "brush 缺省（font 别名 + 默认填充）放行")
    _c3_ok(_br_spec([dict(_bs, style={"grad": ["#111111", "#222222"]})]),
           "brush 渐变填充放行")
    _c3_ok(_br_spec([dict(_bs, style={"image": "_probe/assets/ink.png"})]),
           "brush 图片填充放行")
    _c3_bad(_br_spec([{k: v for k, v in _bs.items() if k != "text"}]),
            "brush 缺 text")
    _c3_bad(_br_spec([dict(_bs, text="  ")]), "brush 空 text")
    _c3_bad(_br_spec([{k: v for k, v in _bs.items() if k != "font"}]),
            "brush 缺 font")
    _c3_bad(_br_spec([dict(_bs, style={"fill": "#111111",
                                       "image": "_probe/assets/ink.png"})]),
            "brush fill/image 互斥")
    _c3_bad(_br_spec([dict(_bs, style={"image": "_probe/assets/nope.png"})]),
            "brush 图片路径不存在")
    _c3_bad(_br_spec([dict(_bs, style={"grad": ["#111111"]})]),
            "brush 渐变非两色")

    # IR 展开：brush 声明盒 → 按 ink 比例适配（rect 收窄到字形 bbox，非原声明盒）
    try:
        import ink_text
        c = SC.compile_spec(_br_spec([dict(_bs)]))
        _ir_b = ir_builder.build_ir(c["slides"][0], _P.resolve(None))
        el = next(e for e in _ir_b["elements"] if e["id"] == "b")
        w_em, h_em = ink_text.measure("永", "kai")
        s = min(3.0 / w_em, 3.0 / h_em)
        ok = (el["type"] == "brush" and el.get("brush", {}).get("font") == "kai"
              and abs(el["rect"][2] - w_em * s) < 1e-3
              and abs(el["rect"][3] - h_em * s) < 1e-3)
        checks_ok = ok
        # 元素 rect 保持声明盒（字形居中适配于其内）
        checks_ok = checks_ok and abs(el["rect"][2]) < 3.0 + 1e-6
        if checks_ok:
            print("[OK] IR brush ink 适配 ✓ rect 收窄到字形 bbox（居中于声明盒）")
            _pass.append("IR brush ink 适配")
        else:
            _fail.append(f"brush ink 适配：rect={el['rect']}")
            print(f"[FAIL!] IR brush ink 适配 rect={el['rect']}")
    except Exception as ex:
        _fail.append(f"brush IR 展开崩溃 {type(ex).__name__}: {ex}")
        print(f"[FAIL!] brush IR 展开崩溃 {type(ex).__name__}: {ex}")

    # ---- B1 契约：矢量图标库（icon → custGeom 描边语义） ----
    def _ic_spec(elems):
        return {"meta": dict(_C3_META), "palette": {"p": "#1F2A44"}, "elements": elems}

    _is = {"id": "i", "type": "icon", "rect": [1, 1, 2, 2], "icon": "水滴"}
    _c3_ok(_ic_spec([dict(_is)]), "icon 中文关键词放行")
    _c3_ok(_ic_spec([dict(_is, icon="droplet")]), "icon 英文名放行")
    _c3_ok(_ic_spec([dict(_is, icon="zzz-not-real")]), "icon 未知名回退 circle-dot 放行")
    _c3_ok(_ic_spec([dict(_is, style={"color": "#2D6CDF", "weight": 2.0})]),
           "icon color/weight 放行")
    _c3_bad(_ic_spec([{k: v for k, v in _is.items() if k != "icon"}]),
            "icon 缺 icon")
    _c3_bad(_ic_spec([dict(_is, icon="  ")]), "icon 空 icon")
    _c3_bad(_ic_spec([dict(_is, style={"fill": "#111111"})]),
            "icon style 未知键 fill")
    _c3_bad(_ic_spec([dict(_is, style={"weight": 0})]), "icon weight ≤ 0")
    _c3_bad(_ic_spec([dict(_is, align="middle")]), "icon 非法 align")

    # icon_lib 解析：名/关键词 → 子路径（viewBox 24×24 ×scale）+ 实心子路径索引
    try:
        import icon_lib
        subs, vw, vh, filled = icon_lib.subpaths("水滴")
        ok = (len(subs) >= 1 and abs(vw - 24000.0) < 1e-6
              and abs(vh - 24000.0) < 1e-6 and isinstance(filled, frozenset))
        checks_ok = ok
        # 关键词解析回退：未知名 → circle-dot（存在）
        checks_ok = checks_ok and icon_lib.resolve("zzz-not-real") == "circle-dot"
        # 实心子路径：chart-scatter 含 fill=currentColor 的点 → filled 非空；
        # 纯描边图标（droplet）→ filled 空
        _s2, _, _, _f2 = icon_lib.subpaths("chart-scatter")
        _s3, _, _, _f3 = icon_lib.subpaths("droplet")
        checks_ok = checks_ok and len(_f2) >= 1 and len(_f3) == 0
        if checks_ok:
            print("[OK] icon_lib 解析 ✓ 子路径/24×24 viewBox/实心索引/关键词回退")
            _pass.append("icon_lib 解析")
        else:
            _fail.append(f"icon_lib 解析：subs={len(subs)} vb={vw} filled={sorted(filled)}")
            print(f"[FAIL!] icon_lib 解析 subs={len(subs)} vb={vw} filled={sorted(filled)}")
    except Exception as ex:
        _fail.append(f"icon_lib 崩溃 {type(ex).__name__}: {ex}")
        print(f"[FAIL!] icon_lib 崩溃 {type(ex).__name__}: {ex}")

    # IR 展开：icon 声明盒 → 正方适配居中（rect 收窄到 min 边正方）
    try:
        c = SC.compile_spec(_ic_spec([dict(_is, rect=[1, 1, 3, 2])]))
        _ir_i = ir_builder.build_ir(c["slides"][0], _P.resolve(None))
        el = next(e for e in _ir_i["elements"] if e["id"] == "i")
        ok = (el["type"] == "icon" and el.get("icon") == "droplet"
              and abs(el["rect"][2] - 2.0) < 1e-3 and abs(el["rect"][3] - 2.0) < 1e-3
              and abs(el["rect"][0] - 1.5) < 1e-3)   # 水平居中（w=3, side=2 → x+0.5）
        if ok:
            print("[OK] IR icon 正方适配 ✓ rect 收窄到 min 边（居中于声明盒）")
            _pass.append("IR icon 正方适配")
        else:
            _fail.append(f"icon 正方适配：rect={el['rect']} icon={el.get('icon')}")
            print(f"[FAIL!] IR icon 正方适配 rect={el['rect']}")
    except Exception as ex:
        _fail.append(f"icon IR 展开崩溃 {type(ex).__name__}: {ex}")
        print(f"[FAIL!] icon IR 展开崩溃 {type(ex).__name__}: {ex}")

    # ---- C1 契约：矢量图内化（type: svg → 原生 custGeom）+ 相对坐标（rect_kind: ratio） ----
    _SVG_SRC = os.path.join(os.path.dirname(__file__), "..", "assets", "figures", "radar.svg")
    _svg_spec = lambda elems: {"meta": dict(_C3_META), "palette": {"q": "#2D6CDF"},
                               "elements": elems}
    _s_v = {"id": "v", "type": "svg", "rect": [1, 1, 3, 2], "src": _SVG_SRC}
    _c3_ok(_svg_spec([dict(_s_v)]), "svg 外链 src 放行")
    _c3_ok(_svg_spec([dict({k: v for k, v in _s_v.items() if k != "src"},
                           svg="<svg xmlns='http://www.w3.org/2000/svg'><circle cx='5' cy='5' r='4' fill='#203040'/></svg>")]),
           "svg 内联源码放行")
    _c3_ok(_svg_spec([dict(_s_v, fit="stretch")]), "svg fit=stretch 放行")
    _c3_bad(_svg_spec([{k: v for k, v in _s_v.items() if k != "src"}]),
            "svg 缺 src/svg 双源")
    _c3_bad(_svg_spec([dict(_s_v, svg="<svg/>")]), "svg 双源（src+svg 互斥）")
    _c3_bad(_svg_spec([dict(_s_v, src="nope")]), "svg src 文件不存在")
    _c3_bad(_svg_spec([dict(_s_v, fit="fill")]), "svg fit 非法枚举")
    # svg 解析 fail-closed：遇不支持构造（text）→ 抛 SvgDocError 转 SpecCompileError
    _c3_bad(_svg_spec([dict(_s_v, svg="<svg xmlns='http://www.w3.org/2000/svg'><text x='1' y='1'>hi</text></svg>")]),
            "svg 不支持 <text>（fail-closed）")
    # svg 渲染生效属性 fail-closed：shape 上 filter=/clip-path=/mask=（引用 defs 定义）
    # → 绝不静默丢效果；<defs> 内未引用定义本身容忍
    _c3_bad(_svg_spec([dict(_s_v, svg="<svg xmlns='http://www.w3.org/2000/svg'><defs><filter id='f'/></defs><rect x='0' y='0' width='2' height='2' fill='#333' filter='url(#f)'/></svg>")]),
            "svg 渲染生效属性 filter=（fail-closed）")
    _c3_ok(_svg_spec([dict({k: v for k, v in _s_v.items() if k != "src"},
                           svg="<svg xmlns='http://www.w3.org/2000/svg'><defs><filter id='f'/></defs><rect x='0' y='0' width='2' height='2' fill='#333'/></svg>")]),
           "svg <defs> 内未引用定义容忍")
    # 相对坐标（rect_kind: ratio）
    _ratio_spec = lambda elems: {"meta": dict(_C3_META, slides=[
        {"title": "r", "elements": elems}]), "palette": {"q": "#2D6CDF"}}
    _r_e = {"id": "r", "type": "text", "rect_kind": "ratio",
            "rect": {"x": 0.2, "y": 0.3, "w": 0.5, "h": 0.1}, "text": "x"}
    _c3_ok(_ratio_spec([_r_e]), "ratio 合法分数放行")
    _c3_ok(_ratio_spec([dict(_r_e, area="slide")]), "ratio area=slide 放行")
    _c3_bad(_ratio_spec([dict(_r_e, rect=[0.2, 0.3, 0.5, 0.1])]), "ratio rect 非 dict")
    _c3_bad(_ratio_spec([dict(_r_e, rect={"x": 0.2})]), "ratio rect 缺键")
    _c3_bad(_ratio_spec([dict(_r_e, rect={"x": -0.1, "y": 0.3, "w": 0.5, "h": 0.1})]),
            "ratio x 越界（<0）")
    _c3_bad(_ratio_spec([dict(_r_e, rect={"x": 0.7, "y": 0.3, "w": 0.5, "h": 0.1})]),
            "ratio x+w 越界（超内容区）")
    _c3_bad(_ratio_spec([dict(_r_e, rect={"x": 0.2, "y": 0.3, "w": 0, "h": 0.1})]),
            "ratio w 非正")
    # ratio IR 解绝对：content 帧 = slide−margin（13.333−1, 7.5−1 = 12.333×6.5）——
    # 经 build_pages._resolve_ratio_rects 真实路径（build_ir 只吃绝对 rect，铁律 1）。
    try:
        import build_ppt
        cc = SC.compile_spec(_ratio_spec([_r_e]))
        _sh = build_ppt.build_pages(cc)[0]
        _ir_r = ir_builder.build_ir(_sh, _sh["_p"])
        el = next(e for e in _ir_r["elements"] if e["id"] == "r")
        exp = (0.5 + 0.2 * 12.333, 0.5 + 0.3 * 6.5,
               0.5 * 12.333, 0.1 * 6.5)
        ok = (all(abs(el["rect"][i] - exp[i]) < 1e-2 for i in range(4))
              and "rect_kind" not in el)
        if ok:
            print("[OK] ratio IR 解绝对 ✓ rect_kind 不在 IR（铁律 1）")
            _pass.append("ratio IR 解绝对")
        else:
            _fail.append(f"ratio 解绝对 rect={el['rect']} 期望≈{tuple(round(x, 1) for x in exp)}")
            print(f"[FAIL!] ratio 解绝对 rect={el['rect']}")
    except Exception as ex:
        _fail.append(f"ratio IR 解绝对崩溃 {type(ex).__name__}: {ex}")
        print(f"[FAIL!] ratio IR 解绝对崩溃 {type(ex).__name__}: {ex}")

    print(f"\n== 突变套件：{len(_pass)} 通过 / {len(_fail)} 失败 ==")
    for f in _fail:
        print("  FAIL! " + f)
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())