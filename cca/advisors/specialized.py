# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Built-in specialized advisors for the CCA Framework.

Advisors provide independent, non-voting oversight to the council.
Each advisor type focuses on a specific governance concern:

- EthicsAuditor    — Reviews decisions for ethical violations and bias
- RiskAuditor      — Second-checks the Risk Cell's blind spots
- ProcessMonitor   — Detects groupthink, process failures, and deliberation quality issues
- ComplianceAuditor — Checks decisions against regulatory frameworks

Advisors run AFTER all cells have completed their analysis/debate rounds
but BEFORE the consensus engine produces its result. Their notes are
appended to the final CouncilDecision as advisory_notes.
"""

from __future__ import annotations

from typing import Any

from cca.advisors.base import AdvisorRole, BaseAdvisor
from cca.core import CellOutput, CellRole, SignalType
from cca.core.prompts import ADVISORY_OUTPUT_FORMAT


# ---------------------------------------------------------------------------
# Specialized advisors
# ---------------------------------------------------------------------------

class EthicsAuditor(BaseAdvisor):
    """
    Independent ethics oversight for council decisions.

    Reviews all cell outputs for ethical blind spots, bias, fairness
    violations, and stakeholder harm that the council may have overlooked.
    Modeled after an independent ethics board member in corporate governance.
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=AdvisorRole.ETHICS_AUDITOR, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return f"""You are an INDEPENDENT ETHICS AUDITOR observing a multi-agent decision council.

You are NOT a voting member — your role is oversight and accountability.

Your responsibilities:
- Review all specialist analyses for ethical blind spots
- Detect potential bias in the council's collective reasoning
- Flag decisions that prioritize efficiency over human welfare
- Identify stakeholders whose interests may be underrepresented
- Check for transparency and explainability of the decision
- Assess whether the decision could be defended to the public

You should be constructive but unafraid to raise uncomfortable truths.
Your advisory notes will be preserved alongside the final decision
for accountability and audit trail purposes.

{ADVISORY_OUTPUT_FORMAT}"""

    async def advise(
        self,
        query: str,
        cell_outputs: list[CellOutput],
        context: dict[str, Any] | None = None,
    ) -> CellOutput:
        outputs_summary = "\n\n".join([
            f"[{o.cell_role.value.upper()} CELL]:\n"
            f"Analysis: {o.analysis}\n"
            f"Recommendation: {o.recommendation}\n"
            f"Confidence: {o.confidence:.0%}"
            for o in cell_outputs
            if o.signal_type != SignalType.ADVISORY
        ])

        prompt = f"""ETHICS AUDIT of council deliberation:

ORIGINAL QUERY:
{query}

CELL ANALYSES TO REVIEW:
{outputs_summary}

As an independent ethics auditor, review these analyses:
1. Are there any ethical blind spots across the council?
2. Are all affected stakeholders considered fairly?
3. Is there evidence of bias or groupthink in the collective analysis?
4. Could this decision be ethically defended if scrutinized publicly?
5. Are there any fundamental principles being violated?"""

        return await self._call_llm(prompt, context=context)


class RiskAuditor(BaseAdvisor):
    """
    Second-checks the Risk Cell's analysis for blind spots.

    Acts as a meta-reviewer: instead of performing independent risk analysis,
    it reviews the Risk Cell's output specifically and challenges any
    assumptions, missing scenarios, or underestimated probabilities.
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=AdvisorRole.RISK_AUDITOR, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return f"""You are an INDEPENDENT RISK AUDITOR observing a multi-agent decision council.

You are NOT a voting member — your role is to second-check risk assessments.

Your responsibilities:
- Review the Risk Cell's analysis for missing failure modes
- Challenge assumptions behind probability and impact estimates
- Identify cascading risks that may not have been considered
- Check for normalcy bias (underestimating unlikely but catastrophic events)
- Verify that mitigation strategies are actionable and sufficient
- Flag any risk scores that seem unreasonably low or high

Think like a senior risk auditor at a financial institution who has
seen many "tail risk" events that were initially dismissed.

