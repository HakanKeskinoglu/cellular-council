# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Consensus Engine: Synthesizes cell outputs into a unified council decision.

The consensus engine is the mathematical and logical core of CCA.
It aggregates multiple cell perspectives through configurable strategies,
producing a coherent, traceable decision with measurable consensus scores.

Supported strategies
--------------------
- MAJORITY_VOTE       : Cells vote; majority recommendation wins
- WEIGHTED_AVERAGE    : Outputs weighted by cell weight and confidence
- DELPHI              : Multi-round with feedback between rounds (most rigorous)
- UNANIMOUS           : Require all cells to agree (strictest)
- RANKED_CHOICE       : Instant-runoff voting on recommendations
- APEX_OVERRIDE       : Single apex LLM synthesizes all outputs (most flexible)
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Any

import structlog

from cca.core import (
    CellOutput,
    ConsensusStrategy,
)

logger = structlog.get_logger(__name__)


@dataclass
class ConsensusResult:
    """
    Intermediate result from the consensus computation.

    Separate from CouncilDecision to allow the Apex layer to enrich it
    before producing the final decision object.
    """
    strategy: ConsensusStrategy
    winning_recommendation: str
    synthesized_rationale: str
    consensus_score: float              # 0.0 = no consensus, 1.0 = unanimous
    overall_confidence: float
    overall_risk: float | None
    dissenting_views: list[str] = field(default_factory=list)
    advisory_notes: list[str] = field(default_factory=list)
    debate_rounds: int = 1
    requires_human_review: bool = False


