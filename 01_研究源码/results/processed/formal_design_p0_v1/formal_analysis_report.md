# Formal paired design analysis

## Material passport

- Formal profile: P0 (`c48533b34eb9e37d1ae28ee4b3baa636e98f99be956adc657d0c148b08cc43b7`)
- Matrix: D0/D1/D2 × C0/C1 × 20 paired seeds (101–120)
- Valid cells: 120/120
- Excluded audit record: the first D0/C0/seed-117 run (`invalid_reason=api`)
- Model: DeepSeek `deepseek-v4-flash`
- Horizon: 30 steps; 5 s per step
- Population: 48 synthetic occupants per run

## Primary cell summaries

| Design | Condition | Escape rate, mean (SD) | Smoke exposure, mean (SD) | Wait events, mean | Backtracks, mean | Median escape step, mean |
|---|---|---:|---:|---:|---:|---:|
| D0 | C0 | 0.572 (0.060) | 2.854 (0.262) | 191.85 | 1.585 | 5.300 |
| D0 | C1 | 0.454 (0.036) | 3.325 (0.115) | 203.60 | 1.926 | 6.525 |
| D1 | C0 | 0.574 (0.060) | 2.794 (0.221) | 183.65 | 1.513 | 5.175 |
| D1 | C1 | 0.452 (0.037) | 3.422 (0.181) | 204.25 | 2.119 | 6.675 |
| D2 | C0 | 0.552 (0.060) | 2.908 (0.200) | 184.10 | 1.607 | 5.125 |
| D2 | C1 | 0.476 (0.041) | 3.311 (0.208) | 193.15 | 1.878 | 6.200 |

## Paired effects

Percentile intervals below are paired-seed bootstrap 95% intervals (20,000
resamples). Wilcoxon results are supportive and unadjusted; conclusions rely
on effect sizes, intervals, negative controls and mechanism consistency.

### C1 disruption effect within D0

- Escape rate: −0.118 (95% CI −0.149 to −0.084)
- Mean smoke exposure: +0.471 (0.354 to 0.580)
- Wait events: +11.75 (4.10 to 18.95)
- Mean backtracks: +0.341 (0.221 to 0.458)
- Median escape step: +1.225 (0.825 to 1.600)

### D1 versus D0

- C0 escape-rate difference: +0.002 (−0.031 to +0.040)
- C1 escape-rate difference: −0.002 (−0.025 to +0.021)
- C1 smoke exposure: +0.098 (+0.018 to +0.182)
- C1 backtracking: +0.193 (+0.023 to +0.368)

D1 has no detectable total escape benefit. Under C1, the widened N06↔N10
connection is inaccessible; D1/C1 therefore serves as a negative mechanism
control and quantifies residual LLM stochasticity.

### D2 versus D0

- C0 escape-rate difference: −0.020 (−0.056 to +0.019)
- C1 escape-rate difference: +0.022 (+0.002 to +0.042)
- C1 wait-event difference: −10.45 (−18.95 to −2.35)
- C1 smoke-exposure difference: −0.013 (−0.114 to +0.085)
- C1 backtrack difference: −0.048 (−0.183 to +0.088)
- Difference-in-differences for escape rate: +0.042 (−0.005 to +0.085)

The D2 escape-rate signal is modest: its paired bootstrap interval for the C1
cell excludes zero, while the Wilcoxon result and disruption
difference-in-differences remain borderline. The reduction in waiting and the
spatial failure mechanism provide stronger evidence than the total escape
rate alone.

## Failure-location mechanism

Across the 20 C1 runs:

| Final death node | D0 | D1 | D2 | D2−D0 |
|---|---:|---:|---:|---:|
| N04 | 128 | 116 | 47 | −81 |
| N06 | 45 | 69 | 26 | −19 |
| N13 | 47 | 48 | 67 | +20 |
| N08 | 38 | 44 | 62 | +24 |
| N14 | 29 | 39 | 48 | +19 |
| N09 | 20 | 20 | 42 | +22 |

D2 reduced N04 deaths by 4.05 agents per run (95% CI −5.40 to −2.70;
Wilcoxon p=0.00033). Total deaths fell by only 1.05 agents per run. Thus most
of the local N04 benefit was offset by downstream redistribution, especially
toward N08, N13, N14 and N09. D2 changes failure geography more strongly than
it changes the total number of failures.

## Synthetic-occupant diagnostics

Pooled across all 120 runs:

| Archetype | Escape rate | Smoke exposure | Backtracks | Final panic |
|---|---:|---:|---:|---:|
| Cognitive | 0.964 | 1.248 | 1.117 | 0.331 |
| Perceptual | 0.738 | 2.595 | 2.621 | 0.747 |
| Follower | 0.171 | 4.239 | 1.502 | 0.975 |

Stress overrides accounted for approximately 0–0.4% of Cognitive decisions,
5–10% of Perceptual decisions and 33–35% of Follower decisions, depending on
the D/C cell. These are operational manifestations of the frozen archetype
definitions and must not be presented as empirically estimated population
behaviour.

Under C1, D2 increased Cognitive escape by 5.0 percentage points and Follower
escape by 2.8 points relative to D0, while the Perceptual change was −0.7
points. All type-specific intervals include zero. The robust type-level result
is differential exposure and failure location, rather than a statistically
secure type-specific escape benefit.

## Baseline triangulation

All 480 no-API baseline runs were valid. D2 ranked highest under C1 for escape
rate in all four baselines:

| Policy | D0/C1 | D1/C1 | D2/C1 |
|---|---:|---:|---:|
| Local Rule | 0.342 | 0.342 | 0.418 |
| Global Shortest Path | 0.698 | 0.698 | 0.889 |
| Risk-aware Dijkstra | 0.857 | 0.857 | 0.881 |
| Random | 0.178 | 0.178 | 0.193 |
| LLM synthetic occupants | 0.454 | 0.452 | 0.476 |

The agreement supports the direction of the redundancy effect. The LLM result
adds local-observation, archetype and failure-redistribution diagnostics; it
does not outperform or replace the global algorithms.

## Computational audit

- Valid LLM decisions: 35,868
- API attempts: 29,955; successful: 29,955 (100%)
- Rule fallbacks: 530 (1.48% of decisions)
- Stress overrides: 5,913 (16.49%)
- Empty justifications: 0
- Invalid targets: 0
- Total tokens: 20,052,666
- Total recorded cost: USD 3.4878
- Total simulation wall time: 3.91 h
- Mean API latency: 2.47 s

The monetary cost per run was low (about USD 0.029), while latency remained
material. A single six-cell design screen at one seed would require roughly
12 minutes under the observed sequential setup; the 20-seed campaign is a
research validation workflow rather than an interactive design response.

## Claim ceiling

The supported claim is that auditable heterogeneous LLM synthetic occupants
can distinguish an inaccessible capacity intervention from a topological
redundancy intervention and expose how a design redistributes local failure
risk under dynamic fire, incomplete perception and congestion. The experiment
does not validate real human behaviour, predict code-compliant evacuation
times, or replace CFD/Pathfinder analysis.
