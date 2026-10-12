# app.py — 完整版（含实验数据 Tab + 自动追加逻辑）

"""app.py — Streamlit 主应用入口"""
from analysis import build_analysis_html
import json
import os
import time

from renderer import build_floorplan_html, build_topology_html, build_dark_topology_html
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pathlib import Path
from recorder import (
    export_step_snapshots, export_agent_final, export_decision_log,
    export_movement_log, export_llm_call_log, export_model_performance,
    export_agent_type_comparison, export_node_occupancy, export_panic_events,
    export_escape_paths, export_simulation_meta, export_all_zip, get_summary,
    save_checkpoint_v4, save_run_v4,
    append_run_to_comparison,
    append_unified_log, export_unified_experiment_log,
    # ── 行为/空间分析（补充）────────────────────────
    export_panic_evolution,
    export_agent_step_panic,
    export_bottleneck_stats,
    export_node_heatmap,
    # ── 实验专项 ─────────────────────────────────────
    export_path_efficiency_analysis,
    append_exp1_mechanism_data,
    append_exp2_behavior_data,
    export_exp2_behavior_report,
    append_exp3_fire_data,
    append_exp4_composition_data,
    export_experiment_package_zip,
)
from config import (
    MAP_FILE, AGENT_FILE, LLM_PROVIDERS,
    DEFAULT_PROVIDER, DEFAULT_API_KEY,
    FORBIDDEN_START_NODES,
)
from engine import SimulationEngine
from llm_api import test_api_connection
from run_config import AgentCounts, RunConfig
from scenarios import apply_scenario, DESIGN_LABELS, CONDITION_LABELS

