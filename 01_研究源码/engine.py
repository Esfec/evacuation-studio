"""engine.py — 仿真引擎"""
import json
import re
import random
import threading
import numpy as np
import networkx as nx
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from datetime import datetime
import time, uuid, datetime as _dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import (
    LLM_PROVIDERS, VALID_START_NODES, FORBIDDEN_START_NODES,
    INITIAL_PANIC, STEP_SECONDS, TYPE_CFG,
    density_to_sense,
)
from llm_api import call_llm
from movement import resolve_moves
from observation import (
    archetype_guidance,
    body_state,
    panic_state,
    smoke_state,
    static_cue_text,
)
from policies import (
    GlobalShortestPathPolicy,
    RiskAwareDijkstraPolicy,
    information_scope_for,
)



# --- LLM output protocol (studio-1.5) -------------------------------------------
# Deterministic, audited repair of the target field. Only targets that are already in
# the agent's local option list can be matched; anything ambiguous stays invalid.
_NODE_ID = re.compile(r"N\d{2}")


def resolve_llm_target(content, paths):
    """Return (path, normalization) for an LLM answer, or (None, None).

    normalization is None for an exact ID, otherwise one of
    'id_case' (e.g. "n05"), 'id_in_text' (exactly one allowed ID inside the string,
    e.g. "N05 中走廊") or 'name' (exactly one allowed target whose name equals the
    string, e.g. "中走廊"). Ambiguous or unknown values are rejected.
    """
    raw = content.get("target_id") if isinstance(content, dict) else None
    if not isinstance(raw, str):
        return None, None
    text = raw.strip()
    by_id = {str(p["target_id"]): p for p in paths}
    if raw in by_id:
        return by_id[raw], None
    if text in by_id:
        return by_id[text], "id_case"
    if text.upper() in by_id:
        return by_id[text.upper()], "id_case"
    ids = set(_NODE_ID.findall(text.upper())) & set(by_id)
    if len(set(_NODE_ID.findall(text.upper()))) == 1 and len(ids) == 1:
        return by_id[ids.pop()], "id_in_text"
    named = [p for p in paths if str(p.get("target_name", "")).strip() == text]
    if len(named) == 1:
        return named[0], "name"
    return None, None


def llm_retry_feedback(error_type, answer, content, allowed):
    """Correction message for the next attempt; states the protocol, adds no new facts."""
    if error_type == "invalid_target":
        raw = content.get("target_id") if isinstance(content, dict) else None
        return (f"上一条回复的 target_id 为「{raw}」，它不是允许的节点 ID。"
                "target_id 必须原样填写下列等号左侧的 ID 之一，不要填写房间名或其他文字。"
                f"\n允许目标：{allowed}\n请重新输出同样格式的 JSON。")
    if error_type == "output_truncated":
        return ("上一条回复被截断。请把 brief_justification 缩短到 60 字以内，并输出完整 JSON。"
                f"\n允许目标：{allowed}")
    if error_type == "invalid_summary":
        return ("brief_justification 必须是一段字符串。请重新输出 JSON。"
                f"\n允许目标：{allowed}")
    return ("上一条回复不是一个 JSON 对象。只输出 "
            '{"target_id":"节点ID","brief_justification":"简短理由"}，不要附加其他文字。'
            f"\n允许目标：{allowed}")

