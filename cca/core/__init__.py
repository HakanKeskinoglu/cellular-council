# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Core types, enums, and data models for the CCA Framework.

This module defines the fundamental data structures that flow through
the entire framework — from individual cell outputs to final council decisions.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CellRole(str, enum.Enum):
    """
    Predefined specialized roles for council cells.

    Cells can also be created with custom roles via the ``custom`` value
    combined with a ``role_description`` parameter.
    """
    RISK = "risk"
    ETHICS = "ethics"
    TECHNICAL = "technical"
    FINANCIAL = "financial"
    LEGAL = "legal"
    SECURITY = "security"
    STRATEGIC = "strategic"
    OPERATIONS = "operations"
    # Biological metaphor roles
    STEM = "stem"          # Undifferentiated — can become any role
    MEMORY = "memory"      # Retains historical context
    EFFECTOR = "effector"  # Executes final actions
    # Custom
    CUSTOM = "custom"


class CellState(str, enum.Enum):
    """Lifecycle state of a cell."""
    DORMANT = "dormant"          # Not yet activated
    DIFFERENTIATING = "differentiating"  # Stem cell specializing
    ACTIVE = "active"            # Processing normally
    DELIBERATING = "deliberating"  # In cluster debate
    FATIGUED = "fatigued"        # Health degraded, needs recovery
    APOPTOTIC = "apoptotic"      # Scheduled for removal


class ConsensusStrategy(str, enum.Enum):
    """Strategy used to reach consensus in the apex layer."""
    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_AVERAGE = "weighted_average"
    DELPHI = "delphi"            # Iterative rounds with feedback
    UNANIMOUS = "unanimous"
    RANKED_CHOICE = "ranked_choice"
    APEX_OVERRIDE = "apex_override"  # Single apex cell decides


class SignalType(str, enum.Enum):
    """Types of signals that flow through synapses."""
    ANALYSIS = "analysis"        # Cell's perspective on the query
    DEBATE = "debate"            # Challenging another cell's view
    SUPPORT = "support"          # Supporting another cell's view
    QUESTION = "question"        # Requesting clarification
    ESCALATION = "escalation"    # Crisis signal
    HEALTH = "health"            # Cell health ping
    ADVISORY = "advisory"        # From advisor roles (non-binding)
    AUDIT = "audit"              # From auditor roles


class ConfidenceLevel(str, enum.Enum):
    """Standardized confidence levels for cell outputs."""
    VERY_LOW = "very_low"    # < 20%
    LOW = "low"              # 20–40%
    MODERATE = "moderate"    # 40–60%
    HIGH = "high"            # 60–80%
    VERY_HIGH = "very_high"  # > 80%

    @classmethod
    def from_float(cls, value: float) -> ConfidenceLevel:
        if value < 0.2:
            return cls.VERY_LOW
        elif value < 0.4:
            return cls.LOW
        elif value < 0.6:
            return cls.MODERATE
        elif value < 0.8:
            return cls.HIGH
        return cls.VERY_HIGH


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

class CellOutput(BaseModel):
    """
    Structured output produced by a cell after analyzing a query.

    This is the fundamental unit of information that flows through synapses
    and gets aggregated by the consensus engine.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    cell_id: str
    cell_role: CellRole
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Core content
    analysis: str = Field(description="Cell's analysis of the query")
    recommendation: str = Field(description="Cell's recommended action/decision")
    reasoning: str = Field(description="Step-by-step reasoning chain")

    # Quantitative signals
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0–1")
    confidence_level: ConfidenceLevel = Field(default=ConfidenceLevel.MODERATE)
    risk_score: float | None = Field(None, ge=0.0, le=1.0)

    # Metadata
    signal_type: SignalType = SignalType.ANALYSIS
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Debate round tracking
    round_number: int = Field(default=1, ge=1)
    in_response_to: str | None = Field(None, description="ID of output being responded to")

    def model_post_init(self, __context: Any) -> None:
        self.confidence_level = ConfidenceLevel.from_float(self.confidence)

    @classmethod
    def from_decision(
        cls,
        decision: "CouncilDecision",
        source_role: CellRole,
        source_id: str,
    ) -> "CellOutput":
        """
        Convert a CouncilDecision into a single CellOutput.

        Used by sub-cell spawning: a cell spawns an internal sub-council,
        runs a full deliberation, and returns the result as its own output.
        The parent council never sees the sub-council internals.

        Parameters
        ----------
        decision : CouncilDecision
            The sub-council's final decision.
        source_role : CellRole
            The role of the parent cell that spawned the sub-council.
        source_id : str
            The ID of the parent cell.

        Returns
        -------
        CellOutput
            A single output encapsulating the sub-council's decision.
        """
        return cls(
            cell_id=source_id,
            cell_role=source_role,
            analysis=decision.rationale,
            recommendation=decision.decision,
            reasoning=f"Sub-council consensus ({decision.strategy_used.value}): "
                      f"{len(decision.participating_cells)} cells, "
                      f"{decision.debate_rounds} debate rounds.",
            confidence=decision.overall_confidence,
            risk_score=decision.risk_level,
            signal_type=SignalType.ANALYSIS,
            metadata={
                "source": "sub_council",
                "sub_council_id": decision.council_id,
                "sub_consensus_score": decision.consensus_score,
                "sub_cell_count": len(decision.participating_cells),
            },
        )


class CouncilDecision(BaseModel):
    """
    Final decision produced by the council after consensus.

    This is the authoritative output of the entire deliberation process.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    council_id: str
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Query context
    query: str
    context: dict[str, Any] = Field(default_factory=dict)

    # Decision output
    decision: str = Field(description="Final decision or recommendation")
    rationale: str = Field(description="Synthesized rationale from all cells")
    action_items: list[str] = Field(default_factory=list)
    dissenting_views: list[str] = Field(default_factory=list)
    advisory_notes: list[str] = Field(default_factory=list)

    # Quantitative
    consensus_score: float = Field(ge=0.0, le=1.0)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    risk_level: float | None = Field(None, ge=0.0, le=1.0)

    # Process metadata
    strategy_used: ConsensusStrategy
    participating_cells: list[str] = Field(default_factory=list)
    debate_rounds: int = Field(default=1)
    cell_outputs: list[CellOutput] = Field(default_factory=list)
    duration_ms: float | None = None

    # Status
    requires_human_review: bool = False
    crisis_mode_activated: bool = False

    model_config = {"ser_json_timedelta": "iso8601"}


class CellHealthReport(BaseModel):
    """Health status of an individual cell."""
    cell_id: str
    cell_role: CellRole
    state: CellState
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Health metrics
    health_score: float = Field(ge=0.0, le=1.0, default=1.0)
    response_time_ms: float | None = None
    error_count: int = 0
    successful_analyses: int = 0
    last_active: datetime | None = None

    # Flags
    is_degraded: bool = False
    recovery_needed: bool = False
    notes: str = ""
