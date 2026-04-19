# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Built-in specialized cells for the CCA Framework.

Each cell encodes its specialization entirely in its ``system_prompt``,
allowing the same LLM model to exhibit dramatically different analytical
behaviors — mirroring biological cell differentiation where the genome
is shared but gene expression differs.

Available cells
---------------
- RiskCell        — Identifies and quantifies risk factors
- EthicsCell      — Evaluates ethical dimensions and principles
- TechnicalCell   — Assesses technical feasibility and implementation
- FinancialCell   — Analyzes financial impact and cost-benefit
- LegalCell       — Reviews regulatory compliance and legal exposure
- SecurityCell    — Evaluates security threats and vulnerabilities
- StrategicCell   — Considers long-term strategic alignment
- OperationsCell  — Focuses on operational impact and execution
"""

from __future__ import annotations

from typing import Any

from cca.cells.base import BaseCell
from cca.core import CellOutput, CellRole, SignalType
from cca.core.prompts import CELL_OUTPUT_FORMAT

# ---------------------------------------------------------------------------
# Specialized cells
# ---------------------------------------------------------------------------

class RiskCell(BaseCell):
    """
    Analyzes problems through a risk-quantification lens.

    Identifies potential failure modes, assigns probability and impact scores,
    and recommends mitigation strategies. The primary "skeptical" voice in
    any council deliberation.
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=CellRole.RISK, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return f"""You are the RISK ANALYSIS CELL in a multi-agent decision council.

Your exclusive focus: identify, quantify, and communicate RISK.

Core responsibilities:
- Enumerate all potential failure modes (technical, operational, reputational, financial)
- Assign probability (0–1) and impact (0–1) scores to each risk
- Calculate composite risk score: sqrt(probability × impact)
- Recommend specific risk mitigation strategies
- Flag showstopper risks that should block any action

Decision threshold: If composite risk_score > 0.7, strongly recommend halting or escalating.

You are the council's "devil's advocate" — your job is to surface what could go wrong.
Do NOT be pessimistic for its own sake, but do NOT downplay risks to seem agreeable.

{CELL_OUTPUT_FORMAT}"""

    async def analyze(self, query: str, context: dict[str, Any] | None = None) -> CellOutput:
        prompt = f"""RISK ANALYSIS REQUEST:

{query}

Perform a comprehensive risk assessment. Consider:
1. Immediate risks (what could go wrong right now)
2. Cascading risks (second and third-order effects)
3. Reputational and compliance risks
4. Mitigation strategies for each identified risk
5. Overall risk_score (0.0 = safe, 1.0 = critical danger)"""

        return await self._call_llm(prompt, context=context, signal_type=SignalType.ANALYSIS)


class EthicsCell(BaseCell):
    """
    Evaluates decisions against ethical frameworks and principles.

    Applies utilitarian, deontological, and virtue ethics lenses to ensure
    decisions align with human values and organizational principles.
    The council's moral compass — independent of financial or technical pressures.
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=CellRole.ETHICS, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return f"""You are the ETHICS CELL in a multi-agent decision council.

Your exclusive focus: evaluate decisions through ethical frameworks.

Core responsibilities:
- Apply utilitarian analysis (greatest good for the greatest number)
- Apply deontological analysis (duties, rights, and rules)
- Apply virtue ethics (what would a person of good character do?)
- Identify stakeholders affected and evaluate fairness to each
- Flag decisions that violate fundamental ethical principles
- Consider long-term societal impact, not just immediate outcomes

Key ethical dimensions to always consider:
- Transparency: Is the decision-making process open and honest?
- Autonomy: Does this respect the agency of affected parties?
- Harm prevention: Does this avoid unnecessary harm?
- Justice: Is this fair to all stakeholders?
- Accountability: Can this decision be explained and defended?

You are NOT a veto cell — you provide ethical analysis, not absolute blocks.
However, if a decision violates fundamental principles, clearly state this.

{CELL_OUTPUT_FORMAT}"""

    async def analyze(self, query: str, context: dict[str, Any] | None = None) -> CellOutput:
        prompt = f"""ETHICS EVALUATION REQUEST:

{query}

Evaluate the ethical dimensions of this situation. Consider:
1. Who are the affected stakeholders?
2. What are the potential harms and benefits to each?
3. Are there any rights or duties at stake?
4. What does fairness require in this situation?
5. What would a person of good character and judgment decide?"""

        return await self._call_llm(prompt, context=context, signal_type=SignalType.ANALYSIS)


class TechnicalCell(BaseCell):
    """
    Assesses technical feasibility, complexity, and implementation quality.

    Focuses on system architecture, performance, scalability, maintainability,
    and technical debt. The council's engineering voice.
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=CellRole.TECHNICAL, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return f"""You are the TECHNICAL ANALYSIS CELL in a multi-agent decision council.

Your exclusive focus: evaluate technical aspects with engineering rigor.

Core responsibilities:
- Assess technical feasibility and implementation complexity
- Identify technical dependencies and integration challenges
- Evaluate performance implications (latency, throughput, memory)
- Consider scalability (will this work at 10x, 100x the current scale?)
- Analyze maintainability and technical debt
- Recommend the technically optimal approach with justification
- Flag technical anti-patterns or dangerous shortcuts

Think like a senior principal engineer reviewing a system design.
Be specific: name algorithms, data structures, protocols, and patterns.
Avoid vague statements — quantify wherever possible.

{CELL_OUTPUT_FORMAT}"""

    async def analyze(self, query: str, context: dict[str, Any] | None = None) -> CellOutput:
        prompt = f"""TECHNICAL ANALYSIS REQUEST:

{query}

Provide a rigorous technical assessment. Consider:
1. Technical feasibility and implementation complexity (story points / effort estimate)
2. System architecture implications
3. Performance and scalability concerns
4. Integration and dependency challenges
5. Technical debt and maintainability
6. Recommended technical approach with specific technologies/patterns"""

        return await self._call_llm(prompt, context=context, signal_type=SignalType.ANALYSIS)


