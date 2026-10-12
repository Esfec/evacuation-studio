# -*- coding: utf-8 -*-
"""
export_replay.py — 将 LLM-Agent 疏散仿真实验运行日志导出为「像素疏散小镇」沙盒可用的回放数据。

用法:
  # 导出仓库 results/release_smoke 下全部运行(默认)
  python export_replay.py

  # 指定仓库根目录与运行集合目录
  python export_replay.py --repo "D:/path/to/llm-evacuation-design-screening" --runs-dir results/release_smoke

  # 导出单个运行目录
  python export_replay.py --run-dir "D:/path/to/results/formal/20261010_xxxxxx"

  # 输出纯 JSON(可在沙盒页面中拖入加载)
  python export_replay.py --format json --out replay_data.json

输出:
  replay_data.js  —— window.REPLAY_DATA = {...}; 与 index.html 同目录放置即可(file:// 可直接加载)
"""
import argparse
import csv
import glob
import json
import os
import sys

# ---------------------------------------------------------------- 地图布局
# 语义拓扑 → 像素平面图布局(单位: 16px 瓦片)。道路+分区式表达,
# 与原研究 "semantic topology / bubble-diagram stage" 定位一致。
TILE = 16
LAYOUT = {
    # node: [x, y, w, h]  (瓦片坐标)
    "N01": [10, 9, 8, 7],    # 主大厅 (起火点)
    "N02": [21, 1, 9, 7],    # 过厅
    "N03": [10, 1, 9, 7],    # 展室
    "N04": [29, 18, 8, 6],   # 教室
    "N05": [16, 17, 11, 5],  # 中走廊
    "N06": [29, 10, 8, 6],   # 印象展区
    "N07": [32, 1, 9, 6],    # 北侧廊
    "N08": [43, 1, 10, 8],   # 临时展厅
    "N09": [18, 24, 6, 4],   # 防火门
    "N10": [39, 10, 5, 9],   # 紧急通道
    "N11": [46, 11, 5, 5],   # 侧门出口
    "N12": [39, 21, 8, 6],   # 中庭花园(死角)
    "N13": [33, 27, 10, 6],  # 临时展区
    "N14": [45, 28, 9, 4],   # 后走廊
    "N15": [1, 19, 7, 7],    # 封闭院落(死角)
    "N16": [56, 27, 6, 6],   # 储藏室(死角)
    "N17": [1, 8, 7, 9],     # 西展区
    "N18": [55, 2, 5, 5],    # 员工出口
}

STATUS_CODE = {"Active": 0, "Escaped": 1, "Dead": 2, "Exhausted": 3}
RESULT_CODE = {
    "": 0, "MOVED": 1, "EDGE_QUEUE": 2, "NODE_FULL": 3, "STAY": 4,
    "NO_VISIBLE_PATHS": 5, "STAMINA_WAIT": 6, "DIED": 7,
    "INACTIVE_ESCAPED": 8, "INACTIVE_DEAD": 9, "NO_DECISION": 10,
}
RESULT_LABEL = {v: k for k, v in RESULT_CODE.items()}


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(x, default=0.0):
    try:
        return round(float(x), 4)
    except (TypeError, ValueError):
        return default


def inum(x, default=0):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return default


def auto_layout(node_ids):
    """为布局表中不存在的节点生成兜底网格位置(画布底部)。"""
    layout = dict(LAYOUT)
    missing = [n for n in node_ids if n not in layout]
    for i, nid in enumerate(missing):
        layout[nid] = [2 + i * 8, 30, 6, 5]
    return layout


