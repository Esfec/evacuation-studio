# 实验数据来源与独立复算

核查日期：2026-10-15。

## 当前 README 与本核查的关系

README 按作者指定的论文报告口径展示图表：每组合20次有效运行，配对效应沿用论文原有20 seed分析、报告区间与舍入精度。图表数据保存在 [paper-source-data.json](paper-source-data.json)，由 `scripts/build_paper_readme_figures.py` 生成 `paper-*` 图表。

下文保留归档数据的独立复算口径。`scripts/build_formal_readme_figures.py` 将复算产物写入被Git忽略的 `local-exports/formal-audit/`，使用经初始房间人数核对的配对子集，C0排除seed 117后为19组，C1为20组。这项核对事实不因论文图表的复现而改变。

| C0 配对效应，百分点 | 论文报告值 | 独立复算，19组 |
|---|---:|---:|
| D1 − D0 | +0.2 | −0.88 |
| D2 − D0 | −2.0 | −2.74 |

论文方法文字还存在三项待作者核对的差异：运行日期写为8月6—7日，归档时间为8月16—17日；D1主要描述为N06→N10扩容，清单记录双向扩容；初始位置列出7个候选节点，实际分配只出现N02—N05。本文仅记录差异，原论文与原始实验文件保持原样。

## 检索到的投稿材料

用户指定的 IFOU 投稿资料中，`疏散/实验1/` 包含三份早期策略比较表：

| 文件 | 数据行 | 唯一 seed | API 调用数 | 重复 seed |
|---|---:|---|---:|---|
| MOCK_exp1_mechanism_comparison.csv | 20 | 0–19 | 0 | 无 |
| RANDOM_exp1_mechanism_comparison.csv | 21 | 0–19 | 0 | 6 有两条 |
| RULE_exp1_mechanism_comparison.csv | 21 | 0–19 | 0 | 17 有两条 |

Random 表另有两条无 run ID/seed 的空记录。三份表均缺少 `design_id`、`condition_id` 和 `valid_run` 字段；内容是本地 Mock、Random、Rule 决策机制比较。`llm_model` 字段虽然写有模型名称，但调用计数全部为零。

这批材料作为早期实验留档。论文对应的完整正式矩阵为下述数据。逐文件检索清单保留在本地归档中，可通过文末命令重新生成。独立复算只依赖仓库内的正式 CSV。

## 独立复算使用的数据

| 用途 | 仓库内源文件 | 纳入情况 |
|---|---|---|
| LLM 设计比较 | `01_研究源码/results/processed/formal_design_p0_v1/paper_summary_v1.csv` | 121 行中 120 行 `valid_run=True` |
| 运行配置与初始分配 | 同目录 `summary_v4.csv` | 按 run ID 对齐 120 次有效运行 |
| 传统策略对照 | `01_研究源码/results/processed/formal_baselines_p0_v1/paper_summary_v1.csv` | 480 次有效运行 |
| 基线初始分配 | 同目录 `summary_v4.csv` | 核对 C1 的 D0/D2 配对 |
| C1 空间计数 | `01_研究源码/results/processed/matched_ablation/policy_diagnostic_run_metrics.csv` | 其中 40 行 LLM 的 D0/D2 运行 |
| LLM-off 对照 | `01_研究源码/results/processed/matched_ablation/llm_off_ablation_c1/run_summary.csv` | 40 次，含对应 LLM run ID 与初始分配 |
| 冻结画像 | `01_研究源码/agent_profiles/formal_profile_lock.json` 及对应 P0 配置 | SHA-256 核对通过 |

LLM 矩阵为三方案、两工况、seeds 101–120，每组合 20 次。每次 48 人，最多 30 步，起火点 N01。归档运行记录了 29,955 次 LLM 调用和 530 次规则兜底事件。该批统计与当前 `studio-1.5-llm-protocol` 的六组 seed 42 展示录制各自保留版本与来源。

## 有效运行和配对选择

API 无效运行 `20260816_190435_24ed4a9f`（D0/C0/seed 117）按其 `valid_run=False` 标记排除。后续有效重跑保留在描述统计中。