# ── 页面配置 ──
st.set_page_config(
    page_title="🔥 博物馆疏散仿真",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 加载数据 ──
@st.cache_data
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

APP_DIR = Path(__file__).resolve().parent
map_data   = load_json(APP_DIR / MAP_FILE)
agent_data = load_json(APP_DIR / AGENT_FILE)

# ── Session State 初始化 ──
for key, default in [
    ("engine", None), ("running", False), ("step", 0),
    ("last_sim_config", None),
    ("comparison_results", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ════════════════════════════════════════
# 侧边栏
# ════════════════════════════════════════
with st.sidebar:
    st.title("⚙️ 仿真设置")

    st.subheader("🤖 LLM 配置")
    provider = st.selectbox(
        "服务商", list(LLM_PROVIDERS.keys()),
        index=list(LLM_PROVIDERS.keys()).index(DEFAULT_PROVIDER),
    )
    model = st.selectbox("模型", LLM_PROVIDERS[provider]["models"])
    api_key = st.text_input(
        "API Key", value=os.environ.get(LLM_PROVIDERS[provider]["env_key"], ""),
        key=f"api_key_{provider}",
        type="password", placeholder="LLM 策略需要对应服务商的密钥",
    )
    policy_labels = {
        "LLM_Agent": "LLM Agent（局部不完全观测）",
        "Local_Rule": "局部规则（同等信息基线）",
        "Global_ShortestPath": "全局最短路径",
        "RiskAware_Dijkstra": "风险感知 Dijkstra",
        "Random": "随机游走（负对照）",
        "Mock_Heterogeneous": "异质 Mock（机制审计）",
    }
    policy_id = st.selectbox(
        "决策策略",
        options=list(policy_labels),
        index=1,
    )
    st.caption(policy_labels[policy_id])
    use_mock = policy_id == "Mock_Heterogeneous"
    use_random = policy_id == "Random"
    baseline_mode_on = policy_id == "Local_Rule"

    design_id = st.selectbox(
        "建筑设计",
        options=list(DESIGN_LABELS),
    )
    st.caption(f"{design_id}：{DESIGN_LABELS[design_id]}")
    condition_id = st.selectbox(
        "火灾工况",
        options=list(CONDITION_LABELS),
    )
    st.caption(f"{condition_id}：{CONDITION_LABELS[condition_id]}")
    run_mode = st.selectbox("运行模式", ["单次运行", "配对策略比较"])
    comparison_policies = []
    if run_mode == "配对策略比较":
        comparison_policies = st.multiselect(
            "比较策略",
            options=list(policy_labels),
            default=["LLM_Agent", "Local_Rule", "Global_ShortestPath"],
        )
        st.caption("；".join(policy_labels[item] for item in comparison_policies))
        if "LLM_Agent" in comparison_policies:
            st.warning("配对比较包含 LLM，将产生 API 调用和费用。")

    if st.button("🔌 测试 API 连接"):
        if api_key:
            with st.spinner("测试中..."):
                ok, msg, lat = test_api_connection(provider, api_key, model)
            if ok:
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")
        else:
            st.warning("请先填写 API Key")

    st.divider()

    # ── 🔥 起火点（必须在「初始房间分布」之前定义）──────────────────
    st.subheader("🔥 火灾参数")
    fire_rate = st.slider("火势蔓延速率", 0.05, 0.30, 0.10, step=0.01)

    # 改为
    risky_coeff = st.slider(
        "风险蔓延系数（Risky步 = 跳数 × 系数）",
        0.5, 8.0, 3.0, step=0.5,  # max 1.5→8.0, default 0.5→3.0
        help="值越大，节点越晚出现烟雾风险"
    )
    blocked_coeff = st.slider(
        "封堵蔓延系数（Blocked步 = 跳数 × 系数）",
        1.0, 15.0, 7.0, step=0.5,  # max 3.0→15.0, default 1.0→7.0
        help="值越大，节点越晚被完全封堵"
    )

    seed = st.number_input("随机种子", value=42, min_value=0)
    temperature = st.slider("LLM Temperature", 0.0, 1.0, 0.1, step=0.05)
    llm_concurrency = st.number_input(
        "LLM 并发数", min_value=1, max_value=32, value=8, step=1,
        help="同一步内先冻结所有 Agent 的观测，再并发请求；移动统一结算。",
    )
    min_hops = st.slider("起始点距出口最少跳数", 1, 6, 3, step=1,
                         help="Agent初始位置距最近出口至少需要几步，避免step0直接逃出")

    all_nodes = {
        n["id"]: n.get("name", n["id"])
        for n in map_data["nodes"]
        if n.get("type") not in ("exit", "deadend")
    }
    fire_origin_options = {f"{nid} ({name})": nid for nid, name in all_nodes.items()}
    selected_label = st.selectbox(
        "🔥 起火点",
        options=list(fire_origin_options.keys()),
        index=list(fire_origin_options.values()).index(
            map_data.get("fire_origin", "N01")
        ),
    )
    custom_fire_origin = fire_origin_options[selected_label]  # ← 在此处定义，供下方使用

    # ── 👥 Agent 数量 ──────────────────────────────────────────────
    st.subheader("👥 Agent 数量")
    n_cognitive  = st.slider("认知型 🔷", 1, 20, 10)
    n_perceptual = st.slider("感知型 🔶", 1, 25, 15)
    n_follower   = st.slider("跟随型 🔴", 1, 30, 23)

    # ── 🏠 初始房间分布（此处 custom_fire_origin 已有值）──────────
    st.subheader("🏠 初始房间分布")
    use_custom_dist = st.checkbox("自定义每房间初始人数", value=False)
    initial_distribution = None

    if use_custom_dist:
        default_dist = {
            n["id"]: 0
            for n in map_data["nodes"]
            if n.get("type") not in ("exit", "fire", "deadend")
               and n["id"] not in FORBIDDEN_START_NODES
               and n["id"] != custom_fire_origin  # ← 安全引用
        }
        dist_input = st.text_area(
            "填写各房间人数（JSON 格式）",
            value=json.dumps(default_dist, ensure_ascii=False, indent=2),
            height=220,
        )
        try:
            parsed = json.loads(dist_input)
            initial_distribution = {k: v for k, v in parsed.items() if v > 0}
            dist_total  = sum(initial_distribution.values())
            agent_total = n_cognitive + n_perceptual + n_follower
            if dist_total == agent_total:
                st.success(f"✅ 总人数匹配：{dist_total} 人")
            else:
                st.warning(
                    f"⚠️ 房间总人数 {dist_total} ≠ Agent 总数 {agent_total}，"
                    f"{'不足部分将随机补齐' if dist_total < agent_total else '超出部分将被截断'}"
                )
        except json.JSONDecodeError:
            st.error("❌ JSON 格式有误")
            initial_distribution = None

    # ── 🧪 实验标签配置 ────────────────────────────────────────────
    st.divider()
    st.subheader("🧪 实验标签配置")

    exp_selector = st.selectbox(
        "当前实验类型",
        ["实验一：决策机制对比", "实验二：Agent类型行为",
         "实验三：起火位置敏感性", "实验四：构成比例影响"],
        index=0,
    )

    crowd_config_label = f"{n_cognitive}C-{n_perceptual}P-{n_follower}F"
    st.caption(f"当前构成标签（自动生成）：`{crowd_config_label}`")

    st.caption(
        "实验一：固定地图+构成，切换4种机制各跑10次种子\n"
        "实验二：固定Mock+地图，观察类型行为差异\n"
        "实验三：固定机制+构成，遍历不同起火点\n"
        "实验四：固定机制+起火点，修改构成比例标签"
    )

    max_steps = st.slider("最大仿真步数", 1, 50, 30)

    current_signature = {
        "seed": int(seed),
        "policy_id": policy_id,
        "design_id": design_id,
        "condition_id": condition_id,
        "fire_origin": custom_fire_origin,
        "max_steps": int(max_steps),
        "agent_counts": {
            "Cognitive": n_cognitive,
            "Perceptual": n_perceptual,
            "Follower": n_follower,
        },
        "fire_rate": fire_rate,
        "risky_coeff": risky_coeff,
        "blocked_coeff": blocked_coeff,
        "temperature": temperature,
        "provider": provider,
        "model": model,
        "initial_distribution": initial_distribution,
        "min_hops_to_exit": min_hops,
        "llm_concurrency": llm_concurrency,
    }
    existing = st.session_state.engine
    frozen_signature = (
        {key: existing.run_config.to_dict().get(key) for key in current_signature}
        if existing is not None and getattr(existing, "run_config", None) is not None
        else None
    )
    config_dirty = frozen_signature is not None and current_signature != frozen_signature
    if config_dirty:
        st.warning("设置已改变，请重新初始化后再运行。")

    # ── ▶️ 仿真控制 ────────────────────────────────────────────────
    st.subheader("▶️ 仿真控制")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 初始化", use_container_width=True):
            if policy_id == "LLM_Agent" and not api_key.strip():
                st.error("LLM_Agent 需要 API Key；不调用 API 请显式选择规则策略。")
                st.stop()
            run_config = RunConfig(
                seed=int(seed),
                policy_id=policy_id,
                design_id=design_id,
                condition_id=condition_id,
                fire_origin=custom_fire_origin,
                max_steps=int(max_steps),
                agent_counts=AgentCounts(
                    n_cognitive, n_perceptual, n_follower
                ),
                fire_rate=fire_rate,
                risky_coeff=risky_coeff,
                blocked_coeff=blocked_coeff,
                temperature=temperature,
                provider=provider,
                model=model,
                experiment_type=exp_selector,
                initial_distribution=initial_distribution,
                min_hops_to_exit=min_hops,
                llm_concurrency=int(llm_concurrency),
            )
            scenario_map, intervention_manifest = apply_scenario(
                map_data, design_id, condition_id,
                run_config.base_edge_capacity,
            )
            eng = SimulationEngine(
                scenario_map, agent_data,
                api_key=api_key if policy_id == "LLM_Agent" else "",
                api_provider=provider,
                api_model=model,
                seed=int(seed),
                temperature=temperature,
                fire_origin=custom_fire_origin,
                risky_coeff=risky_coeff,
                blocked_coeff=blocked_coeff,
                fire_rate=fire_rate,
                run_config=run_config,
                intervention_manifest=intervention_manifest,
            )
            eng.initialize_agents(
                n_cognitive, n_perceptual, n_follower,
                initial_distribution=initial_distribution,
                min_hops_to_exit=min_hops,
            )
            st.session_state.engine  = eng
            st.session_state.step    = 0
            st.session_state.running = False
            st.success(
                f"已初始化：{policy_id} · {design_id}/{condition_id} · "
                f"起火点 {custom_fire_origin}"
            )

    with col2:
        if st.button("⏭ 单步执行", use_container_width=True, disabled=config_dirty):
            if st.session_state.engine:
                st.session_state.engine.run_step()
                st.session_state.step += 1
                checkpoint_dir = save_checkpoint_v4(
                    st.session_state.engine, "results/ui_runs"
                )
                st.session_state.last_checkpoint_dir = str(checkpoint_dir)
            else:
                st.warning("请先初始化")

    if st.button("⚡ 自动运行", use_container_width=True, disabled=config_dirty):
        if st.session_state.engine:
            st.session_state.running = True
        else:
            st.warning("请先初始化")

    if run_mode == "配对策略比较":
        if st.button("🧪 运行配对比较", use_container_width=True):
            if not comparison_policies:
                st.warning("请至少选择一种策略")
            elif "LLM_Agent" in comparison_policies and not api_key:
                st.error("配对比较包含 LLM_Agent，请先填写 API Key")
            else:
                comparison_rows = []
                with st.spinner("正在以相同地图、构成和随机种子运行配对比较..."):
                    for compared_policy in comparison_policies:
                        compared_config = RunConfig(
                            seed=int(seed),
                            policy_id=compared_policy,
                            design_id=design_id,
                            condition_id=condition_id,
                            fire_origin=custom_fire_origin,
                            max_steps=int(max_steps),
                            agent_counts=AgentCounts(
                                n_cognitive, n_perceptual, n_follower
                            ),
                            fire_rate=fire_rate,
                            risky_coeff=risky_coeff,
                            blocked_coeff=blocked_coeff,
                            temperature=temperature,
                            provider=provider,
                            model=model,
                            experiment_type="paired_ui",
                            initial_distribution=initial_distribution,
                            min_hops_to_exit=min_hops,
                            llm_concurrency=int(llm_concurrency),
                        )
                        compared_map, compared_manifest = apply_scenario(
                            map_data, design_id, condition_id,
                            compared_config.base_edge_capacity,
                        )
                        compared_engine = SimulationEngine(
                            compared_map,
                            agent_data,
                            api_key=(api_key if compared_policy == "LLM_Agent" else ""),
                            api_provider=provider,
                            api_model=model,
                            seed=int(seed),
                            temperature=temperature,
                            fire_origin=custom_fire_origin,
                            risky_coeff=risky_coeff,
                            blocked_coeff=blocked_coeff,
                            fire_rate=fire_rate,
                            run_config=compared_config,
                            intervention_manifest=compared_manifest,
                        )
                        compared_engine.initialize_agents(
                            n_cognitive,
                            n_perceptual,
                            n_follower,
                            initial_distribution=initial_distribution,
                            min_hops_to_exit=min_hops,
                        )
                        while (
                            compared_engine.current_step < compared_config.max_steps
                            and compared_engine.get_statistics()["active"] > 0
                        ):
                            compared_engine.run_step()
                        result_stats = compared_engine.get_statistics()
                        save_run_v4(compared_engine, "results/ui_runs")
                        comparison_rows.append({
                            "策略": compared_policy,
                            "设计": design_id,
                            "工况": condition_id,
                            "种子": int(seed),
                            "逃生": result_stats["escaped"],
                            "死亡": result_stats["dead"],
                            "体力耗尽": result_stats["exhausted"],
                            "仍在场": result_stats["active"],
                            "步数": compared_engine.current_step,
                            "有效运行": compared_engine.valid_run,
                            "规则回退": compared_engine.fallback_count,
                        })
                        st.session_state.engine = compared_engine
                        st.session_state.step = compared_engine.current_step
                st.session_state.comparison_results = comparison_rows
                st.success("配对比较完成，结果已自动记录。")

        if st.session_state.comparison_results:
            st.dataframe(
                pd.DataFrame(st.session_state.comparison_results),
                hide_index=True,
                use_container_width=True,
            )

    # ── 火势封堵时间表预览 ─────────────────────────────────────────
    if st.session_state.engine is not None:
        eng_prev = st.session_state.engine
        st.caption(
            f"当前冻结配置：{eng_prev.policy_id} · "
            f"{eng_prev.run_config.design_id}/{eng_prev.run_config.condition_id}"
        )
        with st.expander("🏗️ 设计与工况变换", expanded=False):
            st.json(eng_prev.intervention_manifest)
        with st.expander("🗓️ 自动生成的封堵时间表", expanded=False):
            rows = []
            for nid, nd in sorted(eng_prev.nodes.items()):
                evts = nd.get("events", {})
                if not evts:
                    continue
                risky_s = next(
                    (int(k) for k, v in sorted(evts.items(), key=lambda x: int(x[0]))
                     if v.get("status") == "Risky"), None)
                blocked_s = next(
                    (int(k) for k, v in sorted(evts.items(), key=lambda x: int(x[0]))
                     if v.get("status") == "Blocked"), None)
                rows.append({
                    "节点":        nid,
                    "名称":        nd.get("name", nid),
                    "→Risky步":   risky_s   if risky_s is not None else "—",
                    "→Blocked步": blocked_s if blocked_s is not None else "—",
                })
            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("（初始化后显示）")
    # ──────────────────────────────────────────────────────────────

# ════════════════════════════════════════
# 自动运行逻辑
# ════════════════════════════════════════
if st.session_state.running and st.session_state.engine:
    eng   = st.session_state.engine
    stats = eng.get_statistics()
    frozen_max_steps = (
        eng.run_config.max_steps
        if getattr(eng, "run_config", None) is not None else max_steps
    )
    if config_dirty:
        st.session_state.running = False
        save_run_v4(eng, "results/ui_runs")
        st.warning("设置已改变，自动运行已停止。请重新初始化。")
    elif st.session_state.step < frozen_max_steps and stats["active"] > 0:
        eng.run_step()
        st.session_state.step += 1
        time.sleep(0.05)
        st.rerun()
    else:
        st.session_state.running = False

        # ── 推断决策机制标签 ────────────────────────────
        _mech = eng.policy_id

        _sim_cfg = {
            'seed':                int(seed),
            'decision_mechanism':  _mech,
            'llm_model':           model,
            'llm_provider':        provider,
            'fire_spread_rate':    fire_rate,
            'n_cognitive':         n_cognitive,
            'n_perceptual':        n_perceptual,
            'n_follower':          n_follower,
            'scenario':            custom_fire_origin,
            'design_id':           eng.run_config.design_id,
            'condition_id':        eng.run_config.condition_id,
            'crowd_config':        crowd_config_label,
        }
        st.session_state.last_sim_config = _sim_cfg

        # ── 通用追加 ───────────────────────────────────
        append_run_to_comparison(eng, filepath='run_comparison.csv',
                                 sim_config=_sim_cfg)
        append_unified_log(eng, filepath='unified_experiment_log.csv',
                           sim_config=_sim_cfg)

        # ── 实验专项追加（根据当前实验类型，互斥执行）────
        if "实验一" in exp_selector:
            append_exp1_mechanism_data(eng,
                                       filepath='exp1_mechanism_comparison.csv',
                                       sim_config=_sim_cfg)
        elif "实验二" in exp_selector:
            append_exp2_behavior_data(eng,
                                      filepath='exp2_behavior_timeseries.csv',
                                      sim_config=_sim_cfg)
        elif "实验三" in exp_selector:
            append_exp3_fire_data(eng,
                                  filepath='exp3_fire_sensitivity.csv',
                                  sim_config=_sim_cfg)
        elif "实验四" in exp_selector:
            append_exp4_composition_data(eng,
                                         filepath='exp4_composition_comparison.csv',
                                         sim_config=_sim_cfg)

        st.toast("✅ 本次数据已追加至实验专项文件", icon="💾")

# ════════════════════════════════════════
# 主界面
# ════════════════════════════════════════
st.title("🔥 博物馆火灾疏散 Agent 仿真")

if st.session_state.engine is None:
    st.info("👈 请在左侧侧边栏点击「🚀 初始化」开始仿真")
    st.stop()

eng   = st.session_state.engine
step  = st.session_state.step
stats = eng.get_statistics()

# ── 顶部统计卡片 ──
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("总人数",   stats["total"])
c2.metric("逃生 ✅",  stats["escaped"],
          delta=f"+{stats['escaped']}" if stats['escaped'] else None,
          delta_color="normal")
c3.metric("遇难 💀",  stats["dead"],
          delta=f"+{stats['dead']}" if stats['dead'] else None,
          delta_color="inverse")
c4.metric("仍在场",   stats["active"])
c5.metric("平均恐慌", f"{stats['avg_panic']:.2f}")

st.divider()

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🗺️ 平面图", "🔗 拓扑图", "📊 统计", "📋 决策日志",
    "📈 群体分析", "📦 数据导出", "🧪 实验数据",
])

# ── Tab1：平面图 ──
with tab1:
    html = build_dark_topology_html(eng, step)
    components.html(html, height=1020, scrolling=True)

# ── Tab2：拓扑图 ──
with tab2:
    html = build_topology_html(eng, step)
    components.html(html, height=740, scrolling=True)
    ts = stats.get("type_stats", {})
    if ts:
        rows = []
        for t, d in ts.items():
            rows.append({
                "类型": t,
                "总数": d["total"],
                "逃生": d["escaped"],
                "遇难": d["dead"],
                "存活率": f"{(d['escaped']/d['total']*100):.1f}%",
                "平均恐慌": d["avg_panic"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)

    if eng.logs:
        df = pd.DataFrame(eng.logs)
        st.subheader("历史移动记录")
        st.dataframe(df.tail(50), use_container_width=True)

    if eng.token_usage["calls"] > 0:
        st.subheader("💰 Token 用量")
        tu = eng.token_usage
        st.write(f"调用次数: {tu['calls']} | "
                 f"Prompt: {tu['prompt']} | "
                 f"Completion: {tu['completion']} | "
                 f"Reasoning: {tu['reasoning_tokens']}")

# ── Tab3：统计 ──
with tab3:
    if eng.cot_logs:
        cot_df = pd.DataFrame(eng.cot_logs)
        cols = ["step", "agent_id", "agent_type", "decision_mode",
                "panic_level", "health", "chosen_target", "thought"]
        show_cols = [c for c in cols if c in cot_df.columns]
        st.dataframe(cot_df[show_cols].tail(100), use_container_width=True)

        with st.expander("查看最新 LLM 原始输出"):
            last_llm = [l for l in eng.cot_logs if l.get("llm_prompt")]
            if last_llm:
                latest = last_llm[-1]
                st.text_area("Prompt", latest["llm_prompt"], height=300)
                st.text_area("Response", latest["llm_response"], height=150)
    else:
        st.info("暂无统计数据，请先运行仿真")

# ── Tab4：决策日志 ──
with tab4:
    if eng.cot_logs:
        st.subheader("📋 完整决策日志")
        cot_df = pd.DataFrame(eng.cot_logs)

        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            types = ["全部"] + sorted(cot_df["agent_type"].dropna().unique().tolist()) \
                if "agent_type" in cot_df.columns else ["全部"]
            sel_type = st.selectbox("Agent 类型", types, key="tab4_type")
        with fc2:
            modes = ["全部"] + sorted(cot_df["decision_mode"].dropna().unique().tolist()) \
                if "decision_mode" in cot_df.columns else ["全部"]
            sel_mode = st.selectbox("决策模式", modes, key="tab4_mode")
        with fc3:
            sel_step = st.slider(
                "步骤范围",
                min_value=int(cot_df["step"].min()) if "step" in cot_df.columns else 0,
                max_value=int(cot_df["step"].max()) if "step" in cot_df.columns else 1,
                value=(
                    int(cot_df["step"].min()) if "step" in cot_df.columns else 0,
                    int(cot_df["step"].max()) if "step" in cot_df.columns else 1,
                ),
                key="tab4_step",
            )

        filtered = cot_df.copy()
        if sel_type != "全部" and "agent_type" in filtered.columns:
            filtered = filtered[filtered["agent_type"] == sel_type]
        if sel_mode != "全部" and "decision_mode" in filtered.columns:
            filtered = filtered[filtered["decision_mode"] == sel_mode]
        if "step" in filtered.columns:
            filtered = filtered[
                (filtered["step"] >= sel_step[0]) &
                (filtered["step"] <= sel_step[1])
            ]

        st.caption(f"显示 {len(filtered)} 条 / 共 {len(cot_df)} 条")
        detail_cols = [
            "step", "agent_id", "agent_type", "decision_mode",
            "panic_level", "chosen_target", "thought",
            "model", "prompt_tokens", "completion_tokens", "latency_ms",
        ]
        show_cols = [c for c in detail_cols if c in filtered.columns]
        st.dataframe(filtered[show_cols], use_container_width=True)

        llm_rows = [l for l in eng.cot_logs if l.get("reasoning")]
        if llm_rows:
            st.subheader("🧠 Reasoning 详情")
            idx = st.selectbox(
                "选择记录",
                options=range(len(llm_rows)),
                format_func=lambda i: (
                    f"Step {llm_rows[i].get('step','')} · "
                    f"{llm_rows[i].get('agent_id','')} · "
                    f"{llm_rows[i].get('agent_type','')}"
                ),
                key="tab4_reasoning_sel",
            )
            sel = llm_rows[idx]
            st.text_area("Reasoning", sel.get("reasoning", ""), height=200)
            st.text_area("Thought",   sel.get("thought", ""),   height=100)
    else:
        st.info("暂无决策日志，请先运行仿真")

# ── Tab5：群体分析 ──
with tab5:
    if eng is not None:
        html = build_analysis_html(eng, step)
        components.html(html, height=980, scrolling=True)
    else:
        st.info("尚无决策日志，请先运行仿真")

# ── Tab6：数据导出 ──
with tab6:
    eng_export = st.session_state.get("engine", None)
    if eng_export is not None:
        sm = get_summary(eng_export)
        st.markdown(
            f"当前仿真 **`{getattr(eng_export, 'run_id', '—')}`** · "
            f"**{sm['steps']}** 步 · **{sm['agents']}** 个 Agent · "
            f"**{sm['llm_calls']}** 次 LLM 调用 · "
            f"**{sm['total_tokens']:,}** tokens · "
            f"**≈ ${sm['total_cost_usd']:.4f}** 估算成本"
        )
        st.divider()

        st.markdown("**🧪 统一实验日志（跨实验分析核心文件）**")

        _tab6_mech = ('Mock' if use_mock else
                      'Random' if use_random else
                      'Baseline_Rule' if baseline_mode_on else
                      ('LLM_API' if api_key else 'Rule'))

        st.download_button(
            label="📥 下载本次统一日志（unified_experiment_log）",
            data=export_unified_experiment_log(eng_export, {
                'seed': int(seed),
                'decision_mechanism': _tab6_mech,
                'llm_model': model,
                'llm_provider': provider,
                'fire_spread_rate': fire_rate,
            }),
            file_name=f"{getattr(eng_export, 'run_id', 'run')}_unified_log.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.caption("每行=一次决策，含实验元信息+步骤状态+Agent状态+决策+LLM数据")
        st.divider()

        st.markdown("**🔬 LLM 性能与成本**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "📥 LLM 调用原始日志",
                data=export_llm_call_log(eng_export),
                file_name="llm_call_log.csv", mime="text/csv",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                "📥 模型性能汇总",
                data=export_model_performance(eng_export),
                file_name="model_performance.csv", mime="text/csv",
                use_container_width=True,
            )
        with col3:
            st.download_button(
                "📥 Agent 类型对比",
                data=export_agent_type_comparison(eng_export),
                file_name="agent_type_comparison.csv", mime="text/csv",
                use_container_width=True,
            )

        st.markdown("**📊 群体行为**")
        col4, col5, col6 = st.columns(3)
        with col4:
            st.download_button("📥 步骤快照", data=export_step_snapshots(eng_export),
                               file_name="step_snapshot.csv", mime="text/csv",
                               use_container_width=True)
        with col5:
            st.download_button("📥 节点占用快照", data=export_node_occupancy(eng_export),
                               file_name="node_occupancy.csv", mime="text/csv",
                               use_container_width=True)
        with col6:
            st.download_button("📥 恐慌事件日志", data=export_panic_events(eng_export),
                               file_name="panic_events.csv", mime="text/csv",
                               use_container_width=True)

        st.markdown("**🧍 个体轨迹**")
        col7, col8, col9 = st.columns(3)
        with col7:
            st.download_button("📥 Agent 最终状态", data=export_agent_final(eng_export),
                               file_name="agent_final.csv", mime="text/csv",
                               use_container_width=True)
        with col8:
            st.download_button("📥 移动轨迹", data=export_movement_log(eng_export),
                               file_name="movement_log.csv", mime="text/csv",
                               use_container_width=True)
        with col9:
            st.download_button("📥 逃生路径分析", data=export_escape_paths(eng_export),
                               file_name="escape_paths.csv", mime="text/csv",
                               use_container_width=True)

        st.markdown("**📋 决策与元信息**")
        col10, col11 = st.columns(2)
        with col10:
            st.download_button("📥 决策日志（含 token）",
                               data=export_decision_log(eng_export),
                               file_name="decision_log.csv", mime="text/csv",
                               use_container_width=True)
        with col11:
            st.download_button("📥 仿真元信息",
                               data=export_simulation_meta(eng_export),
                               file_name="simulation_meta.csv", mime="text/csv",
                               use_container_width=True)
    else:
        st.info("尚未运行仿真，请先在侧边栏点击「运行仿真」")

# ════════════════════════════════════════
# Tab7：实验数据
# ════════════════════════════════════════
with tab7:
    eng_exp = st.session_state.get("engine", None)

    if eng_exp is None:
        st.info("👈 请先初始化并运行仿真")
        st.stop()

    _cfg = st.session_state.get("last_sim_config") or {
        'seed': int(seed),
        'decision_mechanism': ('Mock' if use_mock else 'Random' if use_random
                               else 'Baseline_Rule' if baseline_mode_on
                               else 'LLM_API' if api_key else 'Rule'),
        'llm_model': model,
        'llm_provider': provider,
        'fire_spread_rate': fire_rate,
        'n_cognitive': n_cognitive,
        'n_perceptual': n_perceptual,
        'n_follower': n_follower,
        'scenario': custom_fire_origin,
        'crowd_config': crowd_config_label,
    }

    run_id = getattr(eng_exp, 'run_id', 'run')

    st.markdown("### 🧪 实验专项数据导出")
    st.caption(
        f"当前运行：`{run_id}` · "
        f"机制：`{_cfg.get('decision_mechanism')}` · "
        f"起火点：`{_cfg.get('scenario')}` · "
        f"构成：`{_cfg.get('crowd_config')}` · "
        f"种子：`{_cfg.get('seed')}`"
    )
    st.divider()

    # ── 实验一 ──────────────────────────────────────────────────────
    with st.expander("📊 实验一：决策机制对比数据", expanded=True):
        st.markdown(
            "每次运行自动追加到 `exp1_mechanism_comparison.csv`。\n\n"
            "**包含字段**：逃生率、首次逃出步、平均逃生步数、路径效率（BFS最优/实际）、"
            "回溯率、死胡同率、恐慌均值、LLM降级率、成本。\n\n"
            "**使用方法**：4种机制各运行10次不同种子后，下载该文件做 Kruskal-Wallis 检验。"
        )
        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button(
                label="📥 本次运行逐Agent路径效率",
                data=export_path_efficiency_analysis(eng_exp),
                file_name=f"{run_id}_path_efficiency.csv",
                mime="text/csv",
                use_container_width=True,
                help="含optimal_hops / actual_steps / backtrack / dead_end_visits",
            )
        with col_b:
            if os.path.exists('exp1_mechanism_comparison.csv'):
                try:
                    df_exp1 = pd.read_csv('exp1_mechanism_comparison.csv')
                    st.download_button(
                        label=f"📥 实验一累计数据（共{len(df_exp1)}行）",
                        data=df_exp1.to_csv(index=False),
                        file_name="exp1_mechanism_comparison.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                    st.caption(
                        f"已累计 {len(df_exp1)} 次运行 · "
                        f"机制分布：{df_exp1['decision_mechanism'].value_counts().to_dict()}"
                    )
                except Exception:
                    st.info("exp1_mechanism_comparison.csv 读取失败，请运行一次仿真后再试")
            else:
                st.info("运行仿真后此处将显示累计数据下载按钮")

    # ── 实验二 ──────────────────────────────────────────────────────
    with st.expander("🧠 实验二：Agent类型行为差异数据", expanded=True):
        st.markdown(
            "**包含字段**：每步×每类型的恐慌均值/标准差、决策模式分布（Mock/Panic_Follow/LLM等）、"
            "死胡同进入次数、被拥堵次数。\n\n"
            "**使用方法**：直接导入 pandas/matplotlib 绘制恐慌演化曲线和决策模式堆积图。"
        )
        col_c, col_d, col_e = st.columns(3)
        with col_c:
            st.download_button(
                label="📥 类型行为差异报告（逐步）",
                data=export_exp2_behavior_report(eng_exp),
                file_name=f"{run_id}_exp2_behavior.csv",
                mime="text/csv",
                use_container_width=True,
                help="每行 = agent_type × step，含恐慌统计+决策模式分布",
            )
        with col_d:
            st.download_button(
                label="📥 恐慌演化（均值±标准差）",
                data=export_panic_evolution(eng_exp),
                file_name=f"{run_id}_panic_evolution.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_e:
            st.download_button(
                label="📥 逐Agent逐步恐慌轨迹",
                data=export_agent_step_panic(eng_exp),
                file_name=f"{run_id}_agent_step_panic.csv",
                mime="text/csv",
                use_container_width=True,
                help="可绘制个体轨迹折线图或 agent×step 热力矩阵",
            )

        # ── 类型对比表预览（本次运行）──────────────────────────────
        st.markdown("**📋 Agent类型指标预览（本次运行）**")
        try:
            import io
            df_type = pd.read_csv(
                io.StringIO(export_agent_type_comparison(eng_exp))
            )
            display_cols = [
                'agent_type', 'escape_rate', 'avg_escape_steps',
                'avg_final_panic', 'avg_backtrack',
                'panic_follow_ratio', 'dominant_decision_mode',
            ]
            show = [c for c in display_cols if c in df_type.columns]
            st.dataframe(df_type[show], use_container_width=True)
        except Exception as e:
            st.caption(f"预览加载失败：{e}")

        # ── 实验二累计文件预览（与上方预览无关，始终显示）──────────
        st.divider()
        if os.path.exists('exp2_behavior_timeseries.csv'):
            try:
                df_exp2 = pd.read_csv('exp2_behavior_timeseries.csv')
                st.download_button(
                    label=f"📥 实验二累计数据（共{len(df_exp2)}行）",
                    data=df_exp2.to_csv(index=False),
                    file_name="exp2_behavior_timeseries.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
                st.caption(
                    f"已累计 {df_exp2['run_id'].nunique()} 次运行 · "
                    f"步数范围：{df_exp2['step'].min()}~{df_exp2['step'].max()}"
                )
            except Exception as e:
                st.info(f"exp2_behavior_timeseries.csv 读取失败：{e}")
        else:
            st.info("选择「实验二」运行后此处将显示累计数据")

    # ── 实验三 ──────────────────────────────────────────────────────
    with st.expander("🔥 实验三：起火位置敏感性数据", expanded=True):
        st.markdown(
            "每次运行自动追加到 `exp3_fire_sensitivity.csv`。\n\n"
            "**包含字段**：起火点ID/名称、整体逃生率、分类型逃生率、首次逃出步、"
            "达到50%逃生步数、各类型恐慌峰值、Top3瓶颈节点、关键出口最大占用。\n\n"
            "**使用方法**：遍历10个起火点后，按 `fire_origin` 分组绘制脆弱性热力图。"
        )
        col_f, col_g = st.columns(2)
        with col_f:
            st.download_button(
                label="📥 本次起火点数据",
                data=export_simulation_meta(eng_exp, _cfg),
                file_name=f"{run_id}_meta_{_cfg.get('scenario','')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_g:
            if os.path.exists('exp3_fire_sensitivity.csv'):
                try:
                    df_exp3 = pd.read_csv('exp3_fire_sensitivity.csv')
                    st.download_button(
                        label=f"📥 实验三累计数据（共{len(df_exp3)}行）",
                        data=df_exp3.to_csv(index=False),
                        file_name="exp3_fire_sensitivity.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                    st.caption(
                        f"已累计 {len(df_exp3)} 个场景 · "
                        f"起火点分布：{df_exp3['fire_origin'].value_counts().to_dict()}"
                    )
                except Exception:
                    st.info("exp3_fire_sensitivity.csv 读取失败")
            else:
                st.info("切换不同起火点运行后此处将显示累计数据")

        st.markdown("**🗺️ 空间拥堵数据（本次运行）**")
        col_h, col_i = st.columns(2)
        with col_h:
            st.download_button(
                label="📥 瓶颈节点滞留分析",
                data=export_bottleneck_stats(eng_exp),
                file_name=f"{run_id}_bottleneck.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_i:
            st.download_button(
                label="📥 节点热力统计",
                data=export_node_heatmap(eng_exp),
                file_name=f"{run_id}_node_heatmap.csv",
                mime="text/csv",
                use_container_width=True,
            )

    # ── 实验四 ──────────────────────────────────────────────────────
    with st.expander("👥 实验四：构成比例影响数据", expanded=True):
        st.markdown(
            "每次运行自动追加到 `exp4_composition_comparison.csv`。\n\n"
            "**包含字段**：构成标签(crowd_config)、整体逃生率、分类型逃生率/步数/恐慌/回溯、"
            "每5步检查点逃生人数（疏散进程曲线）、关键节点最大占用。\n\n"
            "**使用方法**：7种构成 × 5个种子 = 35行后，按 `crowd_config` 分组分析。"
        )
        col_j, col_k = st.columns(2)
        with col_j:
            st.download_button(
                label="📥 步骤快照（疏散进程原始数据）",
                data=export_step_snapshots(eng_exp),
                file_name=f"{run_id}_step_snapshot.csv",
                mime="text/csv",
                use_container_width=True,
                help="含每步累计逃生人数，可直接绘制S型疏散进程曲线",
            )
        with col_k:
            if os.path.exists('exp4_composition_comparison.csv'):
                try:
                    df_exp4 = pd.read_csv('exp4_composition_comparison.csv')
                    st.download_button(
                        label=f"📥 实验四累计数据（共{len(df_exp4)}行）",
                        data=df_exp4.to_csv(index=False),
                        file_name="exp4_composition_comparison.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                    st.caption(
                        f"已累计 {len(df_exp4)} 次运行 · "
                        f"构成分布：{df_exp4['crowd_config'].value_counts().to_dict()}"
                    )
                except Exception:
                    st.info("exp4_composition_comparison.csv 读取失败")
            else:
                st.info("修改构成比例标签并运行后此处将显示累计数据")

    # ── 一键打包 ────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📦 本次实验数据完整包")
    st.caption(
        "包含：路径效率、行为报告、恐慌演化、逐步恐慌、恐慌事件、"
        "瓶颈统计、节点热力图、步骤快照、逃生路径、Agent最终状态、"
        "仿真元信息、统一日志，共13个CSV文件。"
    )
    st.download_button(
        label="📦 下载本次完整实验数据包（ZIP）",
        data=export_experiment_package_zip(eng_exp, _cfg),
        file_name=f"{run_id}_experiment_package.zip",
        mime="application/zip",
        use_container_width=True,
        type="primary",
    )

    # ── 清除累计数据 ────────────────────────────────────────────────
    st.markdown("### 🗑️ 清除累计数据")
    st.warning("清除后不可恢复，请确认已下载备份")

    cols = st.columns(4)
    files_to_clear = {
        "实验一": "exp1_mechanism_comparison.csv",
        "实验二": "exp2_behavior_timeseries.csv",
        "实验三": "exp3_fire_sensitivity.csv",
        "实验四": "exp4_composition_comparison.csv",
    }
    for i, (label, fpath) in enumerate(files_to_clear.items()):
        with cols[i]:
            if os.path.exists(fpath):
                if st.button(f"🗑️ 清除{label}", use_container_width=True):
                    os.remove(fpath)
                    st.success(f"已清除 {fpath}")
                    st.rerun()
            else:
                st.caption(f"{label}：无数据")
