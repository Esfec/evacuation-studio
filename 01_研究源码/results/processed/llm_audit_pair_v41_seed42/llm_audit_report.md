## Material Passport

- Artifact: LLM synthetic-user operational audit
- Verification status: ANALYZED
- Evidence class: simulator logs and API metadata

# LLM audit: PASS

## Gates

- PASS — `all_runs_valid`
- PASS — `agent_step_complete`
- PASS — `api_attempt_success_ge_0_90`
- PASS — `fallback_ratio_le_0_10`
- PASS — `empty_brief_ratio_le_0_02`
- PASS — `invalid_target_actions_eq_0`
- PASS — `all_agent_types_observed`

## Metrics

- `runs`: 2
- `hybrid_decisions`: 564
- `llm_or_fallback_decisions`: 564
- `llm_call_attempts`: 478
- `api_attempt_success_ratio`: 1.0
- `fallback_count`: 10
- `fallback_ratio`: 0.01773
- `empty_brief_ratio`: 0.0
- `invalid_target_actions`: 0
- `stress_override_count`: 86

## Agent types

- **Cognitive**: {"decisions": 122, "fallbacks": 2, "mean_chosen_risk": 0.136883, "safest_choice_ratio": 0.893443, "dead_end_choice_ratio": 0.0}
- **Perceptual**: {"decisions": 219, "fallbacks": 8, "mean_chosen_risk": 0.217081, "safest_choice_ratio": 0.908676, "dead_end_choice_ratio": 0.054795}
- **Follower**: {"decisions": 223, "fallbacks": 0, "mean_chosen_risk": 0.261907, "safest_choice_ratio": 0.955157, "dead_end_choice_ratio": 0.035874}

> Passing establishes operational auditability only; it does not establish empirical behavioural validity or real-world prediction.
