# recorder.py — 完整版（含 Section F 实验专项数据导出）

"""recorder.py — 仿真数据导出模块（实验增强版 v3）

新增 Section F：四大实验专项数据导出
  export_path_efficiency_analysis   逐agent真实路径效率（BFS最优跳数对比）
  append_exp1_mechanism_data        实验一：决策机制对比（追加行）
  export_exp2_behavior_report       实验二：类型行为差异（完整报告）
  append_exp3_fire_data             实验三：起火点敏感性（追加行）
  append_exp4_composition_data      实验四：构成比例影响（追加行）
  export_experiment_package_zip     一键打包本次实验数据包
"""

import csv
import io
import json
import math
import zipfile
import datetime
from collections import defaultdict
import numpy as np
import os
from pathlib import Path
_PRICE = {
    'gpt-4o':            (0.005,   0.015),
    'gpt-4o-mini':       (0.00015, 0.0006),
    'gpt-4-turbo':       (0.01,    0.03),
    'gpt-4':             (0.03,    0.06),
    'gpt-3.5-turbo':     (0.0005,  0.0015),
    'claude-3-opus':     (0.015,   0.075),
    'claude-3-sonnet':   (0.003,   0.015),
    'claude-3-haiku':    (0.00025, 0.00125),
    'claude-3-5-sonnet': (0.003,   0.015),
    'deepseek':          (0.00014, 0.00028),
    'qwen':              (0.0006,  0.0006),
}


def _est_cost(model: str, prompt_tok: int, comp_tok: int) -> float:
    model_l = model.lower()
    for k, (pi, po) in _PRICE.items():
        if k in model_l:
            return prompt_tok / 1000 * pi + comp_tok / 1000 * po
    return 0.0


def _to_csv(rows: list, fields: list) -> str:
    if not rows:
        return ",".join(fields) + "\n"
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _std(values: list) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1))


# ════════════════════════════════════════════════════════════════════
# SECTION A  核心仿真输出
# ════════════════════════════════════════════════════════════════════

def export_step_snapshots(eng) -> str:
    rows = getattr(eng, 'step_stats', [])
    if not rows:
        return ""
    return _to_csv(rows, list(rows[0].keys()))


_AGENT_STEP_FIELDS = [
    'step', 'sim_time_s', 'agent_id', 'agent_type',
    'status_before', 'status_after', 'from_node', 'proposed_target',
    'actual_node', 'action_result', 'decision_mode', 'brief_justification',
    'visible_path_count', 'visible_targets', 'decision_targets',
    'visible_options_json', 'context_json', 'stress_level', 'exit_cue_masked',
    'behavior_override',
    'origin_risk', 'origin_smoke', 'max_visible_risk', 'max_visible_crowd',
    'chosen_target_risk', 'chosen_target_smoke', 'chosen_target_crowd',
    'chosen_target_flow', 'chosen_perception_source',
    'chosen_is_exit', 'chosen_is_dead_end', 'panic_before', 'panic_after',
    'stamina_before', 'stamina_after', 'health_before', 'health_after',
    'smoke_exposure_this_step', 'cumulative_smoke_exposure',
    'history_length', 'backtrack_count',
    'queue_age_before', 'queue_age_after',
]

_NODE_STEP_FIELDS = [
    'step', 'node_id', 'node_name', 'node_type', 'status', 'risk_level',
    'smoke_density', 'capacity', 'area', 'occupancy', 'active_count',
    'exhausted_count', 'density', 'entrants', 'departures',
    'scenario_blocked',
]

_EDGE_STEP_FIELDS = [
    'step', 'edge_index', 'source', 'target', 'capacity_per_step',
    'proposals', 'accepted', 'edge_queue', 'node_full', 'utilization',
]


def export_agent_step_log(eng) -> str:
    """One row per agent per simulated step, including all wait outcomes."""
    return _to_csv(getattr(eng, 'agent_step_log', []), _AGENT_STEP_FIELDS)


def export_node_step_log(eng) -> str:
    """One row per node per step, including zero-occupancy nodes."""
    return _to_csv(getattr(eng, 'node_step_log', []), _NODE_STEP_FIELDS)


def export_edge_step_log(eng) -> str:
    """One row per directed edge per step, including zero-demand edges."""
    return _to_csv(getattr(eng, 'edge_step_log', []), _EDGE_STEP_FIELDS)


def export_run_metrics(eng) -> str:
    """Fixed, analysis-ready outcomes for design screening and audit plots."""
    agents = getattr(eng, 'agents', [])
    n_agents = len(agents)
    step_stats = getattr(eng, 'step_stats', [])
    agent_steps = getattr(eng, 'agent_step_log', [])
    node_steps = getattr(eng, 'node_step_log', [])
    edge_steps = getattr(eng, 'edge_step_log', [])
    run_config = getattr(eng, 'run_config', None)
    step_seconds = int(getattr(run_config, 'step_seconds', STEP_SECONDS if 'STEP_SECONDS' in globals() else 5))

    escaped_agents = [agent for agent in agents if agent.get('status') == 'Escaped']
    escape_steps = sorted(
        int(agent['escape_step']) for agent in escaped_agents
        if agent.get('escape_step') is not None
    )

    def _time_to_fraction(fraction):
        if not n_agents:
            return ''
        target = math.ceil(n_agents * fraction)
        row = next(
            (item for item in step_stats if int(item.get('escaped', 0)) >= target),
            None,
        )
        return int(row['step']) + 1 if row is not None else ''

    def _percentile(values, percentile):
        if not values:
            return ''
        return round(float(np.percentile(values, percentile)), 4)

    current_step = int(getattr(eng, 'current_step', len(step_stats)))
    active = sum(1 for agent in agents if agent.get('status') == 'Active')
    if active == 0:
        termination_reason = 'all_agents_resolved'
    elif run_config is not None and current_step >= int(run_config.max_steps):
        termination_reason = 'max_steps_reached'
    else:
        termination_reason = 'checkpoint'

    wait_results = {
        'STAMINA_WAIT', 'NO_VISIBLE_PATHS', 'EDGE_QUEUE', 'NODE_FULL',
        'TARGET_BLOCKED', 'INVALID_TARGET', 'NO_DECISION',
    }
    smoke_exposure = [
        float(agent.get('cumulative_smoke_exposure', 0.0)) for agent in agents
    ]
    backtracks = [
        max(0, len(agent.get('history', [])) - len(set(agent.get('history', []))))
        for agent in agents
    ]
    t80 = _time_to_fraction(0.80)
    t90 = _time_to_fraction(0.90)
    t95 = _time_to_fraction(0.95)
    t100 = _time_to_fraction(1.00)
    t0 = getattr(eng, 'sim_start_time', None)
    t1 = getattr(eng, 'sim_end_time', None)
    row = {
        'run_id': getattr(eng, 'run_id', ''),
        'policy_id': getattr(run_config, 'policy_id', getattr(eng, 'policy_id', '')),
        'design_id': getattr(run_config, 'design_id', ''),
        'condition_id': getattr(run_config, 'condition_id', ''),
        'seed': getattr(run_config, 'seed', getattr(eng, 'seed', '')),
        'fire_origin': getattr(run_config, 'fire_origin', getattr(eng, 'map_data', {}).get('fire_origin', '')),
        'total_agents': n_agents,
        'total_steps': current_step,
        'termination_reason': termination_reason,
        'valid_run': bool(getattr(eng, 'valid_run', True)),
        'escaped': len(escaped_agents),
        'dead': sum(1 for agent in agents if agent.get('status') == 'Dead'),
        'exhausted': sum(1 for agent in agents if agent.get('status') == 'Exhausted'),
        'active_remaining': active,
        'escape_rate': round(len(escaped_agents) / n_agents, 6) if n_agents else 0.0,
        't80_step': t80,
        't90_step': t90,
        't95_step': t95,
        'clearance_step': t100,
        't80_seconds': t80 * step_seconds if t80 != '' else '',
        't90_seconds': t90 * step_seconds if t90 != '' else '',
        't95_seconds': t95 * step_seconds if t95 != '' else '',
        'clearance_seconds': t100 * step_seconds if t100 != '' else '',
        'median_escape_step': _percentile(escape_steps, 50),
        'p95_escape_step': _percentile(escape_steps, 95),
        'mean_cumulative_smoke_exposure': (
            round(sum(smoke_exposure) / len(smoke_exposure), 6)
            if smoke_exposure else 0.0
        ),
        'p95_cumulative_smoke_exposure': _percentile(smoke_exposure, 95),
        'total_wait_events': sum(
            1 for item in agent_steps if item.get('action_result') in wait_results
        ),
        'stamina_wait_events': sum(
            1 for item in agent_steps if item.get('action_result') == 'STAMINA_WAIT'
        ),
        'edge_queue_events': sum(
            1 for item in agent_steps if item.get('action_result') == 'EDGE_QUEUE'
        ),
        'node_full_events': sum(
            1 for item in agent_steps if item.get('action_result') == 'NODE_FULL'
        ),
        'max_edge_queue': max(
            (int(item.get('edge_queue', 0)) for item in edge_steps), default=0
        ),
        'max_node_occupancy': max(
            (int(item.get('occupancy', 0)) for item in node_steps), default=0
        ),
        'max_node_density': max(
            (float(item.get('density', 0.0)) for item in node_steps), default=0.0
        ),
        'mean_backtrack_count': (
            round(sum(backtracks) / len(backtracks), 6) if backtracks else 0.0
        ),
        'wall_time_s': round(t1 - t0, 6) if t0 and t1 else 0.0,
        'llm_calls': len(getattr(eng, 'llm_call_log', [])),
        'fallback_count': int(getattr(eng, 'fallback_count', 0)),
    }
    return _to_csv([row], list(row.keys()))


