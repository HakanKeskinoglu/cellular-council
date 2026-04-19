# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
BaseCell: The fundamental unit of the Cellular Council Architecture.

Every specialized cell inherits from BaseCell. The design mirrors biological
cell specialization — a common base structure with differentiated behavior
encoded in the cell's system prompt and analysis methods.

Architecture Note
-----------------
Cells are stateless between sessions but maintain health metrics across
their lifetime. Each call to ``analyze()`` is an independent LLM completion,
making cells horizontally scalable and resilient to individual failures.

    ┌─────────────────────────────────────────────┐
    │                  BaseCell                   │
    │                                             │
    │  ┌──────────┐   ┌──────────┐  ┌─────────┐  │
    │  │ Identity │   │  Health  │  │  LLM    │  │
    │  │ (role,id)│   │ Monitor  │  │ Backend │  │
    │  └──────────┘   └──────────┘  └─────────┘  │
    │                                             │
    │  analyze(query) → CellOutput                │
    │  debate(outputs) → CellOutput               │
    └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import re
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import structlog

from cca.core import CellHealthReport, CellOutput, CellRole, CellState, ConsensusStrategy, SignalType

logger = structlog.get_logger(__name__)


class BaseCell(ABC):
    """
    Abstract base class for all CCA cells.

    Subclasses must implement:
    - ``system_prompt``: property returning the cell's role-specific instructions
    - ``analyze()``: core analysis method

    Parameters
    ----------
    role : CellRole
        The specialized role of this cell.
    llm_backend : Any
        LLM backend instance (OllamaBackend, OpenAIBackend, etc.)
    cell_id : str, optional
        Unique identifier. Auto-generated if not provided.
    weight : float
        Voting weight in consensus (0.0–2.0). Default 1.0.
    max_retries : int
        Number of LLM call retries on failure.
    depth : int
        Hierarchy depth of this cell. 0 = top-level council.
        Used to enforce MAX_DEPTH and prevent infinite sub-council recursion.
    """

    MAX_DEPTH: int = 2  # Maximum sub-council nesting depth

    def __init__(
        self,
        role: CellRole,
        llm_backend: Any,
        cell_id: str | None = None,
        weight: float = 1.0,
        max_retries: int = 3,
        depth: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id = cell_id or str(uuid.uuid4())[:8]
        self.role = role
        self.llm = llm_backend
        self.weight = weight
        self.max_retries = max_retries
        self.depth = depth
        self.metadata = metadata or {}

        # State & health
        self._state = CellState.DORMANT
        self._health_score: float = 1.0
        self._error_count: int = 0
        self._successful_analyses: int = 0
        self._total_response_time_ms: float = 0.0
        self._last_active: datetime | None = None

        self.log = logger.bind(cell_id=self.id, role=self.role.value)
        self.log.info("cell.initialized")

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """
        Role-specific system prompt injected into every LLM call.

        This is what makes each cell "specialized" — the same LLM
        model behaves entirely differently based on this prompt.
        """
        ...

    @abstractmethod
    async def analyze(self, query: str, context: dict[str, Any] | None = None) -> CellOutput:
        """
        Perform the cell's primary analysis on a query.

        Parameters
        ----------
        query : str
            The problem or question to analyze.
        context : dict, optional
            Additional context (e.g., historical data, alarm metadata).

        Returns
        -------
        CellOutput
            Structured analysis from this cell's perspective.
        """
        ...

    # ------------------------------------------------------------------
    # Debate interface (default implementation, can be overridden)
    # ------------------------------------------------------------------

    async def debate(
        self,
        query: str,
        other_outputs: list[CellOutput],
        round_number: int = 2,
        context: dict[str, Any] | None = None,
    ) -> CellOutput:
        """
        Review other cells' analyses and produce a debate response.

        The default implementation summarizes peer outputs and asks the LLM
        to critique, support, or synthesize. Subclasses can override for
        more sophisticated debate strategies.

        Parameters
        ----------
        query : str
            Original query being deliberated.
        other_outputs : list[CellOutput]
            Outputs from peer cells in this cluster.
        round_number : int
            Current debate round (used for escalating scrutiny).
        """
        self._state = CellState.DELIBERATING

        peer_summaries = "\n\n".join([
            f"[{o.cell_role.value.upper()} CELL]:\n"
            f"Analysis: {o.analysis}\n"
            f"Recommendation: {o.recommendation}\n"
            f"Confidence: {o.confidence:.0%}"
            for o in other_outputs
        ])

        debate_prompt = f"""You are in round {round_number} of a council deliberation.

ORIGINAL QUERY:
{query}

PEER ANALYSES:
{peer_summaries}

YOUR TASK:
As the {self.role.value.upper()} specialist, review these perspectives and:
1. Identify agreements and conflicts
2. Challenge any analysis that overlooks {self.role.value} considerations
3. Synthesize a refined recommendation that incorporates valid peer insights
4. Adjust your confidence based on the collective evidence

Be constructive but rigorous. The council's decision quality depends on honest debate."""

        return await self._call_llm(
            user_message=debate_prompt,
            context=context,
            signal_type=SignalType.DEBATE,
            round_number=round_number,
            in_response_to=other_outputs[0].id if other_outputs else None,
        )

    # ------------------------------------------------------------------
    # Protected LLM call helper
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
        signal_type: SignalType = SignalType.ANALYSIS,
        round_number: int = 1,
        in_response_to: str | None = None,
    ) -> CellOutput:
        """
        Invoke the LLM backend and parse the response into a CellOutput.

        Handles retries, health tracking, and structured output parsing.
        """
        start = time.monotonic()
        self._state = CellState.ACTIVE
        self._last_active = datetime.now(timezone.utc)

        context_str = ""
        if context:
            context_str = "\n\nCONTEXT:\n" + "\n".join(
                f"  {k}: {v}" for k, v in context.items()
            )

        full_prompt = user_message + context_str

        for attempt in range(self.max_retries):
            try:
                raw_response = await self.llm.complete(
                    system=self.system_prompt,
                    user=full_prompt,
                )

                elapsed_ms = (time.monotonic() - start) * 1000
                self._total_response_time_ms += elapsed_ms
                self._successful_analyses += 1
                self._state = CellState.ACTIVE

                output = self._parse_response(
                    raw=raw_response,
                    signal_type=signal_type,
                    round_number=round_number,
                    in_response_to=in_response_to,
                )
                self.log.info("cell.analysis.complete", round=round_number, elapsed_ms=elapsed_ms)
                return output

            except Exception as exc:
                self._error_count += 1
                self._health_score = max(0.0, self._health_score - 0.1)
                self.log.warning("cell.llm.error", attempt=attempt + 1, error=str(exc))

                if attempt == self.max_retries - 1:
                    self._state = CellState.FATIGUED
                    raise RuntimeError(
                        f"Cell {self.id} ({self.role.value}) failed after "
                        f"{self.max_retries} attempts: {exc}"
                    ) from exc

        # Should never reach here
        raise RuntimeError("Unexpected exit from retry loop")

    def _parse_response(
        self,
        raw: str,
        signal_type: SignalType,
        round_number: int,
        in_response_to: str | None,
    ) -> CellOutput:
        """
        Parse the raw LLM string response into a structured CellOutput.

        Expects the LLM to follow the structured format defined in the
        system prompt. Falls back gracefully if parsing is incomplete.
        """
        def extract(pattern: str, default: str = "") -> str:
            m = re.search(pattern, raw, re.IGNORECASE | re.DOTALL)
            return m.group(1).strip() if m else default

        def extract_float(pattern: str, default: float = 0.7) -> float:
            m = re.search(pattern, raw, re.IGNORECASE)
            if m:
                try:
                    val = float(m.group(1).replace("%", ""))
                    return val / 100 if val > 1 else val
                except ValueError:
                    pass
            return default

        analysis = (
            extract(r"ANALYSIS[:\s]+(.*?)(?=RECOMMENDATION|REASONING|CONFIDENCE|$)")
            or raw[:500]
        )
        recommendation = extract(r"RECOMMENDATION[:\s]+(.*?)(?=REASONING|CONFIDENCE|RISK|$)")
        reasoning = extract(r"REASONING[:\s]+(.*?)(?=CONFIDENCE|RISK|$)")
        confidence = extract_float(r"CONFIDENCE[:\s]+([\d.]+%?)")
        risk_score = extract_float(r"RISK[_\s]SCORE[:\s]+([\d.]+%?)", default=None)  # type: ignore

        return CellOutput(
            cell_id=self.id,
            cell_role=self.role,
            analysis=analysis,
            recommendation=recommendation or analysis,
            reasoning=reasoning or "See analysis.",
            confidence=confidence,
            risk_score=risk_score,
            signal_type=signal_type,
            round_number=round_number,
            in_response_to=in_response_to,
            metadata={"raw_response_length": len(raw)},
        )

    # ------------------------------------------------------------------
    # Sub-cell spawning
    # ------------------------------------------------------------------

    def _requires_sub_council(self, query: str, context: dict[str, Any] | None = None) -> bool:
        """
        Determine whether this query requires a sub-council.

        Override in subclasses to implement domain-specific complexity
        detection logic. Default returns False (no sub-council).

        Parameters
        ----------
        query : str
            The query being analyzed.
        context : dict, optional
            Additional context.

        Returns
        -------
        bool
            True if a sub-council should be spawned.
        """
        return False

    async def _spawn_sub_council(
        self,
        query: str,
        context: dict[str, Any] | None,
        cells: list[tuple[CellRole, float]],
        strategy: ConsensusStrategy = ConsensusStrategy.MAJORITY_VOTE,
        debate_rounds: int = 0,
    ) -> CellOutput:
        """
        Spawn a sub-council, run a full deliberation, and return the
        result as a single CellOutput from this cell's perspective.

        The parent council never sees the sub-council internals — it
        only receives a single, aggregated output.

        Parameters
        ----------
        query : str
            Query to deliberate in the sub-council.
        context : dict, optional
            Context to pass to the sub-council.
        cells : list[tuple[CellRole, float]]
            List of (role, weight) tuples for sub-council cells.
        strategy : ConsensusStrategy
            Consensus strategy for the sub-council.
        debate_rounds : int
            Number of debate rounds in sub-council. Default: 0.

        Returns
        -------
        CellOutput
            The sub-council's decision wrapped as a CellOutput.

        Raises
        ------
        RuntimeError
            If MAX_DEPTH would be exceeded.
        """
        if self.depth >= self.MAX_DEPTH:
            raise RuntimeError(
                f"Cannot spawn sub-council: depth {self.depth} already at "
                f"MAX_DEPTH={self.MAX_DEPTH}. Falling back to direct analysis."
            )

        # Lazy import to avoid circular dependency
        from cca.core.council import Council

        sub = Council(
            name=f"{self.role.value}_sub_council_L{self.depth + 1}",
            llm_backend=self.llm,
            strategy=strategy,
            debate_rounds=debate_rounds,
        )

        for role, weight in cells:
            sub.add_cell(role, weight=weight)

        self.log.info(
            "cell.sub_council.spawned",
            parent_depth=self.depth,
            sub_cells=len(cells),
            strategy=strategy.value,
        )

        decision = await sub.deliberate(query, context)

        return CellOutput.from_decision(
            decision=decision,
            source_role=self.role,
            source_id=self.id,
        )

    # ------------------------------------------------------------------
    # Health & lifecycle
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """Transition cell from DORMANT to ACTIVE."""
        if self._state == CellState.DORMANT:
            self._state = CellState.ACTIVE
            self.log.info("cell.activated")

    def retire(self) -> None:
        """Mark cell as apoptotic (scheduled for removal)."""
        self._state = CellState.APOPTOTIC
        self.log.info("cell.retired")

    @property
    def state(self) -> CellState:
        return self._state

    @property
    def health_score(self) -> float:
        return self._health_score

    @property
    def avg_response_time_ms(self) -> float:
        if self._successful_analyses == 0:
            return 0.0
        return self._total_response_time_ms / self._successful_analyses

    def health_report(self) -> CellHealthReport:
        return CellHealthReport(
            cell_id=self.id,
            cell_role=self.role,
            state=self._state,
            health_score=self._health_score,
            response_time_ms=self.avg_response_time_ms,
            error_count=self._error_count,
            successful_analyses=self._successful_analyses,
            last_active=self._last_active,
            is_degraded=self._health_score < 0.5,
            recovery_needed=self._state == CellState.FATIGUED,
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.id} role={self.role.value} state={self._state.value}>"
