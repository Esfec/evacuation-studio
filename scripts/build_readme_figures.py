"""Build README evidence from committed recordings only; never call an API.

Run from any directory: python scripts/build_readme_figures.py
Requires requirements-figures.txt. Output values use completed_steps, not step.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Patch
from matplotlib.path import Path as PlotPath
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "02_可视化沙盒" / "talk_data.js"
OUT = ROOT / "media" / "readme"
COLORS = {"D0": "#7E8FA6", "D1": "#C8A6B2", "D2": "#91ADA3"}
INK = "#3E4650"
MUTED = "#7A838C"
PALE = "#E8E9ED"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_runs():
    runs = json.loads(SOURCE.read_text(encoding="utf-8").split("=", 1)[1].strip().rstrip(";"))
    runs = sorted(runs, key=lambda r: (r["config"]["condition_id"], r["config"]["design_id"]))
    require(Counter((r["config"]["design_id"], r["config"]["condition_id"]) for r in runs)
            == Counter((d, c) for c in ("C0", "C1") for d in COLORS), "Expected exactly six recording cells")
    initial = runs[0]["snapshots"][0]["agents"]
    common = {k: v for k, v in runs[0]["config"].items() if k not in ("design_id", "condition_id")}
    for r in runs:
        require(r["source"] == "live_llm" and r["status"] == "completed" and r["valid"], "Incomplete or non-LLM recording")
        require(r["snapshots"][0]["agents"] == initial, "Initial agents differ")
        require({k: v for k, v in r["config"].items() if k not in ("design_id", "condition_id")} == common, "Other settings differ")
        ids = {a["id"] for a in initial}
        prev = 0
        for i, s in enumerate(r["snapshots"]):
            require(s["completed_steps"] == i, "Non-contiguous completed steps")
            require(s["sim_time_s"] == i * r["config"]["step_seconds"], "Incorrect time axis")
            require(len(s["agents"]) == len(ids) and {a["id"] for a in s["agents"]} == ids, "Agent IDs changed")
            counts = Counter(a["status"].lower() for a in s["agents"])
            require(all(s["counts"][k] == counts[k] for k in s["counts"]), "Counts disagree with agents")
            require(sum(s["counts"].values()) == len(ids), "Population not conserved")
            require(s["counts"]["escaped"] >= prev, "Escaped count decreased")
            prev = s["counts"]["escaped"]
    return runs


def summarize(r):
    snapshots = r["snapshots"]
    final = snapshots[-1]
    escaped_at = {}
    for s in snapshots[1:]:
        for a in s["agents"]:
            if a["status"] == "Escaped":
                escaped_at.setdefault(a["id"], s["completed_steps"])
    actions = Counter(a["action"] for s in snapshots[1:] for a in s["agents"])
    protocol = r["llm_protocol"]
    return dict(run_id=r["id"], design=r["config"]["design_id"], condition=r["config"]["condition_id"],
                agents=len(final["agents"]), escaped=final["counts"]["escaped"], dead=final["counts"]["dead"],
                escape_rate=final["counts"]["escaped"] / len(final["agents"]),
                completed_steps=final["completed_steps"], nominal_end_seconds=final["sim_time_s"],
                median_escape_step=float(np.median(list(escaped_at.values()))) if escaped_at else None,
                edge_queue_events=actions["EDGE_QUEUE"], stamina_wait_events=actions["STAMINA_WAIT"],
                node_full_events=actions["NODE_FULL"],
                mean_smoke_exposure=float(np.mean([a["smoke_exposure"] for a in final["agents"]])),
                api_attempts=protocol["attempts"], invalid_outputs=protocol["invalid_outputs"],
                fallback_count=r["fallback_count"], quality=r["quality"])


def save(fig, name):
    for extension in ("png", "svg"):
        target = OUT / f"{name}.{extension}"
        fig.savefig(target, dpi=240, bbox_inches="tight", facecolor="white",
                    metadata={"Date": None} if extension == "svg" else {})
        if extension == "svg":
            clean_svg = "\n".join(line.rstrip() for line in target.read_text(encoding="utf-8").splitlines()) + "\n"
            target.write_bytes(clean_svg.encode("utf-8"))
    plt.close(fig)


def topology(runs):
    # Schematic coordinates only; all connectivity comes from the recording.
    pos = {"N15": (0, 0), "N17": (0, 1), "N01": (0, 2), "N03": (0, 3),
           "N04": (1, 0), "N06": (1, 1), "N05": (1, 2), "N02": (1, 3),
           "N07": (2, 4), "N13": (2, 3), "N09": (2, 2), "N10": (2, 1),
           "N11": (2, 0), "N12": (3, 1), "N08": (3, 4), "N14": (3, 3),
           "N16": (4, 3), "N18": (4, 4)}
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.4))
    for ax, condition in zip(axes, ("C0", "C1")):
        r = next(r for r in runs if r["config"]["design_id"] == "D0" and r["config"]["condition_id"] == condition)
        edge_set = {(e["source"], e["target"]) for e in r["topology"]["edges"]}
        seen = set()
        for u, v in sorted(edge_set):
            pair = tuple(sorted((u, v)))
            if pair in seen:
                continue
            seen.add(pair)
            blocked = condition == "C1" and "N10" in pair
            special = pair == ("N06", "N10")
            color = "#D2D5D8" if blocked else (COLORS["D1"] if special else "#A9B1B5")
            arrow = "<->" if (v, u) in edge_set else "->"
            ax.add_patch(FancyArrowPatch(pos[u], pos[v], arrowstyle=arrow, mutation_scale=10,
                                        shrinkA=21, shrinkB=21, lw=3 if special else 1.5,
                                        linestyle=":" if blocked else "-", color=color, zorder=1))
        # Route this schematic edge between node boxes, without implying extra junctions.
        route = PlotPath([(1.20, 1.20), (1.6, 1.6), (2.6, 1.6), (2.6, 3.5), (2.86, 3.78)])
        ax.add_patch(FancyArrowPatch(path=route, arrowstyle="<->", mutation_scale=11,
                                    lw=2, linestyle="--", color=COLORS["D2"], zorder=2))
        for node, (x, y) in pos.items():
            color = "#E4EEE9" if node in ("N11", "N18") else "#F7F7F5"
            if node == "N01":
                color = "#F1DDDA"
            if node == "N10" and condition == "C1":
                color = "#E7C9CC"
            ax.text(x, y, node, ha="center", va="center", weight="bold", fontsize=10,
                    color=INK, bbox=dict(boxstyle="round,pad=.45", fc=color, ec="#929B99"), zorder=3)
        ax.text(-.12, 2.28, "FIRE", ha="center", fontsize=8, color="#A66D72")
        ax.text(2, -.42, "EXIT", ha="center", fontsize=8, color="#627F74")
        ax.text(4, 4.42, "EXIT", ha="center", fontsize=8, color="#627F74")
        ax.set(title=f"{condition} | " + ("Initially open" if condition == "C0" else "N10 closed from start"),
               xlim=(-.5, 4.6), ylim=(-.6, 4.7), aspect="equal")
        ax.axis("off")
    fig.suptitle("Museum topology and scenario matrix", fontsize=16, weight="semibold", color=INK)
    fig.legend(handles=[Patch(color="#A9B1B5", label="D0  Existing network"),
                        Patch(color=COLORS["D1"], label="D1: N06–N10 capacity 4 → 8"),
                        Patch(color=COLORS["D2"], label="D2: add N06–N08")],
               loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(.5, .06))
    fig.tight_layout(rect=(0, .11, 1, .94))
    save(fig, "scenarios")


def performance(runs, rows):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.2))
    population = rows[0]["agents"]
    for col, condition in enumerate(("C0", "C1")):
        selected = [(r, row) for r, row in zip(runs, rows) if row["condition"] == condition]
        ax = axes[0, col]
        for x, (r, row) in enumerate(selected):
            ax.bar(x, row["escaped"], color=COLORS[row["design"]], width=.55)
            ax.bar(x, row["dead"], bottom=row["escaped"], color=PALE, width=.55)
            ax.text(x, row["escaped"] / 2, f'{row["escaped"]}/{population}\n{row["escape_rate"]:.1%}', ha="center", va="center", color="white", weight="bold")
            ax.text(x, row["escaped"] + row["dead"] / 2, f'{row["dead"]} dead', ha="center", va="center", color=MUTED)
        ax.set(title=f"{condition} · final outcome", xticks=range(3), xticklabels=list(COLORS), ylim=(0, population * 1.07), ylabel="Agents")
        ax = axes[1, col]
        for r, row in selected:
            ax.step([s["completed_steps"] for s in r["snapshots"]],
                    [s["counts"]["escaped"] / row["agents"] * 100 for s in r["snapshots"]],
                    where="post", color=COLORS[row["design"]], label=row["design"], lw=2)
        ax.set(xlabel="Completed simulation steps (5 nominal seconds / step)", ylabel="Cumulative escaped (%)", xlim=(0, 19), ylim=(0, 100))
        ax.legend(frameon=False, loc="upper left", ncol=3)
    fig.suptitle(f"Recorded evacuation outcomes · seed {runs[0]['config']['seed']} · {population} agents", fontsize=15, weight="semibold", color=INK)
    fig.tight_layout(rect=(0, .02, 1, .95))
    save(fig, "recorded-results")


def diagnostics(runs, rows):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.3), gridspec_kw={"width_ratios": [1, 1.5]})
    labels = [f'{r["design"]}/{r["condition"]}' for r in rows]
    y = np.arange(len(rows))
    axes[0].barh(y, [r["edge_queue_events"] for r in rows], color="#93A7B5", label="Edge capacity wait")
    axes[0].barh(y, [r["stamina_wait_events"] for r in rows], left=[r["edge_queue_events"] for r in rows], color="#D8C3A6", label="Stamina wait")
    for i, row in enumerate(rows):
        axes[0].text(row["edge_queue_events"] + row["stamina_wait_events"] + 2, i, str(row["edge_queue_events"] + row["stamina_wait_events"]), va="center", fontsize=9)
    axes[0].set(yticks=y, yticklabels=labels, xlabel="Recorded person-steps waiting", title="Waiting by cause", xlim=(0, 155))
    axes[0].invert_yaxis()
    axes[0].legend(frameon=False, loc="upper left", bbox_to_anchor=(0, -.18), ncol=2, fontsize=8)
    counts = [Counter(a["node"] for a in r["snapshots"][-1]["agents"] if a["status"] == "Dead") for r in runs]
    nodes = sorted(set().union(*(set(c) for c in counts)))
    matrix = np.array([[c[n] for n in nodes] for c in counts])
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("soft_rose", ["#FAFAFA", "#E8DCE1", "#C7A7B7", "#846B7A"])
    axes[1].imshow(matrix, cmap=cmap, aspect="auto", vmin=0, vmax=max(1, matrix.max()))
    for i in range(len(rows)):
        for j in range(len(nodes)):
            axes[1].text(j, i, str(matrix[i, j]), ha="center", va="center", color="white" if matrix[i, j] > matrix.max()*.6 else "#493f32", fontsize=10)
    axes[1].set(yticks=y, yticklabels=labels, xticks=range(len(nodes)), xticklabels=nodes, title="Final death locations · counts", xlabel="Nodes with at least one death in these six recordings")
    fig.suptitle("Waiting events and final spatial distribution", fontsize=16, weight="semibold", color=INK)
    fig.tight_layout(rect=(0, .08, 1, .92))
    save(fig, "recorded-diagnostics")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
                         "font.size": 10, "text.color": INK, "axes.labelcolor": INK, "axes.titlecolor": INK,
                         "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": "white", "axes.facecolor": "white",
                         "axes.edgecolor": "#B8BEC3", "axes.spines.top": False, "axes.spines.right": False,
                         "legend.frameon": False, "svg.fonttype": "none", "pdf.fonttype": 42,
                         "svg.hashsalt": "evacuation-readme"})
    runs = load_runs()
    rows = [summarize(r) for r in runs]
    with (OUT / "recorded-summary.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    evidence = dict(source=SOURCE.relative_to(ROOT).as_posix(), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                    implementation=sorted({r["implementation"] for r in runs}),
                    initial_agents_identical=True, non_scenario_config_identical=True,
                    api_attempts=sum(r["api_attempts"] for r in rows), runs=rows)
    with (OUT / "provenance.json").open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    topology(runs)
    performance(runs, rows)
    diagnostics(runs, rows)
    print(json.dumps({"runs": len(rows), "api_attempts": evidence["api_attempts"], "output": str(OUT)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