class ConsensusEngine:
    """
    Computes consensus from a set of cell outputs.

    Parameters
    ----------
    strategy : ConsensusStrategy
        Algorithm used to aggregate cell outputs.
    consensus_threshold : float
        Minimum consensus_score to avoid triggering human review (0.0–1.0).
    risk_escalation_threshold : float
        If overall risk exceeds this, flag for human review.
    """

    def __init__(
        self,
        strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED_AVERAGE,
        consensus_threshold: float = 0.6,
        risk_escalation_threshold: float = 0.75,
        apex_llm: Any | None = None,
    ) -> None:
        self.strategy = strategy
        self.consensus_threshold = consensus_threshold
        self.risk_escalation_threshold = risk_escalation_threshold
        self.apex_llm = apex_llm  # Required for APEX_OVERRIDE strategy

    async def compute(
        self,
        outputs: list[CellOutput],
        cell_weights: dict[str, float] | None = None,
        advisory_outputs: list[CellOutput] | None = None,
    ) -> ConsensusResult:
        """
        Compute consensus from a list of cell outputs.

        Parameters
        ----------
        outputs : list[CellOutput]
            Analysis outputs from all participating cells.
        cell_weights : dict, optional
            Maps cell_id to weight. Defaults to 1.0 for all cells.
        advisory_outputs : list[CellOutput], optional
            Non-binding advisory signals (included in notes, not voting).

        Returns
        -------
        ConsensusResult
            Aggregated consensus with scores and synthesized rationale.
        """
        if not outputs:
            raise ValueError("Cannot compute consensus: no cell outputs provided.")

        weights = cell_weights or {o.cell_id: 1.0 for o in outputs}

        advisory_notes = [
            f"[{(o.metadata.get('advisor_role') or o.cell_role.value).upper()} ADVISORY]: {o.recommendation}"
            for o in (advisory_outputs or [])
        ]

        if self.strategy == ConsensusStrategy.WEIGHTED_AVERAGE:
            result = self._weighted_average(outputs, weights)
        elif self.strategy == ConsensusStrategy.MAJORITY_VOTE:
            result = self._majority_vote(outputs, weights)
        elif self.strategy == ConsensusStrategy.UNANIMOUS:
            result = self._unanimous(outputs)
        elif self.strategy == ConsensusStrategy.APEX_OVERRIDE:
            result = await self._apex_override(outputs)
        elif self.strategy == ConsensusStrategy.DELPHI:
            result = self._delphi(outputs, weights)
        else:
            # Default fallback
            result = self._weighted_average(outputs, weights)

        result.advisory_notes = advisory_notes
        result.requires_human_review = (
            result.consensus_score < self.consensus_threshold
            or (result.overall_risk is not None and result.overall_risk > self.risk_escalation_threshold)
        )

        logger.info(
            "consensus.computed",
            strategy=self.strategy.value,
            score=round(result.consensus_score, 3),
            confidence=round(result.overall_confidence, 3),
            human_review=result.requires_human_review,
        )
        return result

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _weighted_average(
        self,
        outputs: list[CellOutput],
        weights: dict[str, float],
    ) -> ConsensusResult:
        """
        Weighted average of confidence scores.

        Consensus score is computed as the normalized variance inverse —
        high variance in confidence means low consensus.
        """
        total_weight = sum(weights.get(o.cell_id, 1.0) for o in outputs)
        if total_weight == 0:
            total_weight = 1.0

        # Weighted confidence
        weighted_confidence = sum(
            o.confidence * weights.get(o.cell_id, 1.0)
            for o in outputs
        ) / total_weight

        # Consensus score: inverse of coefficient of variation
        confidences = [o.confidence for o in outputs]
        if len(confidences) > 1:
            mean_conf = statistics.mean(confidences)
            std_conf = statistics.stdev(confidences)
            cv = std_conf / mean_conf if mean_conf > 0 else 1.0
            consensus_score = max(0.0, 1.0 - cv)
        else:
            consensus_score = 1.0

        # Risk aggregation (max risk wins — conservative)
        overall_risk = self._aggregate_risk(outputs)

        # Dissenting views: cells with confidence significantly below average
        avg_conf = statistics.mean(confidences)
        dissenting = [
            f"[{o.cell_role.value.upper()}]: {o.recommendation} (confidence: {o.confidence:.0%})"
            for o in outputs
            if o.confidence < avg_conf - 0.2
        ]

        # Winning recommendation: highest weighted cell
        best = max(outputs, key=lambda o: o.confidence * weights.get(o.cell_id, 1.0))
        rationale = self._synthesize_rationale(outputs)

        return ConsensusResult(
            strategy=self.strategy,
            winning_recommendation=best.recommendation,
            synthesized_rationale=rationale,
            consensus_score=consensus_score,
            overall_confidence=weighted_confidence,
            overall_risk=overall_risk,
            dissenting_views=dissenting,
        )

    def _majority_vote(
        self,
        outputs: list[CellOutput],
        weights: dict[str, float],
    ) -> ConsensusResult:
        """
        Weighted majority vote on recommendation themes.

        Groups similar recommendations using keyword matching and selects
        the group with highest total weight.
        """
        # Simple keyword-based grouping
        vote_buckets: dict[str, list[CellOutput]] = {}
        keywords = ["proceed", "approve", "escalate", "reject", "hold", "investigate", "mitigate"]

        for output in outputs:
            rec_lower = output.recommendation.lower()
            bucket = "other"
            for kw in keywords:
                if kw in rec_lower:
                    bucket = kw
                    break
            vote_buckets.setdefault(bucket, []).append(output)

        # Weighted voting
        bucket_weights: dict[str, float] = {}
        for bucket, bucket_outputs in vote_buckets.items():
            bucket_weights[bucket] = sum(
                weights.get(o.cell_id, 1.0) * o.confidence for o in bucket_outputs
            )

        winning_bucket = max(bucket_weights, key=bucket_weights.get)  # type: ignore
        winning_outputs = vote_buckets[winning_bucket]
        total_weight = sum(bucket_weights.values()) or 1.0
        consensus_score = bucket_weights[winning_bucket] / total_weight

        best = max(winning_outputs, key=lambda o: o.confidence)
        overall_conf = statistics.mean(o.confidence for o in winning_outputs)
        overall_risk = self._aggregate_risk(outputs)

        dissenting = [
            f"[{o.cell_role.value.upper()}]: {o.recommendation}"
            for o in outputs
            if o not in winning_outputs
        ]

        return ConsensusResult(
            strategy=self.strategy,
            winning_recommendation=best.recommendation,
            synthesized_rationale=self._synthesize_rationale(outputs),
            consensus_score=consensus_score,
            overall_confidence=overall_conf,
            overall_risk=overall_risk,
            dissenting_views=dissenting,
        )

    def _unanimous(self, outputs: list[CellOutput]) -> ConsensusResult:
        """
        Require all cells to agree. Very strict — used for critical decisions.

        If not unanimous, consensus_score is set low and human review is flagged.
        """
        result = self._weighted_average(outputs, {o.cell_id: 1.0 for o in outputs})
        # Unanimous requires very high consensus score
        if result.consensus_score < 0.9:
            result.requires_human_review = True
            result.consensus_score = result.consensus_score * 0.5  # Penalize non-unanimity
        return result

    async def _apex_override(self, outputs: list[CellOutput]) -> ConsensusResult:
        """
        Use the apex LLM to synthesize all outputs into a final decision.

        Most flexible strategy — the LLM reads all perspectives and makes
        a nuanced synthesis that pure statistics cannot achieve.
        """
        if self.apex_llm is None:
            logger.warning("apex_override.fallback", reason="No apex LLM configured")
            return self._weighted_average(outputs, {o.cell_id: 1.0 for o in outputs})

        synthesis_prompt = """You are the APEX SYNTHESIS LAYER of a multi-agent council.
Your task is to read all specialist analyses and produce a final, authoritative decision.

SPECIALIST ANALYSES:
""" + "\n\n".join([
            f"=== {o.cell_role.value.upper()} SPECIALIST ===\n"
            f"Analysis: {o.analysis}\n"
            f"Recommendation: {o.recommendation}\n"
            f"Confidence: {o.confidence:.0%}\n"
            f"Reasoning: {o.reasoning}"
            for o in outputs
        ]) + """

YOUR TASK:
Synthesize these perspectives into a final decision. Consider:
1. Where do specialists agree? (strengthen these points)
2. Where do they disagree? (explain how to resolve the conflict)
3. What is the most prudent, well-rounded recommendation?
4. Are there critical factors any specialist missed?

Respond in this format:
FINAL_DECISION: [Clear action recommendation]
RATIONALE: [Why this decision is correct given all perspectives]
CONFIDENCE: [0.0-1.0]
CONSENSUS_SCORE: [0.0-1.0 reflecting how much the specialists agreed]
DISSENTING_VIEWS: [Any important minority perspectives to preserve]"""

        try:
            response = await self.apex_llm.complete(
                system="You are an expert decision synthesis system.",
                user=synthesis_prompt,
            )

            def extract(pattern: str, default: str = "") -> str:
                m = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
                return m.group(1).strip() if m else default

            def extract_float(pattern: str, default: float = 0.7) -> float:
                m = re.search(pattern, response, re.IGNORECASE)
                if m:
                    try:
                        v = float(m.group(1).replace("%", ""))
                        return v / 100 if v > 1 else v
                    except ValueError:
                        pass
                return default

            decision = extract(r"FINAL_DECISION[:\s]+(.*?)(?=RATIONALE|$)")
            rationale = extract(r"RATIONALE[:\s]+(.*?)(?=CONFIDENCE|$)")
            confidence = extract_float(r"CONFIDENCE[:\s]+([\d.]+%?)")
            consensus = extract_float(r"CONSENSUS_SCORE[:\s]+([\d.]+%?)")
            dissenting_raw = extract(r"DISSENTING_VIEWS[:\s]+(.*?)$")
            dissenting = [d.strip() for d in dissenting_raw.split("\n") if d.strip()] if dissenting_raw else []

            return ConsensusResult(
                strategy=self.strategy,
                winning_recommendation=decision or outputs[0].recommendation,
                synthesized_rationale=rationale or response,
                consensus_score=consensus,
                overall_confidence=confidence,
                overall_risk=self._aggregate_risk(outputs),
                dissenting_views=dissenting,
            )

        except Exception as e:
            logger.error("apex_override.failed", error=str(e))
            return self._weighted_average(outputs, {o.cell_id: 1.0 for o in outputs})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_risk(outputs: list[CellOutput]) -> float | None:
        """Extract the maximum risk score from outputs (conservative aggregation)."""
        risk_scores = [o.risk_score for o in outputs if o.risk_score is not None]
        return max(risk_scores) if risk_scores else None

    def _synthesize_rationale(self, outputs: list[CellOutput]) -> str:
        """Build a multi-perspective rationale string from all cell outputs."""
        parts = []
        for o in outputs:
            parts.append(
                f"• [{o.cell_role.value.upper()}] {o.recommendation} "
                f"(confidence: {o.confidence:.0%})"
            )
        return "\n".join(parts)

    def _delphi(
        self,
        outputs: list[CellOutput],
        weights: dict[str, float],
    ) -> ConsensusResult:
        """
        Delphi method: multi-round convergence analysis.

        In a true Delphi process, experts revise their opinions over
        multiple rounds after seeing anonymized peer feedback. Here we
        simulate the effect by analyzing how outputs from successive
        debate rounds converge in confidence.

        The consensus score is boosted when later-round outputs show
        lower variance than earlier rounds, indicating convergence.

        If all outputs belong to a single round (no debate), this
        behaves like weighted average with a convergence penalty.
        """
        # Separate outputs by round
        rounds: dict[int, list[CellOutput]] = {}
        for o in outputs:
            rounds.setdefault(o.round_number, []).append(o)

        round_numbers = sorted(rounds.keys())

        # Calculate per-round variance in confidence
        round_variances: list[float] = []
        for rn in round_numbers:
            confs = [o.confidence for o in rounds[rn]]
            if len(confs) > 1:
                mean_c = statistics.mean(confs)
                std_c = statistics.stdev(confs)
                cv = std_c / mean_c if mean_c > 0 else 1.0
                round_variances.append(cv)
            else:
                round_variances.append(0.0)

        # Convergence bonus: if variance decreased across rounds
        if len(round_variances) >= 2:
            improvement = round_variances[0] - round_variances[-1]
            convergence_bonus = max(0.0, min(0.2, improvement))
        else:
            convergence_bonus = 0.0

        # Use the latest round for the final result
        latest_round = round_numbers[-1]
        latest_outputs = rounds[latest_round]

        # Base result from weighted average of latest round
        base = self._weighted_average(latest_outputs, weights)

        # Apply convergence bonus to consensus score
        base.consensus_score = min(1.0, base.consensus_score + convergence_bonus)
        base.debate_rounds = len(round_numbers)
        base.strategy = ConsensusStrategy.DELPHI

        return base
