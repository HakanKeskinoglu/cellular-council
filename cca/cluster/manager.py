# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Cluster: Groups cells and manages structured debate rounds.

A Cluster is a logical grouping of cells that deliberate on the same topic.
It orchestrates the debate lifecycle:

    Round 1: Every cell independently analyzes the topic.
    Round 2+: Each cell reviews all peer outputs and produces a refined response.

After all rounds complete, the cluster returns the full list of outputs
for the consensus engine to aggregate.

    ┌──────────────────────────────────────────────┐
    │                   Cluster                    │
    │                                              │
    │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐     │
    │  │Cell A│  │Cell B│  │Cell C│  │Cell D│     │
    │  └──┬───┘  └──┬───┘  └──┬───┘  └──┬───┘     │
    │     │         │         │         │          │
    │     └────────┬┴─────────┴┬────────┘          │
    │              ▼           ▼                   │
    │       Round 1 (parallel analyze)             │
    │       Round 2 (cross-examine)                │
    │       Round N (converge)                     │
    │              │                               │
    │              ▼                               │
    │     list[CellOutput]                         │
    └──────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from cca.cells.base import BaseCell
from cca.core import CellOutput

logger = structlog.get_logger(__name__)


class Cluster:
    """
    A logical group of cells that debate a topic together.

    Parameters
    ----------
    name : str
        Human-readable name for this cluster.
    cells : list[BaseCell], optional
        Initial set of cells. More can be added with ``add_cell()``.
    """

    def __init__(self, name: str = "default", cells: list[BaseCell] | None = None) -> None:
        self.name = name
        self._cells: list[BaseCell] = list(cells) if cells else []
        self.log = logger.bind(cluster=name)

    # ------------------------------------------------------------------
    # Cell management
    # ------------------------------------------------------------------

    def add_cell(self, cell: BaseCell) -> None:
        """Register a cell with this cluster."""
        self._cells.append(cell)
        self.log.info("cluster.cell.added", cell_id=cell.id, role=cell.role.value)

    def remove_cell(self, cell_id: str) -> None:
        """Remove a cell by ID."""
        self._cells = [c for c in self._cells if c.id != cell_id]

    @property
    def cells(self) -> list[BaseCell]:
        return list(self._cells)

    @property
    def cell_count(self) -> int:
        return len(self._cells)

    # ------------------------------------------------------------------
    # Debate orchestration
    # ------------------------------------------------------------------

    async def run_debate(
        self,
        topic: str,
        rounds: int = 2,
        context: dict[str, Any] | None = None,
    ) -> list[CellOutput]:
        """
        Run a multi-round debate across all cells in this cluster.

        Parameters
        ----------
        topic : str
            The question or problem to debate.
        rounds : int
            Total number of rounds (including the initial analysis round).
            Minimum 1. Default: 2 (one analysis + one debate).
        context : dict, optional
            Additional context passed to each cell.

        Returns
        -------
        list[CellOutput]
            All outputs from every round, in chronological order.

        Raises
        ------
        ValueError
            If the cluster has no cells.
        """
        if not self._cells:
            raise ValueError("Cluster has no cells. Add cells before running a debate.")

        rounds = max(1, rounds)
        all_outputs: list[CellOutput] = []

        self.log.info("cluster.debate.start", topic=topic[:80], rounds=rounds)

        # --- Round 1: Parallel independent analysis ---
        round1_tasks = [cell.analyze(query=topic, context=context) for cell in self._cells]
        round1_results = await asyncio.gather(*round1_tasks, return_exceptions=True)

        current_outputs: list[CellOutput] = []
        for cell, result in zip(self._cells, round1_results):
            if isinstance(result, Exception):
                self.log.error("cluster.cell.failed", cell_id=cell.id, error=str(result))
            else:
                current_outputs.append(result)
        all_outputs.extend(current_outputs)

        self.log.info("cluster.round.complete", round=1, outputs=len(current_outputs))

        # --- Rounds 2+: Cross-examination debate ---
        for round_num in range(2, rounds + 1):
            debate_tasks = []
            for cell in self._cells:
                peer_outputs = [o for o in current_outputs if o.cell_id != cell.id]
                debate_tasks.append(
                    cell.debate(
                        query=topic,
                        other_outputs=peer_outputs,
                        round_number=round_num,
                        context=context,
                    )
                )

            debate_results = await asyncio.gather(*debate_tasks, return_exceptions=True)

            round_outputs: list[CellOutput] = []
            for cell, result in zip(self._cells, debate_results):
                if isinstance(result, Exception):
                    self.log.error(
                        "cluster.debate.failed",
                        cell_id=cell.id,
                        round=round_num,
                        error=str(result),
                    )
                else:
                    round_outputs.append(result)

            all_outputs.extend(round_outputs)
            current_outputs = round_outputs
            self.log.info("cluster.round.complete", round=round_num, outputs=len(round_outputs))

        self.log.info("cluster.debate.complete", total_outputs=len(all_outputs))
        return all_outputs

    def __repr__(self) -> str:
        return f"<Cluster name={self.name!r} cells={self.cell_count}>"