def export_agent_final(eng) -> str:
    call_log = getattr(eng, 'llm_call_log', [])
    llm_agg = {}
    for lg in call_log:
        aid = lg['agent_id']
        r = llm_agg.setdefault(aid, dict(
            calls=0, prompt_tokens=0, completion_tokens=0,
            total_tokens=0, total_latency=0, cost_usd=0.0))
        r['calls']             += 1
        r['prompt_tokens']     += lg.get('prompt_tokens', 0)
        r['completion_tokens'] += lg.get('completion_tokens', 0)
        r['total_tokens']      += lg.get('total_tokens', 0)
        r['total_latency']     += lg.get('latency_ms', 0)
        r['cost_usd']          += _est_cost(lg.get('model', ''),
                                             lg.get('prompt_tokens', 0),
                                             lg.get('completion_tokens', 0))
    rows = []
    for a in eng.agents:
        hist  = a.get('history', [])
        lm    = llm_agg.get(a['id'], {})
        calls = lm.get('calls', 0)
        rows.append({
            'agent_id':             a['id'],
            'type':                 a['type'],
            'initial_node':         hist[0] if hist else '',
            'final_node':           hist[-1] if hist else '',
            'status':               a['status'],
            'final_panic':          round(float(a.get('panic_level', 0.0)), 4),
            'steps_taken':          max(0, len(hist) - 1),
            'unique_nodes_visited': len(set(hist)),
            'backtrack_count':      max(0, len(hist) - len(set(hist))),
            'llm_calls':            calls,
            'prompt_tokens':        lm.get('prompt_tokens', 0),
            'completion_tokens':    lm.get('completion_tokens', 0),
            'total_tokens':         lm.get('total_tokens', 0),
            'avg_latency_ms':       round(lm.get('total_latency', 0) / calls, 1) if calls else 0,
            'cost_usd':             round(lm.get('cost_usd', 0.0), 6),
            'path':                 '->'.join(hist[:40]),
        })
    fields = [
        'agent_id', 'type', 'initial_node', 'final_node', 'status',
        'final_panic', 'steps_taken', 'unique_nodes_visited', 'backtrack_count',
        'llm_calls', 'prompt_tokens', 'completion_tokens', 'total_tokens',
        'avg_latency_ms', 'cost_usd', 'path',
    ]
    return _to_csv(rows, fields)


def export_decision_log(eng) -> str:
    # One decision may require multiple API attempts; preserve their actual cost/usage.
    attempts = defaultdict(list)
    for call in getattr(eng, 'llm_call_log', []):
        attempts[(call.get('step'), call.get('agent_id'))].append(call)
    rows = []
    for lg in eng.cot_logs:
        calls = attempts.get((lg.get('step'), lg.get('agent_id')), [])
        if calls:
            lg = dict(lg, model=calls[-1].get('model', ''),
                      prompt_tokens=sum(c.get('prompt_tokens', 0) for c in calls),
                      completion_tokens=sum(c.get('completion_tokens', 0) for c in calls),
                      total_tokens=sum(c.get('total_tokens', 0) for c in calls),
                      latency_ms=sum(c.get('latency_ms', 0) for c in calls))
        pt = lg.get('prompt_tokens', 0)
        ct = lg.get('completion_tokens', 0)
        rows.append({
            'step':              lg.get('step', ''),
            'agent_id':          lg.get('agent_id', ''),
            'agent_type':        lg.get('agent_type', ''),
            'from_node':         lg.get('from', ''),
            'to_node':           lg.get('to', ''),
            'decision_mode':     lg.get('decision_mode', ''),
            'panic_level':       round(float(lg.get('panic_level', 0)), 4),
            'model':             lg.get('model', ''),
            'prompt_tokens':     pt,
            'completion_tokens': ct,
            'total_tokens':      lg.get('total_tokens', pt + ct),
            'latency_ms':        lg.get('latency_ms', 0),
            'cost_usd':          round(_est_cost(lg.get('model', ''), pt, ct), 6),
            'brief_justification': str(
                lg.get('brief_justification', lg.get('thought', ''))
            ).replace('\n', ' ')[:300],
            'reasoning':         str(lg.get('reasoning', '')).replace('\n', ' ')[:300],
        })
    fields = [
        'step', 'agent_id', 'agent_type', 'from_node', 'to_node',
        'decision_mode', 'panic_level', 'model',
        'prompt_tokens', 'completion_tokens', 'total_tokens',
        'latency_ms', 'cost_usd', 'brief_justification', 'reasoning',
    ]
    return _to_csv(rows, fields)


def export_movement_log(eng) -> str:
    rows = [{
        'step':     lg.get('Step', ''),
        'agent_id': lg.get('Agent_ID', ''),
        'agent_type': lg.get('Type', ''),
        'from_node':  lg.get('From', ''),
        'proposed_target': lg.get('Proposed_To', lg.get('To', '')),
        'actual_node': lg.get('Actual_To', lg.get('To', '')),
        'result':     lg.get('Result', lg.get('Status', '')),
        'mode':       lg.get('Mode', ''),
        'panic':      round(float(lg.get('Panic', 0)), 4),
        'health':     lg.get('Health', ''),
    } for lg in eng.logs]
    fields = [
        'step', 'agent_id', 'agent_type', 'from_node', 'proposed_target',
        'actual_node', 'result', 'mode', 'panic', 'health',
    ]
    return _to_csv(rows, fields)


def export_escape_paths(eng) -> str:
    rows = []
    for a in eng.agents:
        if a['status'] != 'Escaped':
            continue
        hist = a.get('history', [])
        node_types = [eng.nodes.get(n, {}).get('type', '?') for n in hist]
        rows.append({
            'agent_id':        a['id'],
            'agent_type':      a['type'],
            'steps':           max(0, len(hist) - 1),
            'unique_nodes':    len(set(hist)),
            'backtrack_count': max(0, len(hist) - len(set(hist))),
            'final_panic':     round(a['panic_level'], 4),
            'path':            '->'.join(hist),
            'node_type_seq':   '->'.join(node_types),
        })
    fields = ['agent_id', 'agent_type', 'steps', 'unique_nodes',
              'backtrack_count', 'final_panic', 'path', 'node_type_seq']
    return _to_csv(rows, fields)


def export_simulation_meta(eng, sim_config: dict = None) -> str:
    agents   = eng.agents
    escaped  = [a for a in agents if a['status'] == 'Escaped']
    dead     = [a for a in agents if a['status'] == 'Dead']
    exhausted = [a for a in agents if a['status'] == 'Exhausted']
    active = [a for a in agents if a['status'] == 'Active']
    call_log = getattr(eng, 'llm_call_log', [])
    t0, t1   = getattr(eng, 'sim_start_time', None), getattr(eng, 'sim_end_time', None)
    total_cost = sum(_est_cost(lg.get('model', ''),
                               lg.get('prompt_tokens', 0),
                               lg.get('completion_tokens', 0)) for lg in call_log)
    type_esc = {t: sum(1 for a in escaped if a['type'] == t)
                for t in ('Cognitive', 'Perceptual', 'Follower')}
    row = {
        'schema_version':        getattr(getattr(eng, 'run_config', None), 'schema_version', '4.1'),
        'run_id':               getattr(eng, 'run_id', ''),
        'timestamp':            datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_steps':          len(getattr(eng, 'step_stats', [])),
        'sim_wall_time_s':      round(t1 - t0, 3) if (t0 and t1) else 0,
        'total_agents':         len(agents),
        'escaped':              len(escaped),
        'dead':                 len(dead),
        'active_remaining':     len(active),
        'exhausted':            len(exhausted),
        'overall_escape_rate':  round(len(escaped) / len(agents), 4) if agents else 0,
        'escaped_cognitive':    type_esc['Cognitive'],
        'escaped_perceptual':   type_esc['Perceptual'],
        'escaped_follower':     type_esc['Follower'],
        'node_count':           len(eng.nodes),
        'exit_count':           sum(1 for n in eng.nodes.values() if n.get('type') == 'exit'),
        'total_llm_calls':      len(call_log),
        'total_tokens':         sum(lg.get('total_tokens', 0) for lg in call_log),
        'total_cost_usd':       round(total_cost, 6),
        'avg_llm_latency_ms':   round(sum(lg.get('latency_ms', 0) for lg in call_log)
                                      / len(call_log), 1) if call_log else 0,
    }
    run_config = getattr(eng, 'run_config', None)
    if run_config is not None:
        frozen = run_config.to_dict()
        row.update({
            'policy_id': frozen['policy_id'],
            'information_scope': getattr(eng, 'information_scope', ''),
            'design_id': frozen['design_id'],
            'condition_id': frozen['condition_id'],
            'seed': frozen['seed'],
            'fire_origin': frozen['fire_origin'],
            'max_steps': frozen['max_steps'],
            'step_seconds': frozen['step_seconds'],
            'requested_initial_distribution': json.dumps(
                frozen.get('initial_distribution'), ensure_ascii=False, sort_keys=True
            ),
        })
    row.update({
        'actual_initial_distribution': json.dumps(
            getattr(eng, 'actual_initial_distribution', {}),
            ensure_ascii=False, sort_keys=True,
        ),
        'intervention_manifest': json.dumps(
            getattr(eng, 'intervention_manifest', {}),
            ensure_ascii=False, sort_keys=True,
        ),
        'edge_semantics': 'one directed edge equals one movement step',
        'fallback_count': int(getattr(eng, 'fallback_count', 0)),
        'valid_run': bool(getattr(eng, 'valid_run', True)),
        'invalid_reason': getattr(eng, 'invalid_reason', ''),
    })
    if sim_config:
        row.update(sim_config)
    return _to_csv([row], list(row.keys()))


