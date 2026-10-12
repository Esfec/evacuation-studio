from movement import resolve_moves
import random


def test_resolution_is_invariant_to_proposal_order():
    proposals = [
        {"agent_id": "A", "source": "N01", "target": "N02"},
        {"agent_id": "B", "source": "N02", "target": "N01"},
        {"agent_id": "C", "source": "N03", "target": "N02"},
    ]
    kwargs = {
        "node_counts": {"N01": 1, "N02": 1, "N03": 1},
        "node_capacities": {"N01": 2, "N02": 2, "N03": 2},
        "edge_capacities": {
            ("N01", "N02"): 1,
            ("N02", "N01"): 1,
            ("N03", "N02"): 1,
        },
        "seed": 42,
    }

    first = resolve_moves(proposals, **kwargs)
    second = resolve_moves(list(reversed(proposals)), **kwargs)
    assert first == second


def test_edge_capacity_rejects_excess_proposals():
    result = resolve_moves(
        [
            {"agent_id": "A", "source": "N01", "target": "N02"},
            {"agent_id": "B", "source": "N01", "target": "N02"},
        ],
        node_counts={"N01": 2, "N02": 0},
        node_capacities={"N01": 4, "N02": 4},
        edge_capacities={("N01", "N02"): 1},
        seed=42,
    )
    assert len(result["accepted"]) == 1
    assert list(result["rejected"].values()) == ["EDGE_QUEUE"]


def test_longer_waiting_agent_gets_capacity_before_new_arrival():
    result = resolve_moves(
        [
            {"agent_id": "new", "source": "N01", "target": "N02", "queue_age": 0},
            {"agent_id": "waiting", "source": "N01", "target": "N02", "queue_age": 2},
        ],
        node_counts={"N01": 2, "N02": 0},
        node_capacities={"N01": 4, "N02": 4},
        edge_capacities={("N01", "N02"): 1},
        seed=3,
    )

    assert result["accepted"] == ["waiting"]
    assert result["rejected"] == {"new": "EDGE_QUEUE"}


def test_destination_capacity_uses_post_departure_occupancy():
    result = resolve_moves(
        [
            {"agent_id": "A", "source": "N01", "target": "N02"},
            {"agent_id": "B", "source": "N02", "target": "N01"},
        ],
        node_counts={"N01": 1, "N02": 1},
        node_capacities={"N01": 1, "N02": 1},
        edge_capacities={("N01", "N02"): 1, ("N02", "N01"): 1},
        seed=42,
    )
    assert result["accepted"] == ["A", "B"]
    assert result["rejected"] == {}


def test_blocked_departure_propagates_back_through_full_rooms():
    proposals = [dict(agent_id='a', source='A', target='B'),
                 dict(agent_id='b', source='B', target='C')]
    result = resolve_moves(proposals, node_counts=dict(A=1, B=1, C=1),
                           node_capacities=dict(A=1, B=1, C=1),
                           edge_capacities={('A','B'):1, ('B','C'):1}, seed=42)
    assert result['accepted'] == []
    assert result['rejected'] == {'a':'NODE_FULL', 'b':'NODE_FULL'}


def test_random_networks_never_overfill_or_depend_on_input_order():
    rng = random.Random(284)
    for seed in range(300):
        capacities = {str(i):rng.randint(1, 6) for i in range(6)}
        counts = {i:rng.randint(0, cap) for i,cap in capacities.items()}
        proposals = [dict(agent_id=f'{src}-{j}', source=src,
                          target=rng.choice([n for n in counts if n != src]))
                     for src,n in counts.items() for j in range(n)]
        edge_caps = {(i,j):rng.randint(1,3) for i in counts for j in counts}
        kwargs = dict(node_counts=counts, node_capacities=capacities,
                      edge_capacities=edge_caps, seed=seed)
        result = resolve_moves(proposals, **kwargs)
        assert result == resolve_moves(list(reversed(proposals)), **kwargs)
        after = dict(counts)
        for p in proposals:
            if p['agent_id'] in result['accepted']:
                after[p['source']] -= 1
                after[p['target']] += 1
        assert sum(after.values()) == sum(counts.values())
        assert all(0 <= after[n] <= capacities[n] for n in counts)
