import networkx as nx

from policies import GlobalShortestPathPolicy, RiskAwareDijkstraPolicy


def graph():
    result = nx.DiGraph()
    result.add_edges_from([
        ("A", "B"), ("B", "X"),
        ("A", "C"), ("C", "D"), ("D", "X"),
    ])
    return result


def test_global_shortest_path_chooses_minimum_hops():
    decision = GlobalShortestPathPolicy().decide({
        "graph": graph(),
        "current_node": "A",
        "exits": ["X"],
        "passable_nodes": {"A", "B", "C", "D", "X"},
    })

    assert decision.target_id == "B"
    assert decision.reason_code == "GLOBAL_SHORTEST"
    assert decision.information_scope == "global_current_state"


def test_risk_aware_avoids_high_risk_short_route():
    decision = RiskAwareDijkstraPolicy(6.0, 2.0).decide({
        "graph": graph(),
        "current_node": "A",
        "exits": ["X"],
        "passable_nodes": {"A", "B", "C", "D", "X"},
        "node_risk": {"A": 0, "B": 1, "C": 0, "D": 0, "X": 0},
        "occupancy_ratio": {node: 0 for node in "ABCDX"},
    })

    assert decision.target_id == "C"
    assert decision.reason_code == "GLOBAL_RISK_AWARE"


def test_global_policy_returns_no_route_when_exit_is_cut_off():
    decision = GlobalShortestPathPolicy().decide({
        "graph": graph(),
        "current_node": "A",
        "exits": ["X"],
        "passable_nodes": {"A", "C"},
    })
    assert decision.target_id is None
    assert decision.reason_code == "NO_ROUTE"