def _write_run_artifacts_v4(eng, output_root):
    """Write/refresh the lossless files for one run without finalising it."""
    output_root = Path(output_root)
    run_dir = output_root / getattr(eng, "run_id", "run")
    run_dir.mkdir(parents=True, exist_ok=True)

    meta_text = export_simulation_meta(eng)
    (run_dir / "simulation_meta.csv").write_text(meta_text, encoding="utf-8-sig")
    csv_artifacts = {
        "step_stats.csv": export_step_snapshots(eng),
        "agent_step.csv": export_agent_step_log(eng),
        "node_step.csv": export_node_step_log(eng),
        "edge_step.csv": export_edge_step_log(eng),
        "movement_log.csv": export_movement_log(eng),
        "decision_log.csv": export_decision_log(eng),
        "llm_call_log.csv": export_llm_call_log(eng),
        "agent_final.csv": export_agent_final(eng),
        "run_metrics.csv": export_run_metrics(eng),
    }
    for filename, content in csv_artifacts.items():
        (run_dir / filename).write_text(content, encoding="utf-8-sig")

    state_log = {
        "run_config": (
            eng.run_config.to_dict()
            if getattr(eng, "run_config", None) is not None else {}
        ),
        "intervention_manifest": getattr(eng, "intervention_manifest", {}),
        "initial_state": getattr(eng, "initial_state", {}),
        "agents_final": getattr(eng, "agents", []),
        "nodes_final": getattr(eng, "nodes", {}),
        "step_stats": getattr(eng, "step_stats", []),
        "agent_step_log": getattr(eng, "agent_step_log", []),
        "node_step_log": getattr(eng, "node_step_log", []),
        "edge_step_log": getattr(eng, "edge_step_log", []),
        "movement_log": getattr(eng, "logs", []),
        "decision_log": getattr(eng, "cot_logs", []),
        "node_occupancy_log": getattr(eng, "node_occupancy_log", []),
        "panic_event_log": getattr(eng, "panic_event_log", []),
        "llm_call_log": getattr(eng, "llm_call_log", []),
        "valid_run": getattr(eng, "valid_run", True),
        "invalid_reason": getattr(eng, "invalid_reason", ""),
    }
    (run_dir / "state_log.json").write_text(
        json.dumps(state_log, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return run_dir, meta_text


def save_checkpoint_v4(eng, output_root="results"):
    """Persist a manual/UI checkpoint without adding a final summary row."""
    run_dir, _ = _write_run_artifacts_v4(eng, output_root)
    return run_dir


def save_run_v4(eng, output_root="results"):
    """Persist one completed auditable run and append its summary once."""
    output_root = Path(output_root)
    run_dir, meta_text = _write_run_artifacts_v4(eng, output_root)

    row = next(csv.DictReader(io.StringIO(meta_text)))
    summary_path = output_root / "summary_v4.csv"
    already_saved = bool(getattr(eng, "_summary_v4_saved", False))
    if not already_saved:
        exists = summary_path.exists() and summary_path.stat().st_size > 0
        with summary_path.open("a", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row.keys()))
            if not exists:
                writer.writeheader()
            writer.writerow(row)
        eng._summary_v4_saved = True

    paper_summary_path = output_root / "paper_summary_v1.csv"
    paper_saved = bool(getattr(eng, "_paper_summary_v1_saved", False))
    if not paper_saved:
        metrics_row = next(csv.DictReader(io.StringIO(export_run_metrics(eng))))
        exists = (
            paper_summary_path.exists()
            and paper_summary_path.stat().st_size > 0
        )
        with paper_summary_path.open(
            "a", newline="", encoding="utf-8-sig"
        ) as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(metrics_row.keys())
            )
            if not exists:
                writer.writeheader()
            writer.writerow(metrics_row)
        eng._paper_summary_v1_saved = True
    return run_dir


# ════════════════════════════════════════════════════════════════════
# SECTION B  行为分析输出
# ════════════════════════════════════════════════════════════════════

def export_agent_type_comparison(eng) -> str:
    call_log = getattr(eng, 'llm_call_log', [])
    cot_log  = eng.cot_logs
    rows = []
    for t in ('Cognitive', 'Perceptual', 'Follower'):
        ta   = [a for a in eng.agents if a['type'] == t]
        esc  = [a for a in ta if a['status'] == 'Escaped']
        dead = [a for a in ta if a['status'] == 'Dead']
        n    = len(ta) or 1

        esc_steps  = [len(a['history']) - 1 for a in esc if a.get('history')]
        all_panics = [a['panic_level'] for a in ta]
        bt_counts  = [max(0, len(a['history']) - len(set(a['history'])))
                      for a in ta if a.get('history')]

        tlm   = [lg for lg in call_log if lg.get('agent_type') == t]
        tcot  = [lg for lg in cot_log  if lg.get('agent_type') == t]
        calls = len(tlm)

        mode_cnt = {}
        for lg in tcot:
            m = lg.get('decision_mode', '?')
            mode_cnt[m] = mode_cnt.get(m, 0) + 1
        dom_mode           = max(mode_cnt, key=mode_cnt.get) if mode_cnt else ''
        panic_follow_ratio = round(mode_cnt.get('Panic_Follow', 0) / len(tcot), 4) if tcot else 0

        total_tok  = sum(lg.get('total_tokens', 0) for lg in tlm)
        total_lat  = sum(lg.get('latency_ms', 0)   for lg in tlm)
        total_cost = sum(_est_cost(lg.get('model', ''),
                                   lg.get('prompt_tokens', 0),
                                   lg.get('completion_tokens', 0)) for lg in tlm)
        rows.append({
            'agent_type':             t,
            'total_agents':           len(ta),
            'escaped':                len(esc),
            'dead':                   len(dead),
            'active_remaining':       len(ta) - len(esc) - len(dead),
            'escape_rate':            round(len(esc) / n, 4),
            'avg_escape_steps':       round(sum(esc_steps) / len(esc_steps), 2) if esc_steps else 0,
            'std_escape_steps':       round(_std(esc_steps), 2),
            'min_escape_steps':       min(esc_steps) if esc_steps else 0,
            'max_escape_steps':       max(esc_steps) if esc_steps else 0,
            'avg_final_panic':        round(sum(all_panics) / n, 4),
            'std_final_panic':        round(_std(all_panics), 4),
            'avg_backtrack':          round(sum(bt_counts) / len(bt_counts), 2) if bt_counts else 0,
            'panic_follow_ratio':     panic_follow_ratio,
            'dominant_decision_mode': dom_mode,
            'llm_calls':              calls,
            'avg_tokens_per_call':    round(total_tok / calls, 1) if calls else 0,
            'avg_latency_ms':         round(total_lat / calls, 1) if calls else 0,
            'total_cost_usd':         round(total_cost, 6),
            'avg_cost_per_agent_usd': round(total_cost / n, 8),
        })
    fields = [
        'agent_type', 'total_agents', 'escaped', 'dead', 'active_remaining',
        'escape_rate', 'avg_escape_steps', 'std_escape_steps',
        'min_escape_steps', 'max_escape_steps',
        'avg_final_panic', 'std_final_panic', 'avg_backtrack',
        'panic_follow_ratio', 'dominant_decision_mode',
        'llm_calls', 'avg_tokens_per_call', 'avg_latency_ms',
        'total_cost_usd', 'avg_cost_per_agent_usd',
    ]
    return _to_csv(rows, fields)


