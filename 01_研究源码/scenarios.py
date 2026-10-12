"""Pure map transformations for early-design alternatives and fire conditions."""

from copy import deepcopy


DESIGN_LABELS = {
    "D0": "原始方案",
    "D1": "提高 N06↔N10 每步服务容量（容量×2）",
    "D2": "新增 N06↔N08 双向连接",
}
CONDITION_LABELS = {
    "C0": "动态火灾，初始路径均可用",
    "C1": "动态火灾，N10 从 step 0 不可用",
}


def apply_scenario(base_map, design_id, condition_id, base_edge_capacity=4):
    if design_id not in DESIGN_LABELS:
        raise ValueError(f"Unknown design: {design_id}")
    if condition_id not in CONDITION_LABELS:
        raise ValueError(f"Unknown condition: {condition_id}")
    if base_edge_capacity <= 0:
        raise ValueError("base_edge_capacity must be positive")

    data = deepcopy(base_map)
    for item in data["edges"]:
        item["dist"] = 1
        item["capacity_per_step"] = base_edge_capacity

    manifest = {
        "design_id": design_id,
        "design_label": DESIGN_LABELS[design_id],
        "condition_id": condition_id,
        "condition_label": CONDITION_LABELS[condition_id],
        "edge_semantics": "one directed edge equals one movement step",
        "added_edges": [],
        "capacity_changes": [],
        "blocked_nodes": [],
    }

    if design_id == "D1":
        for source, target in (("N06", "N10"), ("N10", "N06")):
            item = next(
                (edge for edge in data["edges"]
                 if edge["source"] == source and edge["target"] == target),
                None,
            )
            if item is None:
                raise ValueError(f"D1 requires existing edge {source}->{target}")
            item["capacity_per_step"] = base_edge_capacity * 2
            item["intervention"] = "D1"
            manifest["capacity_changes"].append(
                f"{source}->{target}:{base_edge_capacity}->{base_edge_capacity * 2}"
            )
    elif design_id == "D2":
        existing = {(edge["source"], edge["target"]) for edge in data["edges"]}
        for source, target in (("N06", "N08"), ("N08", "N06")):
            if (source, target) in existing:
                raise ValueError(f"D2 edge already exists: {source}->{target}")
            data["edges"].append({
                "source": source,
                "target": target,
                "dist": 1,
                "capacity_per_step": base_edge_capacity,
                "intervention": "D2",
            })
            manifest["added_edges"].append(f"{source}->{target}")

    if condition_id == "C1":
        node = next((node for node in data["nodes"] if node["id"] == "N10"), None)
        if node is None:
            raise ValueError("C1 requires node N10")
        node["scenario_blocked"] = True
        manifest["blocked_nodes"].append("N10")

    return data, manifest
