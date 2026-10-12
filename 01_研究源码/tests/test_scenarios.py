import json
from pathlib import Path

import pytest

from scenarios import apply_scenario


BASE = Path(__file__).parents[1]


def load_map():
    return json.loads((BASE / "Map.json").read_text(encoding="utf-8"))


def edge(data, source, target):
    return next(
        item
        for item in data["edges"]
        if item["source"] == source and item["target"] == target
    )


def test_d0_normalizes_all_edges_to_unit_hop_and_base_capacity():
    data, manifest = apply_scenario(load_map(), "D0", "C0", 4)
    assert all(item["dist"] == 1 for item in data["edges"])
    assert all(item["capacity_per_step"] == 4 for item in data["edges"])
    assert manifest["design_id"] == "D0"


def test_d1_doubles_only_n06_n10_capacity():
    data, manifest = apply_scenario(load_map(), "D1", "C0", 4)
    assert edge(data, "N06", "N10")["capacity_per_step"] == 8
    assert edge(data, "N10", "N06")["capacity_per_step"] == 8
    assert manifest["capacity_changes"] == [
        "N06->N10:4->8",
        "N10->N06:4->8",
    ]


def test_d2_adds_bidirectional_unit_hop():
    data, manifest = apply_scenario(load_map(), "D2", "C0", 4)
    assert edge(data, "N06", "N08")["dist"] == 1
    assert edge(data, "N08", "N06")["capacity_per_step"] == 4
    assert manifest["added_edges"] == ["N06->N08", "N08->N06"]


def test_c1_blocks_n10_without_mutating_base_map():
    base = load_map()
    data, manifest = apply_scenario(base, "D0", "C1", 4)
    n10 = next(node for node in data["nodes"] if node["id"] == "N10")
    original = next(node for node in base["nodes"] if node["id"] == "N10")
    assert n10["scenario_blocked"] is True
    assert "scenario_blocked" not in original
    assert manifest["blocked_nodes"] == ["N10"]


def test_scenario_rejects_unknown_design_or_condition():
    with pytest.raises(ValueError):
        apply_scenario(load_map(), "D9", "C0", 4)
    with pytest.raises(ValueError):
        apply_scenario(load_map(), "D0", "C9", 4)
