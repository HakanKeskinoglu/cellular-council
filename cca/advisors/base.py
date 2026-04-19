# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

import structlog

from cca.core import CellOutput, CellRole, SignalType


class AdvisorRole(str, Enum):
    ETHICS_AUDITOR = "ethics_auditor"
    RISK_AUDITOR = "risk_auditor"
    PROCESS_MONITOR = "process_monitor"
    COMPLIANCE_AUDITOR = "compliance_auditor"


class BaseAdvisor(ABC):
    """
    Abstract base class for all CCA advisors.

    Advisors provide independent, non-voting oversight to the council.
    """

    def __init__(self, role: AdvisorRole, llm_backend: Any, **kwargs: Any) -> None:
        self.id = str(uuid.uuid4())[:8]
        self.role = role
        self.llm = llm_backend
        self.log = structlog.get_logger(__name__).bind(
            advisor_id=self.id, role=role.value
        )

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        ...

    @abstractmethod
    async def advise(
        self,
        query: str,
        cell_outputs: list[CellOutput],
        context: dict[str, Any] | None = None,
    ) -> CellOutput:
        ...

    async def _call_llm(
        self,
        user_message: str,
        context: dict[str, Any] | None = None,
    ) -> CellOutput:
        """Invoke the LLM backend and parse the response into a CellOutput."""
        context_str = ""
        if context:
            context_str = "\n\nCONTEXT:\n" + "\n".join(
                f"  {k}: {v}" for k, v in context.items()
            )

        raw_response = await self.llm.complete(
            system=self.system_prompt,
            user=user_message + context_str,
        )

        return _parse_llm_response(raw_response, advisor_id=self.id, role=self.role)


def _parse_llm_response(raw: str, advisor_id: str, role: AdvisorRole) -> CellOutput:
    """Parse a raw LLM response string into a structured CellOutput."""
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
        extract(r"(?:ANALYSIS|ADVISORY)[:\s]+(.*?)(?=RECOMMENDATION|REASONING|CONFIDENCE|$)")
        or raw[:500]
    )
    recommendation = extract(r"RECOMMENDATION[:\s]+(.*?)(?=REASONING|CONFIDENCE|RISK|CONCERN|$)")
    reasoning = extract(r"REASONING[:\s]+(.*?)(?=CONFIDENCE|RISK|$)")
    confidence = extract_float(r"CONFIDENCE[:\s]+([\d.]+%?)")
    risk_score = extract_float(r"RISK[_\s]SCORE[:\s]+([\d.]+%?)", default=0.0)

    return CellOutput(
        cell_id=advisor_id,
        cell_role=CellRole.CUSTOM,
        analysis=analysis,
        recommendation=recommendation or analysis,
        reasoning=reasoning or "See analysis.",
        confidence=confidence,
        risk_score=risk_score if risk_score > 0 else None,
        signal_type=SignalType.ADVISORY,
        metadata={"raw_response_length": len(raw), "advisor_role": role.value},
    )
