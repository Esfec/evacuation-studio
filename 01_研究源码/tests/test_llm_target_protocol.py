"""studio-1.5 LLM output protocol: audited target repair and corrective retries."""
from engine import resolve_llm_target, llm_retry_feedback

PATHS = [
    {"target_id": "N03", "target_name": "展室"},
    {"target_id": "N05", "target_name": "中走廊"},
    {"target_id": "N13", "target_name": "临时展区"},
]


def pick(value):
    path, how = resolve_llm_target({"target_id": value}, PATHS)
    return (path or {}).get("target_id"), how


def test_exact_id_is_unchanged():
    assert pick("N05") == ("N05", None)


def test_case_and_whitespace_are_marked():
    assert pick("n05") == ("N05", "id_case")
    assert pick(" N05 ") == ("N05", "id_case")


def test_single_allowed_id_inside_text():
    assert pick("N05 中走廊") == ("N05", "id_in_text")
    assert pick("前往N13") == ("N13", "id_in_text")


def test_unique_allowed_name_maps_to_id():
    assert pick("中走廊") == ("N05", "name")


def test_ambiguous_or_unknown_values_stay_invalid():
    assert pick("N05 或 N03") == (None, None)
    assert pick("N05 不去N02") == (None, None)       # mentions a non-option ID
    assert pick("过厅") == (None, None)               # not a local option (e.g. current room)
    assert pick("N02") == (None, None)
    assert pick("") == (None, None)
    assert resolve_llm_target({"target_id": 5}, PATHS) == (None, None)
    assert resolve_llm_target([], PATHS) == (None, None)


def test_duplicate_names_are_never_guessed():
    paths = PATHS + [{"target_id": "N09", "target_name": "中走廊"}]
    assert resolve_llm_target({"target_id": "中走廊"}, paths) == (None, None)


def test_feedback_restates_protocol_without_new_facts():
    allowed = "N03=展室, N05=中走廊"
    text = llm_retry_feedback("invalid_target", "", {"target_id": "过厅"}, allowed)
    assert "「过厅」" in text and "允许目标：" + allowed in text and "房间名" in text
    for kind in ("output_truncated", "invalid_json", "invalid_summary"):
        assert "允许目标：" + allowed in llm_retry_feedback(kind, "", {}, allowed)
