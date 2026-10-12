"""Auditable policy objects used by the evacuation engine."""

from dataclasses import dataclass
from typing import Optional

import networkx as nx


@dataclass(frozen=True)
class Decision:
    target_id: Optional[str]
    reason_code: str
    brief_justification: str
    policy_id: str
    information_scope: str
    fallback_used: bool = False
    error: str = ""


class GlobalShortestPathPolicy:
    policy_id = "Global_ShortestPath"
    information_scope = "global_current_state"

    def decide(self, context):
        graph = context["graph"].subgraph(context["passable_nodes"]).copy()
        current = context["current_node"]
        candidates = []
        for exit_id in sorted(context["exits"]):
            try:
                path = nx.shortest_path(graph, current, exit_id)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            if len(path) > 1:
                candidates.append(path)
        if not candidates:
            return Decision(
                None,
                "NO_ROUTE",
                "No passable route in the current topology",
                self.policy_id,
                self.information_scope,
            )
        path = min(candidates, key=lambda item: (len(item), tuple(item)))
        return Decision(
            path[1],
            "GLOBAL_SHORTEST",
            f"Current minimum-hop route has {len(path) - 1} hops",
            self.policy_id,
            self.information_scope,
        )


class RiskAwareDijkstraPolicy:
    policy_id = "RiskAware_Dijkstra"
    information_scope = "global_current_state"

    def __init__(self, risk_weight=6.0, crowd_weight=2.0):
        self.risk_weight = float(risk_weight)
        self.crowd_weight = float(crowd_weight)

    def decide(self, context):
        graph = context["graph"].subgraph(context["passable_nodes"]).copy()
        risk = context.get("node_risk", {})
        crowd = context.get("occupancy_ratio", {})
        for source, target in graph.edges:
            graph[source][target]["cost"] = (
                1.0
                + self.risk_weight * max(0.0, float(risk.get(target, 0.0)))
                + self.crowd_weight * max(0.0, float(crowd.get(target, 0.0)))
            )

        candidates = []
        for exit_id in sorted(context["exits"]):
            try:
                path = nx.shortest_path(
                    graph, context["current_node"], exit_id, weight="cost"
                )
                cost = nx.path_weight(graph, path, weight="cost")
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            if len(path) > 1:
                candidates.append((cost, path))
        if not candidates:
            return Decision(
                None,
                "NO_ROUTE",
                "No passable route in the current risk field",
                self.policy_id,
                self.information_scope,
            )
        cost, path = min(candidates, key=lambda item: (item[0], tuple(item[1])))
        return Decision(
            path[1],
            "GLOBAL_RISK_AWARE",
            f"Minimum current risk-crowding cost is {cost:.3f}",
            self.policy_id,
            self.information_scope,
        )


GLOBAL_POLICY_TYPES = {
    "Global_ShortestPath": GlobalShortestPathPolicy,
    "RiskAware_Dijkstra": RiskAwareDijkstraPolicy,
}


def information_scope_for(policy_id):
    if policy_id in GLOBAL_POLICY_TYPES:
        return "global_current_state"
    if policy_id == "Random":
        return "local_adjacent_state"
    return "local_partial_observation"
