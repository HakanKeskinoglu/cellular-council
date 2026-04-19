# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
StemCell: Undifferentiated cell that specializes at runtime.

Mirrors biological stem cell differentiation — the same base model with
different "gene expression" (system prompts) generated on demand.

    ┌─────────────────────────────────────────────────────────┐
    │                     StemCell                            │
    │                                                         │
    │  State: DORMANT → DIFFERENTIATING → ACTIVE → DORMANT   │
    │                                                         │
    │  differentiate(role, context)                           │
    │     → generates system_prompt at runtime                │
    │     → cell now behaves as a specialist                  │
    │                                                         │
    │  reset()                                                │
    │     → clears specialization, returns to pool            │
    └─────────────────────────────────────────────────────────┘

Design Decisions (from README)
------------------------------
- Who triggers differentiation?  → Rule-based for now (deterministic, testable)
- Who writes the system prompt?  → Template fill (avoids second LLM trust surface)
- When is the cell recycled?     → After session (clean state guarantees)
- Depth applies?                 → Cap at 1 for stem-originated sub-councils
"""

from __future__ import annotations

from typing import Any

import structlog

from cca.cells.base import BaseCell
from cca.core import CellOutput, CellRole, CellState, SignalType
from cca.core.prompts import CELL_OUTPUT_FORMAT

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates for stem cell differentiation
# ---------------------------------------------------------------------------

_STEM_PROMPT_TEMPLATES: dict[str, str] = {
    "database": """You are a DATABASE SPECIALIST in a multi-agent decision council.

Your expertise: relational databases (PostgreSQL, MySQL), NoSQL (MongoDB, Redis),
query optimization, replication, backup/restore, ACID guarantees, connection pooling,
schema design, migration strategies, and data integrity.

When analyzing:
- Assess database health and performance implications
- Identify data integrity risks
- Evaluate backup and recovery readiness
- Recommend database-specific actions

{output_format}""",

    "network": """You are a NETWORK SPECIALIST in a multi-agent decision council.

Your expertise: TCP/IP, BGP/OSPF routing, DNS, load balancing, CDN,
firewalls, VPN, network segmentation, bandwidth management, latency
optimization, packet analysis, and network security.

When analyzing:
- Identify affected network layers (L1–L7)
- Estimate blast radius across the network topology
- Distinguish symptoms from root causes
- Recommend network-level remediation

{output_format}""",

    "system": """You are a SYSTEMS ENGINEER SPECIALIST in a multi-agent decision council.

Your expertise: Linux/Unix administration, containerization (Docker/K8s),
process management, memory management, CPU scheduling, filesystem,
monitoring (Prometheus/Grafana), log analysis, and infrastructure automation.

When analyzing:
- Assess system resource utilization and bottlenecks
- Identify process, memory, or storage issues
- Evaluate container orchestration health
- Recommend system-level remediation

{output_format}""",

    "performance": """You are a PERFORMANCE ENGINEERING SPECIALIST in a multi-agent decision council.

Your expertise: load testing, profiling, bottleneck analysis, caching strategies,
query optimization, CDN tuning, connection pool sizing, thread pool management,
and capacity planning.

When analyzing:
- Identify performance bottlenecks and their root causes
- Quantify impact on latency, throughput, and resource utilization
- Recommend targeted performance optimizations
- Estimate capacity limits and scaling requirements

{output_format}""",

    "incident_response": """You are an INCIDENT RESPONSE SPECIALIST in a multi-agent decision council.

Your expertise: incident management (PagerDuty/OpsGenie), runbook execution,
war room coordination, post-mortem analysis, SLA management, communication
protocols, escalation procedures, and disaster recovery.

When analyzing:
- Classify incident severity (P1–P4)
- Recommend immediate response actions
- Identify communication and escalation needs
- Suggest runbook or playbook to execute

{output_format}""",
}

_GENERIC_TEMPLATE = """You are a {role} SPECIALIST in a multi-agent decision council.

Your exclusive focus: analyze problems from the perspective of a {role} expert.

Core responsibilities:
- Provide thorough analysis from your specialized viewpoint
- Identify issues and opportunities specific to your domain
- Recommend concrete actions with clear justification
- Quantify confidence and risk where applicable
{regulations_section}
{context_section}

