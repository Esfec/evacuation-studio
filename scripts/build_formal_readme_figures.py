"""Rebuild independent audit figures from frozen multi-seed summaries.

This is the independent archival audit (C0: 19 matched seeds).
The main README reproduces the manuscript via build_paper_readme_figures.py.


No simulation or API calls. Run from any directory. Cell summaries use all
valid runs; paired effects additionally require matching recorded initial
room distributions. The experimental unit for CIs is a seed, not an agent.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator

import build_readme_figures as demo_figures
from build_readme_figures import COLORS, INK, MUTED, ROOT, save

OUT = ROOT / "local-exports" / "formal-audit"

PROCESSED = ROOT / "01_研究源码" / "results" / "processed"
BOOTSTRAP_SAMPLES = 20000
SEEDS = set(range(101, 121))
SOURCES = {
    "llm": PROCESSED / "formal_design_p0_v1/paper_summary_v1.csv",
    "meta": PROCESSED / "formal_design_p0_v1/summary_v4.csv",
    "baseline": PROCESSED / "formal_baselines_p0_v1/paper_summary_v1.csv",
    "baseline_meta": PROCESSED / "formal_baselines_p0_v1/summary_v4.csv",
    "diagnostics": PROCESSED / "matched_ablation/policy_diagnostic_run_metrics.csv",
    "ablation": PROCESSED / "matched_ablation/llm_off_ablation_c1/run_summary.csv",
    "profile_lock": ROOT / "01_研究源码/agent_profiles/formal_profile_lock.json",
    "profile": ROOT / "01_研究源码/agent_profiles/Agent_P0_current.json",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(name, value):
    (OUT / name).write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def write_csv(name, rows):
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def ci_mean(values, rng_seed=20261015):
    x = np.asarray(values, dtype=float)
    require(x.ndim == 1 and len(x) > 1 and np.isfinite(x).all(), "Invalid bootstrap sample")
    rng = np.random.default_rng(rng_seed)
    means = x[rng.integers(0, len(x), (BOOTSTRAP_SAMPLES, len(x)))].mean(axis=1)
    low, high = np.quantile(means, [.025, .975])
    return dict(n=len(x), mean=float(x.mean()), ci_low=float(low), ci_high=float(high))


def initial_signature(row):
    return json.dumps(json.loads(row["actual_initial_distribution"]), sort_keys=True)


def load_evidence():
    all_llm = csv_rows(SOURCES["llm"])
    all_meta = csv_rows(SOURCES["meta"])
    llm = [r for r in all_llm if r["valid_run"].lower() == "true"]
    meta = [r for r in all_meta if r["valid_run"].lower() == "true"]
    by_id = {r["run_id"]: r for r in meta}
    require(len(llm) == len(meta) == len(by_id) == 120, "Expected 120 unique valid LLM runs")
    require({r["run_id"] for r in llm} == set(by_id), "Metrics/metadata run IDs differ")
    cells = {}
    for c in ("C0", "C1"):
        for d in COLORS:
            cell = {int(r["seed"]): r for r in llm if r["design_id"] == d and r["condition_id"] == c}
            require(len(cell) == 20 and set(cell) == SEEDS, f"Missing or duplicated cell {d}/{c}")
            cells[d, c] = cell
    for r in llm:
        m = by_id[r["run_id"]]
        total = int(r["total_agents"])
        require(total == 48, "Population changed")
        require(sum(int(r[k]) for k in ("escaped", "dead", "exhausted", "active_remaining")) == total,
                "Run population is not conserved")
        require(abs(float(r["escape_rate"]) - int(r["escaped"]) / total) < 1e-6, "Escape fraction mismatch")
        require(int(m["escaped"]) == int(r["escaped"]) and int(m["dead"]) == int(r["dead"]), "Metadata counts differ")
        require(sum(json.loads(m["actual_initial_distribution"]).values()) == total, "Initial distribution incomplete")
        require(sum(int(m[k]) for k in ("escaped_cognitive", "escaped_perceptual", "escaped_follower")) == int(r["escaped"]),
                "Profile counts do not sum to escaped")
        require(all(0 <= int(m[k]) <= n for k,n in (("escaped_cognitive",10),("escaped_perceptual",15),("escaped_follower",23))),
                "A profile escape count exceeds its population")
        require(int(m["node_count"]) == 18 and int(m["exit_count"]) == 2, "Unexpected topology size")
        require(m["fire_origin"] == "N01" and int(m["step_seconds"]) == 5 and int(m["max_steps"]) == 30,
                "Formal experiment settings differ")
        manifest = json.loads(m["intervention_manifest"])
        require(manifest["design_id"] == r["design_id"] and manifest["condition_id"] == r["condition_id"], "Manifest differs")
        require(manifest["blocked_nodes"] == (["N10"] if r["condition_id"] == "C1" else []), "Unexpected condition")
        if r["design_id"] == "D1":
            require(set(manifest["capacity_changes"]) == {"N06->N10:4->8", "N10->N06:4->8"}, "Unexpected D1")
        if r["design_id"] == "D2":
            require(set(manifest["added_edges"]) == {"N06->N08", "N08->N06"}, "Unexpected D2")
    matched, mismatches = {}, []
    for c in ("C0", "C1"):
        matched[c] = []
        for seed in sorted(SEEDS):
            rows = [by_id[cells[d, c][seed]["run_id"]] for d in COLORS]
            if len({initial_signature(r) for r in rows}) == 1:
                matched[c].append(seed)
            else:
                mismatches.append(dict(condition=c, seed=seed, distributions={r["design_id"]: json.loads(r["actual_initial_distribution"]) for r in rows}))
    require(len(matched["C1"]) == 20 and len(matched["C0"]) >= 2, "Insufficient matched seeds")
    lock = json.loads(SOURCES["profile_lock"].read_text(encoding="utf-8"))
    require(hashlib.sha256(SOURCES["profile"].read_bytes()).hexdigest() == lock["sha256"], "Frozen profile hash mismatch")
    return llm, by_id, cells, matched, mismatches, [r for r in all_llm if r not in llm]


def escape(row):
    # Prefer exact integer counts over the six-decimal archived fraction.
    return int(row["escaped"]) / int(row["total_agents"])


def summarize_cells(cells):
    output = []
    for c in ("C0", "C1"):
        for d in COLORS:
            rows = [cells[d, c][s] for s in sorted(SEEDS)]
            for metric, get_value in (("escape_rate", escape),
                                      ("total_wait_events", lambda r: float(r["total_wait_events"])),
                                      ("edge_queue_events", lambda r: float(r["edge_queue_events"])),
                                      ("mean_cumulative_smoke_exposure", lambda r: float(r["mean_cumulative_smoke_exposure"]))):
                output.append(dict(design=d, condition=c, metric=metric, **ci_mean([get_value(r) for r in rows])))
    return output


def paired_effects(cells, matched):
    output = []
    points = []
    for c in ("C0", "C1"):
        for d in ("D1", "D2"):
            values = []
            for seed in matched[c]:
                delta = (escape(cells[d, c][seed]) - escape(cells["D0", c][seed])) * 100
                values.append(delta)
                points.append(dict(design=d, condition=c, seed=seed, escape_difference_pp=delta,
                                   treatment_run=cells[d, c][seed]["run_id"], reference_run=cells["D0", c][seed]["run_id"]))
            output.append(dict(design=d, condition=c, contrast=f"{d} - D0", metric="escape_difference_pp", **ci_mean(values)))
    write_csv("formal-paired-source.csv", points)
    return output


def overview(cells, summary, effects):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1.2, 1]})
    ax = axes[0]
    offsets = np.linspace(-.16, .16, 20)
    for ci, c in enumerate(("C0", "C1")):
        for di, d in enumerate(COLORS):
            x = ci * 4 + di
            stats = next(r for r in summary if r["condition"] == c and r["design"] == d and r["metric"] == "escape_rate")
            values = np.array([escape(cells[d, c][s]) * 100 for s in sorted(SEEDS)])
            ax.scatter(x + offsets, values, s=19, color=COLORS[d], alpha=.6, edgecolors="white", linewidths=.25, zorder=2)
            ax.errorbar(x, stats["mean"] * 100, yerr=[[100*(stats["mean"]-stats["ci_low"])], [100*(stats["ci_high"]-stats["mean"])]],
                        fmt="o", color=INK, capsize=4, markersize=5, lw=1.5, zorder=3)
            ax.text(x, 80.5, f'{100*stats["mean"]:.1f}%', ha="center", fontsize=10, color=INK)
        ax.text(ci*4+1, -.22, f"{c} · 20 seeds per design", transform=ax.get_xaxis_transform(), ha="center", color=MUTED)
    ax.set(xticks=[0,1,2,4,5,6], xticklabels=["D0","D1","D2"]*2, ylabel="Escape rate (%)", ylim=(0,88), xlim=(-.6,6.6))
    ax.set_title("a  Outcomes across individual seeds", loc="left", pad=13)
    ax = axes[1]
    ax.axvline(0, color="#B8BEC3", lw=1, ls="--")
    for i, row in enumerate(effects):
        ax.errorbar(row["mean"], i, xerr=[[row["mean"]-row["ci_low"]],[row["ci_high"]-row["mean"]]],
                    fmt="o", color=COLORS[row["design"]], markersize=7, capsize=4, lw=2)
        ax.text(5.8, i, f'{row["mean"]:+.2f}', ha="right", va="center", fontsize=10)
    ax.set(yticks=range(4), yticklabels=[f'{r["condition"]}   {r["contrast"]}  (n={r["n"]})' for r in effects],
           xlabel="Paired change in escape rate (percentage points)", xlim=(-8,6))
    ax.invert_yaxis()
    ax.set_title("b  Design effects relative to D0", loc="left", pad=13)
    fig.text(.5,.015,"Dots: individual runs or paired means. Error bars: 95% bootstrap confidence intervals over seeds.",ha="center",fontsize=9,color=MUTED)
    fig.tight_layout(rect=(0,.09,1,1),w_pad=3)
    save(fig,"formal-results")


def diagnostics_figure(summary, cells):
    diag = csv_rows(SOURCES["diagnostics"])
    target = [r for r in diag if r["policy_id"] == "LLM_Agent"]
    require(len(target) == 40, "Expected 40 LLM C1 diagnostic rows")
    keyed = {(r["design_id"],int(r["seed"])):r for r in target}
    require(len(keyed)==40, "Duplicate diagnostic rows")
    for (d,s),r in keyed.items():
        require(abs(float(r["escape_rate"])-escape(cells[d,"C1"][s]))<.000051,"Diagnostic escape fractions disagree")
        require(int(r["total_failures"])==int(cells[d,"C1"][s]["dead"]),"Failure totals disagree")
    n04 = sum(int(keyed["D2",s]["n04_failures"])-int(keyed["D0",s]["n04_failures"]) for s in SEEDS)
    total = sum(int(keyed["D2",s]["total_failures"])-int(keyed["D0",s]["total_failures"]) for s in SEEDS)
    totals = []
    for region, field in (("N04","n04_failures"),("All rooms","total_failures")):
        a = sum(int(keyed["D0",s][field])for s in SEEDS)
        b = sum(int(keyed["D2",s][field])for s in SEEDS)
        totals.append(dict(region=region,design_D0=a,design_D2=b,change_D2_minus_D0=b-a))
    totals.insert(1,dict(region="Other rooms",design_D0=totals[1]["design_D0"]-totals[0]["design_D0"],
                         design_D2=totals[1]["design_D2"]-totals[0]["design_D2"],change_D2_minus_D0=total-n04))
    require(sum(r["change_D2_minus_D0"]for r in totals[:2])==totals[2]["change_D2_minus_D0"],"Spatial accounting error")
    write_csv("formal-spatial-summary.csv",totals)
    fig, axes = plt.subplots(1,3,figsize=(13,4.4),gridspec_kw={"width_ratios":[1,1,1.05]})
    for ax,metric,title,ylabel in zip(axes[:2],("total_wait_events","mean_cumulative_smoke_exposure"),
                                   ("a  Waiting events","b  Cumulative smoke exposure"),
                                   ("Mean waiting events per run","Mean relative exposure per agent")):
        for ci,c in enumerate(("C0","C1")):
            for di,d in enumerate(COLORS):
                x=ci*4+di
                row=next(r for r in summary if r["design"]==d and r["condition"]==c and r["metric"]==metric)
                ax.bar(x,row["mean"],color=COLORS[d],width=.65)
                ax.errorbar(x,row["mean"],yerr=[[row["mean"]-row["ci_low"]],[row["ci_high"]-row["mean"]]],fmt="none",color=INK,capsize=3,lw=1)
            ax.text(ci*4+1,-.22,c,transform=ax.get_xaxis_transform(),ha="center",color=MUTED)
        ax.set(xticks=[0,1,2,4,5,6],xticklabels=["D0","D1","D2"]*2,ylabel=ylabel)
        ax.set_ylim(bottom=0)
        ax.set_title(title,loc="left",pad=13)
        if metric=="total_wait_events": ax.yaxis.set_major_locator(MaxNLocator(5))
    ax=axes[2]
    vals=[r["change_D2_minus_D0"]for r in totals]
    ax.axhline(0,color="#B8BEC3",lw=1)
    ax.bar(range(3),vals,color=[COLORS["D2"],COLORS["D1"],COLORS["D0"]],width=.58)
    for i,v in enumerate(vals):
        ax.text(i,v+(4 if v>=0 else -4),f"{v:+d}",ha="center",va="bottom" if v>=0 else "top",fontsize=12,color=INK)
    ax.set(xticks=range(3),xticklabels=["N04","Other\nrooms","Total"],ylabel="Change in deaths across 20 C1 runs",ylim=(-105,82))
    ax.set_title("c  Spatial effect of D2 versus D0",loc="left",pad=13,fontsize=10.5)
    fig.text(.5,.015,"a,b: mean and 95% bootstrap CI, 20 seeds per cell. c: aggregated room counts, D2 minus D0 under C1.",ha="center",fontsize=9,color=MUTED)
    fig.tight_layout(rect=(0,.09,1,1),w_pad=2.4)
    save(fig,"formal-diagnostics")
    return totals


def behavior_figure(llm,cells,meta):
    baseline=[r for r in csv_rows(SOURCES["baseline"])if r["valid_run"].lower()=="true"]
    require(len(baseline)==480,"Expected 480 valid baseline runs")
    baseline_meta={r["run_id"]:r for r in csv_rows(SOURCES["baseline_meta"])if r["valid_run"].lower()=="true"}
    ablation=csv_rows(SOURCES["ablation"])
    require(len(ablation)==40,"Expected 40 ablation rows")
    policies=[]
    for policy,label in (("Global_ShortestPath","Global shortest path"),("LLM_Off_Ablation","LLM-off ablation"),
                         ("Local_Rule","Local rule"),("RiskAware_Dijkstra","Risk-aware Dijkstra"),
                         ("LLM_Agent","LLM agents"),("Random","Random")):
        if policy=="LLM_Agent":
            a,b=cells["D0","C1"],cells["D2","C1"]
            values=[100*(escape(b[s])-escape(a[s]))for s in sorted(SEEDS)]
        elif policy=="LLM_Off_Ablation":
            keyed={(r["design_id"],int(r["seed"])):r for r in ablation}
            require(len(keyed)==40,"Duplicate ablation seed")
            values=[]
            for s in sorted(SEEDS):
                for d in ("D0","D2"):
                    row=keyed[d,s]
                    require(row["reference_llm_run"]==cells[d,"C1"][s]["run_id"],"Ablation reference differs")
                    require(json.loads(row["initial_distribution"])==json.loads(meta[row["reference_llm_run"]]["actual_initial_distribution"]),"Ablation initial distribution differs")
                values.append(100*(float(keyed["D2",s]["escape_rate"])-float(keyed["D0",s]["escape_rate"])))
        else:
            keyed={(r["design_id"],int(r["seed"])):r for r in baseline if r["policy_id"]==policy and r["condition_id"]=="C1" and r["design_id"]in("D0","D2")}
            require(len(keyed)==40,"Baseline pair missing")
            for s in SEEDS:
                require(initial_signature(baseline_meta[keyed["D0",s]["run_id"]])==initial_signature(baseline_meta[keyed["D2",s]["run_id"]]),"Baseline pair initial distributions differ")
            values=[100*(escape(keyed["D2",s])-escape(keyed["D0",s]))for s in sorted(SEEDS)]
        policies.append(dict(policy=policy,label=label,metric="escape_difference_pp",**ci_mean(values)))
    profiles=[]
    for key,label,n in (("escaped_cognitive","Staff",10),("escaped_perceptual","Visitor",15),("escaped_follower","Follower",23)):
        # Each cluster includes all six design/condition cells from one seed.
        clusters=[np.mean([int(meta[r["run_id"]][key])/n for r in llm if int(r["seed"])==s])*100 for s in sorted(SEEDS)]
        profiles.append(dict(profile=label,runs=120,seed_clusters=20,agents_per_run=n,**ci_mean(clusters)))
    write_csv("formal-policy-effects.csv",policies)
    write_csv("formal-profile-summary.csv",profiles)
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),gridspec_kw={"width_ratios":[1.45,1]})
    ax=axes[0]
    ax.axvline(0,color="#B8BEC3",lw=1,ls="--")
    for i,row in enumerate(policies):
        ax.errorbar(row["mean"],i,xerr=[[row["mean"]-row["ci_low"]],[row["ci_high"]-row["mean"]]],fmt="o",capsize=4,lw=1.7,
                    color=COLORS["D1"]if row["policy"]=="LLM_Agent" else "#93A7B5",markersize=7)
        ax.text(24,i,f'{row["mean"]:+.2f}',va="center",ha="right",fontsize=10)
    ax.set(yticks=range(6),yticklabels=[r["label"]for r in policies],xlabel="D2 minus D0 escape rate (percentage points)",xlim=(-3,25))
    ax.invert_yaxis()
    ax.set_title("a  Design effect by decision policy · C1",loc="left",pad=13)
    ax=axes[1]
    for i,(row,color)in enumerate(zip(profiles,COLORS.values())):
        ax.bar(i,row["mean"],color=color,width=.6)
        ax.errorbar(i,row["mean"],yerr=[[row["mean"]-row["ci_low"]],[row["ci_high"]-row["mean"]]],fmt="none",color=INK,capsize=4)
        ax.text(i, row["ci_high"]+3, f'{row["mean"]:.1f}%',ha="center",fontsize=11)
    ax.set(xticks=range(3),xticklabels=[r["profile"]for r in profiles],ylabel="Escape rate (%)",ylim=(0,108))
    ax.set_title("b  Synthetic occupant profiles",loc="left",pad=13)
    fig.text(.5,.015,"95% bootstrap CIs. a: 20 paired seeds per policy. b: all 120 LLM runs, resampled in 20 seed clusters.",ha="center",fontsize=9,color=MUTED)
    fig.tight_layout(rect=(0,.055,1,1),w_pad=3)
    save(fig,"formal-behavior")
    return policies,profiles


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission-root",type=Path,help="Optionally inventory a local submission folder; raw files are not copied")
    args=parser.parse_args()
    demo_figures.OUT=OUT
    OUT.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({"font.family":"sans-serif","font.sans-serif":["Arial","Helvetica","DejaVu Sans","sans-serif"],
                         "font.size":10,"text.color":INK,"axes.labelcolor":INK,"axes.titlecolor":INK,
                         "xtick.color":MUTED,"ytick.color":MUTED,"figure.facecolor":"white","axes.facecolor":"white",
                         "axes.edgecolor":"#B8BEC3","axes.spines.top":False,"axes.spines.right":False,
                         "legend.frameon":False,"svg.fonttype":"none","pdf.fonttype":42,"svg.hashsalt":"evacuation-formal-readme"})
    llm,meta,cells,matched,mismatches,excluded=load_evidence()
    summary=summarize_cells(cells)
    effects=paired_effects(cells,matched)
    write_csv("formal-cell-summary.csv",summary)
    write_csv("formal-design-effects.csv",effects)
    overview(cells,summary,effects)
    spatial=diagnostics_figure(summary,cells)
    policies,profiles=behavior_figure(llm,cells,meta)
    evidence=dict(dataset="formal_design_p0_v1",valid_llm_runs=len(llm),seeds=sorted(SEEDS),
                  units=dict(descriptive="run",paired="matched seed",profiles="seed cluster over six cells"),
                  valid_baseline_runs=480,matched_ablation_runs=40,
                  cell_run_count=20,matched_seeds_by_condition=matched,
                  initial_distribution_mismatches=mismatches,
                  excluded_runs=[dict(run_id=r["run_id"],design=r["design_id"],condition=r["condition_id"],seed=r["seed"])for r in excluded],
                  bootstrap=dict(samples=BOOTSTRAP_SAMPLES,interval="percentile 2.5% / 97.5%",rng_seed=20261015),
                  source_files={k:dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest())for k,p in SOURCES.items()},
                  api_calls=sum(int(r["llm_calls"])for r in llm),fallback_events=sum(int(r["fallback_count"])for r in llm),
                  frozen_profile_sha256=hashlib.sha256(SOURCES["profile"].read_bytes()).hexdigest())
    write_json("formal-provenance.json",evidence)
    if args.submission_root:
        inventory=[]
        for path in sorted(args.submission_root.rglob("*.csv")):
            rows=csv_rows(path)
            data=[r for r in rows if (r.get("run_id")or "").strip() and (r.get("seed")or "").strip()]
            counts=Counter(int(r["seed"])for r in data)
            inventory.append(dict(file=path.relative_to(args.submission_root).as_posix(),
                                  sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                  csv_rows=len(rows),data_rows=len(data),unique_seeds=sorted(counts),
                                  duplicate_seeds={str(k):v for k,v in counts.items()if v>1},
                                  decision_mechanisms=sorted({r["decision_mechanism"]for r in data}),
                                  llm_calls=sum(int(float(r.get("total_llm_calls")or 0))for r in data),
                                  absent_design_fields=[k for k in ("design_id","condition_id","valid_run")if k not in (rows[0]if rows else {})]))
        write_json("source-selection.json",dict(searched_collection="IFOU submission",files=inventory,
                    selected_dataset="formal_design_p0_v1",
                    selection_reason="The early CSVs compare local decision mechanisms. The formal dataset records all six design/condition cells with valid-run flags and seeds 101–120."))
    print(json.dumps(dict(llm_runs=len(llm),matched_seeds={k:len(v)for k,v in matched.items()},effects=effects,spatial=spatial),ensure_ascii=True))


if __name__=="__main__":
    main()
