# -*- coding: utf-8 -*-
"""revisioner.py — 修订链调度 + 修复动作库 + 事务应用 + fix.diff（决策部件②）。

组合角色（build_ppt --fix 主循环消费）：
  1. plan(violations)：归因结果 → 修订计划。internal 出现即停机（不修订）；
     fixable/advisory → 动作 + 候选菜单 + 修订器归属（spec=机械默认 / llm / manual）。
  2. apply_revisions(spec_raw, revisions)：**纯结构级**应用（不写盘）。path 是
     逻辑页内路径；单页 SPEC（顶层形态）与多页（meta.slides）由应用层统一映射。
     失败（old 不匹配 / 索引越界）→ 返回错误列表，调用方整体不落盘（事务性）。
  3. write_fix_diff / snapshot_file / rollback：审计与回滚（fix.diff 行格式：
     轮次|修订器|动作|字段路径|旧→新|理由|置信度|数据来源）。
"""

# ---- 动作库候选菜单（决策部件② 动作库原文；默认动作 = 机械保守项在前）----
MENU = {
    "autofit":   ["降号", "扩框", "浓缩文本", "拆元素", "人工"],
    "safety":    ["平移/收缩", "调换位置", "缩放", "人工"],
    "overlap":   ["补overlap", "移A", "移B", "挪开", "人工"],
    "zfix":      ["补z_override", "人工"],
    "fontscale": ["调至合法档", "人工"],
    "content":   ["从brief生成文本", "引用现有文本", "移除(若装饰)", "人工"],
    "manual":    ["人工"],
}


def plan(violations):
    """attribution.Violation 列表 → (internal, items)。

    internal 任何出现 → 停机（items 仍生成但调用方须先停机 exit 4）。
    items: [{v, fixer, action}]；fixer ∈ spec | llm | manual。
    """
    internal = [v for v in violations if v.klass == "internal"]
    items = []
    for v in violations:
        if v.klass == "internal":
            items.append({"v": v, "fixer": "manual", "action": "manual",
                          "candidates": ["人工"]})
        elif v.klass == "advisory":
            items.append({"v": v, "fixer": "manual", "action": v.action,
                          "candidates": MENU.get("manual", ["人工"])})
        else:  # fixable
            if v.action == "content":
                items.append({"v": v, "fixer": "llm", "action": "content",
                              "candidates": MENU["content"]})
            else:
                items.append({"v": v, "fixer": "spec", "action": v.action,
                              "candidates": MENU.get(v.action, ["人工"])})
    return internal, items


# ---- 路径应用（纯函数；spec_raw = 原始 YAML 加载后的 dict）----

def _page_container(spec_raw):
    """原始 SPEC 形态判定：返回 (容器 dict, 多页 flag)。单页顶层形态 → spec 自身；
    多页 meta.slides → {"slides": [...]} 宿主。"""
    if isinstance(spec_raw.get("meta"), dict) \
            and isinstance(spec_raw["meta"].get("slides"), list) \
            and spec_raw["meta"]["slides"]:
        return spec_raw["meta"], True
    return spec_raw, False


def _annotate_page(revision, pg):
    """revision 补页标（spec_fixer 产出时不带 pg，由调用方标注）。返回新 dict。"""
    r = dict(revision)
    r["pg"] = pg
    return r


def _apply_one(host, path, new, old_marker):
    """在 host（逻辑页容器：含 elements/relations 键）上应用页内 path。返回错误串或 None。"""
    segs = list(path)
    if not segs:
        return "空路径"
    if segs[0] == "elements":
        if len(segs) < 2 or not isinstance(segs[1], int):
            return f"elements 路径缺索引: {path}"
        idx = segs[1]
        try:
            elem = host["elements"][idx]
        except (KeyError, IndexError):
            return f"elements[{idx}] 越界"
        # 缺层 dict 创建（如 text_style.fs 新增）；整型段（list 下标）跳过 walk
        for k in segs[2:]:
            if not isinstance(k, str):
                continue
            if not isinstance(elem, dict):
                return f"{path}: 中间段非 dict"
            if k not in elem:
                if k == segs[-1]:
                    break          # 叶子缺失：交给 _set_leaf（old=None 新建）
                elem[k] = {}
            elem = elem[k]
        _set_leaf(host, path, new, old_marker)
        return None
    if segs[0] == "relations":
        rel = host.setdefault("relations", {})
        if len(segs) >= 3 and segs[2] == "+":
            rel.setdefault(segs[1], []).append(new)
            return None
        # ("relations", 段, idx, 字段)
        if len(segs) < 4:
            return f"relations 路径不完整: {path}"
        seg, idx, field = segs[1], segs[2], segs[3]
        try:
            item = rel.get(seg, [])[idx]
        except IndexError:
            return f"relations.{seg}[{idx}] 越界"
        _set_leaf(host, path, new, old_marker)
        return None
    return f"未知段 {segs[0]!r}: {path}"