逐 seed 核对三个设计的 `actual_initial_distribution`，发现 C0/seed 117 有如下差异：

| 设计 | N02 | N03 | N04 | N05 |
|---|---:|---:|---:|---:|
| D0，有效重跑 | 16 | 6 | 11 | 15 |
| D1 | 15 | 16 | 6 | 11 |
| D2 | 15 | 16 | 6 | 11 |

因此采用两个明确的样本集合：

- **组合描述统计**：全部 120 次有效运行，每组合 20 次，报告各组均值。
- **LLM 设计配对效应**：同工况、同 seed，三个方案记录的初始房间人数分配一致。C0 使用 19 个 seed（排除 117），C1 使用全部 20 个。

配对结果由处理方案减 D0，逐 seed 的两个 run ID 与差值写入本地输出 `local-exports/formal-audit/formal-paired-source.csv`。本页重算采用上述筛选，因此 C0 配对结果与原归档分析报告的全 20 seed 版本存在差异。

## 图表与统计口径

- **逃生率**：使用整数 `escaped / total_agents`，避免归档小数舍入影响。
- **组合均值区间**：每组合的 20 个 seed 有放回抽样 20,000 次。
- **配对效应区间**：对筛选后的逐 seed 差值有放回抽样 20,000 次。
- **画像区间**：以 seed 为簇，每簇保留六个方案/工况组合，再对 20 簇进行 bootstrap。每类人数为 10、15、23，来自冻结 P0 实验人群。
- **区间与随机数**：95% 百分位区间（2.5%、97.5%），NumPy RNG seed `20261015`。每项指标重新初始化 RNG，保证重建稳定。
- **等待**：读取 `total_wait_events`，涵盖排队、体力等待及其他等待/受阻类别；`edge_queue_events` 另存于组合统计表。
- **烟雾**：每轮全体人员的累计相对暴露均值，再跨运行汇总。
- **空间变化**：20 次 C1 运行的 N04、其他房间和全体遇难计数。N04 为 128→47，其他房间为 396→456，全体为 524→503，差值满足 −81+60=−21。
- **策略比较**：四种基线、LLM 与匹配 LLM-off 在 C1 下比较 D2−D0，每种使用 20 个配对 seed。

独立复算图保持白色背景，输出 PNG 和文字可编辑的 SVG。全部统计源路径、源文件哈希、排除项和配对不一致记录见 [formal-provenance.json](formal-provenance.json)。

## 重建

在仓库根目录执行：

```text
python -m pip install -r requirements-figures.txt
python scripts/build_formal_readme_figures.py
```

可选：重新检查本地投稿目录并更新检索清单：

```text
python scripts/build_formal_readme_figures.py --submission-root "<IFOU投稿资料目录>"
```

脚本在 `local-exports/formal-audit/` 生成三张多 seed 图、六份派生 CSV 和来源 JSON。仓库只保留复算脚本、源数据和 [已核对的来源清单](formal-provenance.json)，衍生图表按需生成。当前归档材料提供运行汇总与 C1 空间诊断，因此独立复算图采用这些已保存指标。

## 论文图表的来源与导出

README的五组图使用 [paper-source-data.json](paper-source-data.json) 中的论文报告值：拓扑对应论文图2；总体结果对应表3、图3；空间变化对应图4；策略对照对应表4；画像表现对应图5。表格数值、区间和舍入精度沿用原文。组合误差线为SD，配对效应误差线为95% bootstrap置信区间。策略和画像面板展示原文点估计。

图表采用白底、Arial、低饱和灰蓝/灰绿/灰粉配色，宽度182.88 mm，网页PNG为360 dpi。默认重建只更新5张README图片：

```text
python scripts/build_paper_readme_figures.py
```

需要完整图表包时运行 `python scripts/build_paper_readme_figures.py --exports`，可编辑SVG、矢量PDF、PNG、CSV和导出哈希清单保存到 `local-exports/paper-figures/`。全部报告数值已保存在统一JSON中，因此这些派生格式无需重复提交。

精简前已对照论文核查114项数值，并检查五组图的可编辑文字和PDF边界；本地归档保留原导出及核验记录。仓库保留足以重建图表的数据、脚本和审计来源。