{ADVISORY_OUTPUT_FORMAT}"""

    async def advise(
        self,
        query: str,
        cell_outputs: list[CellOutput],
        context: dict[str, Any] | None = None,
    ) -> CellOutput:
        # Find the Risk Cell's output specifically
        risk_outputs = [o for o in cell_outputs if o.cell_role == CellRole.RISK]
        all_outputs_summary = "\n\n".join([
            f"[{o.cell_role.value.upper()} CELL]:\n"
            f"Analysis: {o.analysis}\n"
            f"Recommendation: {o.recommendation}\n"
            f"Confidence: {o.confidence:.0%}\n"
            f"Risk Score: {o.risk_score or 'N/A'}"
            for o in cell_outputs
            if o.signal_type != SignalType.ADVISORY
        ])

        risk_section = ""
        if risk_outputs:
            r = risk_outputs[0]
            risk_section = f"""
PRIMARY RISK CELL OUTPUT TO AUDIT:
Analysis: {r.analysis}
Recommendation: {r.recommendation}
Risk Score: {r.risk_score or 'N/A'}
Confidence: {r.confidence:.0%}
"""

        prompt = f"""RISK AUDIT of council deliberation:

ORIGINAL QUERY:
{query}
{risk_section}
ALL CELL ANALYSES:
{all_outputs_summary}

As an independent risk auditor:
1. Has the Risk Cell identified all material failure modes?
2. Are the probability and impact estimates reasonable?
3. What cascading risks might have been missed?
4. Are the proposed mitigation strategies sufficient?
5. Is there normalcy bias in the risk assessment?"""

        return await self._call_llm(prompt, context=context)


class ProcessMonitor(BaseAdvisor):
    """
    Monitors the quality of the deliberation process itself.

    Detects groupthink, echo chambers, insufficient debate, and
    process failures that compromise decision quality — independent
    of the decision's content.
    """

    def __init__(self, llm_backend: Any, **kwargs: Any) -> None:
        super().__init__(role=AdvisorRole.PROCESS_MONITOR, llm_backend=llm_backend, **kwargs)

    @property
    def system_prompt(self) -> str:
        return f"""You are a PROCESS QUALITY MONITOR observing a multi-agent decision council.

You are NOT evaluating the decision itself — you are evaluating the
QUALITY OF THE DELIBERATION PROCESS.

Your responsibilities:
- Detect groupthink: Are all cells reaching the same conclusion too easily?
- Identify echo chambers: Are cells simply echoing each other's reasoning?
- Check for sufficient debate: Did cells genuinely challenge each other?
- Evaluate confidence calibration: Are confidence scores well-justified?
- Flag anchoring bias: Is one dominant cell unduly influencing others?
- Assess completeness: Are there important perspectives missing from the council?

Your advisory note should focus on PROCESS improvements, not the
decision outcome. Think like a management consultant evaluating
a corporate board's decision-making process.

{ADVISORY_OUTPUT_FORMAT}"""

    async def advise(
        self,
        query: str,
        cell_outputs: list[CellOutput],
        context: dict[str, Any] | None = None,
    ) -> CellOutput:
        # Analyze process metrics
        voting_outputs = [o for o in cell_outputs if o.signal_type != SignalType.ADVISORY]
        confidences = [o.confidence for o in voting_outputs]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        conf_spread = max(confidences) - min(confidences) if len(confidences) > 1 else 0

        outputs_summary = "\n\n".join([
            f"[{o.cell_role.value.upper()} CELL] (Round {o.round_number}):\n"
            f"Recommendation: {o.recommendation}\n"
            f"Confidence: {o.confidence:.0%}"
            for o in voting_outputs
        ])

        prompt = f"""PROCESS QUALITY AUDIT:

ORIGINAL QUERY:
{query}

CELL OUTPUTS TO EVALUATE (process quality, not content):
{outputs_summary}

PROCESS METRICS:
- Total outputs: {len(voting_outputs)}
- Average confidence: {avg_conf:.0%}
- Confidence spread: {conf_spread:.0%} (low spread may indicate groupthink)
- Unique roles: {len(set(o.cell_role.value for o in voting_outputs))}