class SimulationEngine:
    def __init__(self, map_data, agent_data, api_key=None,
                 api_provider="Poe", api_model="GPT-4o", seed=42,
                 temperature=0.1, reasoning_effort=None,
                 fire_origin=None,
                 risky_coeff: float = 3.0,
                 blocked_coeff: float = 7.0,
                 fire_rate: float = 0.1,
                 run_config=None,
                 intervention_manifest=None, event_sink=None):
        self.map_data = json.loads(json.dumps(map_data))
        map_data = self.map_data
        if run_config is not None:
            seed = run_config.seed
            fire_origin = run_config.fire_origin
            fire_rate = run_config.fire_rate
            risky_coeff = run_config.risky_coeff
            blocked_coeff = run_config.blocked_coeff
            temperature = run_config.temperature
            api_provider = run_config.provider
            api_model = run_config.model
        self.run_config = run_config
        self.intervention_manifest = intervention_manifest or {}
        self.event_sink = event_sink
        self._audit_lock = threading.RLock()
        self.observer_errors = []

        if fire_origin:
            self.map_data["fire_origin"] = fire_origin

        # Change 2: 删除此处恒为 False 的死代码块
        # fo = self.map_data.get("fire_origin", "N01")
        # if fo in self.map_data.get("nodes", []):
        #     pass

        self.api_key = api_key or ""
        self.api_provider = api_provider
        self.api_model = api_model
        self.temperature = temperature
        self.reasoning_effort = reasoning_effort
        self.rng = random.Random(seed)
        self.seed = seed
        self.risky_coeff = risky_coeff       # ← Change 1
        self.blocked_coeff = blocked_coeff   # ← Change 1
        self.fire_rate = fire_rate
        self.policy_id = getattr(run_config, "policy_id", "LLM_Agent" if api_key else "Local_Rule")
        self.information_scope = information_scope_for(self.policy_id)
        self.valid_run = True
        self.invalid_reason = ""
        self.fallback_count = 0
        self.llm_disabled = False
        self.llm_concurrency = int(getattr(run_config, "llm_concurrency", 8))

        templates = (agent_data if isinstance(agent_data, list)
                     else agent_data.get("agents", []))
        self.template_map = {t["type"]: t for t in templates}

        self.nodes = {}
        for n in map_data["nodes"]:
            node = dict(n)
            node["base_type"] = "hall" if node.get("type") == "fire" else node.get("type", "room")
            self.nodes[n["id"]] = node
        # ── 找到这个块，替换为下面的版本 ──────────────────────────────────────────
        fo = self.map_data.get("fire_origin", "N01")
        for nid, nd in self.nodes.items():
            if nd.get("type") == "fire" and nid != fo:
                nd["type"] = nd.get("base_type", "room")
                nd["status"] = "Open"  # ← 清除旧火源残留的 Blocked 状态
                nd["risk_level"] = 0.0  # ← 重置风险
                nd["smoke_density"] = 0.0  # ← 重置烟雾
                nd.pop("_init_blocked", None)  # ← 解除永久跳过锁，允许火势重新计算
        if fo in self.nodes:
            self.nodes[fo]["type"] = "fire"
            self.nodes[fo]["status"] = "Risky"  # ← 预置：起火点初始就是 Risky，不等 run_step

        # The operational bubble-map model treats every edge as one topological hop.
        # Keep the legacy ``dist`` field in Map.json for compatibility, but do not
        # interpret it as a physical distance or travel time.
        default_capacity = getattr(run_config, "base_edge_capacity", 4)
        self.edges = [
            {
                **e,
                "dist": 1.0,
                "capacity_per_step": int(e.get("capacity_per_step", default_capacity)),
            }
            for e in map_data["edges"]
        ]
        self.adj = {nid: [] for nid in self.nodes}
        self.G = nx.DiGraph()
        for e in self.edges:
            self.adj[e["source"]].append(e)
            self.G.add_edge(e["source"], e["target"], weight=1.0)
        for nid in self.nodes:
            self.G.add_node(nid)
        self.G_und = self.G.to_undirected()

        for d in self.nodes.values():
            d.setdefault("capacity", 60)
            d.setdefault("area", 60.0)
            d.setdefault("current_count", 0)
            d.setdefault("smoke_density", 0.0)
            d.setdefault("risk_level", 0.0)
            if d.get("scenario_blocked"):
                d["status"] = "Blocked"
                d["_scenario_blocked"] = True
            if d.get("status") == "Blocked":
                d["_init_blocked"] = True
            else:
                d.setdefault("status", "Open")

        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=Retry(
            total=2, backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504])))

        self.agents = []
        self.logs = []
        self.cot_logs = []
        self.current_step = 0
        self.step_event_log = []
        self.token_usage = {"prompt": 0, "completion": 0,
                            "reasoning_tokens": 0, "calls": 0}
        self.run_id = (
            _dt.datetime.now().strftime('%Y%m%d_%H%M%S')
            + "_" + uuid.uuid4().hex[:8]
        )
        self.llm_call_log = []
        self.node_occupancy_log = []
        # Paper-grade audit tables.  These are deliberately denormalised so
        # every table can be analysed directly without reconstructing hidden
        # simulator state.
        self.agent_step_log = []
        self.node_step_log = []
        self.edge_step_log = []
        self.initial_state = {"agents": [], "nodes": []}
        self.panic_event_log = []
        self.sim_start_time = None
        self.sim_end_time = None
        self._prev_panic = {}
        self.step_stats = []

        self._generate_fire_events_v4()

    # ════════════════════════════════════════════════════════════════
    # Change 3: 新增 _generate_fire_events 方法
    # ════════════════════════════════════════════════════════════════
    def _generate_fire_events(self):
        origin = self.map_data.get("fire_origin", "N01")
        G_und = self.G.to_undirected()
        fire_scale = 0.1 / max(0.01, self.fire_rate)

        for nid, nd in self.nodes.items():
            if nd.get("_init_blocked") or nd.get("type") in ("exit",):
                continue
            if nid == origin:
                origin_risky_step = 0
                origin_blocked_step = max(2, int(round(5 * fire_scale)))
                nd["events"] = {
                    str(origin_risky_step): {
                        "status": "Risky",
                        "desc": f"{nd.get('name', nid)} 是起火点，立即出现烟雾",
                    },
                    str(origin_blocked_step): {
                        "status": "Blocked",
                        "desc": f"{nd.get('name', nid)} 起火，迅速封堵",
                    },
                }
                continue

            try:
                hops = nx.shortest_path_length(G_und, origin, nid)
            except Exception:
                continue

            risky_step = max(1, int(round(hops * self.risky_coeff * fire_scale)))

            # ✅ 关键修复：blocked = risky + 额外延迟，两个系数都生效
            extra_delay = max(1, int(round(hops * self.blocked_coeff * fire_scale)))
            blocked_step = risky_step + extra_delay

            nd["events"] = {
                str(risky_step): {
                    "status": "Risky",
                    "desc": f"火势蔓延，{nd.get('name', nid)} 出现烟雾风险",
                },
                str(blocked_step): {
                    "status": "Blocked",
                    "desc": f"火势蔓延，{nd.get('name', nid)} 被完全封堵",
                },
            }

    def _hazard_timing(self, node_id, rate=None):
        """Return the single source of truth for Risky/Blocked steps."""
        node = self.nodes[node_id]
        if node.get("_scenario_blocked"):
            return 0, 0
        if node.get("type") == "exit":
            return None, None
        origin = self.map_data.get("fire_origin", "N01")
        fire_scale = 0.1 / max(0.01, self.fire_rate if rate is None else rate)
        if node_id == origin:
            return 0, max(2, int(round(5 * fire_scale)))
        try:
            hops = nx.shortest_path_length(self.G_und, origin, node_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None, None
        risky_step = max(1, int(round(hops * self.risky_coeff * fire_scale)))
        blocked_step = risky_step + max(
            1, int(round(hops * self.blocked_coeff * fire_scale))
        )
        return risky_step, blocked_step

    def _hazard_state(self, node_id, step):
        """Calculate smoke, risk and status from the frozen fire parameters."""
        node = self.nodes[node_id]
        if node.get("_scenario_blocked"):
            return 0.0, 0.0, "Blocked"
        risky_step, blocked_step = self._hazard_timing(node_id)
        smoke_rate = getattr(self.run_config, 'smoke_rate', None)
        smoke_scale = getattr(self.run_config, 'smoke_scale', 0.9)
        def smoke_at_time():
            sr, sb = self._hazard_timing(node_id, smoke_rate)
            if sr is None:
                return 0.0
            if sb == 0 or step >= sb:
                return 1.0
            if sr == 0:
                progress = 0.5 + 0.5 * step / max(1, sb)
            elif step < sr:
                progress = 0.49 * step / max(1, sr)
            else:
                progress = 0.5 + 0.5 * (step - sr) / max(1, sb - sr)
            return max(0.0, min(1.0, progress * smoke_scale))
        if risky_step is None:
            return 0.0, 0.0, "Open"
        if blocked_step == 0 or step >= blocked_step:
            return 1.0, smoke_at_time(), "Blocked"
        if risky_step == 0:
            progress = 0.5 + 0.5 * step / max(1, blocked_step)
        elif step < risky_step:
            progress = 0.49 * step / max(1, risky_step)
        else:
            progress = 0.5 + 0.5 * (step - risky_step) / max(
                1, blocked_step - risky_step
            )
        risk = max(0.0, min(1.0, progress))
        smoke = smoke_at_time()
        return risk, smoke, "Risky" if step >= risky_step else "Open"

    def _generate_fire_events_v4(self):
        for node_id, node in self.nodes.items():
            risky_step, blocked_step = self._hazard_timing(node_id)
            if risky_step is None:
                node["events"] = {}
                continue
            node["events"] = {
                str(risky_step): {
                    "status": "Risky" if blocked_step != 0 else "Blocked",
                    "desc": f"{node.get('name', node_id)} 进入烟火影响状态",
                },
                str(blocked_step): {
                    "status": "Blocked",
                    "desc": f"{node.get('name', node_id)} 达到不可通行阈值",
                },
            }

    def update_environment_v4(self, step):
        for node in self.nodes.values():
            node["current_count"] = 0
        for agent in self.agents:
            if agent["status"] in ("Active", "Exhausted"):
                self.nodes[agent["current_node"]]["current_count"] += 1
        for node_id, node in self.nodes.items():
            risk, smoke, status = self._hazard_state(node_id, step)
            node["risk_level"] = risk
            node["smoke_density"] = smoke
            node["status"] = status
            triggered = [
                int(key) for key in node.get("events", {}) if int(key) <= step
            ]
            node["_event_desc"] = (
                node["events"][str(max(triggered))].get("desc", "")
                if triggered else ""
            )

    # ════════════════════════════════════════════════════════════════
    # 过滤距出口太近的起始节点
    # ════════════════════════════════════════════════════════════════
    def _get_valid_start_nodes(self, min_hops_to_exit: int = 3) -> list:
        # Change 5: 使用从 config 导入的 VALID_START_NODES 替换局部硬编码
        # 若 config 未配置则回退到 {"N11"}
        actual_exit_nodes = [
            nid for nid, nd in self.nodes.items()
            if nd.get('type') == 'exit'
        ]
        configured_starts = {
            nid for nid in VALID_START_NODES
            if nid in self.nodes
            and self.nodes[nid].get('type') not in ('exit', 'fire')
            and nid not in FORBIDDEN_START_NODES
        }
        candidate_nodes = configured_starts or {
            nid for nid, nd in self.nodes.items()
            if nd.get('type') not in ('exit', 'fire')
            and nid not in FORBIDDEN_START_NODES
        }

        G_und = self.G.to_undirected()

        def _filter(min_h):
            result = []
            for nid in sorted(candidate_nodes):
                nd = self.nodes[nid]
                if nd.get('status') == 'Blocked':
                    continue
                min_dist = float('inf')
                for ex in actual_exit_nodes:
                    try:
                        d = nx.shortest_path_length(G_und, nid, ex)
                        min_dist = min(min_dist, d)
                    except Exception:
                        continue
                if min_dist != float('inf') and min_dist >= min_h:
                    result.append(nid)
            return result

        for threshold in (min_hops_to_exit, 2, 1):
            nodes = _filter(threshold)
            if nodes:
                return nodes

        return sorted(candidate_nodes)

    def initialize_agents(self, cognitive=10, perceptual=15, follower=23,
                          initial_distribution=None,
                          min_hops_to_exit: int = 3, initial_positions=None):
        self.agents = []
        rng = self.rng
        total = cognitive + perceptual + follower
        if initial_distribution is None and self.run_config is not None:
            initial_distribution = self.run_config.initial_distribution_dict()
        if initial_positions is None and getattr(self.run_config, 'initial_positions', None) is not None:
            initial_positions = dict(self.run_config.initial_positions)
        expected_ids = []
        for prefix, count in (('C', cognitive), ('P', perceptual), ('F', follower)):
            offset = len(expected_ids)
            expected_ids.extend(f'{prefix}{offset+j+1:02d}' for j in range(count))
        if initial_distribution is not None and initial_positions is not None:
            raise ValueError('不能同时设置按房间分布与逐个位置')
        if initial_positions is not None:
            if set(initial_positions) != set(expected_ids):
                raise ValueError('逐个位置必须完整匹配人数生成的 Agent ID')
            node_assignments = [initial_positions[aid] for aid in expected_ids]
            use_custom = True
        elif initial_distribution is not None:
            if any(isinstance(n,bool) or int(n)!=n or n<0 for n in initial_distribution.values()):
                raise ValueError('房间人数必须为非负整数')
            if sum(initial_distribution.values()) != total:
                raise ValueError('各房间人数之和必须等于 Agent 总数')
            node_assignments = [nid for nid, count in sorted(initial_distribution.items()) for _ in range(int(count))]
            rng.shuffle(node_assignments)
            use_custom = True
        else:
            valid = self._get_valid_start_nodes(min_hops_to_exit)
            use_custom = False

        if use_custom:
            from collections import Counter
            for nid, count in Counter(node_assignments).items():
                if nid not in self.nodes or self.nodes[nid].get('type')=='exit' or self.nodes[nid].get('status')=='Blocked':
                    raise ValueError(f'无效初始位置 {nid}：不存在、出口或已关闭')
                if count > self.nodes[nid]['capacity']:
                    raise ValueError(f'{nid} 初始人数 {count} 超过房间容量')

        assign_idx = 0
        idx = 0
        allocated = {nid: 0 for nid in self.nodes}
        for atype, count in [("Cognitive", cognitive),
                              ("Perceptual", perceptual),
                              ("Follower", follower)]:
            tmpl = self.template_map.get(atype)
            if not tmpl:
                continue
            for _ in range(count):
                idx += 1
                # 改为（强制覆盖，不用 setdefault）
                params = json.loads(json.dumps(tmpl["params"]))
                params.setdefault("physical", {})
                params["physical"].setdefault("base_speed", 1.2)
                params["physical"].setdefault("stamina", 100)
                params.setdefault("psychology", {
                    "panic_threshold": 0.8, "stress_resistance": 0.5,
                    "panic_behavior": {
                        "mistake_prob": 0.3, "ignore_exit_prob": 0.2,
                        "follow_crowd_bias": 0.3}})

                if use_custom:
                    node = node_assignments[assign_idx]
                    assign_idx += 1
                else:
                    available = [nid for nid in valid if allocated[nid] < self.nodes[nid]['capacity']]
                    if not available:
                        raise ValueError('自动起点容量不足；请减少人数或手动指定更多房间')
                    node = self.rng.choice(available)
                allocated[node] += 1

                raw_panic = INITIAL_PANIC.get(atype, 0.1) + self.rng.uniform(-0.05, 0.05)
                self.agents.append({
                    "id": f"{atype[0]}{idx:02d}", "type": atype,
                    "desc": tmpl["desc"],
                    "role_description": tmpl.get("role_description", ""),
                    "params": params, "current_node": node,
                    "status": "Active",
                    "health": 100.0,
                    "stamina": float(params["physical"]["stamina"]),
                    "cumulative_smoke_exposure": 0.0,
                    "panic_level": max(0.0, min(1.0, raw_panic)),
                    "history": [node], "recent_thoughts": [],
                    "known_connections": {},
                    "last_thought": "", "last_reasoning": "",
                    "_slot_x": self.rng.uniform(-0.35, 0.35),
                    "_slot_y": self.rng.uniform(-0.35, 0.35),
                    "_move_skip": False,
                    "_queue_age": 0,
                    "_queued_edge": None,
                })
        from collections import Counter
        dist = Counter(a['current_node'] for a in self.agents)
        for nid, node in self.nodes.items():
            node['current_count'] = dist.get(nid, 0)
        self.actual_initial_distribution = dict(sorted(dist.items()))
        self.initial_state = {
            "agents": [
                {
                    "agent_id": agent["id"],
                    "agent_type": agent["type"],
                    "initial_node": agent["current_node"],
                    "panic_level": round(agent["panic_level"], 6),
                    "stamina": round(agent["stamina"], 6),
                    "health": round(agent["health"], 6),
                }
                for agent in self.agents
            ],
            "nodes": [
                {
                    "node_id": node_id,
                    "node_type": node.get("type", ""),
                    "status": node.get("status", "Open"),
                    "capacity": int(node.get("capacity", 60)),
                    "area": float(node.get("area", 60.0)),
                }
                for node_id, node in sorted(self.nodes.items())
            ],
        }
        return len(self.agents)

    # ── 环境更新 ──   火势蔓延参数设置，不能太快
    def update_environment(self, step, fire_rate=0.1):
        for d in self.nodes.values():
            d["current_count"] = 0
        for a in self.agents:
            if a["status"] in ("Active", "Exhausted"):
                self.nodes[a["current_node"]]["current_count"] += 1

        origin = self.map_data.get("fire_origin", "N01")
        for nid, node in self.nodes.items():
            if node.get("_init_blocked"):
                continue
            try:
                dist = nx.shortest_path_length(self.G_und, origin, nid, weight="weight")
            except Exception:
                dist = 999
            sf = min(1.0, step * fire_rate * 0.05)  # 0.12 → 0.05，扩散慢3倍
            risk = max(0.0, sf - dist * 0.15)  # 0.08 → 0.15，距离衰减更强
            node["risk_level"] = min(1.0, risk)
            node["smoke_density"] = min(1.0, risk * 0.85)
            if risk > 0.92:  # 0.85 → 0.92，更难触发Blocked
                node["status"] = "Blocked"

        for nid, node in self.nodes.items():
            events = node.get("events", {})
            if not events:
                continue
            triggered = [int(k) for k in events if int(k) <= step]
            if triggered:
                evt = events[str(max(triggered))]
                ns = evt.get("status")
                if ns and node.get("status") not in ("Blocked",):
                    node["status"] = ns
                node["_event_desc"] = evt.get("desc", "")

    def apply_consequences(self, agent):
        node = self.nodes[agent["current_node"]]
        risk = node.get("risk_level", 0)
        smoke = node.get("smoke_density", 0)
        if risk > 0.8:
            agent["health"] -= 50
        elif risk > 0.5:
            agent["health"] -= 20
        elif smoke > 0.5:
            agent["health"] -= 5
        density = node["current_count"] / node.get("area", 60.0)

        # ← 修复：拆开写，避免三元运算符吞掉前两项
        base_cost = agent["params"]["physical"].get("stamina_decay_rate", 2.0) * 0.4
        smoke_cost = smoke * 1.5 if smoke > 0.3 else 0.0
        scost = base_cost + density * 0.6 + smoke_cost
        agent["stamina"] -= scost
        agent["health"] = max(0.0, agent["health"])
        agent["stamina"] = max(0.0, agent["stamina"])

        resist = self._stress_resistance(agent)
        agent["panic_level"] = min(1.0, max(0.0,
                                            agent["panic_level"] + density * 0.1 + smoke * 0.3 - resist * 0.05))
        if agent["health"] <= 0:
            agent["status"] = "Dead"
            return False
        if agent["stamina"] <= 0:
            agent["status"] = "Exhausted"
            return False
        return True

    def _stress_resistance(self, agent):
        """Return the configured value without an undocumented type bonus."""
        return float(
            agent["params"]["psychology"].get("stress_resistance", 0.5)
        )

    def get_observation(self, agent):
        curr = agent["current_node"]
        bias = agent["params"]["perception"]["discovery_bias"]
        paths, seen = [], set()
        known = agent.setdefault("known_connections", {})

        def recent_flow(target):
            for row in reversed(self.edge_step_log):
                row_step = int(row.get("step", -1))
                if row_step < self.current_step - 1:
                    break
                if (row_step == self.current_step - 1
                        and row.get("source") == curr
                        and row.get("target") == target):
                    return int(row.get("accepted", 0))
            return 0

        def describe(edge, source):
            tid = edge["target"]
            node = self.nodes[tid]
            risk = node.get("risk_level", 0)
            smoke = node.get("smoke_density", 0)
            noise = agent["params"]["perception"].get("noise", 0.0)
            ar = risk
            if source == "direct" and noise > 0 and self.rng.random() < noise:
                ar = max(0.0, min(1.0, risk + self.rng.choice([-0.25, 0.25])))
            density = node["current_count"] / node.get("area", 60.0)
            perceived_smoke = max(0.0, min(1.0, smoke + (ar - risk) * 0.9))
            static_hint = (
                static_cue_text(node) if source == "direct"
                else "凭空间记忆辨认相邻门洞" if source == "memory"
                else "沿墙摸索到相邻门洞"
            )
            return {
                "target_name": node.get("name", tid), "target_id": tid,
                "air_condition": smoke_state(perceived_smoke, node.get("status", "Open")),
                "crowd_feeling": density_to_sense(density),
                "static_hint": static_hint, "env_hint": static_hint,
                "event_hint": node.get("_event_desc", "") if source == 'direct' else '',
                "passable": node.get("status", "Open") not in ("Blocked", "Deadly"),
                "_risk": risk,
                "_is_exit": node.get("type", "").lower() in ("exit", "stairs") or tid in ("N11",),
                "_is_dead_end": node.get("is_dead_end", False),
                "_status": node.get("status", "Open"), "_dist": edge["dist"],
                "_via": edge.get("_via"), "_crowd_count": node["current_count"],
                "_recent_flow": recent_flow(tid), "_perception_source": source,
            }
        for edge in self.adj.get(curr, []):
            tid = edge["target"]
            if tid in seen:
                continue
            seen.add(tid)
            node = self.nodes.get(tid)
            if not node:
                continue
            risk = node.get("risk_level", 0)
            smoke = node.get("smoke_density", 0)
            low = smoke > 0.5
            dp = bias.get("low_visibility" if low else "high_visibility", 0.8)
            dp = max(0.0, min(1.0, float(dp)))
            if self.rng.random() > dp:
                continue
            paths.append(describe(edge, "direct"))
            known.setdefault(curr, [])
            if tid not in known[curr]:
                known[curr].append(tid)
                known[curr].sort()

        observed_ids = {path['target_id'] for path in paths}
        for edge in self.adj.get(curr, []):
            tid = edge['target']
            if tid in known.get(curr, []) and tid not in observed_ids:
                paths.append(describe(edge, 'memory'))
                observed_ids.add(tid)

        if not any(path["passable"] for path in paths):
            passable_edges = [
                edge for edge in self.adj.get(curr, [])
                if self.nodes.get(edge["target"], {}).get("status", "Open")
                not in ("Blocked", "Deadly")
            ]
            remembered = [
                edge for edge in passable_edges
                if edge["target"] in known.get(curr, [])
            ]
            fallback_edges = remembered or passable_edges
            if fallback_edges:
                edge = self.rng.choice(sorted(fallback_edges, key=lambda item: str(item["target"])))
                paths.append(describe(edge, "memory" if remembered else "tactile"))
        return paths

    # ── 决策入口 ──
    def _global_policy_context(self, agent):
        passable_nodes = {
            node_id
            for node_id, node in self.nodes.items()
            if node.get("status", "Open") not in ("Blocked", "Deadly")
        }
        passable_nodes.add(agent["current_node"])
        exits = [
            node_id
            for node_id, node in self.nodes.items()
            if node.get("type", "").lower() in ("exit", "stairs")
        ]
        node_risk = {
            node_id: float(node.get("risk_level", 0.0))
            for node_id, node in self.nodes.items()
        }
        occupancy_ratio = {
            node_id: (
                float(node.get("current_count", 0))
                / max(1.0, float(node.get("capacity", 60)))
            )
            for node_id, node in self.nodes.items()
        }
        return {
            "graph": self.G,
            "current_node": agent["current_node"],
            "exits": exits,
            "passable_nodes": passable_nodes,
            "node_risk": node_risk,
            "occupancy_ratio": occupancy_ratio,
        }

    def _apply_stress_modulation(self, agent, paths, step=None):
        """Apply seeded, declared high-panic effects before LLM deliberation."""
        available = list(paths)
        threshold = float(
            agent["params"]["psychology"].get("panic_threshold", 0.75)
        )
        panic = max(0.0, min(1.0, float(agent.get("panic_level", 0.0))))
        denominator = max(1e-9, 1.0 - threshold)
        stress = max(0.0, min(1.0, (panic - threshold) / denominator))
        meta = {
            "stress_level": round(stress, 6),
            "exit_cue_masked": False,
            "behavior_override": "",
        }
        if not available or stress <= 0.0:
            return available, None, meta

        behavior = agent["params"]["psychology"].get("panic_behavior", {})
        ignore_probability = max(
            0.0,
            min(1.0, float(behavior.get("ignore_exit_prob", 0.0)) * stress),
        )
        if self.rng.random() < ignore_probability:
            non_exits = [path for path in available if not path.get("_is_exit", False)]
            if non_exits:
                available = non_exits
                meta["exit_cue_masked"] = True

        follow_probability = max(
            0.0,
            min(1.0, float(behavior.get("follow_crowd_bias", 0.0)) * stress),
        )
        recent_flows = [int(path.get("_recent_flow", 0)) for path in available]
        has_crowd_gradient = bool(recent_flows) and max(recent_flows) > 0
        if has_crowd_gradient and self.rng.random() < follow_probability:
            target = max(
                available,
                key=lambda path: (
                    int(path.get("_recent_flow", 0)),
                    str(path.get("target_id", "")),
                ),
            )
            thought = f"高压力下跟随较明显的人群流向→{target['target_name']}"
            decision = (
                {"target_node": target["target_id"]},
                "Panic_Crowd_Override",
                thought,
                "",
            )
            meta["behavior_override"] = "crowd_follow"
            if step is not None:
                self._record_cot(
                    step,
                    agent,
                    decision[1],
                    target["target_id"],
                    thought,
                    "",
                    len(available),
                )
            return available, decision, meta

        mistake_probability = max(
            0.0,
            min(1.0, float(behavior.get("mistake_prob", 0.0)) * stress),
        )
        if self.rng.random() < mistake_probability:
            target = self.rng.choice(available)
            thought = f"高压力扰动导致非审慎选择→{target['target_name']}"
            decision = (
                {"target_node": target["target_id"]},
                "Panic_Error_Override",
                thought,
                "",
            )
            meta["behavior_override"] = "action_error"
            if step is not None:
                self._record_cot(
                    step,
                    agent,
                    decision[1],
                    target["target_id"],
                    thought,
                    "",
                    len(available),
                )
            return available, decision, meta

        return available, None, meta

    def decide(self, agent, paths, step, use_mock=None,
               baseline_mode=False, random_mode=False, policy_id=None):
        selected_policy = policy_id or self.policy_id
        if self.run_config is None:
            if random_mode:
                selected_policy = "Random"
            elif baseline_mode:
                selected_policy = "Local_Rule"
            elif use_mock:
                selected_policy = "Mock_Heterogeneous"

        if selected_policy == "Global_ShortestPath":
            result = GlobalShortestPathPolicy().decide(
                self._global_policy_context(agent)
            )
            thought = result.brief_justification
            self._record_cot(step, agent, selected_policy, result.target_id,
                             thought, "", len(paths))
            return ({"target_node": result.target_id} if result.target_id else None,
                    selected_policy, thought, "")
        if selected_policy == "RiskAware_Dijkstra":
            risk_weight = getattr(self.run_config, "risk_weight", 6.0)
            crowd_weight = getattr(self.run_config, "crowd_weight", 2.0)
            result = RiskAwareDijkstraPolicy(risk_weight, crowd_weight).decide(
                self._global_policy_context(agent)
            )
            thought = result.brief_justification
            self._record_cot(step, agent, selected_policy, result.target_id,
                             thought, "", len(paths))
            return ({"target_node": result.target_id} if result.target_id else None,
                    selected_policy, thought, "")

        valid = [p for p in paths if p["passable"]]
        if not valid:
            return None, "Trapped", "所有路径封闭，被困", ""
        if selected_policy == "Random":
            thought, target = self._random_decision(agent, valid)
            self._record_cot(step, agent, "Random", target, thought, "", len(valid))
            return {"target_node": target}, "Random", thought, ""

        if selected_policy == "Local_Rule":
            valid, override, _ = self._apply_stress_modulation(agent, valid, step=step)
            if override is not None:
                return override

        if selected_policy == "Local_Rule":
            thought, target = self._baseline_rule_decision(agent, valid)
            self._record_cot(step, agent, "Local_Rule", target, thought, "", len(valid))
            return {"target_node": target}, "Local_Rule", thought, ""

        if selected_policy == "Mock_Heterogeneous":
            thought, target = self._mock_decision(agent, valid)
            self._record_cot(step, agent, "Mock_Heterogeneous", target, thought, "", len(valid))
            return {"target_node": target}, "Mock_Heterogeneous", thought, ""

        if not agent["params"]["behavior"].get("can_backtrack", True):
            prev_nid = agent["history"][-2] if len(agent["history"]) > 1 else None
            if prev_nid:
                nb = [p for p in valid if p["target_id"] != prev_nid]
                valid = nb if nb else valid

        if selected_policy == "LLM_Agent" and self.api_key and not self.llm_disabled:
            return self._call_llm(agent, valid, step)

        thought, target = self._rule_decision(agent, valid)
        self._record_cot(step, agent, "Local_Rule_Fallback", target, thought, "", len(valid))
        return {"target_node": target}, "Local_Rule_Fallback", thought, ""

    def _mock_decision(self, agent, paths):
        if not paths:
            return "❓ 无路可走", None

        t = agent["type"]
        panic = agent["panic_level"]
        pb = agent["params"]["psychology"].get("panic_behavior", {})
        pt = agent["params"]["psychology"].get("panic_threshold", 0.75)

        TYPE_PARAMS = {
            "Cognitive":  {"mistake_mult": 0.4, "ignore_mult": 0.3, "exit_recog": 0.95},
            "Perceptual": {"mistake_mult": 0.8, "ignore_mult": 0.6, "exit_recog": 0.70},
            "Follower":   {"mistake_mult": 1.3, "ignore_mult": 1.0, "exit_recog": 0.35},
        }
        tp = TYPE_PARAMS.get(t, TYPE_PARAMS["Follower"])

        mistake_prob = pb.get("mistake_prob", 0.3) * panic * tp["mistake_mult"]
        ignore_exit  = pb.get("ignore_exit_prob", 0.2) * panic * tp["ignore_mult"]
        follow_crowd = pb.get("follow_crowd_bias", 0.3) * panic if 0.4 < panic < pt else 0.0
        can_backtrack = agent["params"]["behavior"].get("can_backtrack", True)
        prev = agent["history"][-2] if len(agent["history"]) > 1 else None

        if not can_backtrack and prev is not None:
            forward = [p for p in paths if p["target_id"] != prev] or paths
        else:
            forward = paths

        safe = (
            [p for p in forward
             if not p.get("_is_dead_end", False) and p.get("_risk", 1.0) < 0.5]
            or forward
        )

        EXIT_NAME_KEYS = ["出口", "🚪", "corridor", "EXIT", "exit", "紧急通道"]
        EXIT_HINT_KEYS = ["EXIT", "紧急通道标识", "指示灯", "透光", "出口", "应急"]

        def _is_exit(p):
            if p.get("_is_exit", False):
                return True
            if any(k in p.get("target_name", "") for k in EXIT_NAME_KEYS):
                return True
            if any(k in p.get("env_hint", "") for k in EXIT_HINT_KEYS):
                return True
            return False

        all_exits  = [p for p in paths if _is_exit(p)]
        exit_hints = [p for p in all_exits if self.rng.random() < tp["exit_recog"]]

        visible_flow = max(
            (int(path.get("_recent_flow", 0)) for path in paths),
            default=0,
        )
        if visible_flow > 0 and follow_crowd > 0 and self.rng.random() < follow_crowd:
            crowded = sorted(paths, key=lambda p: -p.get("_recent_flow", 0))
            if crowded:
                c = crowded[0]
                return f"😰 慌乱跟人→{c['target_name']}", c["target_id"]

        if exit_hints and self.rng.random() > ignore_exit:
            if self.rng.random() > mistake_prob:
                c = min(exit_hints, key=lambda p: p.get("_risk", 1.0))
                return f"🏃 发现出路→{c['target_name']}", c["target_id"]
            else:
                wrong = [p for p in forward if p not in exit_hints] or forward
                c = self.rng.choice(wrong)
                return f"😰 慌乱走错→{c['target_name']}", c["target_id"]

        if t == "Cognitive":
            history = agent["history"]
            is_looping = (len(history) >= 4 and
                          history[-1] == history[-3] and
                          history[-2] == history[-4])
            if is_looping:
                candidates = [p for p in forward
                              if p["target_id"] != agent["history"][-2]] or forward
                c = self.rng.choice(candidates)
                return f"🧠 打破僵局→{c['target_name']}", c["target_id"]
            sp = sorted(safe, key=lambda p: p.get("_risk", 1.0))
            tn = max(max(1, len(sp) // 2), int(len(sp) * (0.2 + panic * 0.4)))
            c = self.rng.choice(sp[:tn])
            return f"🧠 理性选择→{c['target_name']}", c["target_id"]

        elif t == "Perceptual":
            VISUAL_KEYS = ["廊", "门", "梯", "灯", "亮", "指示", "标识"]
            bright = [p for p in safe
                      if any(k in p.get("env_hint", "") for k in VISUAL_KEYS)]
            c = (self.rng.choice(bright)
                 if bright and self.rng.random() > 0.3
                 else self.rng.choice(safe))
            return f"👁️ 视觉吸引→{c['target_name']}", c["target_id"]

        else:  # Follower
            crowded = sorted(forward, key=lambda p: -p.get("_crowd_count", 0))
            c = crowded[0] if crowded else self.rng.choice(forward)
            return f"🐑 跟随人群→{c['target_name']}", c["target_id"]

    def _rule_decision(self, agent, paths, decision_rng=None):
        decision_rng = decision_rng or self.rng
        best, bs = paths[0], -999
        for p in paths:
            if p["_is_dead_end"]:
                continue
            s = ((1 - p["_risk"]) * 10 - p["_dist"] * 0.3
                 + (20 if p["_is_exit"] else 0)
                 + decision_rng.uniform(-1, 1) * 2)
            if s > bs:
                bs, best = s, p
        return f"规则决策→{best['target_name']}", best["target_id"]

    def _random_decision(self, agent, paths):
        """完全随机游走：从可通行路径中均匀随机选择，不带任何偏好。"""
        if not paths:
            return "❓ 无路可走", None
        prev = agent["history"][-2] if len(agent["history"]) > 1 else None
        can_backtrack = agent["params"]["behavior"].get("can_backtrack", True)
        if not can_backtrack and prev is not None:
            forward = [p for p in paths if p["target_id"] != prev] or paths
        else:
            forward = paths
        c = self.rng.choice(forward)
        return f"🎲 随机游走→{c['target_name']}", c["target_id"]

    def _baseline_rule_decision(self, agent, paths):
        agent_type = agent["type"]
        panic = agent["panic_level"]

        if agent_type == "Cognitive":
            valid = [p for p in paths if not p.get("_is_dead_end", False)]
        elif agent_type == "Perceptual":
            valid = [p for p in paths
                     if not p.get("_is_dead_end", False) or self.rng.random() < 0.5]
        else:
            valid = list(paths)
        if not valid:
            valid = list(paths)

        EXIT_CUES = ["EXIT", "紧急通道标识", "指示灯", "透光", "脚步",
                     "出口", "🚪", "紧急通道", "安全门"]
        EXIT_RECOG_RATE = {
            "Cognitive":  0.55,
            "Perceptual": 0.65,
            "Follower":   0.15,
        }

        def air_to_perceived_risk(air_cond: str) -> float:
            if any(k in air_cond for k in ("浓烟", "危险", "致命", "Deadly")):
                return self.rng.uniform(0.70, 1.00)
            elif any(k in air_cond for k in ("烟", "刺激", "轻微", "Smoky")):
                return self.rng.uniform(0.30, 0.70)
            else:
                return self.rng.uniform(0.00, 0.30)

        best, best_score = valid[0], -999.0
        best_is_recog_exit = False

        for p in valid:
            perceived_risk = air_to_perceived_risk(p.get("air_condition", ""))
            safety = (1.0 - perceived_risk) * 10.0

            has_exit_cue = (
                any(k in p.get("env_hint", "")    for k in EXIT_CUES) or
                any(k in p.get("target_name", "") for k in EXIT_CUES)
            )
            recog_rate     = EXIT_RECOG_RATE[agent_type] * max(0.0, 1.0 - panic)
            recognized_exit = has_exit_cue and (self.rng.random() < recog_rate)
            exit_bonus = 3.5 if recognized_exit else 0.0

            crowd = p.get("crowd_feeling", "")

            if agent_type == "Cognitive":
                dist_penalty = p["_dist"] * 0.5
                extra_exit   = 0.5 if recognized_exit else 0.0
                crowd_effect = 0.0
                noise        = self.rng.uniform(-2.5, 2.5)
            elif agent_type == "Perceptual":
                dist_penalty = p["_dist"] * 0.3
                extra_exit   = 0.0
                crowd_effect = -2.0 if "拥挤" in crowd else 1.0
                noise        = self.rng.uniform(-2.5, 2.5)
            else:
                dist_penalty = p["_dist"] * 0.2
                extra_exit   = 0.0
                crowd_effect = 1.5 if "拥挤" in crowd else -0.5
                noise        = self.rng.uniform(-3.0, 3.0)

            panic_penalty = p["_dist"] * panic * 0.5

            score = (safety + exit_bonus + extra_exit + crowd_effect
                     - dist_penalty - panic_penalty + noise)

            if score > best_score:
                best_score = score
                best = p
                best_is_recog_exit = recognized_exit

        if best_is_recog_exit:
            thought = f"📋 规则识别出口→{best['target_name']}"
        elif panic > 0.6:
            thought = f"😰 规则受恐慌干扰→{best['target_name']}"
        else:
            thought = f"📋 规则评估最优→{best['target_name']}"

        return thought, best["target_id"]


    def _build_prompt(self, agent, paths, step, blocked_paths=None):
        current_node = self.nodes.get(agent["current_node"], {})
        curr_name = current_node.get("name", "未知位置")
        step_seconds = int(
            getattr(self.run_config, "step_seconds", STEP_SECONDS)
        )
        elapsed = step * step_seconds
        ml = agent["params"]["memory"].get("memory_prompt_length", 2)
        rh = agent["history"][-(ml + 1):]
        hn = [self.nodes.get(n, {}).get("name", n) for n in rh]
        prev_name = hn[-2] if len(hn) >= 2 else "无（刚出发）"
        if len(hn) >= 3:
            mem = " → ".join(hn[:-1]) + f" → 【{hn[-1]}（当前）】"
        elif len(hn) == 2:
            mem = f"{hn[0]} → 【{hn[1]}（当前）】"
        else:
            mem = f"【{hn[0]}（刚出发）】"
        bs = body_state(agent["health"], agent["stamina"])
        ms = panic_state(agent["panic_level"])
        current_density = (
            float(current_node.get("current_count", 0))
            / max(1.0, float(current_node.get("area", 60.0)))
        )
        current_air = smoke_state(
            current_node.get("smoke_density", 0.0),
            current_node.get("status", "Open"),
        )
        current_crowd = density_to_sense(current_density)
        current_cues = static_cue_text(current_node)
        pd2 = []
        for p in paths:
            evt = f"⚠️{p['event_hint']} " if p.get("event_hint") else ""
            pd2.append(
                f"  - 前往【{p['target_name']}】：{p['air_condition']}，"
                f"人群{p['crowd_feeling']}，"
                f"上一时步从当前位置沿此方向通过 {int(p.get('_recent_flow', 0))} 人，"
                f"空间线索：{p.get('static_hint', p.get('env_hint', ''))}。{evt}")

        blocked_paths = list(blocked_paths or [])
        blocked_names = [p["target_name"] for p in blocked_paths]
        blocked_hint = (
            f"⛔ 已观察到但无法选择的封堵方向：{'、'.join(blocked_names)}\n"
            if blocked_names else ""
        )
        guidance = archetype_guidance(agent.get("type", ""))
        return f"""=== 紧急疏散 | 火灾已持续约 {elapsed} 秒 ===
【你的状态】
身体状况: {bs}
精神状态: {ms}
近期路径: {mem}

【当前位置环境】
当前位置: {curr_name}
空气状况: {current_air}
人群状况: {current_crowd}
空间线索: {current_cues}

{blocked_hint}【你能感知到的可通行方向】（从中选择一个方向）:
{chr(10).join(pd2)}

【决策约束】:
1. 只能选择上面列出的可通行方向。
2. 仅依据所列局部感知与空间记忆，不要假定自己知道完整地图；记得门洞不代表知道门外完整环境。
3. 你的行为倾向：{guidance}
4. 上一个位置是 {prev_name}；是否折返取决于当前可见线索。

【简短决策摘要的写法】：
用第一人称的一两句自然语言，结合对这次选择真正有影响的观察、身体和精神状态、
当前环境及近期路径，说明准备往哪里走。突出相关线索，不要逐项罗列四个标题，
不要机械重复身份或套用固定开头；相同证据可以产生相似摘要。
只能使用输入中的事实；没有记忆就不编造经历，看不到门外就不声称知道门外情况。
这是行动前的简短理由，不能声称已经抵达目标或已经通过排队。

请严格输出JSON（不带markdown符号，不增加其他字段）:
{{"target_id": "节点ID", "brief_justification": "简短可审计理由（100字内）"}}"""

    def _call_llm(self, agent, paths, step, blocked_paths=None):
        """Request an auditable action; never request or store hidden reasoning."""
        prompt = self._build_prompt(
            agent,
            paths,
            step,
            blocked_paths=blocked_paths,
        )
        allowed = ", ".join(
            f"{path['target_id']}={path['target_name']}" for path in paths
        )
        system_content = (
            f"{agent.get('role_description', '')}\n"
            "你正在建筑火灾中疏散，只能使用给定的局部观测。"
            "选择一个可通行目标，不要输出思维链。"
            "target_id 必须填写“允许目标”中等号左侧的节点 ID（如 N05），不能填写房间名。"
            "严格输出 JSON："
            '{"target_id":"节点ID","brief_justification":"简短可审计理由"}。'
        )
        base_messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"{prompt}\n允许目标：{allowed}"},
        ]
        messages = base_messages

        result = None
        resolved = None
        normalization = None
        for attempt in range(1, 4):
            feedback_used = messages is not base_messages
            started = time.time()
            self._emit('api.started', step=step, agent_id=agent['id'],
                       attempt=attempt, provider=self.api_provider, model=self.api_model)
            try:
                result = call_llm(
                    self.api_provider,
                    self.api_key,
                    self.api_model,
                    messages,
                    self.session if self.llm_concurrency <= 1 else None,
                    temperature=self.temperature,
                    reasoning_effort=self.reasoning_effort,
                )
            except Exception as exc:
                result = {
                    "reasoning": "", "answer": "", "usage": {},
                    "error": str(exc)[:200], "error_type": "transport",
                    "retryable": True,
                }
            usage = result.get("usage", {}) or {}
            transport_success = not bool(result.get("error"))
            if transport_success:
                # Count consumed tokens even if the final answer is unusable.
                with self._audit_lock:
                    self.token_usage["calls"] += 1
                    self.token_usage["prompt"] += usage.get("prompt_tokens", 0)
                    self.token_usage["completion"] += usage.get("completion_tokens", 0)
                output_error = None
                content = {}
                resolved, normalization = None, None
                if result.get("finish_reason") == "length":
                    output_error = "output_truncated"
                else:
                    try:
                        answer = result.get("answer", "")
                        content = json.loads(answer.replace("```json", "").replace("```", "").strip())
                        if not isinstance(content, dict):
                            output_error = "invalid_json"
                    except (TypeError, AttributeError, json.JSONDecodeError):
                        output_error = "invalid_json"
                    if output_error is None:
                        resolved, normalization = resolve_llm_target(content, paths)
                        if resolved is None:
                            output_error = "invalid_target"
                    if output_error is None and not isinstance(content.get("brief_justification"), str):
                        output_error = "invalid_summary"
                if output_error:
                    result = dict(result, error=output_error, error_type=output_error, retryable=True)
                    # The next attempt sees its own answer and a protocol correction.
                    previous = result.get("answer", "")
                    messages = base_messages + (
                        [{"role": "assistant", "content": previous}]
                        if isinstance(previous, str) and previous.strip() else []
                    ) + [{"role": "user", "content": llm_retry_feedback(
                        output_error, previous, content, allowed)}]
            self._emit('api.finished', step=step, agent_id=agent['id'],
                       attempt=attempt, success=not bool(result.get('error')),
                       transport_success=transport_success,
                       finish_reason=result.get('finish_reason'),
                       error_type=result.get('error_type'),
                       latency_ms=int((time.time() - started) * 1000), usage=usage)
            self.llm_call_log.append({
                "step": step,
                "agent_id": agent["id"],
                "agent_type": agent["type"],
                "model": result.get("model") or self.api_model,
                "attempt": attempt,
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get(
                    "total_tokens",
                    usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
                ),
                "latency_ms": int((time.time() - started) * 1000),
                "success": not bool(result.get("error")),
                "transport_success": transport_success,
                "finish_reason": result.get("finish_reason"),
                "request_mode": result.get("request_mode"),
                "response_text": result.get("answer", ""),
                "error_type": result.get("error_type"),
                "error_msg": str(result.get("error") or "")[:200],
                "target_normalization": (normalization or "") if not result.get("error") else "",
                "feedback_retry": bool(feedback_used),
            })
            if not result.get("error"):
                break
            if not result.get("retryable", False):
                self.valid_run = False
                self.invalid_reason = result.get("error_type") or "fatal_llm_error"
                self.llm_disabled = True
                break

        if result is None or result.get("error"):
            thought, target = self._llm_fallback(agent, paths, step)
            error_text = str((result or {}).get("error") or "unknown LLM error")
            self._record_cot(
                step, agent, "Rule_Fallback", target,
                thought, "", len(paths), prompt, error_text,
            )
            return {"target_node": target}, "Rule_Fallback", thought, ""

        try:
            answer = result.get("answer", "")
            content = json.loads(
                (answer if isinstance(answer, str) else "").replace("```json", "").replace("```", "").strip()
            )
        except (TypeError, json.JSONDecodeError):
            content = {}
        if not isinstance(content, dict):
            content = {}
        matched, normalization = resolve_llm_target(content, paths)
        if matched is None:
            thought, target = self._llm_fallback(agent, paths, step)
            self._record_cot(
                step, agent, "Rule_Fallback", target,
                thought, "", len(paths), prompt, result.get("answer", ""),
            )
            return {"target_node": target}, "Rule_Fallback", thought, ""

        usage = result.get("usage", {}) or {}
        brief = str(content.get("brief_justification", "选择当前可行方向"))[:120]
        self._record_cot(
            step, agent, "LLM_API", matched["target_id"],
            brief, "", len(paths), prompt, result.get("answer", ""),
        )
        return {"target_node": matched["target_id"]}, "LLM_API", brief, ""

    def observable_context(self, agent):
        """Public input context, using the same sensory helpers as the prompt."""
        node = self.nodes[agent['current_node']]
        length = int(agent['params'].get('memory', {}).get('memory_prompt_length', 2))
        return {
            'state': {'body': body_state(agent['health'], agent['stamina']),
                      'panic': panic_state(agent['panic_level']),
                      'health': agent['health'], 'stamina': agent['stamina']},
            'environment': {
                'air': smoke_state(node.get('smoke_density', 0), node.get('status', 'Open')),
                'crowd': density_to_sense(node.get('current_count', 0) / max(1, node.get('area', 60))),
                'cues': static_cue_text(node)},
            'memory': list(agent['history'][-(length + 1):]),
            'memory_kind': 'recent_path',
            'known_connections': list(
                agent.get('known_connections', {}).get(agent['current_node'], [])
            ),
        }

    def _emit(self, event_type, **data):
        if self.event_sink:
            try:
                self.event_sink(event_type, data)
            except Exception as exc:
                self.observer_errors.append(type(exc).__name__)

    def _llm_fallback(self, agent, paths, step):
        # A network completion order must not consume the shared simulation RNG.
        decision_rng = random.Random(f'{self.seed}|{step}|{agent["id"]}|fallback')
        with self._audit_lock:
            self.fallback_count += 1
        return self._rule_decision(agent, paths, decision_rng)

    def _record_cot(self, step, agent, mode, target, thought,
                    reasoning, n_paths, prompt="", response=""):
        self.cot_logs.append({
            "step": step, "agent_id": agent["id"], "agent_type": agent["type"],
            "from": agent.get("current_node", ""), "to": target,
            "decision_mode": mode,
            "panic_level":   round(agent["panic_level"], 2),
            "health":        round(agent["health"], 1),
            "stamina":       round(agent["stamina"], 1),
            "visible_paths": n_paths, "chosen_target": target,
            "thought": thought, "brief_justification": thought,
            "reasoning": reasoning,
            "llm_prompt": prompt, "llm_response": response,
            "timestamp": datetime.now().isoformat()})
        agent["recent_thoughts"].append(thought)
        agent["last_thought"]    = thought
        agent["last_reasoning"]  = reasoning

    def run_step(self, use_mock=None, fire_rate=None,
                 baseline_mode=False, random_mode=False, policy_id=None):
        step = self.current_step
        if self.run_config is not None and step >= self.run_config.max_steps:
            return []

        # Change 4: 删除此处的 `import time`，顶部已导入
        _step_t0 = time.time()
        if self.sim_start_time is None:
            self.sim_start_time = _step_t0
        _pre_panic = {a['id']: a['panic_level'] for a in self.agents}

        self.update_environment_v4(step)
        self._emit('step.started', step=step)
        self.step_event_log = []
        audit_rows = {}
        for agent in self.agents:
            node = self.nodes[agent["current_node"]]
            agent.setdefault("cumulative_smoke_exposure", 0.0)
            audit_rows[agent["id"]] = {
                "step": step,
                "sim_time_s": (step + 1) * int(getattr(self.run_config, "step_seconds", STEP_SECONDS)),
                "agent_id": agent["id"],
                "agent_type": agent["type"],
                "status_before": agent["status"],
                "status_after": agent["status"],
                "from_node": agent["current_node"],
                "proposed_target": "",
                "actual_node": agent["current_node"],
                "action_result": (
                    "PENDING" if agent["status"] == "Active"
                    else f"INACTIVE_{str(agent['status']).upper()}"
                ),
                "decision_mode": "",
                "brief_justification": "",
                "visible_path_count": 0,
                "visible_targets": "",
                "decision_targets": "",
                "visible_options_json": "[]",
                "context_json": json.dumps(self.observable_context(agent), ensure_ascii=False),
                "stress_level": 0.0,
                "exit_cue_masked": False,
                "behavior_override": "",
                "origin_risk": round(float(node.get("risk_level", 0.0)), 6),
                "origin_smoke": round(float(node.get("smoke_density", 0.0)), 6),
                "max_visible_risk": "",
                "max_visible_crowd": "",
                "chosen_target_risk": "",
                "chosen_target_smoke": "",
                "chosen_target_crowd": "",
                "chosen_is_exit": "",
                "chosen_is_dead_end": "",
                "panic_before": round(float(agent["panic_level"]), 6),
                "panic_after": round(float(agent["panic_level"]), 6),
                "stamina_before": round(float(agent["stamina"]), 6),
                "stamina_after": round(float(agent["stamina"]), 6),
                "health_before": round(float(agent["health"]), 6),
                "health_after": round(float(agent["health"]), 6),
                "queue_age_before": int(agent.get("_queue_age", 0)),
                "queue_age_after": int(agent.get("_queue_age", 0)),
                "smoke_exposure_this_step": 0.0,
                "cumulative_smoke_exposure": round(
                    float(agent["cumulative_smoke_exposure"]), 6
                ),
            }
        moves = []
        decision_candidates = []
        for agent in self.agents:
            if agent["status"] != "Active":
                continue
            row = audit_rows[agent["id"]]
            exposure = float(
                self.nodes[agent["current_node"]].get("smoke_density", 0.0)
            )
            agent["cumulative_smoke_exposure"] += exposure
            row["smoke_exposure_this_step"] = round(exposure, 6)
            if not self.apply_consequences(agent):
                row["action_result"] = (
                    "DIED" if agent["status"] == "Dead" else "EXHAUSTED"
                )
                if agent["status"] == "Dead":
                    agent.setdefault("death_step", step + 1)
                elif agent["status"] == "Exhausted":
                    agent.setdefault("exhaustion_step", step + 1)
                continue
        # Consequences use the same pre-step occupancy. Decisions and capacity
        # allocation use occupancy after all simultaneous terminal transitions.
        for node in self.nodes.values():
            node['current_count'] = 0
        for agent in self.agents:
            if agent['status'] in ('Active', 'Exhausted'):
                self.nodes[agent['current_node']]['current_count'] += 1
            else:
                agent['_queue_age'] = 0
                agent['_queued_edge'] = None
        for agent in self.agents:
            if agent['status'] != 'Active':
                continue
            row = audit_rows[agent['id']]
            speed = agent["params"]["physical"].get("base_speed", 1.2)
            sr = max(0.3, agent["stamina"] / 100.0)
            if self.rng.random() > min(1.0, speed * sr):
                row["action_result"] = "STAMINA_WAIT"
                self.step_event_log.append(
                    f"[{step}] {agent['id']} 体力不足，原地等待")
                continue
            paths = self.get_observation(agent)
            row["visible_path_count"] = len(paths)
            row["visible_targets"] = "|".join(
                sorted(str(path.get("target_id", "")) for path in paths)
            )
            row["visible_options_json"] = json.dumps(
                [
                    {
                        "target_id": path.get("target_id", ""),
                        "risk": round(float(path.get("_risk", 0.0)), 6),
                        "crowd_count": int(path.get("_crowd_count", 0)),
                        "recent_flow": int(path.get("_recent_flow", 0)),
                        "perception_source": path.get("_perception_source", "direct"),
                        "status": path.get("_status", "Open"),
                        "is_exit": bool(path.get("_is_exit", False)),
                        "is_dead_end": bool(path.get("_is_dead_end", False)),
                        "passable": bool(path.get("passable", False)),
                    }
                    for path in paths
                ],
                ensure_ascii=False,
                sort_keys=True,
            )
            if paths:
                row["max_visible_risk"] = round(
                    max(float(path.get("_risk", 0.0)) for path in paths), 6
                )
                row["max_visible_crowd"] = max(
                    int(path.get("_crowd_count", 0)) for path in paths
                )
            context = self.observable_context(agent)
            row['context_json'] = json.dumps(context, ensure_ascii=False)
            self._emit('agent.observed', step=step, agent_id=agent['id'], context=context,
                       from_node=agent['current_node'],
                       options=json.loads(row['visible_options_json']))
            if not paths:
                row["action_result"] = "NO_VISIBLE_PATHS"
                self.step_event_log.append(
                    f"[{step}] {agent['id']} 感知为空，等待")
                continue
            decision_candidates.append((agent, paths))

        def register_decision(agent, paths, decision_result):
            dec, mode, thought, reasoning = decision_result
            row = audit_rows[agent["id"]]
            row["decision_mode"] = mode
            row["brief_justification"] = str(thought)[:300]
            self._emit('agent.decided', step=step, agent_id=agent['id'],
                       target=dec.get('target_node') if dec else None,
                       mode=mode, summary=str(thought)[:300])
            if dec:
                target = dec["target_node"]
                row["proposed_target"] = target
                selected = next(
                    (path for path in paths if path.get("target_id") == target),
                    None,
                )
                if selected is not None:
                    target_node = self.nodes.get(target, {})
                    row["chosen_target_risk"] = round(
                        float(selected.get("_risk", 0.0)), 6
                    )
                    row["chosen_target_smoke"] = round(
                        float(target_node.get("smoke_density", 0.0)), 6
                    )
                    row["chosen_target_crowd"] = int(
                        selected.get("_crowd_count", 0)
                    )
                    row["chosen_target_flow"] = int(selected.get("_recent_flow", 0))
                    row["chosen_perception_source"] = selected.get(
                        "_perception_source", "direct"
                    )
                    row["chosen_is_exit"] = bool(
                        selected.get("_is_exit", False)
                    )
                    row["chosen_is_dead_end"] = bool(
                        selected.get("_is_dead_end", False)
                    )
                if (
                    target in self.nodes
                    and any(edge["target"] == target
                            for edge in self.adj.get(agent["current_node"], []))
                    and self.nodes[target].get("status", "Open")
                    not in ("Blocked", "Deadly")
                ):
                    moves.append((agent, target, thought, mode, reasoning))
                elif target not in self.nodes or not any(
                    edge["target"] == target
                    for edge in self.adj.get(agent["current_node"], [])
                ):
                    row["action_result"] = "INVALID_TARGET"
                else:
                    row["action_result"] = "TARGET_BLOCKED"
            else:
                row["action_result"] = "NO_DECISION"

        selected_policy = policy_id or self.policy_id
        if self.run_config is None:
            if random_mode:
                selected_policy = "Random"
            elif baseline_mode:
                selected_policy = "Local_Rule"
            elif use_mock:
                selected_policy = "Mock_Heterogeneous"

        use_parallel_llm = (
            selected_policy == "LLM_Agent"
            and bool(self.api_key)
            and not self.llm_disabled
            and self.llm_concurrency > 1
        )
        if selected_policy == "LLM_Agent":
            llm_jobs = []
            for agent, observed_paths in decision_candidates:
                valid = [path for path in observed_paths if path["passable"]]
                blocked = [path for path in observed_paths if not path["passable"]]
                if not agent["params"]["behavior"].get("can_backtrack", True):
                    previous = (
                        agent["history"][-2]
                        if len(agent["history"]) > 1 else None
                    )
                    if previous:
                        without_backtrack = [
                            path for path in valid
                            if path["target_id"] != previous
                        ]
                        valid = without_backtrack or valid
                decision_paths, override, stress_meta = (
                    self._apply_stress_modulation(agent, valid, step=step)
                )
                row = audit_rows[agent["id"]]
                row.update(stress_meta)
                row["decision_targets"] = "|".join(
                    sorted(path["target_id"] for path in decision_paths)
                )
                if not decision_paths:
                    row["action_result"] = "NO_DECISION_OPTIONS"
                elif override is not None:
                    register_decision(agent, decision_paths, override)
                else:
                    llm_jobs.append((agent, decision_paths, blocked))

            if use_parallel_llm and llm_jobs:
                parallel_results = {}
                with ThreadPoolExecutor(
                    max_workers=min(self.llm_concurrency, len(llm_jobs))
                ) as executor:
                    futures = {
                        executor.submit(
                            self._call_llm,
                            agent,
                            paths,
                            step,
                            blocked_paths=blocked,
                        ): (agent, paths)
                        for agent, paths, blocked in llm_jobs
                    }
                    for future in as_completed(futures):
                        agent, paths = futures[future]
                        parallel_results[agent["id"]] = (
                            agent,
                            paths,
                            future.result(),
                        )
                for agent_id in sorted(parallel_results):
                    agent, paths, decision_result = parallel_results[agent_id]
                    register_decision(agent, paths, decision_result)
            else:
                for agent, paths, blocked in llm_jobs:
                    if self.api_key and not self.llm_disabled:
                        decision_result = self._call_llm(
                            agent,
                            paths,
                            step,
                            blocked_paths=blocked,
                        )
                    else:
                        decision_result = self.decide(
                            agent,
                            paths,
                            step,
                            use_mock,
                            baseline_mode,
                            random_mode,
                            policy_id=policy_id,
                        )
                    register_decision(agent, paths, decision_result)

            self.cot_logs.sort(
                key=lambda item: (
                    int(item.get("step", 0)), str(item.get("agent_id", ""))
                )
            )
            self.llm_call_log.sort(
                key=lambda item: (
                    int(item.get("step", 0)), str(item.get("agent_id", "")),
                    int(item.get("attempt", 1)),
                )
            )
        else:
            for agent, paths in decision_candidates:
                register_decision(
                    agent,
                    paths,
                    self.decide(
                        agent, paths, step, use_mock, baseline_mode,
                        random_mode, policy_id=policy_id,
                    ),
                )

        move_by_agent = {
            agent["id"]: (agent, target, thought, mode, reasoning)
            for agent, target, thought, mode, reasoning in moves
        }
        proposals = [
            {
                "agent_id": agent["id"],
                "source": agent["current_node"],
                "target": target,
                "queue_age": (
                    int(agent.get("_queue_age", 0))
                    if agent.get("_queued_edge") == (agent["current_node"], target)
                    else 0
                ),
            }
            for agent, target, _, _, _ in moves
        ]
        edge_capacities = {
            (edge["source"], edge["target"]): int(edge["capacity_per_step"])
            for edge in self.edges
        }
        resolution = resolve_moves(
            proposals,
            node_counts={
                node_id: int(node.get("current_count", 0))
                for node_id, node in self.nodes.items()
            },
            node_capacities={
                node_id: int(node.get("capacity", 60))
                for node_id, node in self.nodes.items()
            },
            edge_capacities=edge_capacities,
            seed=self.seed * 1000 + step,
        )
        accepted = set(resolution["accepted"])
        proposing_ids = {proposal["agent_id"] for proposal in proposals}
        for agent in self.agents:
            if agent["status"] == "Active" and agent["id"] not in proposing_ids:
                agent["_queue_age"] = 0
                agent["_queued_edge"] = None

        step_logs = []
        accepted_moves = []
        for agent_id in sorted(move_by_agent):
            agent, target, thought, mode, reasoning = move_by_agent[agent_id]
            previous = agent["current_node"]
            result = resolution["rejected"].get(agent_id, "Moved")
            if agent_id in accepted:
                agent["_queue_age"] = 0
                agent["_queued_edge"] = None
                agent["current_node"] = target
                agent["history"].append(target)
                known = agent.setdefault("known_connections", {})
                known.setdefault(previous, [])
                if target not in known[previous]:
                    known[previous].append(target)
                    known[previous].sort()
                if any(edge["target"] == previous for edge in self.adj.get(target, [])):
                    known.setdefault(target, [])
                    if previous not in known[target]:
                        known[target].append(previous)
                        known[target].sort()
                agent["_slot_x"] = self.rng.uniform(-0.38, 0.38)
                agent["_slot_y"] = self.rng.uniform(-0.38, 0.38)
                target_node = self.nodes[target]
                node_type = target_node.get("type", "").lower()
                if node_type == "exit" or target == "N11":
                    agent["status"] = "Escaped"
                    agent.setdefault("escape_step", step + 1)
                elif target_node.get("is_dead_end"):
                    agent["panic_level"] = min(
                        1.0, agent["panic_level"] + 0.35
                    )
                self.step_event_log.append(
                    f"[{step}] {agent_id} {previous}→{target} | {thought[:20]}"
                )
                accepted_moves.append((agent_id, previous, target))
            else:
                if result in ("EDGE_QUEUE", "NODE_FULL"):
                    queued_edge = (previous, target)
                    previous_age = (
                        int(agent.get("_queue_age", 0))
                        if agent.get("_queued_edge") == queued_edge else 0
                    )
                    agent["_queue_age"] = previous_age + 1
                    agent["_queued_edge"] = queued_edge
                else:
                    agent["_queue_age"] = 0
                    agent["_queued_edge"] = None
                self.step_event_log.append(
                    f"[{step}] {agent_id} waits at {previous}: {result}"
                )
            audit_rows[agent_id]["action_result"] = result.upper()
            audit_rows[agent_id]["actual_node"] = agent["current_node"]
            step_logs.append({
                "Step": step,
                "Agent_ID": agent_id,
                "Type": agent["type"],
                "From": previous,
                "Proposed_To": target,
                "Actual_To": agent["current_node"],
                "To": target if agent_id in accepted else previous,
                "Result": result,
                "Mode": mode,
                "Panic": round(agent["panic_level"], 2),
                "Health": round(agent["health"], 2),
                "Thought": thought,
            })

        for node in self.nodes.values():
            node["current_count"] = 0
        for agent in self.agents:
            if agent["status"] in ("Active", "Exhausted"):
                self.nodes[agent["current_node"]]["current_count"] += 1

        self.logs.extend(step_logs)

        for agent in self.agents:
            row = audit_rows[agent["id"]]
            row["status_after"] = agent["status"]
            row["actual_node"] = agent["current_node"]
            row["panic_after"] = round(float(agent["panic_level"]), 6)
            row["stamina_after"] = round(float(agent["stamina"]), 6)
            row["health_after"] = round(float(agent["health"]), 6)
            row["queue_age_after"] = int(agent.get("_queue_age", 0))
            row["cumulative_smoke_exposure"] = round(
                float(agent.get("cumulative_smoke_exposure", 0.0)), 6
            )
            row["history_length"] = len(agent.get("history", []))
            row["backtrack_count"] = max(
                0,
                len(agent.get("history", []))
                - len(set(agent.get("history", []))),
            )
        self.agent_step_log.extend(
            audit_rows[agent_id] for agent_id in sorted(audit_rows)
        )

        proposals_by_edge = {}
        for proposal in proposals:
            key = (proposal["source"], proposal["target"])
            proposals_by_edge.setdefault(key, []).append(proposal["agent_id"])
        accepted_by_edge = {}
        for agent_id, source, target in accepted_moves:
            accepted_by_edge.setdefault((source, target), []).append(agent_id)
        for edge_index, edge in enumerate(self.edges):
            key = (edge["source"], edge["target"])
            proposed_ids = proposals_by_edge.get(key, [])
            accepted_ids = accepted_by_edge.get(key, [])
            edge_queue = sum(
                1 for agent_id in proposed_ids
                if resolution["rejected"].get(agent_id) == "EDGE_QUEUE"
            )
            node_full = sum(
                1 for agent_id in proposed_ids
                if resolution["rejected"].get(agent_id) == "NODE_FULL"
            )
            capacity = int(edge.get("capacity_per_step", 0))
            self.edge_step_log.append({
                "step": step,
                "edge_index": edge_index,
                "source": edge["source"],
                "target": edge["target"],
                "capacity_per_step": capacity,
                "proposals": len(proposed_ids),
                "accepted": len(accepted_ids),
                "edge_queue": edge_queue,
                "node_full": node_full,
                "utilization": (
                    round(len(accepted_ids) / capacity, 6) if capacity else 0.0
                ),
            })

        entrants = {}
        departures = {}
        for _, source, target in accepted_moves:
            departures[source] = departures.get(source, 0) + 1
            entrants[target] = entrants.get(target, 0) + 1
        for node_id, node in sorted(self.nodes.items()):
            active_count = sum(
                1 for agent in self.agents
                if agent["status"] == "Active"
                and agent["current_node"] == node_id
            )
            exhausted_count = sum(
                1 for agent in self.agents
                if agent["status"] == "Exhausted"
                and agent["current_node"] == node_id
            )
            occupancy = active_count + exhausted_count
            area = float(node.get("area", 60.0))
            self.node_step_log.append({
                "step": step,
                "node_id": node_id,
                "node_name": node.get("name", ""),
                "node_type": node.get("type", ""),
                "status": node.get("status", "Open"),
                "risk_level": round(float(node.get("risk_level", 0.0)), 6),
                "smoke_density": round(float(node.get("smoke_density", 0.0)), 6),
                "capacity": int(node.get("capacity", 60)),
                "area": area,
                "occupancy": occupancy,
                "active_count": active_count,
                "exhausted_count": exhausted_count,
                "density": round(occupancy / area, 6) if area else 0.0,
                "entrants": entrants.get(node_id, 0),
                "departures": departures.get(node_id, 0),
                "scenario_blocked": bool(node.get("_scenario_blocked", False)),
            })
        self.current_step += 1

        ss = {'step': step}
        for t in ('Cognitive', 'Perceptual', 'Follower'):
            ta = [a for a in self.agents if a['type'] == t]
            ac = [a for a in ta if a['status'] == 'Active']
            ss[f'escaped_{t}'] = sum(1 for a in ta if a['status'] == 'Escaped')
            ss[f'dead_{t}']    = sum(1 for a in ta if a['status'] == 'Dead')
            ss[f'active_{t}']  = len(ac)
            ss[f'avg_panic_{t}'] = (round(sum(a['panic_level'] for a in ac) / len(ac), 3)
                                    if ac else 0.0)
        ss['escaped'] = sum(1 for a in self.agents if a['status'] == 'Escaped')
        ss['dead']    = sum(1 for a in self.agents if a['status'] == 'Dead')
        ss['active']  = sum(1 for a in self.agents if a['status'] == 'Active')
        ss['exhausted'] = sum(
            1 for a in self.agents if a['status'] == 'Exhausted'
        )

        _step_dur = int((time.time() - _step_t0) * 1000)
        self.sim_end_time = time.time()
        _calls_this_step = [lg for lg in getattr(self, 'llm_call_log', [])
                            if lg.get('step') == step]
        ss['duration_ms']         = _step_dur
        ss['llm_calls_this_step'] = len(_calls_this_step)
        ss['tokens_this_step']    = sum(lg.get('total_tokens', 0)
                                        for lg in _calls_this_step)

        self.step_stats.append(ss)

        if not hasattr(self, 'node_occupancy_log'):
            self.node_occupancy_log = []
        for nid, nd in self.nodes.items():
            cnt = sum(1 for a in self.agents
                      if a['status'] == 'Active' and a.get('current_node') == nid)
            if cnt > 0:
                self.node_occupancy_log.append({
                    'step':      step,
                    'node_id':   nid,
                    'node_type': nd.get('type', ''),
                    'node_name': nd.get('name', ''),
                    'count':     cnt,
                })

        if not hasattr(self, 'panic_event_log'):
            self.panic_event_log = []
        for a in self.agents:
            old_p = _pre_panic.get(a['id'], 0.0)
            new_p = a['panic_level']
            if old_p == new_p:
                continue
            for thr in (0.3, 0.5, 0.7, 0.9):
                if old_p < thr <= new_p:
                    self.panic_event_log.append({
                        'step':       step,
                        'agent_id':   a['id'],
                        'agent_type': a['type'],
                        'event':      'rise',
                        'threshold':  thr,
                        'old_panic':  round(old_p, 4),
                        'new_panic':  round(new_p, 4),
                        'node':       a.get('current_node', ''),
                    })
                elif old_p >= thr > new_p:
                    self.panic_event_log.append({
                        'step':       step,
                        'agent_id':   a['id'],
                        'agent_type': a['type'],
                        'event':      'drop',
                        'threshold':  thr,
                        'old_panic':  round(old_p, 4),
                        'new_panic':  round(new_p, 4),
                        'node':       a.get('current_node', ''),
                    })

        return step_logs

    def get_statistics(self):
        active    = sum(1 for a in self.agents if a["status"] == "Active")
        escaped   = sum(1 for a in self.agents if a["status"] == "Escaped")
        dead      = sum(1 for a in self.agents if a["status"] == "Dead")
        exhausted = sum(1 for a in self.agents if a["status"] == "Exhausted")
        avg_panic = (np.mean([a["panic_level"] for a in self.agents
                              if a["status"] == "Active"])
                     if active > 0 else 0)
        ts = {}
        for t in ("Cognitive", "Perceptual", "Follower"):
            ta = [a for a in self.agents if a["type"] == t]
            if ta:
                ts[t] = {
                    "total":    len(ta),
                    "escaped":  sum(1 for a in ta if a["status"] == "Escaped"),
                    "dead":     sum(1 for a in ta if a["status"] == "Dead"),
                    "avg_panic": round(np.mean(
                        [a["panic_level"] for a in ta]), 2)}
        return {"active": active, "escaped": escaped, "dead": dead,
                "exhausted": exhausted, "avg_panic": round(avg_panic, 2),
                "total": len(self.agents), "type_stats": ts}
