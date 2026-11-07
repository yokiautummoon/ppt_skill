# -*- coding: utf-8 -*-
"""test_alpha_math.py — 半透明层叠加反解（性质②：JAnim apart_alpha 移植）单测。

覆盖：merge_alpha 合成 / apart_alpha 闭式 / face_alpha 反解（含无解）/ ε 断言 /
cylinder face_opacity 集成（spec 校验、ir_builder 端面 alpha 反解、verify 叠区
保真断言）/ 缺省 face_opacity → 端面实色（向后兼容）。无 Office。
运行：win_py -X utf8 tests/test_alpha_math.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import alpha_math as AM
import ir_builder
import spec_compile as SC
import verify
import params as P
import yaml


# ---------- 工具 ----------

def test_merge_alpha():
    assert abs(AM.merge_alpha([0.3, 0.429]) - 0.6003) < 1e-3   # 1-(0.7)(0.571)
    assert abs(AM.merge_alpha([0.2, 0.2, 0.2]) - 0.488) < 1e-3  # 三层
    assert AM.merge_alpha([]) == 0.0
    assert abs(AM.merge_alpha([1.0, 0.5]) - 1.0) < 1e-9          # 全不透明 ≡ 全不透明


def test_apart_alpha():
    a = AM.apart_alpha(0.6, 2)
    assert abs(AM.merge_alpha([a, a]) - 0.6) < 1e-3              # 两层叠加还原 target
    b = AM.apart_alpha(0.36, 3)
    assert abs(AM.merge_alpha([b] * 3) - 0.36) < 1e-3            # 三层
    assert AM.apart_alpha(0.6, 1) == 0.6


def test_face_alpha():
    a = AM.face_alpha(0.6, 0.3)
    assert abs(a - (0.6 - 0.3) / 0.7) < 1e-9                     # 闭式
    assert abs(AM.merge_alpha([0.3, a]) - 0.6) < 1e-3            # 叠区保真
    assert AM.face_alpha(1.0, 0.35) is not None
    assert abs(AM.face_alpha(1.0, 0.35) - 1.0) < 1e-9            # 缺省端面实色
    assert AM.face_alpha(0.3, 0.3) is None                       # 无解（≤ 侧壁）
    assert AM.face_alpha(1.0, 1.0) is None


def test_check_merge():
    assert AM.check_merge([0.3, 0.429], 0.6) is not None
    assert AM.check_merge([0.3, 0.429], 1.0) is None             # 偏差超 ε


# ---------- cylinder 集成 ----------

_CYL = {"meta": {"title": "t", "slide": {"w": 13.333, "h": 7.5}},
        "elements": [{"id": "cy", "type": "shape", "kind": "cylinder",
                      "rect": [1.0, 1.0, 3.0, 4.0], "text": "缸",
                      "opacity": 0.3, "face_opacity": 0.6}]}


def _compiled(**kw):
    d = _CYL.copy()
    el = dict(d["elements"][0])
    el.update(kw)
    d["elements"] = [el]
    return SC.compile_spec(SC.load_yaml(yaml.safe_dump(d, allow_unicode=True,
                                                       sort_keys=False)))


def test_spec_face_opacity_valid():
    ok = _compiled()
    assert ok["elements"][0]["face_opacity"] == 0.6


def test_spec_face_opacity_rejects():
    def neg(**kw):
        try:
            _compiled(**kw)
            assert False, f"未拦截 {kw}"
        except SC.SpecCompileError:
            pass
    neg(face_opacity=0.6, opacity=0.7)      # face_opacity ≤ opacity → 无解
    neg(face_opacity=1.5)                   # 超界
    neg(face_opacity=0.0)                   # 0 不允许（端面全透明无意义）
    neg(face_opacity="x")                   # 非数值
    neg(face_opacity=0.6, opacity=1.0)      # opacity=1 → face 无法更透


def test_ir_face_alpha_solved():
    p = P.resolve(None)
    compiled = _compiled()
    ir = ir_builder.build_ir(compiled, p)
    parts = {e["id"]: e for e in ir["elements"]}
    side = parts["cy.side"]["style"]["opacity"]
    bot = parts["cy.bot"]["style"]["opacity"]
    assert side == 0.3
    assert abs(bot - 0.429) < 1e-3                                # (0.6-0.3)/0.7
    assert abs(AM.merge_alpha([side, bot]) - 0.6) < 1e-3          # 叠区保真
    assert parts["cy.top"]["style"]["opacity"] == bot              # 顶底同反解


def test_ir_face_opacity_default_opaque():
    p = P.resolve(None)
    ir = ir_builder.build_ir(_compiled(face_opacity=None), p)
    parts = {e["id"]: e for e in ir["elements"]}
    assert parts["cy.bot"]["style"]["opacity"] == 1.0             # 向后兼容：实色


def test_verify_face_alpha_assertion():
    p = P.resolve(None)
    compiled = _compiled()
    ir = ir_builder.build_ir(compiled, p)
    v = verify.run(ir, compiled, p)
    names = [c[1] for c in v.checks if c[0].startswith("S")]
    alc = [c for c in v.checks if "叠区保真" in c[1]]
    assert len(alc) == 2, v.checks                               # bot + top 两条
    assert all(c[1] for c in alc), [c for c in alc if not c[1]]


if __name__ == "__main__":
    fns = (test_merge_alpha, test_apart_alpha, test_face_alpha, test_check_merge,
           test_spec_face_opacity_valid, test_spec_face_opacity_rejects,
           test_ir_face_alpha_solved, test_ir_face_opacity_default_opaque,
           test_verify_face_alpha_assertion)
    fails = 0
    for fn in fns:
        try:
            fn()
            print(f"[OK] {fn.__name__}")
        except AssertionError as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {ex}")
        except Exception as ex:
            fails += 1
            print(f"[FAIL] {fn.__name__}: {type(ex).__name__}: {ex}")
    print(f"== alpha_math：{len(fns) - fails} 通过 / {fails} 失败 ==")
    sys.exit(1 if fails else 0)