def export_model_performance(eng) -> str:
    call_log  = getattr(eng, 'llm_call_log', [])
    agg       = {}
    lat_lists = {}
    for lg in call_log:
        m = lg.get('model', 'unknown')
        if m not in agg:
            agg[m]       = dict(model=m, calls=0, success=0, failed=0,
                                prompt_tokens=0, completion_tokens=0, total_tokens=0,
                                total_latency_ms=0, min_lat=10**9, max_lat=0, cost_usd=0.0)
            lat_lists[m] = []
        r   = agg[m]
        lat = lg.get('latency_ms', 0)
        r['calls'] += 1
        r['success' if lg.get('success', True) else 'failed'] += 1
        r['prompt_tokens']     += lg.get('prompt_tokens', 0)
        r['completion_tokens'] += lg.get('completion_tokens', 0)
        r['total_tokens']      += lg.get('total_tokens', 0)
        r['total_latency_ms']  += lat
        r['min_lat']            = min(r['min_lat'], lat)
        r['max_lat']            = max(r['max_lat'], lat)
        r['cost_usd']          += _est_cost(m, lg.get('prompt_tokens', 0),
                                              lg.get('completion_tokens', 0))
        lat_lists[m].append(lat)
    rows = []
    for m, r in sorted(agg.items()):
        c    = r['calls'] or 1
        lats = sorted(lat_lists[m])
        rows.append({
            'model':                 r['model'],
            'total_calls':           r['calls'],
            'success_calls':         r['success'],
            'failed_calls':          r['failed'],
            'success_rate':          round(r['success'] / c, 4),
            'prompt_tokens':         r['prompt_tokens'],
            'completion_tokens':     r['completion_tokens'],
            'avg_tokens_per_call':   round(r['total_tokens'] / c, 1),
            'avg_latency_ms':        round(r['total_latency_ms'] / c, 1),
            'p50_latency_ms':        lats[len(lats) // 2]          if lats else 0,
            'p95_latency_ms':        lats[int(len(lats) * 0.95)]   if lats else 0,
            'min_latency_ms':        r['min_lat'] if r['min_lat'] != 10**9 else 0,
            'max_latency_ms':        r['max_lat'],
            'total_cost_usd':        round(r['cost_usd'], 6),
            'avg_cost_per_call_usd': round(r['cost_usd'] / c, 8),
        })
    fields = [
        'model', 'total_calls', 'success_calls', 'failed_calls', 'success_rate',
        'prompt_tokens', 'completion_tokens', 'avg_tokens_per_call',
        'avg_latency_ms', 'p50_latency_ms', 'p95_latency_ms',
        'min_latency_ms', 'max_latency_ms',
        'total_cost_usd', 'avg_cost_per_call_usd',
    ]
    return _to_csv(rows, fields)


def export_panic_evolution(eng) -> str:
    agg: dict = defaultdict(list)
    for lg in eng.logs:
        step = lg.get('Step', '')
        t    = lg.get('Type', '')
        p    = lg.get('Panic', None)
        if step != '' and t and p is not None:
            agg[(int(step), t)].append(float(p))

    rows = []
    for (step, t), panics in sorted(agg.items()):
        rows.append({
            'step':       step,
            'agent_type': t,
            'n_agents':   len(panics),
            'mean_panic': round(sum(panics) / len(panics), 4),
            'std_panic':  round(_std(panics), 4),
            'min_panic':  round(min(panics), 4),
            'max_panic':  round(max(panics), 4),
        })
    fields = ['step', 'agent_type', 'n_agents',
              'mean_panic', 'std_panic', 'min_panic', 'max_panic']
    return _to_csv(rows, fields)


def export_agent_step_panic(eng) -> str:
    rows = [{
        'step':     lg.get('Step', ''),
        'agent_id': lg.get('Agent_ID', ''),
        'agent_type': lg.get('Type', ''),
        'node':       lg.get('To', ''),
        'status':     lg.get('Status', ''),
        'panic':      round(float(lg.get('Panic', 0)), 4),
        'health':     lg.get('Health', ''),
    } for lg in eng.logs]
    fields = ['step', 'agent_id', 'agent_type', 'node', 'status', 'panic', 'health']
    return _to_csv(rows, fields)


def export_panic_events(eng) -> str:
    rows = getattr(eng, 'panic_event_log', [])
    if not rows:
        return ""
    return _to_csv(rows, ['step', 'agent_id', 'agent_type', 'event',
                           'threshold', 'old_panic', 'new_panic', 'node'])


# ════════════════════════════════════════════════════════════════════
# SECTION C  空间分析输出
# ════════════════════════════════════════════════════════════════════

def export_node_occupancy(eng) -> str:
    rows = getattr(eng, 'node_occupancy_log', [])
    if not rows:
        return ""
    return _to_csv(rows, ['step', 'node_id', 'node_type', 'node_name', 'count'])


def export_node_heatmap(eng) -> str:
    occ_log = getattr(eng, 'node_occupancy_log', [])
    if not occ_log:
        return ""

    def _cap(node_id):
        return eng.nodes.get(node_id, {}).get('capacity', 5)

    agg: dict = {}
    for row in occ_log:
        nid   = row['node_id']
        count = int(row.get('count', 0))
        if nid not in agg:
            agg[nid] = {
                'node_id':           nid,
                'node_type':         row.get('node_type', ''),
                'node_name':         row.get('node_name', ''),
                'capacity':          _cap(nid),
                'total_agent_steps': 0,
                'steps_occupied':    0,
                'congestion_steps':  0,
                'max_occupancy':     0,
                '_counts':           [],
            }
        r = agg[nid]
        r['total_agent_steps'] += count
        if count > 0:
            r['steps_occupied'] += 1
        if count > r['capacity'] * 0.6:
            r['congestion_steps'] += 1
        r['max_occupancy'] = max(r['max_occupancy'], count)
        r['_counts'].append(count)

    rows = []
    for nid, r in sorted(agg.items()):
        counts      = r.pop('_counts')
        total_steps = len(counts) or 1
        rows.append({
            **r,
            'avg_occupancy':   round(sum(counts) / total_steps, 3),
            'congestion_rate': round(r['congestion_steps'] / total_steps, 4),
        })
    rows.sort(key=lambda x: x['congestion_steps'], reverse=True)
    fields = [
        'node_id', 'node_type', 'node_name', 'capacity',
        'total_agent_steps', 'steps_occupied', 'max_occupancy',
        'avg_occupancy', 'congestion_steps', 'congestion_rate',
    ]
    return _to_csv(rows, fields)


def export_bottleneck_stats(eng) -> str:
    node_stats: dict = defaultdict(lambda: {
        'total_passes':    0,
        'unique_agents':   set(),
        'dwell_events':    0,
        'total_dwell_steps': 0,
        'max_dwell_steps': 0,
    })

    for a in eng.agents:
        hist = a.get('history', [])
        if not hist:
            continue
        aid = a['id']
        i = 0
        while i < len(hist):
            node  = hist[i]
            dwell = 1
            while i + dwell < len(hist) and hist[i + dwell] == node:
                dwell += 1
            r = node_stats[node]
            r['total_passes'] += 1
            r['unique_agents'].add(aid)
            if dwell >= 2:
                r['dwell_events']      += 1
                r['total_dwell_steps'] += dwell
                r['max_dwell_steps']    = max(r['max_dwell_steps'], dwell)
            i += dwell

    rows = []
    for nid, r in node_stats.items():
        n_meta = eng.nodes.get(nid, {})
        rows.append({
            'node_id':         nid,
            'node_type':       n_meta.get('type', ''),
            'node_name':       n_meta.get('name', nid),
            'total_passes':    r['total_passes'],
            'unique_agents':   len(r['unique_agents']),
            'dwell_events':    r['dwell_events'],
            'avg_dwell_steps': round(r['total_dwell_steps'] / r['dwell_events'], 2)
                               if r['dwell_events'] else 0,
            'max_dwell_steps': r['max_dwell_steps'],
            'dwell_rate':      round(r['dwell_events'] / r['total_passes'], 4)
                               if r['total_passes'] else 0,
        })
    rows.sort(key=lambda x: x['dwell_events'], reverse=True)
    fields = [
        'node_id', 'node_type', 'node_name',
        'total_passes', 'unique_agents',
        'dwell_events', 'avg_dwell_steps', 'max_dwell_steps', 'dwell_rate',
    ]
    return _to_csv(rows, fields)


def export_node_risk_log(eng) -> str:
    rows = getattr(eng, 'node_risk_log', [])
    if not rows:
        return ""
    fields = ['step', 'node_id', 'node_name', 'risk_level', 'smoke_density', 'status']
    return _to_csv(rows, fields)


# ════════════════════════════════════════════════════════════════════
# SECTION D  跨实验多次运行对比
# ════════════════════════════════════════════════════════════════════

def append_run_to_comparison(eng, filepath: str = 'run_comparison.csv',
                              sim_config: dict = None) -> str:
    import os

    agents   = eng.agents
    escaped  = [a for a in agents if a['status'] == 'Escaped']
    call_log = getattr(eng, 'llm_call_log', [])
    t0, t1   = getattr(eng, 'sim_start_time', None), getattr(eng, 'sim_end_time', None)
    total_cost = sum(_est_cost(lg.get('model', ''),
                               lg.get('prompt_tokens', 0),
                               lg.get('completion_tokens', 0)) for lg in call_log)

    def _type_stats(t: str) -> dict:
        ta  = [a for a in agents if a['type'] == t]
        esc = [a for a in ta if a['status'] == 'Escaped']
        pv  = [a['panic_level'] for a in ta]
        bt  = [max(0, len(a['history']) - len(set(a['history'])))
               for a in ta if a.get('history')]
        tl  = t.lower()
        return {
            f'n_{tl}':              len(ta),
            f'escaped_{tl}':        len(esc),
            f'escape_rate_{tl}':    round(len(esc) / len(ta), 4) if ta else 0,
            f'avg_panic_{tl}':      round(sum(pv) / len(pv), 4)  if pv else 0,
            f'avg_backtrack_{tl}':  round(sum(bt) / len(bt), 2)  if bt else 0,
        }

    all_bt    = [max(0, len(a['history']) - len(set(a['history'])))
                 for a in agents if a.get('history')]
    esc_steps = [len(a['history']) - 1 for a in escaped if a.get('history')]

    row = {
        'run_id':              getattr(eng, 'run_id', ''),
        'timestamp':           datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_steps':         len(getattr(eng, 'step_stats', [])),
        'sim_wall_time_s':     round(t1 - t0, 3) if (t0 and t1) else 0,
        'total_agents':        len(agents),
        'escaped':             len(escaped),
        'dead':                sum(1 for a in agents if a['status'] == 'Dead'),
        'overall_escape_rate': round(len(escaped) / len(agents), 4) if agents else 0,
        'avg_escape_steps':    round(sum(esc_steps) / len(esc_steps), 2) if esc_steps else 0,
        'avg_backtrack':       round(sum(all_bt) / len(all_bt), 2) if all_bt else 0,
        **_type_stats('Cognitive'),
        **_type_stats('Perceptual'),
        **_type_stats('Follower'),
        'total_llm_calls':     len(call_log),
        'total_tokens':        sum(lg.get('total_tokens', 0) for lg in call_log),
        'avg_latency_ms':      round(sum(lg.get('latency_ms', 0) for lg in call_log)
                                     / len(call_log), 1) if call_log else 0,
        'total_cost_usd':      round(total_cost, 6),
    }
    if sim_config:
        row.update(sim_config)

    file_exists = os.path.exists(filepath)
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()), extrasaction='ignore')
        if not file_exists:
            w.writeheader()
        w.writerow(row)
    return filepath


