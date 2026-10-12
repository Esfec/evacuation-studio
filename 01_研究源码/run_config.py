"""Immutable, serializable configuration for one simulation run."""

from dataclasses import asdict, dataclass
from typing import Dict, Mapping, Optional, Tuple
import math


POLICY_IDS = {
    "LLM_Agent",
    "Local_Rule",
    "Global_ShortestPath",
    "RiskAware_Dijkstra",
    "Random",
    "Mock_Heterogeneous",
}
DESIGN_IDS = {"D0", "D1", "D2"}
CONDITION_IDS = {"C0", "C1"}


@dataclass(frozen=True)
class AgentCounts:
    cognitive: int
    perceptual: int
    follower: int

    def __post_init__(self):
        if any(isinstance(n, bool) or not isinstance(n, int)
               for n in (self.cognitive, self.perceptual, self.follower)):
            raise ValueError('Agent counts must be integers')
        if min(self.cognitive, self.perceptual, self.follower) < 0:
            raise ValueError("Agent counts must be non-negative")
        if self.total <= 0:
            raise ValueError("At least one Agent is required")

    @property
    def total(self) -> int:
        return self.cognitive + self.perceptual + self.follower

    def as_named_dict(self) -> Dict[str, int]:
        return {
            "Cognitive": self.cognitive,
            "Perceptual": self.perceptual,
            "Follower": self.follower,
        }


@dataclass(frozen=True)
class RunConfig:
    seed: int
    policy_id: str
    design_id: str
    condition_id: str
    fire_origin: str
    max_steps: int
    agent_counts: AgentCounts
    fire_rate: float = 0.10
    risky_coeff: float = 3.0
    blocked_coeff: float = 7.0
    temperature: float = 0.10
    base_edge_capacity: int = 4
    risk_weight: float = 6.0
    crowd_weight: float = 2.0
    step_seconds: int = 5
    provider: str = "Poe"
    model: str = "GPT-4o"
    experiment_type: str = "exploratory"
    initial_distribution: Optional[Mapping[str, int]] = None
    initial_positions: Optional[Mapping[str, str]] = None
    smoke_rate: Optional[float] = None
    smoke_scale: float = 0.9
    min_hops_to_exit: int = 3
    llm_concurrency: int = 8
    schema_version: str = "4.1"

    def __post_init__(self):
        if self.policy_id not in POLICY_IDS:
            raise ValueError(f"Unknown policy_id: {self.policy_id}")
        if self.design_id not in DESIGN_IDS:
            raise ValueError(f"Unknown design_id: {self.design_id}")
        if self.condition_id not in CONDITION_IDS:
            raise ValueError(f"Unknown condition_id: {self.condition_id}")
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.base_edge_capacity <= 0:
            raise ValueError("base_edge_capacity must be positive")
        if self.min_hops_to_exit < 1:
            raise ValueError("min_hops_to_exit must be at least 1")
        if not 1 <= self.llm_concurrency <= 32:
            raise ValueError("llm_concurrency must be between 1 and 32")
        if not self.fire_origin:
            raise ValueError("fire_origin is required")
        for name in ('fire_rate', 'risky_coeff', 'blocked_coeff', 'step_seconds'):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if self.smoke_rate is not None and (not math.isfinite(self.smoke_rate) or self.smoke_rate <= 0):
            raise ValueError('smoke_rate must be finite and positive')
        for name in ('risk_weight', 'crowd_weight', 'smoke_scale', 'temperature'):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{name} must be finite and non-negative')
        if self.initial_distribution is not None and self.initial_positions is not None:
            raise ValueError('Choose initial_distribution or initial_positions, not both')
        if self.initial_positions is not None:
            object.__setattr__(self, 'initial_positions', tuple(sorted(self.initial_positions.items())))
        if self.initial_distribution is not None:
            if any(isinstance(n, bool) or not isinstance(n, int)
                   for n in self.initial_distribution.values()):
                raise ValueError('Initial distribution counts must be integers')
            frozen_distribution: Tuple[Tuple[str, int], ...] = tuple(
                sorted((str(node), int(count)) for node, count in self.initial_distribution.items())
            )
            if any(count < 0 for _, count in frozen_distribution):
                raise ValueError("Initial distribution counts must be non-negative")
            object.__setattr__(self, "initial_distribution", frozen_distribution)

    def initial_distribution_dict(self) -> Optional[Dict[str, int]]:
        if self.initial_distribution is None:
            return None
        return dict(self.initial_distribution)

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["agent_counts"] = self.agent_counts.as_named_dict()
        data["initial_distribution"] = self.initial_distribution_dict()
        data['initial_positions'] = dict(self.initial_positions) if self.initial_positions is not None else None
        return data
