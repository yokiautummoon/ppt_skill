# -*- coding: utf-8 -*-
"""anim_group.py — 声明式动画组：确定性展开为 COM 时间轴（JAnim 移植）。

SPEC 页级/顶层 `anim`（结构层语法由 spec_compile 校验，本模块做语义校验与展开）：
    anim:
      mode: succession            # succession 串行接续 | aligned 对齐 | group 联合
      trigger: on_click           # 组根触发（缺省 on_click；组内成员的时序全由此 + start 定）
      start: 0.2                  # 组首叶相对触发点的延迟秒（缺省 0）
      gap: 0.25                   # succession 链相邻叶间隔秒（缺省 0.2，嵌套组可覆盖）
      items:
        - {id: e1}                # 叶：引用有 animation 的顶层元素
        - {id: e2}
        - mode: group             # 嵌套组：成员同块（组内可再 succession/aligned/group）
          gap: 0.1
          items: [{id: e3}, {id: e4}]

展开（无 COM 依赖，纯代数——确定性时间轴的唯一真相源）：
  1. 树叶递归 depth-first，每叶得绝对时间轴 {start, end} 相对组根（组根 = 0）：
       - succession 链：叶 i.start = 前叶.end + gap（首尾相接，链条上无重叠无空洞）
       - aligned/group 块：成员 start = 块注入点；块 end = max 成员 end
  2. 每叶 trigger/delay（供 com_layer AddEffect 直用）：
       - 根链首叶 → trigger = 组根 trigger、delay = 组 start（沿嵌套链首传递）
       - succession 链中 → after_previous + 组 gap（锚定前一叶结束）
       - aligned/group 成员 → with_previous + 0（与链首对齐）
  3. AddEffect 序（ir["anim_sequence"]）：DFS 序；aligned/group 块内 children 按
     end 降序——块末 = 最晚结束者 = 父 succession 链的锚定代表（after_previous
     锚定"最后加入的 effect"，块 end 由它代表，链式语义自洽）。嵌套块内已按
     end 降序 → 子块末叶即子块 end 代表，父排序 key 一致。
  4. 时间一致性断言（TimeAligner 的 ε 量化思想，随展开产出 violations）：
       - succession 首尾相接 start[i+1] ≈ end[i] + gap（EPS=1e-4）
       - aligned/group 同块成员 start 相等
     com_layer COM 回读阶段复用同一 EPS。

规定：
  - 组内成员**必须有 animation 且不得自带 trigger/delay**（时序全由组决定，
    元素级声明与组编排冲突 → 编译期拦截）。
  - 容器（stack/dock/graph）不得为组员（渲染无单形状可挂时间轴，同元素级动画规则）。
  - 嵌套组仅允许 mode/gap/items（trigger/start 属组根；嵌套继承父上下文）。
"""
import animation_recipes

TIMELINE_EPS = 1e-4          # TimeAligner 量化容差（秒）：浮点累加漂移在此内视为精确
TRIGGERS = ("with_previous", "after_previous", "on_click")
_MODES = ("succession", "aligned", "group")
_GROUP_KEYS = {"mode", "gap", "items"}
_ROOT_KEYS = {"mode", "trigger", "start", "gap", "items"}


class AgError(ValueError):
    """动画组语义错误（结构层语法在 spec_compile；spec_compile 捕获转贵审文案）。"""


def _dur_of(anim):
    """元素 animation → 时长秒：effect 配方 dur；behaviors 逃生通道取各行为 dur 最大值。"""
    if "effect" in anim:
        return animation_recipes.RECIPES[anim["effect"]]["dur"]
    return max(b["dur"] for b in anim["behaviors"])


