# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Council: Top-level orchestrator for the Cellular Council Architecture.

The Council coordinates the full deliberation lifecycle:
  1. Cell activation and health check
  2. Parallel initial analysis (Round 1)
  3. Structured debate rounds (Round 2+)
  4. Consensus computation
  5. Decision finalization

    ┌─────────────────────────────────────────────────────────┐
    │                       Council                           │
    │                                                         │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
    │  │  Risk    │  │  Ethics  │  │Technical │  ← Cells     │
    │  │  Cell    │  │  Cell    │  │  Cell    │              │
    │  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
    │       │             │             │                     │
    │  ┌────▼─────────────▼─────────────▼─────┐              │
    │  │          Cluster Deliberation         │              │
    │  │    (parallel analysis → debate)       │              │
    │  └──────────────────┬────────────────────┘              │
    │                     │                                   │
    │  ┌──────────────────▼────────────────────┐              │
    │  │         Consensus Engine              │              │
    │  │    (weighted_avg / vote / apex)       │              │
    │  └──────────────────┬────────────────────┘              │
    │                     │                                   │
    │  ┌──────────────────▼────────────────────┐              │
    │  │         CouncilDecision               │              │
    │  └───────────────────────────────────────┘              │
    └─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import structlog

from cca.advisors.base import BaseAdvisor
from cca.advisors.specialized import create_advisor
from cca.cells.base import BaseCell
from cca.cells.specialized import create_cell
from cca.consensus.engine import ConsensusEngine
from cca.core import (
    CellHealthReport,
    CellOutput,
    CellRole,
    ConsensusStrategy,
    CouncilDecision,
    SignalType,
)

logger = structlog.get_logger(__name__)