# ════════════════════════════════════════════════════════════════════
# SECTION E  统一实验日志
# ════════════════════════════════════════════════════════════════════

def export_unified_experiment_log(eng, sim_config: dict = None) -> str:
    from config import STEP_SECONDS

    sc = sim_config or {}

    move_result = {}
    for lg in eng.logs:
        key = (int(lg.get('Step', -1)), lg.get('Agent_ID', ''))
        move_result[key] = lg.get('Result', '')

    step_agg = {int(s['step']): s for s in getattr(eng, 'step_stats', [])}

    llm_by_key = {}
    for lg in getattr(eng, 'llm_call_log', []):
        key = (int(lg['step']), lg['agent_id'])
        llm_by_key[key] = lg

    n_cog = sum(1 for a in eng.agents if a['type'] == 'Cognitive')
    n_per = sum(1 for a in eng.agents if a['type'] == 'Perceptual')
    n_fol = sum(1 for a in eng.agents if a['type'] == 'Follower')

    run_id       = getattr(eng, 'run_id', '')
    seed         = sc.get('seed', getattr(eng, 'seed', ''))
    dec_mech     = sc.get('decision_mechanism', '')
    llm_model    = sc.get('llm_model', getattr(eng, 'api_model', ''))
    llm_provider = sc.get('llm_provider', getattr(eng, 'api_provider', ''))
    fire_rate    = sc.get('fire_spread_rate', '')
    fire_origin  = eng.map_data.get('fire_origin', '')

    rows = []
    for lg in eng.cot_logs:
        step   = int(lg.get('step', 0))
        aid    = lg.get('agent_id', '')
        atype  = lg.get('agent_type', '')
        mode   = lg.get('decision_mode', '')
        chosen = lg.get('chosen_target', '')
        is_llm = (mode == 'LLM_API')

        sa   = step_agg.get(step, {})
        lc   = llm_by_key.get((step, aid), {})
        mr   = move_result.get((step, aid), '')

        node      = eng.nodes.get(chosen, {})
        node_risk = node.get('risk_level', '')
        node_smk  = node.get('smoke_density', '')

        pt = int(lc.get('prompt_tokens', 0) or 0)
        ct = int(lc.get('completion_tokens', 0) or 0)

        rows.append({
            'run_id':             run_id,
            'seed':               seed,
            'decision_mechanism': dec_mech or mode,
            'llm_model':          llm_model,
            'llm_provider':       llm_provider,
            'fire_origin':        fire_origin,
            'fire_spread_rate':   fire_rate,
            'n_cognitive':        n_cog,
            'n_perceptual':       n_per,
            'n_follower':         n_fol,
            'total_agents':       len(eng.agents),
            'step':               step,
            'elapsed_seconds':    step * STEP_SECONDS,
            'step_escaped_total': sa.get('escaped', ''),
            'step_dead_total':    sa.get('dead', ''),
            'step_active_total':  sa.get('active', ''),
            'step_escaped_cog':   sa.get('escaped_Cognitive', ''),
            'step_escaped_per':   sa.get('escaped_Perceptual', ''),
            'step_escaped_fol':   sa.get('escaped_Follower', ''),
            'step_avg_panic_cog': sa.get('avg_panic_Cognitive', ''),
            'step_avg_panic_per': sa.get('avg_panic_Perceptual', ''),
            'step_avg_panic_fol': sa.get('avg_panic_Follower', ''),
            'agent_id':           aid,
            'agent_type':         atype,
            'panic_level':        round(float(lg.get('panic_level', 0)), 4),
            'health':             round(float(lg.get('health', 100)), 1),
            'stamina':            round(float(lg.get('stamina', 100)), 1),
            'visible_paths':      lg.get('visible_paths', ''),
            'decision_mode':      mode,
            'chosen_target_id':   chosen,
            'chosen_node_name':   node.get('name', ''),
            'chosen_node_type':   node.get('type', ''),
            'chosen_node_risk':   round(float(node_risk), 4) if node_risk != '' else '',
            'chosen_node_smoke':  round(float(node_smk),  4) if node_smk  != '' else '',
            'chosen_node_status': node.get('status', ''),
            'thought':            str(lg.get('thought', '')).replace('\n', ' ')[:150],
            'move_result':        mr,
            'llm_prompt_tokens':     pt  if is_llm else '',
            'llm_completion_tokens': ct  if is_llm else '',
            'llm_total_tokens':      lc.get('total_tokens', pt + ct) if is_llm else '',
            'llm_latency_ms':        lc.get('latency_ms', '')   if is_llm else '',
            'llm_success':           lc.get('success', '')      if is_llm else '',
            'llm_error':             lc.get('error_msg', '')    if is_llm else '',
            'llm_cost_usd':          round(_est_cost(
                                         lc.get('model', ''), pt, ct), 6) if is_llm else '',
        })

    fields = [
        'run_id', 'seed', 'decision_mechanism', 'llm_model', 'llm_provider',
        'fire_origin', 'fire_spread_rate',
        'n_cognitive', 'n_perceptual', 'n_follower', 'total_agents',
        'step', 'elapsed_seconds',
        'step_escaped_total', 'step_dead_total', 'step_active_total',
        'step_escaped_cog', 'step_escaped_per', 'step_escaped_fol',
        'step_avg_panic_cog', 'step_avg_panic_per', 'step_avg_panic_fol',
        'agent_id', 'agent_type', 'panic_level', 'health', 'stamina', 'visible_paths',
        'decision_mode', 'chosen_target_id', 'chosen_node_name', 'chosen_node_type',
        'chosen_node_risk', 'chosen_node_smoke', 'chosen_node_status', 'thought',
        'move_result',
        'llm_prompt_tokens', 'llm_completion_tokens', 'llm_total_tokens',
        'llm_latency_ms', 'llm_success', 'llm_error', 'llm_cost_usd',
    ]
    return _to_csv(rows, fields)


def append_unified_log(eng, filepath: str = 'unified_experiment_log.csv',
                        sim_config: dict = None) -> str:
    import os
    content = export_unified_experiment_log(eng, sim_config)
    if not content:
        return filepath

    lines = content.splitlines(keepends=True)
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0

    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        if not file_exists:
            f.writelines(lines)
        else:
            f.writelines(lines[1:])

    return filepath


# ════════════════════════════════════════════════════════════════════
# SECTION F  四大实验专项数据导出（新增）
# ════════════════════════════════════════════════════════════════════