def _walk(node, t, tri0, gap, by_id, blocks, out):
    """展开节点 → 叶记录（append 进 out）与块元数据（append 进 blocks）；
    返回 (节点 end, 块元数据)。tri0 = 父链上下文注入的 trigger（供 idx0
    沿嵌套链首传递）；叶的 delay 由 expand_group 按绝对时间轴统一导出。"""
    if "id" in node:
        dur = _dur_of(by_id[node["id"]]["animation"])
        rec = {"id": node["id"], "start": round(t, 6), "end": round(t + dur, 6),
               "trigger": tri0}
        out.append(rec)
        return rec["end"], {"kind": "leaf", "start": t, "end": rec["end"],
                            "members": [rec]}
    mode = node.get("mode", "succession")
    gap_n = node.get("gap", gap)
    sub = []                       # (child_end, child_meta, child_leaves)
    end, prev_end = t, None
    for i, it in enumerate(node["items"]):
        if isinstance(it, str):             # YAML 简写：items: [eid, ...] ≡ {id: eid}
            it = {"id": it}
        if i == 0:
            it_t, it_tri = t, tri0
        elif mode == "succession":
            it_t, it_tri = prev_end + gap_n, "after_previous"
        else:                       # aligned / group：同块对齐
            it_t, it_tri = t, "with_previous"
        local = []
        e_cur, meta = _walk(it, it_t, it_tri, gap_n, by_id, blocks, local)
        sub.append((e_cur, meta, local))
        prev_end = e_cur
        end = max(end, e_cur)
    if mode in ("aligned", "group") and len(sub) > 1:
        # 块首固定 = 锚点成员 idx0（携带父链 trigger 语义，after_previous 锚定
        # 块外前驱，必须首位加入）；其余按 end 升序 → 块末尽量 = 最晚结束者
        # （父 succession 链下叶的直观锚定代表；即便锚点恰为最长者导致块末
        # 非块 end，delay 减法也会精确补偿，时间轴恒自洽）。
        end_hint = lambda s: s[0]
        anchor, rest = sub[0], sorted(sub[1:], key=end_hint)
        sub = [anchor] + rest
    for e_cur, meta, local in sub:
        out.extend(local)
    meta = {"kind": mode, "start": t, "end": end, "gap": gap_n,
            "members": [_m for _, _m, _ in sub]}
    blocks.append(meta)
    return end, meta


def expand_group(anim, elements):
    """页级 anim → (leaves, seq, blocks, violations)。

    leaves = [{id,start,end,trigger,delay}]（相对组根的绝对秒时间轴）；
    seq = AddEffect 序的 id 列表（ir["anim_sequence"]，块内按 end 升序其余、
    块首 = 父链锚定成员、块末 = 最晚结束者 = 父链下叶锚定代表）；
    blocks = 块结构元数据 [{kind,start,end,members}]（时间一致性断言用）；
    violations = 时间一致性断言违规列表（succession 断链 / aligned 偏移）。
    不改动 elements；调用方（ir_builder）将 trigger/delay 写回成员动画。

    delay 推导：PPT 链式锚定模型下，effect 的 TriggerDelayTime 相对"锚定目标"
    计时（with_previous → 锚定前一个加入 effect 的**开始**；after_previous →
    锚定它的**结束**；根触发 → 锚定触发点 T0=0）。故每叶 delay = 自身
    start − 锚定目标时刻，由绝对时间轴**减法**导出（非 gap/start 直接透传），
    块内排序（块末 = 最晚结束者）与"锚点成员恰为最长"等 edge 全部自洽——
    AddEffect 序单调（start 不递减）保证 delay ≥ 0。"""
    by_id = {e["id"]: e for e in elements}
    root = {"mode": anim.get("mode", "succession"), "items": anim["items"],
            "trigger": anim.get("trigger", "on_click"),
            "start": anim.get("start", 0.0), "gap": anim.get("gap", 0.2)}
    leaves, blocks = [], []
    # 根链首绝对 start = 组 start（相对触发点 T0 的延迟）
    _walk(root, root["start"], root["trigger"], root["gap"], by_id, blocks,
          leaves)
    # AddEffect 序 = 全局按 start 稳定排序（时间轴单调 → with_previous 前驱
    # start ≤ 自身 start，delay 非负恒成立；同 start 保留树序——块内局部序
    # 保留为 after_previous 语义友好的树次）。delay 导出：
    #   delay = 自身 start − 锚定目标时刻（after_previous → 前驱 end；
    #   with_previous → 前驱 start；根触发 → 触发点 T0 = 0）。
    # 前驱 end > 自身 start（链尾成员 start 漂移出对齐块的极端嵌套）时
    # after_previous 产生负 delay → 降级 with_previous（锚定前驱 start，
    # 恒非负）；绝对时间轴不因锚定方式而变（delay 减法恒使 COM 实际时刻
    # = 引擎 start）。
    leaves.sort(key=lambda x: x["start"])
    seq = [r["id"] for r in leaves]
    root_trig = anim.get("trigger", "on_click")
    prev = None
    for r in leaves:
        if prev is None:
            r["trigger"], r["delay"] = root_trig, round(r["start"], 6)
        elif r["trigger"] == "after_previous" and \
                prev["end"] <= r["start"] + TIMELINE_EPS:
            r["delay"] = round(r["start"] - prev["end"], 6)
        else:
            r["trigger"], r["delay"] = "with_previous", \
                round(r["start"] - prev["start"], 6)
        prev = r

    violations = []
    for b in blocks:
        if b["kind"] == "succession":
            for i in range(1, len(b["members"])):
                prev, cur = b["members"][i - 1], b["members"][i]
                if abs(cur["start"] - (prev["end"] + b["gap"])) > TIMELINE_EPS:
                    violations.append(
                        f"succession 断链 {cur['start']} ≠ {prev['end']} + {b['gap']}")
        elif b["kind"] in ("aligned", "group"):
            s0 = b["members"][0]["start"]
            for m in b["members"][1:]:
                if abs(m["start"] - s0) > TIMELINE_EPS:
                    violations.append(f"{b['kind']} 对齐偏移 {m['start']} ≠ {s0}")
    return leaves, seq, blocks, violations


