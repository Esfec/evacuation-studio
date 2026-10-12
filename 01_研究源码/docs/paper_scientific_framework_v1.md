# Scientific framework — public release

This replaces an early planning outline. It describes the executed conference
study; proposed future sensitivity experiments are not completed evidence.

## Research question

Can auditable, heterogeneous synthetic occupants support early-stage
topological design screening by revealing how capacity and redundancy
interventions redistribute evacuation flow and residual failures?

## Executed comparison

- The inferential unit is the simulation run, paired by seed within each
  policy's design comparison, not an individual synthetic occupant.
- Primary endpoint: escape fraction at the fixed 30-step horizon.
- Main contrast: D2/C1 minus D0/C1. Difference-in-differences across C0/C1
  is an interaction robustness analysis.
- Process measures include RMET30 (each non-escape assigned 30 steps),
  waiting, link use, node occupancy and terminal failure locations.
- Formal matrix: 48 occupants (10 Cognitive, 15 Perceptual, 23 Follower),
  seeds 101–120, D0/D1/D2 × C0/C1; 120 LLM and 480 legacy-baseline runs.
- A separate post hoc 40-run LLM-off analysis uses recorded LLM initial
  states and preserves the LLM-path perception/profile/stress layers.
  Ordinary Local_Rule is not this matched ablation.
- P0/P1 selection was an implementation-selection exercise preceding the
  formal comparison, not empirical behavioural validation.

## Interpretation

The design effect is decision-policy-sensitive. A smaller LLM effect is not
evidence of greater realism or superiority. The architectural contribution
is diagnosis of local relief and downstream redistribution under the
specified topology and hazard assumptions.

Legacy baseline cross-policy differences are descriptive: initial node
assignments were not exactly matched across processes. Matching was
established separately for LLM-off using archived states. See
RELEASE_REVIEW.md for implementation-level limitations.

Mechanism tests verify implementation, not predictive validity for people
or physical evacuation times. Alternate fire origins, populations and model
families are future validation directions; the formal matrix uses N01.

