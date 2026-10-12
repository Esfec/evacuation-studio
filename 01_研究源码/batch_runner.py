"""Command-line runner for paired policy × design × condition experiments."""

import argparse
import csv
import hashlib
import json
import os
from itertools import product
from pathlib import Path

from engine import SimulationEngine
from config import LLM_PROVIDERS
from llm_api import test_api_connection
from recorder import save_run_v4
from run_config import AgentCounts, RunConfig
from scenarios import apply_scenario


BASE = Path(__file__).resolve().parent


def build_matrix(policies, designs, conditions, seeds):
    return [
        {
            "policy_id": policy,
            "design_id": design,
            "condition_id": condition,
            "seed": int(seed),
        }
        for policy, design, condition, seed
        in product(policies, designs, conditions, seeds)
    ]


def completed_case_keys(output_root):
    """Return valid case identities already present in a batch summary."""
    summary = Path(output_root) / "summary_v4.csv"
    if not summary.exists():
        return set()
    completed = set()
    with summary.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("valid_run", "")).strip().lower() != "true":
                continue
            try:
                seed = int(row["seed"])
            except (KeyError, TypeError, ValueError):
                continue
            completed.add((
                row.get("policy_id", ""),
                row.get("design_id", ""),
                row.get("condition_id", ""),
                seed,
            ))
    return completed


def filter_pending_cases(matrix, completed):
    """Preserve matrix order while omitting valid completed cells."""
    return [
        case for case in matrix
        if (
            case["policy_id"], case["design_id"],
            case["condition_id"], case["seed"],
        ) not in completed
    ]


