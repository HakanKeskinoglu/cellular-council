# Copyright 2025 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Shared prompt templates for CCA cells and advisors.

Centralizes the structured output format instructions so all agents
use a consistent format and changes are made in one place.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Shared structured output format
# ---------------------------------------------------------------------------

CELL_OUTPUT_FORMAT = """
Respond ONLY in the following structured format:

ANALYSIS:
[Your detailed analysis from your specialized perspective]

RECOMMENDATION:
[Your specific recommended action or decision]

REASONING:
[Step-by-step chain of thought that led to your recommendation]

CONFIDENCE: [0.0–1.0 or percentage]

RISK_SCORE: [0.0–1.0 where 1.0 = maximum risk, only if applicable]
"""

ADVISORY_OUTPUT_FORMAT = """
Respond ONLY in the following structured format:

ADVISORY:
[Your advisory observation — what you noticed as an independent reviewer]

CONCERN:
[Specific concern or blind spot you identified, if any]

RECOMMENDATION:
[Your non-binding recommendation to the council]

CONFIDENCE: [0.0–1.0 — how confident you are in your advisory assessment]
"""

# ---------------------------------------------------------------------------
# Shared output-to-prompt formatting
# ---------------------------------------------------------------------------


def format_outputs_for_prompt(
    outputs: list,
    label: str = "SPECIALIST",
    include_analysis: bool = True,
    include_confidence: bool = True,
    include_risk: bool = False,
) -> str:
    """
    Format a list of CellOutput objects into a text block for LLM consumption.

    Parameters
    ----------
    outputs : list[CellOutput]
        The outputs to format.
    label : str
        Label for each block (e.g., "SPECIALIST", "CELL").
    include_analysis : bool
        Whether to include the analysis field.
    include_confidence : bool
        Whether to include the confidence field.
    include_risk : bool
        Whether to include the risk_score field.
    """
    parts = []
    for o in outputs:
        block = f"[{o.cell_role.value.upper()} {label}]:\n"
        if include_analysis:
            block += f"Analysis: {o.analysis}\n"
        block += f"Recommendation: {o.recommendation}\n"
        if include_confidence:
            block += f"Confidence: {o.confidence:.0%}\n"
        if include_risk and o.risk_score is not None:
            block += f"Risk Score: {o.risk_score}\n"
        parts.append(block)
    return "\n\n".join(parts)