def export_path_efficiency_analysis(eng) -> str:
    """
    实验一/二通用：逐 agent 路径效率分析。
    path_efficiency = optimal_hops / actual_steps（仅逃生者，越接近1越好）
    optimal_hops = BFS无权最短跳数（起点 → 最近出口）
    dead_end_visits = 路径中进入 deadend 节点的次数（含N12/N15/N16）
    """
    import networkx as nx

    exit_nodes = [nid for nid, nd in eng.nodes.items()
                  if nd.get('type') == 'exit']

    rows = []
    for a in eng.agents:
        hist         = a.get('history', [])
        start        = hist[0] if hist else ''
        actual_steps = max(0, len(hist) - 1)

        # BFS最短跳数到最近出口
        min_hops     = float('inf')
        nearest_exit = ''
        for ex in exit_nodes:
            try:
                h = nx.shortest_path_length(eng.G, start, ex)
                if h < min_hops:
                    min_hops, nearest_exit = h, ex
            except Exception:
                continue

        optimal_hops = int(min_hops) if min_hops != float('inf') else -1

        if a['status'] == 'Escaped' and actual_steps > 0 and optimal_hops > 0:
            path_eff = round(min(1.0, optimal_hops / actual_steps), 4)
        else:
            path_eff = 0.0

        bt = max(0, len(hist) - len(set(hist)))
        de_visits = sum(
            1 for n in hist
            if eng.nodes.get(n, {}).get('is_dead_end', False)
            or eng.nodes.get(n, {}).get('type', '') == 'deadend'
        )

        rows.append({
            'agent_id':         a['id'],
            'agent_type':       a['type'],
            'status':           a['status'],
            'start_node':       start,
            'nearest_exit':     nearest_exit,
            'optimal_hops':     optimal_hops,
            'actual_steps':     actual_steps,
            'path_efficiency':  path_eff,
            'backtrack_count':  bt,
            'unique_nodes':     len(set(hist)),
            'dead_end_visits':  de_visits,
            'final_panic':      round(a['panic_level'], 4),
        })

    fields = [
        'agent_id', 'agent_type', 'status', 'start_node', 'nearest_exit',
        'optimal_hops', 'actual_steps', 'path_efficiency',
        'backtrack_count', 'unique_nodes', 'dead_end_visits', 'final_panic',
    ]
    return _to_csv(rows, fields)


def append_exp1_mechanism_data(eng,
                                filepath: str = 'exp1_mechanism_comparison.csv',
                                sim_config: dict = None) -> str:
    """
    实验一：决策机制对比（每次运行追加一行）。
    包含逃生率、路径效率、步数、回溯、死胡同率、首次逃出步、恐慌、LLM成本。
    建议：4种机制 × 10个种子 = 40行后做 Kruskal-Wallis 检验。
    """
    import os
    import networkx as nx

    sc      = sim_config or {}
    agents  = eng.agents
    escaped = [a for a in agents if a['status'] == 'Escaped']
    call_log = getattr(eng, 'llm_call_log', [])
    t0, t1   = getattr(eng, 'sim_start_time', None), getattr(eng, 'sim_end_time', None)
    total_cost = sum(_est_cost(lg.get('model', ''),
                               lg.get('prompt_tokens', 0),
                               lg.get('completion_tokens', 0)) for lg in call_log)

    exit_nodes = [nid for nid, nd in eng.nodes.items() if nd.get('type') == 'exit']

    eff_list, bt_esc_list, de_esc_list, esc_steps_list = [], [], [], []
    all_bt_list, all_de_list = [], []

    for a in agents:
        hist = a.get('history', [])
        if not hist:
            continue
        actual = max(0, len(hist) - 1)
        bt = max(0, len(hist) - len(set(hist)))
        de = sum(1 for n in hist
                 if eng.nodes.get(n, {}).get('is_dead_end', False)
                 or eng.nodes.get(n, {}).get('type', '') == 'deadend')
        all_bt_list.append(bt)
        all_de_list.append(de)

        if a['status'] == 'Escaped':
            esc_steps_list.append(actual)
            bt_esc_list.append(bt)
            de_esc_list.append(de)
            min_hops = float('inf')
            for ex in exit_nodes:
                try:
                    h = nx.shortest_path_length(eng.G, hist[0], ex)
                    min_hops = min(min_hops, h)
                except Exception:
                    pass
            if actual > 0 and min_hops != float('inf'):
                eff_list.append(min(1.0, min_hops / actual))

    # first_escape_step
    first_esc = -1
    for ss in getattr(eng, 'step_stats', []):
        if ss.get('escaped', 0) > 0:
            first_esc = ss['step']
            break

    # LLM 降级率
    fallback_modes = {'LLM_Error', 'LLM_ParseError', 'Rule_Fallback'}
    fallback_cnt   = sum(1 for lg in eng.cot_logs
                         if lg.get('decision_mode') in fallback_modes)
    total_dec      = len(eng.cot_logs) or 1

    # 各类型逃生率
    def _er(t):
        ta = [a for a in agents if a['type'] == t]
        return round(sum(1 for a in ta if a['status'] == 'Escaped') / len(ta), 4) if ta else 0

    row = {
        'run_id':                  getattr(eng, 'run_id', ''),
        'decision_mechanism':      sc.get('decision_mechanism', ''),
        'llm_model':               sc.get('llm_model', ''),
        'seed':                    sc.get('seed', ''),
        'fire_origin':             sc.get('scenario', eng.map_data.get('fire_origin', '')),
        'fire_spread_rate':        sc.get('fire_spread_rate', ''),
        'n_cognitive':             sc.get('n_cognitive', ''),
        'n_perceptual':            sc.get('n_perceptual', ''),
        'n_follower':              sc.get('n_follower', ''),
        'total_agents':            len(agents),
        'total_steps':             len(getattr(eng, 'step_stats', [])),
        'sim_wall_time_s':         round(t1 - t0, 3) if (t0 and t1) else 0,
        # 核心结果
        'overall_escape_rate':     round(len(escaped) / len(agents), 4) if agents else 0,
        'escaped_count':           len(escaped),
        'dead_count':              sum(1 for a in agents if a['status'] == 'Dead'),
        'active_remaining':        sum(1 for a in agents if a['status'] == 'Active'),
        'escape_rate_cognitive':   _er('Cognitive'),
        'escape_rate_perceptual':  _er('Perceptual'),
        'escape_rate_follower':    _er('Follower'),
        'first_escape_step':       first_esc,
        # 步数
        'avg_escape_steps':        round(sum(esc_steps_list)/len(esc_steps_list), 2) if esc_steps_list else 0,
        'std_escape_steps':        round(_std(esc_steps_list), 2),
        # 路径质量
        'avg_path_efficiency':     round(sum(eff_list)/len(eff_list), 4) if eff_list else 0,
        'std_path_efficiency':     round(_std(eff_list), 4),
        'avg_backtrack_escaped':   round(sum(bt_esc_list)/len(bt_esc_list), 2) if bt_esc_list else 0,
        'avg_backtrack_all':       round(sum(all_bt_list)/len(all_bt_list), 2) if all_bt_list else 0,
        'dead_end_rate_escaped':   round(sum(de_esc_list)/len(de_esc_list), 4) if de_esc_list else 0,
        'dead_end_rate_all':       round(sum(all_de_list)/len(all_de_list), 4) if all_de_list else 0,
        # 恐慌
        'avg_final_panic':         round(sum(a['panic_level'] for a in agents)/len(agents), 4) if agents else 0,
        'std_final_panic':         round(_std([a['panic_level'] for a in agents]), 4),
        # LLM 专项
        'total_llm_calls':         len(call_log),
        'llm_fallback_count':      fallback_cnt,
        'llm_fallback_rate':       round(fallback_cnt / total_dec, 4),
        'total_tokens':            sum(lg.get('total_tokens', 0) for lg in call_log),
        'avg_latency_ms':          round(sum(lg.get('latency_ms', 0) for lg in call_log)
                                         / len(call_log), 1) if call_log else 0,
        'total_cost_usd':          round(total_cost, 6),
    }

    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()), extrasaction='ignore')
        if not file_exists:
            w.writeheader()
        w.writerow(row)
    return filepath


# ── 在 append_exp1_mechanism_data 函数结束后，紧接着加入 ──────────────────

