from types import SimpleNamespace

import pytest

from batch_runner import (
    build_matrix,
    completed_case_keys,
    filter_pending_cases,
    preflight_llm,
)


def test_matrix_has_six_dc_cells_and_paired_seeds():
    matrix = build_matrix(
        policies=["Local_Rule", "Global_ShortestPath"],
        designs=["D0", "D1", "D2"],
        conditions=["C0", "C1"],
        seeds=[1, 2],
    )
    assert len(matrix) == 24
    assert {item["seed"] for item in matrix} == {1, 2}
    assert len({
        (item["design_id"], item["condition_id"])
        for item in matrix
    }) == 6


def test_llm_preflight_fails_closed_before_formal_runs(monkeypatch):
    args = SimpleNamespace(
        provider="DeepSeek", model="deepseek-v4-flash"
    )
    matrix = [{"policy_id": "LLM_Agent"}]
    monkeypatch.setattr(
        "batch_runner.test_api_connection",
        lambda *args, **kwargs: (False, "model unavailable", 12),
    )

    with pytest.raises(RuntimeError, match="model unavailable"):
        preflight_llm(args, matrix, "test-key")


def test_completed_case_keys_reads_only_valid_rows(tmp_path):
    summary = tmp_path / "summary_v4.csv"
    summary.write_text(
        "policy_id,design_id,condition_id,seed,valid_run\n"
        "LLM_Agent,D0,C0,41,True\n"
        "LLM_Agent,D0,C1,41,False\n",
        encoding="utf-8",
    )
    assert completed_case_keys(tmp_path) == {
        ("LLM_Agent", "D0", "C0", 41)
    }


def test_filter_pending_cases_preserves_matrix_order():
    matrix = build_matrix(["LLM_Agent"], ["D0"], ["C0", "C1"], [41])
    pending = filter_pending_cases(
        matrix, {("LLM_Agent", "D0", "C0", 41)}
    )
    assert pending == [matrix[1]]