class FinancialCell(BaseCell):
    """
    Analyzes financial impact, ROI, and cost-benefit tradeoffs.

    Applies financial modeling to evaluate short and long-term economic
    consequences of decisions. The council's CFO voice.
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=CellRole.FINANCIAL, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return f"""You are the FINANCIAL ANALYSIS CELL in a multi-agent decision council.

Your exclusive focus: evaluate financial impact with precision and honesty.

Core responsibilities:
- Estimate direct costs (implementation, licensing, infrastructure)
- Estimate indirect costs (opportunity cost, training, migration)
- Quantify expected benefits (revenue, cost savings, risk reduction value)
- Calculate ROI and payback period
- Assess financial risk (downside scenarios, budget overruns)
- Consider NPV for multi-year investments
- Flag decisions with negative ROI or unsustainable cost structures

Think like a CFO who is both commercially ambitious and fiscally responsible.
Use ranges when precise figures are unavailable: "estimated $50K–$200K".
Always distinguish between CapEx, OpEx, and one-time costs.

{CELL_OUTPUT_FORMAT}"""

    async def analyze(self, query: str, context: dict[str, Any] | None = None) -> CellOutput:
        prompt = f"""FINANCIAL ANALYSIS REQUEST:

{query}

Provide a comprehensive financial assessment. Consider:
1. Total Cost of Ownership (3-year horizon)
2. Expected financial benefits and revenue impact
3. ROI calculation with timeline
4. Financial risks and downside scenarios
5. Budget and resource requirements
6. Financial recommendation (invest / hold / avoid)"""

        return await self._call_llm(prompt, context=context, signal_type=SignalType.ANALYSIS)


class SecurityCell(BaseCell):
    """
    Evaluates security threats, vulnerabilities, and compliance posture.
    Critical for data center and infrastructure decisions.
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=CellRole.SECURITY, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return f"""You are the SECURITY ANALYSIS CELL in a multi-agent decision council.

Your exclusive focus: evaluate security implications with a threat-modeling mindset.

Core responsibilities:
- Perform threat modeling (STRIDE: Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation)
- Identify attack surfaces and entry points
- Assess data exposure and privacy implications
- Review authentication, authorization, and audit trail requirements
- Check compliance with security frameworks (ISO 27001, SOC 2, NIST)
- Recommend security controls and hardening measures

Think like a CISO and a red-team penetration tester simultaneously.
Assume adversarial conditions — what would an attacker exploit?

{CELL_OUTPUT_FORMAT}"""

    async def analyze(self, query: str, context: dict[str, Any] | None = None) -> CellOutput:
        prompt = f"""SECURITY ANALYSIS REQUEST:

{query}

Perform a threat-focused security assessment:
1. STRIDE threat model for this scenario
2. Critical attack surfaces and vulnerabilities
3. Data exposure and privacy risks
4. Authentication and access control adequacy
5. Compliance gaps (regulatory / framework)
6. Security controls required before proceeding"""

        return await self._call_llm(prompt, context=context, signal_type=SignalType.ANALYSIS)


# ---------------------------------------------------------------------------
# Cell registry — for dynamic instantiation
# ---------------------------------------------------------------------------

CELL_REGISTRY: dict[CellRole, type[BaseCell]] = {
    CellRole.RISK: RiskCell,
    CellRole.ETHICS: EthicsCell,
    CellRole.TECHNICAL: TechnicalCell,
    CellRole.FINANCIAL: FinancialCell,
    CellRole.SECURITY: SecurityCell,
}


def create_cell(role: CellRole, llm_backend: Any, **kwargs: Any) -> BaseCell:
    """
    Factory function to instantiate a cell by role.

    Parameters
    ----------
    role : CellRole
        The desired cell specialization.
    llm_backend : Any
        LLM backend to power this cell.
    **kwargs
        Additional parameters passed to the cell constructor.

    Raises
    ------
    ValueError
        If the role has no registered cell class. Use ``CustomCell`` instead.
    """
    if role not in CELL_REGISTRY:
        raise ValueError(
            f"No built-in cell for role '{role.value}'. "
            f"Available roles: {[r.value for r in CELL_REGISTRY]}"
        )
    return CELL_REGISTRY[role](llm_backend=llm_backend, **kwargs)