Evaluate the deliberation process:
1. GROUPTHINK: Are all cells suspiciously agreeing? (confidence spread < 10% is a red flag)
2. ECHO CHAMBER: Are later-round outputs just restating earlier ones?
3. ANCHORING: Is one high-confidence cell dominating the narrative?
4. COMPLETENESS: Are important analytical perspectives missing?
5. CALIBRATION: Do the confidence scores seem well-justified?"""

        return await self._call_llm(prompt, context=context)


class ComplianceAuditor(BaseAdvisor):
    """
    Checks decisions against regulatory and compliance frameworks.

    Configurable with specific regulations to enforce (GDPR, SOC2,
    ISO 27001, HIPAA, etc.).
    """

    def __init__(
        self,
        llm_backend: Any,
        regulations: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            role=AdvisorRole.COMPLIANCE_AUDITOR,
            llm_backend=llm_backend,
            **kwargs,
        )
        self.regulations = regulations or ["GDPR", "SOC2", "ISO27001"]

    @property
    def system_prompt(self) -> str:
        regs = ", ".join(self.regulations)
        return f"""You are a COMPLIANCE AUDITOR observing a multi-agent decision council.

You are NOT a voting member — your role is regulatory oversight.

Regulatory frameworks you are responsible for: {regs}

Your responsibilities:
- Check if the proposed decision violates any applicable regulation
- Identify data handling, privacy, or security compliance gaps
- Flag decisions that could trigger regulatory penalties
- Recommend compliance safeguards to add before implementation
- Note any audit trail or documentation requirements

Be specific about which regulation clause is relevant.
Use language like "Under GDPR Article 17..." or "SOC2 CC6.1 requires...".

{ADVISORY_OUTPUT_FORMAT}"""

    async def advise(
        self,
        query: str,
        cell_outputs: list[CellOutput],
        context: dict[str, Any] | None = None,
    ) -> CellOutput:
        outputs_summary = "\n\n".join([
            f"[{o.cell_role.value.upper()} CELL]:\n"
            f"Recommendation: {o.recommendation}"
            for o in cell_outputs
            if o.signal_type != SignalType.ADVISORY
        ])

        regs = ", ".join(self.regulations)
        prompt = f"""COMPLIANCE AUDIT ({regs}):

ORIGINAL QUERY:
{query}

CELL RECOMMENDATIONS TO REVIEW:
{outputs_summary}

Audit for compliance with {regs}:
1. Does any recommendation violate applicable regulations?
2. Are there data handling or privacy implications?
3. What compliance safeguards should be added?
4. Are there documentation or audit trail requirements?
5. Could this decision trigger regulatory scrutiny?"""

        return await self._call_llm(prompt, context=context)


# ---------------------------------------------------------------------------
# Advisor registry — for dynamic instantiation
# ---------------------------------------------------------------------------

ADVISOR_REGISTRY: dict[AdvisorRole, type[BaseAdvisor]] = {
    AdvisorRole.ETHICS_AUDITOR: EthicsAuditor,
    AdvisorRole.RISK_AUDITOR: RiskAuditor,
    AdvisorRole.PROCESS_MONITOR: ProcessMonitor,
    AdvisorRole.COMPLIANCE_AUDITOR: ComplianceAuditor,
}


def create_advisor(role: AdvisorRole, llm_backend: Any, **kwargs: Any) -> BaseAdvisor:
    """
    Factory function to instantiate an advisor by role.

    Parameters
    ----------
    role : AdvisorRole
        The desired advisor specialization.
    llm_backend : Any
        LLM backend to power this advisor.
    **kwargs
        Additional parameters passed to the advisor constructor.

    Raises
    ------
    ValueError
        If the role has no registered advisor class.
    """
    if role not in ADVISOR_REGISTRY:
        raise ValueError(
            f"No built-in advisor for role '{role.value}'. "
            f"Available roles: {[r.value for r in ADVISOR_REGISTRY]}"
        )
    return ADVISOR_REGISTRY[role](llm_backend=llm_backend, **kwargs)