def append_exp2_behavior_data(engine, filepath, sim_config):
    """
    实验二：每次运行结束后，追加逐步×类型的恐慌时序数据
    数据来源：engine.logs（与 export_panic_evolution 一致）
    """
    sc        = sim_config or {}
    run_id    = getattr(engine, 'run_id', 'unknown')
    seed      = sc.get("seed", -1)
    mechanism = sc.get("decision_mechanism", "unknown")

    # 从 engine.logs 聚合每步×类型的恐慌
    agg = defaultdict(list)
    for lg in engine.logs:
        step = lg.get('Step', '')
        t    = lg.get('Type', '')
        p    = lg.get('Panic', None)
        if step != '' and t and p is not None:
            agg[(int(step), t)].append(float(p))

    if not agg:
        return

    # 从 engine.cot_logs 聚合决策模式
    mode_agg = defaultdict(lambda: defaultdict(int))
    for lg in engine.cot_logs:
        step = int(lg.get('step', 0))
        t    = lg.get('agent_type', '')
        mode = lg.get('decision_mode', '')
        if t and mode:
            mode_agg[(step, t)][mode] += 1

    rows = []
    for (step, agent_type), panics in sorted(agg.items()):
        modes     = mode_agg.get((step, agent_type), {})
        total_dec = sum(modes.values()) or 1
        rows.append({
            "run_id":             run_id,
            "seed":               seed,
            "decision_mechanism": mechanism,
            "step":               step,
            "agent_type":         agent_type,
            "panic_mean":         round(sum(panics) / len(panics), 4),
            "panic_std":          round(_std(panics), 4),
            "alive_count":        len(panics),
            "mode_mock":          modes.get('Mock', 0),
            "mode_panic_follow":  modes.get('Panic_Follow', 0),
            "mode_llm_api":       modes.get('LLM_API', 0),
            "mode_rule":          modes.get('Rule', 0),
            "mode_random":        modes.get('Random', 0),
        })

    fields = [
        "run_id", "seed", "decision_mechanism", "step", "agent_type",
        "panic_mean", "panic_std", "alive_count",
        "mode_mock", "mode_panic_follow", "mode_llm_api",
        "mode_rule", "mode_random",
    ]

    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        if not file_exists:
            w.writeheader()
        w.writerows(rows)


def export_exp2_behavior_report(eng) -> str:
    """
    实验二：Agent类型行为差异完整报告（单次运行全量输出）。
    每行 = agent_type × step，含恐慌统计、决策模式分布、死胡同进入次数。
    可直接用于绘制：
      - 恐慌演化曲线（mean ± std 带）
      - 决策模式随时间变化堆积图
      - 各类型死胡同进入频率折线
    """
    # 每步×类型 恐慌聚合
    panic_agg: dict = defaultdict(list)
    for lg in eng.logs:
        step = lg.get('Step', '')
        t    = lg.get('Type', '')
        p    = lg.get('Panic', None)
        if step != '' and t and p is not None:
            panic_agg[(int(step), t)].append(float(p))

    # 每步×类型 决策模式计数
    mode_agg: dict = defaultdict(lambda: defaultdict(int))
    for lg in eng.cot_logs:
        step = int(lg.get('step', 0))
        t    = lg.get('agent_type', '')
        mode = lg.get('decision_mode', '')
        if t and mode:
            mode_agg[(step, t)][mode] += 1

    # 每步×类型 死胡同进入次数
    de_agg: dict = defaultdict(int)
    for lg in eng.cot_logs:
        step   = int(lg.get('step', 0))
        t      = lg.get('agent_type', '')
        chosen = lg.get('chosen_target', '')
        nd     = eng.nodes.get(chosen, {})
        if nd.get('is_dead_end', False) or nd.get('type', '') == 'deadend':
            de_agg[(step, t)] += 1

    # 每步×类型 被blocked次数（来自 move_result）
    blocked_agg: dict = defaultdict(int)
    for lg in eng.logs:
        step = lg.get('Step', '')
        t = lg.get('Type', '')
        result = lg.get('Result', '') or lg.get('Status', '')
        if result == 'Blocked' and step != '' and t:
            blocked_agg[(int(step), t)] += 1

    all_keys = set(panic_agg.keys()) | set(mode_agg.keys())
    rows = []
    for (step, t) in sorted(all_keys):
        panics        = panic_agg.get((step, t), [])
        modes         = mode_agg.get((step, t), {})
        total_dec     = sum(modes.values()) or 1
        rows.append({
            'step':                    step,
            'agent_type':              t,
            'n_agents_active':         len(panics),
            'mean_panic':              round(sum(panics)/len(panics), 4) if panics else '',
            'std_panic':               round(_std(panics), 4) if len(panics) >= 2 else 0,
            'min_panic':               round(min(panics), 4) if panics else '',
            'max_panic':               round(max(panics), 4) if panics else '',
            'total_decisions':         total_dec if total_dec > 1 else 0,
            'mode_mock':               modes.get('Mock', 0),
            'mode_panic_follow':       modes.get('Panic_Follow', 0),
            'mode_llm_api':            modes.get('LLM_API', 0),
            'mode_baseline_rule':      modes.get('Baseline_Rule', 0),
            'mode_random':             modes.get('Random', 0),
            'mode_rule':               modes.get('Rule', 0),
            'mode_llm_error':          modes.get('LLM_Error', 0) + modes.get('Rule_Fallback', 0),
            'panic_follow_ratio':      round(modes.get('Panic_Follow', 0) / total_dec, 4),
            'dead_end_entries':        de_agg.get((step, t), 0),
            'blocked_moves':           blocked_agg.get((step, t), 0),
        })

    fields = [
        'step', 'agent_type', 'n_agents_active',
        'mean_panic', 'std_panic', 'min_panic', 'max_panic',
        'total_decisions',
        'mode_mock', 'mode_panic_follow', 'mode_llm_api',
        'mode_baseline_rule', 'mode_random', 'mode_rule', 'mode_llm_error',
        'panic_follow_ratio', 'dead_end_entries', 'blocked_moves',
    ]
    return _to_csv(rows, fields)


def append_exp3_fire_data(eng,
                           filepath: str = 'exp3_fire_sensitivity.csv',
                           sim_config: dict = None) -> str:
    """
    实验三：起火位置敏感性（每次运行追加一行）。
    遍历不同 fire_origin，固定机制+种子，每次追加。
    最终按 fire_origin 分组分析逃生率、首逃步、恐慌峰值、瓶颈节点。
    """
    import os

    sc         = sim_config or {}
    agents     = eng.agents
    escaped    = [a for a in agents if a['status'] == 'Escaped']
    step_stats = getattr(eng, 'step_stats', [])

    # 时序特征
    first_esc = -1
    half_esc  = -1
    target_half = len(agents) * 0.5
    for ss in step_stats:
        if ss.get('escaped', 0) > 0 and first_esc == -1:
            first_esc = ss['step']
        if ss.get('escaped', 0) >= target_half and half_esc == -1:
            half_esc = ss['step']

    # 各类型恐慌峰值
    def _peak(key):
        return round(max((ss.get(key, 0) or 0 for ss in step_stats), default=0), 4)

    # 瓶颈：dwell_events最多的Top3节点
    node_dwell: dict = defaultdict(int)
    for a in agents:
        hist = a.get('history', [])
        i = 0
        while i < len(hist):
            node  = hist[i]
            dwell = 1
            while i + dwell < len(hist) and hist[i + dwell] == node:
                dwell += 1
            if dwell >= 2:
                node_dwell[node] += 1
            i += dwell
    top3 = sorted(node_dwell.items(), key=lambda x: -x[1])[:3]
    bn_str = ';'.join(
        f"{n}({eng.nodes.get(n,{}).get('name',n)}):{c}" for n, c in top3
    )

    # 关键节点最大人数
    def _max_occ(nid):
        return max(
            (r.get('count', 0) for r in getattr(eng, 'node_occupancy_log', [])
             if r.get('node_id') == nid),
            default=0
        )

    # 分类型逃生率
    def _er(t):
        ta = [a for a in agents if a['type'] == t]
        return round(sum(1 for a in ta if a['status'] == 'Escaped') / len(ta), 4) if ta else 0

    fire_origin = sc.get('scenario', eng.map_data.get('fire_origin', ''))
    row = {
        'run_id':                      getattr(eng, 'run_id', ''),
        'fire_origin':                 fire_origin,
        'fire_origin_name':            eng.nodes.get(fire_origin, {}).get('name', ''),
        'fire_origin_type':            eng.nodes.get(fire_origin, {}).get('type', ''),
        'fire_spread_rate':            sc.get('fire_spread_rate', ''),
        'decision_mechanism':          sc.get('decision_mechanism', ''),
        'seed':                        sc.get('seed', ''),
        'n_cognitive':                 sc.get('n_cognitive', ''),
        'n_perceptual':                sc.get('n_perceptual', ''),
        'n_follower':                  sc.get('n_follower', ''),
        'total_agents':                len(agents),
        'total_steps':                 len(step_stats),
        # 核心结果
        'overall_escape_rate':         round(len(escaped)/len(agents), 4) if agents else 0,
        'escaped_count':               len(escaped),
        'dead_count':                  sum(1 for a in agents if a['status'] == 'Dead'),
        'active_remaining':            sum(1 for a in agents if a['status'] == 'Active'),
        'escape_rate_cognitive':       _er('Cognitive'),
        'escape_rate_perceptual':      _er('Perceptual'),
        'escape_rate_follower':        _er('Follower'),
        # 时序特征
        'first_escape_step':           first_esc,
        'step_half_escaped':           half_esc,
        # 恐慌峰值
        'peak_panic_cognitive':        _peak('avg_panic_Cognitive'),
        'peak_panic_perceptual':       _peak('avg_panic_Perceptual'),
        'peak_panic_follower':         _peak('avg_panic_Follower'),
        # 空间
        'top3_bottleneck_nodes':       bn_str,
        'max_occ_N09':                 _max_occ('N09'),
        'max_occ_N10':                 _max_occ('N10'),
        'max_occ_N11':                 _max_occ('N11'),
        'max_occ_N18':                 _max_occ('N18'),
    }

    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()), extrasaction='ignore')
        if not file_exists:
            w.writeheader()
        w.writerow(row)
    return filepath


