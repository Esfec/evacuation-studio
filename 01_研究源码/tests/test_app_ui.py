from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_ui_exposes_policy_design_and_condition_selectors():
    app = Path(__file__).parents[1] / "app.py"
    at = AppTest.from_file(str(app)).run(timeout=30)
    labels = [widget.label for widget in at.selectbox]
    assert "决策策略" in labels
    assert "建筑设计" in labels
    assert "火灾工况" in labels
    assert len(at.exception) == 0
    number_labels = [widget.label for widget in at.number_input]
    assert "LLM 并发数" in number_labels


def test_ui_has_no_conflicting_policy_checkboxes():
    app = Path(__file__).parents[1] / "app.py"
    at = AppTest.from_file(str(app)).run(timeout=30)
    labels = [widget.label for widget in at.checkbox]
    assert not any("Mock 模式" in label for label in labels)
    assert not any("Random 模式" in label for label in labels)
    assert not any("Baseline_Rule" in label for label in labels)


def test_ui_initialization_applies_frozen_d2_c1_scenario():
    app = Path(__file__).parents[1] / "app.py"
    at = AppTest.from_file(str(app)).run(timeout=30)
    next(widget for widget in at.selectbox if widget.label == "建筑设计").set_value("D2")
    next(widget for widget in at.selectbox if widget.label == "火灾工况").set_value("C1")
    next(button for button in at.button if button.label == "🚀 初始化").click()
    at.run(timeout=30)

    assert len(at.exception) == 0
    engine = at.session_state.engine
    assert engine.run_config.design_id == "D2"
    assert engine.run_config.condition_id == "C1"
    assert engine.run_config.llm_concurrency == 8
    assert engine.nodes["N10"]["status"] == "Blocked"
    assert any(
        edge["source"] == "N06" and edge["target"] == "N08"
        for edge in engine.edges
    )


def test_ui_single_step_persists_an_audit_checkpoint():
    app = Path(__file__).parents[1] / "app.py"
    source = app.read_text(encoding="utf-8")

    assert "save_checkpoint_v4" in source
    single_step_block = source[source.index('if st.button("⏭ 单步执行"'):]
    single_step_block = single_step_block[:single_step_block.index("with col")]
    assert "save_checkpoint_v4" in single_step_block
