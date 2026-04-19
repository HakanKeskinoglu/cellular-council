# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Apex Layer: The final decision authority in the Cellular Council Architecture.

The Apex Layer sits at the top of the council hierarchy. After all cells have
analyzed a problem and debated their perspectives, the Apex Layer synthesizes
every cell output into a single, authoritative decision.

This mirrors the role of a board chairman or CEO who listens to all advisors
and then makes the final call — weighing competing priorities, resolving
conflicts, and articulating a clear rationale.

    Cell Outputs ──┐
                   │
    Cell Outputs ──┼──▶  ApexLayer.synthesize()  ──▶  Final Decision
                   │
    Cell Outputs ──┘

The Apex Layer is used by the APEX_OVERRIDE consensus strategy, where
statistical aggregation is replaced by a holistic LLM synthesis.
"""

from __future__ import annotations

from typing import Any

import structlog

from cca.core import CellOutput

logger = structlog.get_logger(__name__)


class ApexLayer:
    """
    Final synthesis authority for the Cellular Council Architecture.

    The ApexLayer receives all cell outputs and uses an LLM to produce
    a single, holistic decision that accounts for every specialist
    perspective — resolving conflicts and highlighting consensus.

    Parameters
    ----------
    llm_backend : Any, optional
        LLM backend used for synthesis. Can be set at construction
        or passed per call to ``synthesize()``.
    """

    def __init__(self, llm_backend: Any | None = None) -> None:
        self.llm = llm_backend
        self.log = logger.bind(component="apex_layer")

    async def synthesize(
        self,
        cell_outputs: list[CellOutput],
        context: str,
        llm_backend: Any | None = None,
    ) -> str:
        """
        Synthesize all cell outputs into a final authoritative decision.

        Parameters
        ----------
        cell_outputs : list[CellOutput]
            Analysis outputs from every participating cell.
        context : str
            The original query or context string for the deliberation.
        llm_backend : Any, optional
            Override the instance-level LLM backend for this call.

        Returns
        -------
        str
            The synthesized final decision text.

        Raises
        ------
        ValueError
            If no cell outputs are provided.
        RuntimeError
            If no LLM backend is available.
        """
        if not cell_outputs:
            raise ValueError("ApexLayer requires at least one cell output to synthesize.")

        backend = llm_backend or self.llm
        if backend is None:
            raise RuntimeError(
                "ApexLayer has no LLM backend. Provide one at construction or via the "
                "llm_backend parameter."
            )

        self.log.info(
            "apex.synthesis.start",
            cell_count=len(cell_outputs),
        )

        # Build the specialist summary block
        specialist_block = "\n\n".join(
            f"=== {o.cell_role.value.upper()} SPECIALIST ===\n"
            f"Analysis: {o.analysis}\n"
            f"Recommendation: {o.recommendation}\n"
            f"Confidence: {o.confidence:.0%}\n"
            f"Reasoning: {o.reasoning}"
            for o in cell_outputs
        )

        system_prompt = (
            "You are the APEX SYNTHESIS LAYER of a multi-agent decision council. "
            "Your role is to read every specialist analysis and produce a single, "
            "authoritative, well-reasoned final decision. Be concise and actionable."
        )

        user_prompt = f"""CONTEXT:
{context}

SPECIALIST ANALYSES:
{specialist_block}

YOUR TASK:
1. Identify points of agreement across specialists.
2. Resolve any conflicts with clear justification.
3. Produce a single, actionable recommendation.
4. Note any critical minority views that decision-makers should be aware of.

Respond with a clear FINAL DECISION followed by a concise RATIONALE."""

        response = await backend.complete(system=system_prompt, user=user_prompt)

        self.log.info("apex.synthesis.complete", response_length=len(response))
        return response