def preflight_llm(args, matrix, api_key):
    """Fail before the matrix if credentials or the frozen model are unusable."""
    if not any(case["policy_id"] == "LLM_Agent" for case in matrix):
        return None
    if not api_key:
        raise RuntimeError("LLM_Agent requires a non-empty API key")
    ok, message, latency_ms = test_api_connection(
        args.provider, api_key, args.model
    )
    if not ok:
        raise RuntimeError(f"LLM preflight failed: {message}")
    print(
        f"LLM preflight passed: {args.provider}/{args.model} "
        f"({latency_ms} ms)",
        flush=True,
    )
    return {"message": message, "latency_ms": latency_ms}


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_case(case, args, base_map, agent_data):
    counts = AgentCounts(*args.agent_counts)
    config = RunConfig(
        seed=case["seed"],
        policy_id=case["policy_id"],
        design_id=case["design_id"],
        condition_id=case["condition_id"],
        fire_origin=args.fire_origin,
        max_steps=args.max_steps,
        agent_counts=counts,
        fire_rate=args.fire_rate,
        risky_coeff=args.risky_coeff,
        blocked_coeff=args.blocked_coeff,
        temperature=args.temperature,
        provider=args.provider,
        model=args.model,
        experiment_type="formal_batch",
        min_hops_to_exit=args.min_hops,
        llm_concurrency=args.llm_concurrency,
    )
    scenario_map, manifest = apply_scenario(
        base_map, config.design_id, config.condition_id,
        config.base_edge_capacity,
    )
    api_key = (
        os.environ.get(args.api_key_env, "")
        if config.policy_id == "LLM_Agent" else ""
    )
    if config.policy_id == "LLM_Agent" and not api_key:
        raise RuntimeError(
            f"LLM_Agent requires environment variable {args.api_key_env}"
        )
    engine = SimulationEngine(
        scenario_map,
        agent_data,
        api_key=api_key,
        api_provider=config.provider,
        api_model=config.model,
        seed=config.seed,
        temperature=config.temperature,
        fire_origin=config.fire_origin,
        risky_coeff=config.risky_coeff,
        blocked_coeff=config.blocked_coeff,
        fire_rate=config.fire_rate,
        run_config=config,
        intervention_manifest=manifest,
    )
    engine.initialize_agents(
        counts.cognitive,
        counts.perceptual,
        counts.follower,
        min_hops_to_exit=config.min_hops_to_exit,
    )
    while (
        engine.current_step < config.max_steps
        and engine.get_statistics()["active"] > 0
        and engine.valid_run
    ):
        engine.run_step()
    save_run_v4(engine, args.output)
    return engine


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policies", nargs="+", required=True)
    parser.add_argument("--designs", nargs="+", default=["D0", "D1", "D2"])
    parser.add_argument("--conditions", nargs="+", default=["C0", "C1"])
    parser.add_argument("--seeds", nargs="+", type=int, required=True)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--output", default="results/formal_v4")
    parser.add_argument("--map", default=str(BASE / "Map.json"))
    parser.add_argument("--agents", default=str(BASE / "Agent.json"))
    parser.add_argument("--agent-counts", nargs=3, type=int, default=[10, 15, 23])
    parser.add_argument("--fire-origin", default="N01")
    parser.add_argument("--fire-rate", type=float, default=0.10)
    parser.add_argument("--risky-coeff", type=float, default=3.0)
    parser.add_argument("--blocked-coeff", type=float, default=7.0)
    parser.add_argument("--min-hops", type=int, default=3)
    parser.add_argument("--temperature", type=float, default=0.10)
    parser.add_argument("--provider", default="DeepSeek", choices=list(LLM_PROVIDERS))
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--api-key-env", default=None)
    parser.add_argument("--llm-concurrency", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    return parser


def ensure_batch_contract(args, base_map, agent_data):
    """Reject incompatible result reuse; never store API credentials."""
    fields = ("max_steps", "agent_counts", "fire_origin", "fire_rate",
              "risky_coeff", "blocked_coeff", "min_hops", "temperature",
              "provider", "model", "llm_concurrency")
    contract = {name: getattr(args, name) for name in fields}
    for name, data in (("map", base_map), ("agents", agent_data)):
        encoded = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
        contract[name + "_sha256"] = hashlib.sha256(encoded).hexdigest()
    contract["code_sha256"] = {
        name: hashlib.sha256((BASE / name).read_bytes()).hexdigest()
        for name in ("engine.py", "observation.py", "movement.py", "policies.py",
                     "scenarios.py", "llm_api.py", "run_config.py", "config.py",
                     "batch_runner.py", "recorder.py")
    }
    contract["pythonhashseed"] = os.environ.get("PYTHONHASHSEED", "unset")
    root = Path(args.output)
    path = root / "batch_contract.json"
    if path.exists():
        if _load_json(path) != contract:
            raise ValueError("Batch configuration differs; use a new output directory.")
        if (root / "summary_v4.csv").exists() and not args.resume:
            raise ValueError("Existing batch configuration/results; use --resume or a new output directory.")
    elif (root / "summary_v4.csv").exists():
        raise ValueError("Legacy results have no batch configuration contract; use a new output directory.")
    else:
        root.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.api_key_env = args.api_key_env or LLM_PROVIDERS[args.provider]["env_key"]
    base_map = _load_json(args.map)
    agent_data = _load_json(args.agents)
    matrix = build_matrix(
        args.policies, args.designs, args.conditions, args.seeds
    )
    ensure_batch_contract(args, base_map, agent_data)
    total_cells = len(matrix)
    if args.resume:
        matrix = filter_pending_cases(
            matrix, completed_case_keys(args.output)
        )
        print(
            f"Resume: total={total_cells}, pending={len(matrix)}, "
            f"completed={total_cells - len(matrix)}",
            flush=True,
        )
    if not matrix:
        print(json.dumps({"runs": 0, "output": args.output}, ensure_ascii=False))
        return 0
    preflight_llm(
        args,
        matrix,
        os.environ.get(args.api_key_env, ""),
    )
    for index, case in enumerate(matrix, start=1):
        label = (
            f"[{index}/{len(matrix)}] {case['policy_id']} "
            f"{case['design_id']}/{case['condition_id']} seed={case['seed']}"
        )
        print(label, flush=True)
        engine = run_case(case, args, base_map, agent_data)
        if not getattr(engine, "valid_run", True):
            print("Batch stopped: invalid run was recorded. Fix the error before resuming.", flush=True)
            return 1
    print(json.dumps({"runs": len(matrix), "output": args.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