def check_anim_groups(anim, elems, path):
    """语义校验（spec_compile 编译期调用）：组谱系（mode/gap/items）、
    trigger/start 仅在根、叶引用存在且带 animation、成员不得自带
    trigger/delay（时序由组决定）、容器不得为组员、成员不得重复。raise AgError。"""
    if not isinstance(anim, dict):
        raise AgError(f"{path}: 必须为 dict{{mode|trigger|start|gap|items}}，实为 {anim!r}")
    seen = set()
    _check_node(anim, path, elems, root=True, seen=seen)


def _check_node(node, path, elems, root, seen):
    for k in node:
        if k not in (_ROOT_KEYS if root else _GROUP_KEYS):
            raise AgError(f"{path}.{k}: 未知键（允许 {sorted(_ROOT_KEYS if root else _GROUP_KEYS)}）")
    mode = node.get("mode", "succession")
    if mode not in _MODES:
        raise AgError(f"{path}.mode: 未知模式 {mode!r}（可选 {sorted(_MODES)}）")
    if root:
        tr = node.get("trigger", "on_click")
        if tr not in TRIGGERS:
            raise AgError(f"{path}.trigger: 未知触发 {tr!r}"
                          f"（可选 {sorted(TRIGGERS)}）")
        start = node.get("start")
        if start is not None and (isinstance(start, bool)
                                  or not isinstance(start, (int, float))
                                  or start < 0):
            raise AgError(f"{path}.start: 必须为非负数值秒，实为 {start!r}")
    gap = node.get("gap")
    if gap is not None and (isinstance(gap, bool) or not isinstance(gap, (int, float))
                            or gap < 0):
        raise AgError(f"{path}.gap: 必须为非负数值秒，实为 {gap!r}")
    if not isinstance(node.get("items"), list) or not node["items"]:
        raise AgError(f"{path}.items: 必须为非空列表")
    for i, it in enumerate(node["items"]):
        ip = f"{path}.items[{i}]"
        if isinstance(it, str):             # YAML 简写：items: [eid, ...] ≡ {id: eid}
            it = {"id": it}
        elif not isinstance(it, dict):
            raise AgError(f"{ip}: 必须为 dict{{id}} 或 {{mode|gap|items}}")
        if "id" in it:
            for k in it:
                if k != "id":
                    raise AgError(f"{ip}.{k}: 叶仅允许 id 字段")
            eid = it["id"]
            if not isinstance(eid, str) or eid not in elems:
                raise AgError(f"{ip}.id: 引用不存在的顶层元素 {eid!r}")
            if eid in seen:
                raise AgError(f"{ip}.id: 组员 {eid!r} 重复声明")
            seen.add(eid)
            kt = elems[eid].get("type")
            if kt in ("stack", "dock", "graph"):
                raise AgError(f"{ip}.id: 容器 {eid!r} 不得为动画组员"
                              "（渲染无单形状可挂时间轴，同元素级动画规则）")
            if kt == "shape" and elems[eid].get("kind") == "cylinder":
                raise AgError(f"{ip}.id: cylinder {eid!r} 不支持动画"
                              "（复合形状展开为多部件，无单形状时间轴）")
            anim = elems[eid].get("animation")
            if not anim:
                raise AgError(f"{ip}.id: 组员 {eid!r} 必须声明 animation"
                              "（动画组编排有动画元素的时序）")
            for k in ("trigger", "delay"):
                if k in anim:
                    raise AgError(f"{ip}.id: 组员 {eid!r} 自带 animation.{k}"
                                  " 与组编排冲突（时序由组决定，请移除元素级时序）")
        else:
            if "trigger" in it or "start" in it:
                raise AgError(f"{ip}: 嵌套组仅允许 mode/gap/items"
                              "（trigger/start 属组根，嵌套继承父上下文）")
            _check_node(it, ip, elems, root=False, seen=seen)


if __name__ == "__main__":
    demo = {"mode": "succession", "trigger": "on_click", "start": 0.3, "gap": 0.2,
            "items": [{"id": "a"}, {"mode": "group", "items": [{"id": "b"}, {"id": "c"}]},
                      {"id": "d"}]}
    els = [{"id": k, "animation": {"effect": "进入动画_快速淡入"}} for k in "abcd"]
    leaves, seq, _b, viol = expand_group(demo, els)
    for r in leaves:
        print(f"{r['id']}: [{r['start']:.3f}, {r['end']:.3f}] {r['trigger']} "
              f"delay={r['delay']:.3f}")
    print("seq:", seq, "violations:", viol)