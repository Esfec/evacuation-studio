"""Order-invariant, two-phase movement-capacity resolution."""

import hashlib
from collections import defaultdict


def _rank(seed, phase, proposal):
    payload = (
        f"{seed}|{phase}|{proposal['agent_id']}|"
        f"{proposal['source']}|{proposal['target']}"
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _queue_rank(seed, phase, proposal):
    """Prefer continuous waiters, then use a stable seeded tie-break."""
    return (-max(0, int(proposal.get("queue_age", 0))), _rank(seed, phase, proposal))


def resolve_moves(
    proposals,
    *,
    node_counts,
    node_capacities,
    edge_capacities,
    seed,
):
    """Resolve simultaneous proposals without depending on loop order.

    Edge throughput is applied first. Destination capacity is then evaluated
    against occupancy after all edge-admitted departures, allowing swaps.
    """
    by_edge = defaultdict(list)
    for proposal in proposals:
        by_edge[(proposal["source"], proposal["target"])].append(dict(proposal))

    edge_admitted = []
    rejected = {}
    for edge_key in sorted(by_edge):
        group = sorted(by_edge[edge_key], key=lambda item: _queue_rank(seed, "edge", item))
        limit = max(0, int(edge_capacities.get(edge_key, 0)))
        edge_admitted.extend(group[:limit])
        for proposal in group[limit:]:
            rejected[proposal["agent_id"]] = "EDGE_QUEUE"

    # Rejected departures remain in their source. Propagate that occupancy
    # backwards until all accepted flows are simultaneously feasible. Starting
    # with all edge-admitted proposals preserves full-room swaps and cycles.
    pending = {p["agent_id"]: p for p in edge_admitted}
    while pending:
        departures = defaultdict(int)
        by_target = defaultdict(list)
        for proposal in pending.values():
            departures[proposal["source"]] += 1
            by_target[proposal["target"]].append(proposal)
        remove = set()
        for target in sorted(by_target):
            group = sorted(by_target[target], key=lambda p: _queue_rank(seed, "node", p))
            post_departure = int(node_counts.get(target, 0)) - departures[target]
            available = max(0, int(node_capacities.get(target, 0)) - post_departure)
            remove.update(p["agent_id"] for p in group[available:])
        if not remove:
            break
        for aid in remove:
            rejected[aid] = "NODE_FULL"
            del pending[aid]
    accepted = list(pending)

    return {
        "accepted": sorted(accepted),
        "rejected": {agent_id: rejected[agent_id] for agent_id in sorted(rejected)},
    }