def append_exp4_composition_data(eng,
                                  filepath: str = 'exp4_composition_comparison.csv',
                                  sim_config: dict = None) -> str:
    """
    实验四：Agent构成比例影响（每次运行追加一行）。
    固定机制+起火点+种子，遍历不同比例组合。
    crowd_config 建议传入 '10C-15P-23F' 格式标签以便分组。
    """
    import os

    sc         = sim_config or {}
    agents     = eng.agents
    escaped    = [a for a in agents if a['status'] == 'Escaped']
    step_stats = getattr(eng, 'step_stats', [])

    # 疏散进程检查点（每5步一个）
    checkpoints = {}
    for chk in [5, 10, 15, 20, 25, 30]:
        ss = next((s for s in step_stats if s['step'] == chk), None)
        checkpoints[f'escaped_at_step{chk:02d}'] = ss.get('escaped', 0) if ss else 0

    # 恐慌峰值
    def _peak(key):
        return round(max((ss.get(key, 0) or 0 for ss in step_stats), default=0), 4)

    # 分类型全指标
    def _type_row(t):
        ta  = [a for a in agents if a['type'] == t]
        esc = [a for a in ta if a['status'] == 'Escaped']
        pv  = [a['panic_level'] for a in ta]
        bt  = [max(0, len(a['history']) - len(set(a['history'])))
               for a in ta if a.get('history')]
        esc_s = [len(a['history']) - 1 for a in esc if a.get('history')]
        tl = t.lower()
        return {
            f'n_{tl}':               len(ta),
            f'escaped_{tl}':         len(esc),
            f'escape_rate_{tl}':     round(len(esc)/len(ta), 4) if ta else 0,
            f'avg_escape_steps_{tl}': round(sum(esc_s)/len(esc_s), 2) if esc_s else 0,
            f'avg_panic_{tl}':       round(sum(pv)/len(pv), 4) if pv else 0,
            f'peak_panic_{tl}':      _peak(f'avg_panic_{t}'),
            f'avg_backtrack_{tl}':   round(sum(bt)/len(bt), 2) if bt else 0,
        }

    # 关键瓶颈节点最大占用
    def _max_occ(nid):
        return max(
            (r.get('count', 0) for r in getattr(eng, 'node_occupancy_log', [])
             if r.get('node_id') == nid),
            default=0
        )

    # first_escape_step
    first_esc = -1
    for ss in step_stats:
        if ss.get('escaped', 0) > 0:
            first_esc = ss['step']
            break

    n_cog = sc.get('n_cognitive', len([a for a in agents if a['type'] == 'Cognitive']))
    n_per = sc.get('n_perceptual', len([a for a in agents if a['type'] == 'Perceptual']))
    n_fol = sc.get('n_follower',   len([a for a in agents if a['type'] == 'Follower']))
    crowd_cfg = sc.get('crowd_config', f'{n_cog}C-{n_per}P-{n_fol}F')

    row = {
        'run_id':              getattr(eng, 'run_id', ''),
        'crowd_config':        crowd_cfg,
        'decision_mechanism':  sc.get('decision_mechanism', ''),
        'fire_origin':         sc.get('scenario', eng.map_data.get('fire_origin', '')),
        'fire_spread_rate':    sc.get('fire_spread_rate', ''),
        'seed':                sc.get('seed', ''),
        'total_agents':        len(agents),
        'total_steps':         len(step_stats),
        'overall_escape_rate': round(len(escaped)/len(agents), 4) if agents else 0,
        'escaped_count':       len(escaped),
        'dead_count':          sum(1 for a in agents if a['status'] == 'Dead'),
        'first_escape_step':   first_esc,
        **_type_row('Cognitive'),
        **_type_row('Perceptual'),
        **_type_row('Follower'),
        **checkpoints,
        'max_occ_N09': _max_occ('N09'),
        'max_occ_N10': _max_occ('N10'),
        'max_occ_N11': _max_occ('N11'),
        'max_occ_N18': _max_occ('N18'),
    }

    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()), extrasaction='ignore')
        if not file_exists:
            w.writeheader()
        w.writerow(row)
    return filepath


def export_experiment_package_zip(eng, sim_config: dict = None) -> bytes:
    """
    实验数据包：打包本次仿真所有实验相关 CSV 为 ZIP。
    包含路径效率、行为报告、恐慌演化、瓶颈、热力图、逃生路径、元信息。
    """
    run_id = getattr(eng, 'run_id', 'run')
    files = {
        f'{run_id}_A_path_efficiency.csv':   export_path_efficiency_analysis(eng),
        f'{run_id}_B_exp2_behavior.csv':     export_exp2_behavior_report(eng),
        f'{run_id}_C_agent_type_cmp.csv':    export_agent_type_comparison(eng),
        f'{run_id}_D_panic_evolution.csv':   export_panic_evolution(eng),
        f'{run_id}_E_agent_step_panic.csv':  export_agent_step_panic(eng),
        f'{run_id}_F_panic_events.csv':      export_panic_events(eng),
        f'{run_id}_G_bottleneck_stats.csv':  export_bottleneck_stats(eng),
        f'{run_id}_H_node_heatmap.csv':      export_node_heatmap(eng),
        f'{run_id}_I_step_snapshot.csv':     export_step_snapshots(eng),
        f'{run_id}_J_escape_paths.csv':      export_escape_paths(eng),
        f'{run_id}_K_agent_final.csv':       export_agent_final(eng),
        f'{run_id}_L_simulation_meta.csv':   export_simulation_meta(eng, sim_config),
        f'{run_id}_M_unified_log.csv':       export_unified_experiment_log(eng, sim_config),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files.items():
            if content:
                zf.writestr(fname, content.encode('utf-8'))
    buf.seek(0)
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════
# UTILITY
# ════════════════════════════════════════════════════════════════════

def export_all_zip(eng, sim_config: dict = None) -> bytes:
    run_id = getattr(eng, 'run_id', 'run')
    files = {
        f'{run_id}_01_step_snapshot.csv':        export_step_snapshots(eng),
        f'{run_id}_02_agent_final.csv':           export_agent_final(eng),
        f'{run_id}_03_decision_log.csv':          export_decision_log(eng),
        f'{run_id}_04_movement_log.csv':          export_movement_log(eng),
        f'{run_id}_05_agent_type_comparison.csv': export_agent_type_comparison(eng),
        f'{run_id}_06_model_performance.csv':     export_model_performance(eng),
        f'{run_id}_07_panic_evolution.csv':       export_panic_evolution(eng),
        f'{run_id}_08_agent_step_panic.csv':      export_agent_step_panic(eng),
        f'{run_id}_09_panic_events.csv':          export_panic_events(eng),
        f'{run_id}_10_node_occupancy.csv':        export_node_occupancy(eng),
        f'{run_id}_11_node_heatmap.csv':          export_node_heatmap(eng),
        f'{run_id}_12_bottleneck_stats.csv':      export_bottleneck_stats(eng),
        f'{run_id}_13_node_risk_log.csv':         export_node_risk_log(eng),
        f'{run_id}_14_escape_paths.csv':          export_escape_paths(eng),
        f'{run_id}_15_simulation_meta.csv':       export_simulation_meta(eng, sim_config),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname, content in files.items():
            if content:
                zf.writestr(fname, content.encode('utf-8'))
    buf.seek(0)
    return buf.getvalue()


def get_summary(eng) -> dict:
    call_log   = getattr(eng, 'llm_call_log', [])
    total_cost = sum(_est_cost(lg.get('model', ''),
                               lg.get('prompt_tokens', 0),
                               lg.get('completion_tokens', 0)) for lg in call_log)
    escaped    = sum(1 for a in eng.agents if a['status'] == 'Escaped')
    return {
        'steps':          len(getattr(eng, 'step_stats', [])),
        'agents':         len(eng.agents),
        'escaped':        escaped,
        'escape_rate':    round(escaped / len(eng.agents), 4) if eng.agents else 0,
        'decisions':      len(eng.cot_logs),
        'movements':      len(eng.logs),
        'llm_calls':      len(call_log),
        'total_tokens':   sum(lg.get('total_tokens', 0) for lg in call_log),
        'total_cost_usd': round(total_cost, 6),
        'panic_events':   len(getattr(eng, 'panic_event_log', [])),
    }


def export_llm_call_log(eng) -> str:
    """Export one row per LLM API attempt for operational auditing."""
    fields = [
        'step', 'agent_id', 'agent_type', 'model', 'attempt',
        'prompt_tokens', 'completion_tokens', 'total_tokens',
        'latency_ms', 'success', 'error_type', 'error_msg',
        'transport_success', 'finish_reason', 'request_mode', 'response_text',
        'target_normalization', 'feedback_retry',
    ]
    return _to_csv(getattr(eng, 'llm_call_log', []), fields)