def export_run(run_dir, map_nodes, node_idx):
    """导出一个运行目录,返回紧凑 dict;失败返回 None。"""
    needed = ["agent_step.csv", "node_step.csv", "run_metrics.csv", "state_log.json"]
    if not all(os.path.exists(os.path.join(run_dir, p)) for p in needed):
        return None

    with open(os.path.join(run_dir, "state_log.json"), encoding="utf-8") as f:
        state = json.load(f)
    cfg = state.get("run_config", {})
    manifest = state.get("intervention_manifest", {})

    metrics_rows = read_csv(os.path.join(run_dir, "run_metrics.csv"))
    m = metrics_rows[0] if metrics_rows else {}
    metrics = {
        "escaped": inum(m.get("escaped")), "dead": inum(m.get("dead")),
        "exhausted": inum(m.get("exhausted")),
        "active_remaining": inum(m.get("active_remaining")),
        "escape_rate": fnum(m.get("escape_rate")),
        "total_steps": inum(m.get("total_steps")),
        "termination": m.get("termination_reason", ""),
        "edge_queue_events": inum(m.get("edge_queue_events")),
        "mean_smoke": fnum(m.get("mean_cumulative_smoke_exposure")),
        "llm_calls": inum(m.get("llm_calls")),
        "mean_backtrack": fnum(m.get("mean_backtrack_count")),
    }

    # --- agent 静态信息(初始分布) ---
    init_state = {a["agent_id"]: a for a in state.get("initial_state", {}).get("agents", [])}

    # --- agent_step: 逐帧状态 ---
    agent_rows = read_csv(os.path.join(run_dir, "agent_step.csv"))
    steps_map = {}   # step -> {aid: record}
    agent_meta = {}
    for r in agent_rows:
        s = inum(r["step"])
        aid = r["agent_id"]
        if aid not in agent_meta:
            agent_meta[aid] = {"id": aid, "type": r["agent_type"]}
        steps_map.setdefault(s, {})[aid] = r

    # --- node_step ---
    node_rows = read_csv(os.path.join(run_dir, "node_step.csv"))
    node_steps = {}
    for r in node_rows:
        s = inum(r["step"])
        node_steps.setdefault(s, {})[r["node_id"]] = [
            fnum(r["risk_level"]), fnum(r["smoke_density"]),
            inum(r["occupancy"]), 1 if r.get("scenario_blocked") == "True" else 0,
            r.get("status", "Open"),
        ]

    # --- edge_step (只保留有拥堵/高利用的) ---
    edge_steps = {}
    ep = os.path.join(run_dir, "edge_step.csv")
    if os.path.exists(ep):
        for r in read_csv(ep):
            util, q = fnum(r.get("utilization")), inum(r.get("edge_queue"))
            if util >= 0.5 or q > 0:
                s = inum(r["step"])
                edge_steps.setdefault(s, {})[r["source"] + ">" + r["target"]] = [
                    round(util, 2), q]

    # --- decision_log: 理由/推理文本 ---
    just_table, just_idx = [], {}
    reason_table, reason_idx = [], {}
    decisions = {}  # (step, aid) -> (justI, reasonI, mode)
    dp = os.path.join(run_dir, "decision_log.csv")
    if os.path.exists(dp):
        for r in read_csv(dp):
            key = (inum(r["step"]), r["agent_id"])
            j = (r.get("brief_justification") or "").strip()
            rs = (r.get("reasoning") or "").strip()
            ji, ri = -1, -1
            if j:
                if j not in just_idx:
                    just_idx[j] = len(just_table); just_table.append(j)
                ji = just_idx[j]
            if rs:
                if rs not in reason_idx:
                    reason_idx[rs] = len(reason_table); reason_table.append(rs)
                ri = reason_idx[rs]
            decisions[key] = (ji, ri, r.get("decision_mode", ""))

    max_step = max(steps_map.keys()) if steps_map else 0

    # agent 列表(按 id 排序保证稳定)
    agent_ids = sorted(agent_meta.keys())
    agents = []
    for aid in agent_ids:
        meta = agent_meta[aid]
        init = init_state.get(aid, {})
        agents.append({
            "id": aid, "type": meta["type"],
            "init": init.get("initial_node",
                             steps_map.get(0, {}).get(aid, {}).get("from_node", "")),
        })

    # 逐步帧
    steps = []
    for s in range(max_step + 1):
        nodes_frame = {}
        for nid, vals in node_steps.get(s, {}).items():
            if nid in node_idx:
                nodes_frame[node_idx[nid]] = vals
        agents_frame = {}
        for aid, r in steps_map.get(s, {}).items():
            ji, ri, dmode = decisions.get((s, aid), (-1, -1, ""))
            to_node = r.get("actual_node") or r.get("from_node") or ""
            from_node = r.get("from_node") or to_node
            prop = r.get("proposed_target") or ""
            agents_frame[aid] = [
                node_idx.get(to_node, -1),                 # 0 实际位置
                STATUS_CODE.get(r.get("status_after"), 0),  # 1 状态
                fnum(r.get("panic_after")),                 # 2 恐慌
                fnum(r.get("stamina_after")),               # 3 体力
                fnum(r.get("health_after")),                # 4 健康
                RESULT_CODE.get(str(r.get("action_result", "")).upper(), 0),
                ji,                                         # 6 理由索引
                node_idx.get(from_node, -1),                # 7 步初位置
                node_idx.get(prop, -1),                     # 8 意图目标
                ri,                                         # 9 推理索引
                dmode,                                      # 10 决策模式
            ]
        steps.append({
            "n": nodes_frame,
            "a": agents_frame,
            "e": edge_steps.get(s, {}),
        })

    return {
        "id": os.path.basename(run_dir),
        "policy": cfg.get("policy_id", m.get("policy_id", "?")),
        "design": cfg.get("design_id", m.get("design_id", "?")),
        "condition": cfg.get("condition_id", m.get("condition_id", "?")),
        "seed": inum(cfg.get("seed", m.get("seed"))),
        "fire_origin": cfg.get("fire_origin", "N01"),
        "step_seconds": inum(cfg.get("step_seconds", 5), 5),
        "agent_counts": cfg.get("agent_counts", {}),
        "blocked_nodes": manifest.get("blocked_nodes", []),
        "added_edges": manifest.get("added_edges", []),
        "capacity_changes": manifest.get("capacity_changes", []),
        "design_label": manifest.get("design_label", ""),
        "condition_label": manifest.get("condition_label", ""),
        "metrics": metrics,
        "agents": agents,
        "just": just_table,
        "reason": reason_table,
        "steps": steps,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.join(os.path.dirname(__file__), "..", "01_研究源码"),
                    help="研究仓库根目录(含 Map.json)")
    ap.add_argument("--runs-dir", default=None,
                    help="运行集合目录(相对 repo 或绝对路径),默认 results/release_smoke")
    ap.add_argument("--run-dir", action="append", default=[],
                    help="单个运行目录,可重复指定")
    ap.add_argument("--out", default=None, help="输出文件路径")
    ap.add_argument("--format", choices=["js", "json"], default="js")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    map_path = os.path.join(repo, "Map.json")
    if not os.path.exists(map_path):
        print("未找到 Map.json:", map_path); sys.exit(1)
    with open(map_path, encoding="utf-8") as f:
        map_data = json.load(f)

    node_ids = [n["id"] for n in map_data["nodes"]]
    node_idx = {nid: i for i, nid in enumerate(node_ids)}
    layout = auto_layout(node_ids)

    nodes = []
    for n in map_data["nodes"]:
        x, y, w, h = layout[n["id"]]
        nodes.append({
            "id": n["id"], "name": n["name"], "type": n["type"],
            "x": x, "y": y, "w": w, "h": h,
            "cx": x + w / 2, "cy": y + h / 2,
            "cap": n.get("capacity", 0), "area": n.get("area", 0),
            "dead_end": bool(n.get("is_dead_end")), "desc": n.get("desc", ""),
        })

    # 无向边去重
    seen, edges = set(), []
    for e in map_data["edges"]:
        key = tuple(sorted([e["source"], e["target"]]))
        if key not in seen:
            seen.add(key)
            edges.append([node_idx[e["source"]], node_idx[e["target"]]])

    # 收集运行目录
    run_dirs = list(args.run_dir)
    if not run_dirs:
        runs_dir = args.runs_dir or "results/release_smoke"
        runs_dir = runs_dir if os.path.isabs(runs_dir) else os.path.join(repo, runs_dir)
        run_dirs = sorted(glob.glob(os.path.join(runs_dir, "2*")))

    runs = []
    for d in run_dirs:
        r = export_run(os.path.abspath(d), map_data["nodes"], node_idx)
        if r:
            runs.append(r)
            print("导出:", r["id"], r["policy"], r["design"], r["condition"],
                  "seed", r["seed"], "-", len(r["steps"]), "steps")
        else:
            print("跳过(日志不完整):", d)

    payload = {
        "meta": {"tile": TILE, "map_name": map_data.get("map_name", ""),
                 "source": "llm-evacuation-design-screening"},
        "nodes": nodes,
        "edges": edges,
        "runs": runs,
    }

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "replay_data." + ("js" if args.format == "js" else "json"))
    if args.format == "js":
        with open(out, "w", encoding="utf-8") as f:
            f.write("window.REPLAY_DATA = ")
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            f.write(";\n")
    else:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    print("写出:", out, f"({os.path.getsize(out)/1024:.0f} KB, {len(runs)} runs)")


if __name__ == "__main__":
    main()