class Council:
    """
    The primary interface for the Cellular Council Architecture.

    A Council manages a set of specialized cells, orchestrates deliberation
    sessions, and produces structured decisions through consensus.

    Parameters
    ----------
    name : str
        Human-readable name for this council instance.
    llm_backend : Any
        Default LLM backend for all cells (can be overridden per cell).
    strategy : ConsensusStrategy
        Consensus strategy to use. Default: WEIGHTED_AVERAGE.
    debate_rounds : int
        Number of debate rounds after initial analysis. Default: 1.
    consensus_threshold : float
        Minimum consensus score before flagging human review.
    risk_escalation_threshold : float
        Risk score above which human review is flagged.
    council_id : str, optional
        Unique ID for this council. Auto-generated if not provided.

    Examples
    --------
    >>> from cca import Council, CellRole
    >>> from cca.llm.backends import OllamaBackend
    >>>
    >>> council = Council(
    ...     name="SecurityCouncil",
    ...     llm_backend=OllamaBackend(model="llama3.2"),
    ...     strategy=ConsensusStrategy.APEX_OVERRIDE,
    ...     debate_rounds=2,
    ... )
    >>> council.add_cell(CellRole.RISK)
    >>> council.add_cell(CellRole.SECURITY)
    >>> council.add_cell(CellRole.TECHNICAL)
    >>>
    >>> decision = await council.deliberate(
    ...     query="Should we take down the primary database server for maintenance?",
    ...     context={"current_load": "72%", "maintenance_window": "02:00-04:00 UTC"},
    ... )
    >>> print(decision.decision)
    """

    def __init__(
        self,
        name: str,
        llm_backend: Any,
        strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED_AVERAGE,
        debate_rounds: int = 1,
        consensus_threshold: float = 0.6,
        risk_escalation_threshold: float = 0.75,
        council_id: str | None = None,
    ) -> None:
        self.name = name
        self.id = council_id or str(uuid.uuid4())[:8]
        self.llm_backend = llm_backend
        self.debate_rounds = debate_rounds

        self._cells: dict[str, BaseCell] = {}
        self._advisors: list[BaseAdvisor] = []

        self._consensus_engine = ConsensusEngine(
            strategy=strategy,
            consensus_threshold=consensus_threshold,
            risk_escalation_threshold=risk_escalation_threshold,
            apex_llm=llm_backend if strategy == ConsensusStrategy.APEX_OVERRIDE else None,
        )

        self.log = logger.bind(council_id=self.id, council_name=name)
        self.log.info("council.initialized", strategy=strategy.value)

    # ------------------------------------------------------------------
    # Cell management
    # ------------------------------------------------------------------

    def add_cell(
        self,
        role: CellRole,
        weight: float = 1.0,
        llm_backend: Any | None = None,
        **kwargs: Any,
    ) -> BaseCell:
        """
        Add a specialized cell to the council.

        Parameters
        ----------
        role : CellRole
            The cell specialization (RISK, ETHICS, TECHNICAL, etc.)
        weight : float
            Voting weight for this cell (0.5 = half weight, 2.0 = double).
        llm_backend : optional
            Override the council's default LLM backend for this cell.

        Returns
        -------
        BaseCell
            The newly created and activated cell.
        """
        backend = llm_backend or self.llm_backend
        cell = create_cell(role=role, llm_backend=backend, weight=weight, **kwargs)
        cell.activate()
        self._cells[cell.id] = cell
        self.log.info("council.cell.added", cell_id=cell.id, role=role.value, weight=weight)
        return cell

    def add_custom_cell(self, cell: BaseCell) -> None:
        """Add a pre-built custom cell to the council."""
        cell.activate()
        self._cells[cell.id] = cell
        self.log.info("council.custom_cell.added", cell_id=cell.id, role=cell.role.value)

    # ------------------------------------------------------------------
    # Advisor management
    # ------------------------------------------------------------------

    def add_advisor(
        self,
        role: "AdvisorRole | None" = None,
        llm_backend: Any | None = None,
        advisor: BaseAdvisor | None = None,
        **kwargs: Any,
    ) -> BaseAdvisor:
        """
        Add an independent advisor to the council.

        Advisors do NOT vote in consensus — they provide non-binding
        oversight notes that are included in the final decision.

        Parameters
        ----------
        role : AdvisorRole, optional
            Create an advisor from a predefined role.
        llm_backend : Any, optional
            LLM backend for this advisor. Defaults to council's backend.
        advisor : BaseAdvisor, optional
            Add a pre-built custom advisor instance directly.

        Returns
        -------
        BaseAdvisor
            The newly added advisor.
        """
        if advisor is not None:
            self._advisors.append(advisor)
            self.log.info("council.advisor.added", advisor_id=advisor.id, role=advisor.role.value)
            return advisor

        if role is None:
            raise ValueError("Provide either 'role' or 'advisor' parameter.")

        from cca.advisors.base import AdvisorRole as AR
        backend = llm_backend or self.llm_backend
        adv = create_advisor(role=role, llm_backend=backend, **kwargs)
        self._advisors.append(adv)
        self.log.info("council.advisor.added", advisor_id=adv.id, role=role.value)
        return adv

    @property
    def advisors(self) -> list[BaseAdvisor]:
        return list(self._advisors)

    @property
    def advisor_count(self) -> int:
        return len(self._advisors)

    def remove_cell(self, cell_id: str) -> None:
        """Remove a cell from the council."""
        if cell_id in self._cells:
            self._cells[cell_id].retire()
            del self._cells[cell_id]
            self.log.info("council.cell.removed", cell_id=cell_id)

    @property
    def cells(self) -> list[BaseCell]:
        return list(self._cells.values())

    @property
    def cell_count(self) -> int:
        return len(self._cells)

    # ------------------------------------------------------------------
    # Core deliberation
    # ------------------------------------------------------------------

    async def deliberate(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> CouncilDecision:
        """
        Run the full deliberation process and return a council decision.

        Flow
        ----
        1. Validate council has cells
        2. Round 1: All cells analyze in parallel
        3. Rounds 2–N: Debate rounds (each cell reviews peers and responds)
        4. Consensus computation
        5. Decision assembly

        Parameters
        ----------
        query : str
            The question, problem, or alarm to deliberate on.
        context : dict, optional
            Structured context to provide to all cells.
        session_id : str, optional
            Unique ID for this deliberation session.

        Returns
        -------
        CouncilDecision
            Fully structured decision with rationale, scores, and metadata.

        Raises
        ------
        ValueError
            If council has no cells.
        """
        if not self._cells:
            raise ValueError(
                "Council has no cells. Add at least one cell with council.add_cell() before deliberating."
            )

        session_id = session_id or str(uuid.uuid4())[:8]
        start_time = time.monotonic()
        self.log.info("deliberation.start", session_id=session_id, cell_count=len(self._cells))

        # --- Round 1: Parallel initial analysis ---
        all_outputs: list[CellOutput] = []
        round1_outputs = await self._round_analyze(query=query, context=context)
        all_outputs.extend(round1_outputs)
        self.log.info("deliberation.round1.complete", outputs=len(round1_outputs))

        # --- Rounds 2+: Debate ---
        current_outputs = round1_outputs
        for round_num in range(2, self.debate_rounds + 2):
            debate_outputs = await self._round_debate(
                query=query,
                outputs=current_outputs,
                round_number=round_num,
                context=context,
            )
            all_outputs.extend(debate_outputs)
            current_outputs = debate_outputs
            self.log.info("deliberation.debate_round.complete", round=round_num)

        # --- Advisory round (non-voting oversight) ---
        advisory_outputs: list[CellOutput] = []
        if self._advisors:
            self.log.info("deliberation.advisory.start", advisor_count=len(self._advisors))
            advisory_tasks = [
                advisor.advise(query=query, cell_outputs=current_outputs, context=context)
                for advisor in self._advisors
            ]
            advisory_results = await asyncio.gather(*advisory_tasks, return_exceptions=True)
            for advisor, result in zip(self._advisors, advisory_results):
                if isinstance(result, Exception):
                    self.log.error("advisor.advise.failed", advisor_id=advisor.id, error=str(result))
                else:
                    advisory_outputs.append(result)
            self.log.info("deliberation.advisory.complete", notes=len(advisory_outputs))

        # --- Consensus ---
        cell_weights = {cell_id: cell.weight for cell_id, cell in self._cells.items()}
        consensus_result = await self._consensus_engine.compute(
            outputs=current_outputs,
            cell_weights=cell_weights,
            advisory_outputs=advisory_outputs,
        )

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # --- Assemble final decision ---
        decision = CouncilDecision(
            council_id=self.id,
            session_id=session_id,
            query=query,
            context=context or {},
            decision=consensus_result.winning_recommendation,
            rationale=consensus_result.synthesized_rationale,
            action_items=self._extract_action_items(current_outputs),
            dissenting_views=consensus_result.dissenting_views,
            advisory_notes=consensus_result.advisory_notes,
            consensus_score=consensus_result.consensus_score,
            overall_confidence=consensus_result.overall_confidence,
            risk_level=consensus_result.overall_risk,
            strategy_used=self._consensus_engine.strategy,
            participating_cells=[c.id for c in self._cells.values()],
            debate_rounds=self.debate_rounds,
            cell_outputs=all_outputs,
            duration_ms=elapsed_ms,
            requires_human_review=consensus_result.requires_human_review,
        )

        self.log.info(
            "deliberation.complete",
            session_id=session_id,
            consensus_score=round(decision.consensus_score, 3),
            confidence=round(decision.overall_confidence, 3),
            duration_ms=round(elapsed_ms),
            human_review=decision.requires_human_review,
            advisors=len(advisory_outputs),
        )
        return decision

    # ------------------------------------------------------------------
    # Private orchestration helpers
    # ------------------------------------------------------------------

    async def _round_analyze(
        self,
        query: str,
        context: dict[str, Any] | None,
    ) -> list[CellOutput]:
        """Execute Round 1: All cells analyze in parallel."""
        tasks = [
            cell.analyze(query=query, context=context)
            for cell in self._cells.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        outputs = []
        for cell, result in zip(self._cells.values(), results):
            if isinstance(result, Exception):
                self.log.error("cell.analyze.failed", cell_id=cell.id, error=str(result))
            else:
                outputs.append(result)
        return outputs

    async def _round_debate(
        self,
        query: str,
        outputs: list[CellOutput],
        round_number: int,
        context: dict[str, Any] | None,
    ) -> list[CellOutput]:
        """Execute a debate round: each cell reviews all other cells' outputs."""
        tasks = []
        for cell in self._cells.values():
            peer_outputs = [o for o in outputs if o.cell_id != cell.id]
            tasks.append(
                cell.debate(
                    query=query,
                    other_outputs=peer_outputs,
                    round_number=round_number,
                    context=context,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        debate_outputs = []
        for cell, result in zip(self._cells.values(), results):
            if isinstance(result, Exception):
                self.log.error("cell.debate.failed", cell_id=cell.id, error=str(result))
            else:
                debate_outputs.append(result)
        return debate_outputs

    def _extract_action_items(self, outputs: list[CellOutput]) -> list[str]:
        """Extract actionable items from cell recommendations."""
        items = []
        for o in outputs:
            rec = o.recommendation.strip()
            if rec and len(rec) > 10:
                items.append(f"[{o.cell_role.value.upper()}] {rec}")
        return items

    # ------------------------------------------------------------------
    # Health & introspection
    # ------------------------------------------------------------------

    def health_check(self) -> list[CellHealthReport]:
        """Return health reports for all cells in the council."""
        return [cell.health_report() for cell in self._cells.values()]

    def __repr__(self) -> str:
        return (
            f"<Council name={self.name!r} id={self.id} "
            f"cells={self.cell_count} strategy={self._consensus_engine.strategy.value}>"
        )