{output_format}"""


class StemCell(BaseCell):
    """
    Undifferentiated cell that can be specialized at runtime.

    A StemCell has no fixed role. The council assigns it a specialization
    by generating a system prompt on the fly. This mirrors biological cell
    differentiation — the same base model, different gene expression.

    Parameters
    ----------
    llm_backend : Any
        LLM backend instance.
    **kwargs
        Additional parameters passed to BaseCell.

    Examples
    --------
    >>> stem = StemCell(llm_backend=backend)
    >>> await stem.differentiate("database", context={"db_type": "PostgreSQL"})
    >>> output = await stem.analyze("Should we failover to replica?")
    >>> stem.reset()  # Returns to undifferentiated state
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=CellRole.STEM, llm_backend=llm_backend, **kwargs)
        self._dynamic_role: str | None = None
        self._dynamic_system_prompt: str | None = None
        self._differentiated: bool = False
        self._regulations: list[str] | None = None
        self._differentiation_context: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Differentiation
    # ------------------------------------------------------------------

    async def differentiate(
        self,
        role: str,
        context: dict[str, Any] | None = None,
        regulations: list[str] | None = None,
    ) -> StemCell:
        """
        Specialize this stem cell into a domain expert at runtime.

        Generates a role-specific system prompt either from a known template
        or from a generic template filled with the role name. Uses template
        fill approach (not meta-LLM call) for determinism and testability.

        Parameters
        ----------
        role : str
            The specialization role (e.g., "database", "network", "custom_role").
        context : dict, optional
            Domain context to enrich the system prompt.
        regulations : list[str], optional
            Regulatory frameworks to include in the prompt.

        Returns
        -------
        StemCell
            self, now differentiated and ready for analysis.

        Raises
        ------
        RuntimeError
            If the cell is already differentiated (call reset() first).
        """
        if self._differentiated:
            raise RuntimeError(
                f"StemCell {self.id} is already differentiated as '{self._dynamic_role}'. "
                "Call reset() before re-differentiating."
            )

        self._state = CellState.DIFFERENTIATING
        self._dynamic_role = role.lower()
        self._regulations = regulations
        self._differentiation_context = context

        self._dynamic_system_prompt = self._generate_system_prompt(
            role=self._dynamic_role,
            context=context,
            regulations=regulations,
        )

        self._differentiated = True
        self._state = CellState.ACTIVE

        self.log.info(
            "stem_cell.differentiated",
            dynamic_role=self._dynamic_role,
            template_used=self._dynamic_role in _STEM_PROMPT_TEMPLATES,
        )
        return self

    def _generate_system_prompt(
        self,
        role: str,
        context: dict[str, Any] | None = None,
        regulations: list[str] | None = None,
    ) -> str:
        """
        Generate a system prompt for the given specialization.

        Uses template fill approach (Paper 4 recommendation) — avoids
        a second LLM trust surface and remains deterministic/testable.
        """
        # Check for a known template first
        if role in _STEM_PROMPT_TEMPLATES:
            return _STEM_PROMPT_TEMPLATES[role].format(
                output_format=CELL_OUTPUT_FORMAT
            )

        # Fall back to generic template
        regulations_section = ""
        if regulations:
            regs = ", ".join(regulations)
            regulations_section = f"\nRegulatory frameworks to consider: {regs}"

        context_section = ""
        if context:
            ctx_lines = "\n".join(f"  - {k}: {v}" for k, v in context.items())
            context_section = f"\nDomain context:\n{ctx_lines}"

        return _GENERIC_TEMPLATE.format(
            role=role.upper(),
            regulations_section=regulations_section,
            context_section=context_section,
            output_format=CELL_OUTPUT_FORMAT,
        )

    # ------------------------------------------------------------------
    # BaseCell interface
    # ------------------------------------------------------------------

    @property
    def system_prompt(self) -> str:
        """Return the dynamically generated system prompt."""
        if not self._differentiated or self._dynamic_system_prompt is None:
            raise RuntimeError(
                f"StemCell {self.id} must be differentiated before use. "
                "Call await stem.differentiate('role_name') first."
            )
        return self._dynamic_system_prompt

    async def analyze(self, query: str, context: dict[str, Any] | None = None) -> CellOutput:
        """
        Perform analysis using the differentiated specialization.

        Raises RuntimeError if the cell has not been differentiated.
        """
        if not self._differentiated:
            raise RuntimeError(
                f"StemCell {self.id} must be differentiated before analysis. "
                "Call await stem.differentiate('role_name') first."
            )

        prompt = f"""SPECIALIST ANALYSIS REQUEST ({self._dynamic_role.upper()}):

{query}

Provide a thorough analysis from your specialized perspective."""

        return await self._call_llm(prompt, context=context, signal_type=SignalType.ANALYSIS)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """
        Clear the specialization and return to undifferentiated state.

        After reset, this cell can be re-differentiated into a different
        role. Used by StemCellPool for cell recycling.
        """
        self._dynamic_role = None
        self._dynamic_system_prompt = None
        self._differentiated = False
        self._regulations = None
        self._differentiation_context = None
        self._state = CellState.DORMANT

        self.log.info("stem_cell.reset")

    @property
    def is_differentiated(self) -> bool:
        """Whether this stem cell has been specialized."""
        return self._differentiated

    @property
    def dynamic_role(self) -> str | None:
        """The current dynamic specialization role, or None."""
        return self._dynamic_role

    def __repr__(self) -> str:
        role_str = self._dynamic_role or "undifferentiated"
        return (
            f"<StemCell id={self.id} role={role_str} "
            f"differentiated={self._differentiated} state={self._state.value}>"
        )