def _set_leaf(host, path, new, old_marker):
    """叶值写入：old 存在且不匹配 → 抛 ValueError（调用方整体回滚）。
    支持 dict 键与 list 下标（rect 数值下标；注意 list 不能用成员检查）。"""
    segs = list(path)
    node = host
    for k in segs[:-1]:
        node = node[k]
    key = segs[-1]
    if isinstance(node, dict):
        exists = key in node
    elif isinstance(node, list):
        exists = isinstance(key, int) and 0 <= key < len(node)
    else:
        exists = False
    if old_marker is not None and exists and node[key] != old_marker:
        raise ValueError(f"{path}: 当前 {node[key]!r} ≠ 修订基准 {old_marker!r}")
    node[key] = new


def apply_revisions(spec_raw, revisions):
    """spec_raw: 原始 SPEC dict（未编译）。revisions: [{action,path,old,new,pg,...}]。
    → (新 spec_raw, diffs, errors)。任一失败 → errors 非空且返回原样 spec_raw
    （事务性：调用方不得落盘，须回滚本轮）。"""
    host, multi = _page_container(spec_raw)
    work = dict(spec_raw)              # 浅拷贝；新增段（setdefault）必须落在 work 上
    if multi:
        work["meta"] = dict(work.get("meta") or {})      # slides 宿主需深一层拷贝
        work_meta = work["meta"]
        work_meta["slides"] = [dict(sl) for sl in (work_meta.get("slides") or [])]
    host, multi = _page_container(work)
    diffs, errors = [], []
    for rev in revisions:
        pg = rev.get("pg", 0)
        container = host["slides"][pg] if multi else host
        try:
            err = _apply_one(container, rev["path"], rev["new"], rev.get("old"))
            if err:
                errors.append(f"{rev['action']}/{rev['path']}: {err}")
                continue
            diffs.append(rev)
        except ValueError as ex:
            errors.append(str(ex))
    return (work, diffs, errors) if not errors else (spec_raw, [], errors)


# ---- fix.diff（行格式：轮次|修订器|动作|字段路径|旧→新|理由|置信度|数据来源）----

def format_path(path, pg=-1, multi=False):
    parts = []
    p = list(path)
    if p and p[0] == "elements":
        parts = ["elements", f"[{p[1]}]"] + _fmt_fields(p[2:])
    elif p and p[0] == "relations":
        rest = p[1:]
        if len(rest) == 2 and rest[1] == "+":
            parts = [f"relations.{rest[0]}", "+"]
        else:
            parts = [f"relations.{rest[0]}", f"[{rest[1]}]"] + _fmt_fields(rest[2:])
    s = "".join(parts)
    if multi and pg >= 0:
        s = f"slides[{pg}].{s}"
    return s or "<path>"


def _fmt_fields(fs):
    out = []
    for f in fs:
        out.append(f".{f}" if isinstance(f, str) else f"[{f}]")
    return out


def write_fix_diff(path, diffs, round_n, fixer="spec"):
    """diffs: apply_revisions 产出的 [rev]；path: fix.diff 文件。追写（多轮轮次累加）。"""
    lines = []
    for d in diffs:
        old = "∅" if d.get("old") is None else str(d["old"])
        new = "∅" if d.get("new") is None else str(d["new"])
        fp = format_path(d["path"], pg=d.get("pg", 0), multi=d.get("multi", False))
        lines.append(f"{round_n}|{fixer}|{d['action']}|{fp}|{old}→{new}|"
                     f"{d.get('basis', '')}|{d.get('confidence', 0)}|{d.get('data_source', '')}")
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    return len(lines)


def snapshot_file(spec_path, round_n):
    """修订前快照：spec_path.snap.N。返回快照路径。"""
    snap = f"{spec_path}.snap.{round_n}"
    with open(spec_path, "r", encoding="utf-8") as f:
        text = f.read()
    with open(snap, "w", encoding="utf-8") as f:
        f.write(text)
    return snap


def rollback(spec_path, round_n):
    """回滚到快照 spec_path.snap.N。返回是否成功。"""
    snap = f"{spec_path}.snap.{round_n}"
    try:
        with open(snap, "r", encoding="utf-8") as f:
            text = f.read()
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(text)
        return True
    except OSError:
        return False


# ---- SPEC 序列化（应用后写回；YAML 注释不保留——SPEC 是 agent 生成物）----

def dump_spec(spec_raw, newline=None):
    """spec_raw dict → YAML 文本。newline="\r\n" 时保留 CRLF（Windows 编辑一致性）。"""
    import yaml
    text = yaml.safe_dump(spec_raw, allow_unicode=True, sort_keys=False,
                          default_flow_style=False)
    if newline == "\r\n":
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    return text