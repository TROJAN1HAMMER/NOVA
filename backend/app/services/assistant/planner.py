"""
AEKOF — Knowledge Planner & Intent Analyzer Subsystem
"""

import structlog
from dataclasses import dataclass, field

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionPlan:
    query: str
    complexity_level: str  # "routine" | "standard" | "complex"
    active_paths: list[int] = field(default_factory=lambda: [0, 1, 2])
    timeout_ms: int = 1500
    min_confidence: float = 0.15
    reasoning_needed: bool = False


class KnowledgePlanner:
    def analyze_and_plan(self, query: str) -> ExecutionPlan:
        q_lower = query.lower().strip()
        words = q_lower.split()

        # Routine / Short query
        if len(words) <= 3:
            plan = ExecutionPlan(
                query=query,
                complexity_level="routine",
                active_paths=[0, 1],  # FAQ + Dense
                timeout_ms=500,
                min_confidence=0.10,
                reasoning_needed=False,
            )
        elif any(k in q_lower for k in ["compare", "policy", "difference", "requirement", "versus"]):
            plan = ExecutionPlan(
                query=query,
                complexity_level="complex",
                active_paths=[0, 1, 2, 3, 4],  # FAQ, Dense, Sparse, GraphRAG, Memory
                timeout_ms=2500,
                min_confidence=0.25,
                reasoning_needed=True,
            )
        else:
            plan = ExecutionPlan(
                query=query,
                complexity_level="standard",
                active_paths=[0, 1, 2, 4],  # FAQ, Dense, Sparse, Memory
                timeout_ms=1500,
                min_confidence=0.15,
                reasoning_needed=False,
            )

        logger.info("knowledge_planner.planned", complexity=plan.complexity_level, active_paths=plan.active_paths)
        return plan


knowledge_planner = KnowledgePlanner()
