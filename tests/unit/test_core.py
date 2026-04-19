# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for CCA core components.

Uses a MockLLMBackend to test all logic without requiring a real LLM.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from cca.llm.backends import BaseLLMBackend
from cca.cells.specialized import RiskCell, EthicsCell, TechnicalCell, create_cell
from cca.consensus.engine import ConsensusEngine
from cca.core import CellRole, CellState, ConsensusStrategy, CellOutput
from cca.core.council import Council


# ---------------------------------------------------------------------------
# Mock LLM backend
# ---------------------------------------------------------------------------

class MockLLMBackend(BaseLLMBackend):
    """Returns structured mock responses for testing."""

    def __init__(self, response_template: str | None = None):
        self.call_count = 0
        self.response_template = response_template or (
            "ANALYSIS: This is a test analysis from the mock LLM.\n"
            "RECOMMENDATION: Proceed with caution.\n"
            "REASONING: Test reasoning chain.\n"
            "CONFIDENCE: 0.75\n"
            "RISK_SCORE: 0.3"
        )

    async def complete(self, system: str, user: str) -> str:
        self.call_count += 1
        return self.response_template

    async def health_check(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Cell tests
# ---------------------------------------------------------------------------

class TestBaseCell:
    def test_risk_cell_initialization(self):
        backend = MockLLMBackend()
        cell = RiskCell(llm_backend=backend)

        assert cell.role == CellRole.RISK
        assert cell.state == CellState.DORMANT
        assert cell.health_score == 1.0
        assert len(cell.id) == 8

    def test_cell_activation(self):
        cell = RiskCell(llm_backend=MockLLMBackend())
        assert cell.state == CellState.DORMANT
        cell.activate()
        assert cell.state == CellState.ACTIVE

    def test_cell_retirement(self):
        cell = RiskCell(llm_backend=MockLLMBackend())
        cell.activate()
        cell.retire()
        assert cell.state == CellState.APOPTOTIC

    @pytest.mark.asyncio
    async def test_cell_analyze_returns_output(self):
        backend = MockLLMBackend()
        cell = RiskCell(llm_backend=backend)
        cell.activate()

        output = await cell.analyze("Should we deploy?")

        assert output is not None
        assert output.cell_id == cell.id
        assert output.cell_role == CellRole.RISK
        assert 0.0 <= output.confidence <= 1.0
        assert backend.call_count == 1

    @pytest.mark.asyncio
    async def test_cell_debate_returns_output(self):
        backend = MockLLMBackend()
        cell = RiskCell(llm_backend=backend)
        cell.activate()

        # Create a peer output to debate against
        peer_output = CellOutput(
            cell_id="peer-cell",
            cell_role=CellRole.TECHNICAL,
            analysis="Technical analysis",
            recommendation="Proceed",
            reasoning="Test reasoning",
            confidence=0.8,
        )

        debate_output = await cell.debate(
            query="Should we deploy?",
            other_outputs=[peer_output],
            round_number=2,
        )

        assert debate_output is not None
        assert debate_output.round_number == 2

    def test_health_report(self):
        cell = RiskCell(llm_backend=MockLLMBackend())
        report = cell.health_report()
        assert report.cell_id == cell.id
        assert report.health_score == 1.0
        assert report.is_degraded is False

    @pytest.mark.asyncio
    async def test_health_degrades_on_error(self):
        class FailingBackend(BaseLLMBackend):
            async def complete(self, system, user):
                raise ConnectionError("LLM unreachable")
            async def health_check(self):
                return False

        cell = RiskCell(llm_backend=FailingBackend(), max_retries=1)
        cell.activate()

        with pytest.raises(RuntimeError):
            await cell.analyze("test query")

        assert cell.health_score < 1.0
        assert cell.state == CellState.FATIGUED


class TestCellFactory:
    def test_create_cell_by_role(self):
        backend = MockLLMBackend()
        for role in [CellRole.RISK, CellRole.ETHICS, CellRole.TECHNICAL, CellRole.FINANCIAL]:
            cell = create_cell(role=role, llm_backend=backend)
            assert cell.role == role

    def test_create_cell_unknown_role_raises(self):
        with pytest.raises(ValueError, match="No built-in cell"):
            create_cell(role=CellRole.CUSTOM, llm_backend=MockLLMBackend())


# ---------------------------------------------------------------------------
# Consensus engine tests
# ---------------------------------------------------------------------------

class TestConsensusEngine:
    def make_outputs(self, count: int = 3, base_confidence: float = 0.75) -> list[CellOutput]:
        roles = [CellRole.RISK, CellRole.ETHICS, CellRole.TECHNICAL, CellRole.FINANCIAL]
        return [
            CellOutput(
                cell_id=f"cell-{i}",
                cell_role=roles[i % len(roles)],
                analysis=f"Analysis from cell {i}",
                recommendation="Proceed with caution",
                reasoning=f"Reasoning {i}",
                confidence=base_confidence + (i * 0.02),
                risk_score=0.3,
            )
            for i in range(count)
        ]

    @pytest.mark.asyncio
    async def test_weighted_average_strategy(self):
        engine = ConsensusEngine(strategy=ConsensusStrategy.WEIGHTED_AVERAGE)
        outputs = self.make_outputs(3, base_confidence=0.75)
        result = await engine.compute(outputs)

        assert result is not None
        assert 0.0 <= result.consensus_score <= 1.0
        assert 0.0 <= result.overall_confidence <= 1.0
        assert result.overall_risk == 0.3
        assert result.strategy == ConsensusStrategy.WEIGHTED_AVERAGE

    @pytest.mark.asyncio
    async def test_majority_vote_strategy(self):
        engine = ConsensusEngine(strategy=ConsensusStrategy.MAJORITY_VOTE)
        outputs = self.make_outputs(4)
        result = await engine.compute(outputs)
        assert result is not None
        assert result.strategy == ConsensusStrategy.MAJORITY_VOTE

    @pytest.mark.asyncio
    async def test_empty_outputs_raises(self):
        engine = ConsensusEngine()
        with pytest.raises(ValueError, match="no cell outputs"):
            await engine.compute([])

    @pytest.mark.asyncio
    async def test_low_consensus_flags_human_review(self):
        engine = ConsensusEngine(
            strategy=ConsensusStrategy.WEIGHTED_AVERAGE,
            consensus_threshold=0.9,  # Very high threshold
        )
        # Create outputs with high variance in confidence
        outputs = [
            CellOutput(
                cell_id=f"cell-{i}",
                cell_role=CellRole.RISK,
                analysis="analysis",
                recommendation="rec",
                reasoning="reason",
                confidence=conf,
            )
            for i, conf in enumerate([0.1, 0.9, 0.1, 0.9])  # High variance
        ]
        result = await engine.compute(outputs)
        assert result.requires_human_review is True

    @pytest.mark.asyncio
    async def test_high_risk_flags_human_review(self):
        engine = ConsensusEngine(risk_escalation_threshold=0.5)
        outputs = self.make_outputs(2)
        # Override risk scores
        for o in outputs:
            o.risk_score = 0.9  # Above threshold
        result = await engine.compute(outputs)
        assert result.requires_human_review is True


# ---------------------------------------------------------------------------
# Council integration tests
# ---------------------------------------------------------------------------

class TestCouncil:
    def make_council(self, debate_rounds: int = 1) -> Council:
        backend = MockLLMBackend()
        return Council(
            name="TestCouncil",
            llm_backend=backend,
            debate_rounds=debate_rounds,
        )

    def test_council_initialization(self):
        council = self.make_council()
        assert council.name == "TestCouncil"
        assert council.cell_count == 0

    def test_add_cell(self):
        council = self.make_council()
        cell = council.add_cell(CellRole.RISK)
        assert council.cell_count == 1
        assert cell.state == CellState.ACTIVE

    def test_add_multiple_cells(self):
        council = self.make_council()
        council.add_cell(CellRole.RISK)
        council.add_cell(CellRole.ETHICS)
        council.add_cell(CellRole.TECHNICAL)
        assert council.cell_count == 3

    def test_remove_cell(self):
        council = self.make_council()
        cell = council.add_cell(CellRole.RISK)
        council.remove_cell(cell.id)
        assert council.cell_count == 0

    def test_deliberate_without_cells_raises(self):
        council = self.make_council()
        with pytest.raises(ValueError, match="no cells"):
            asyncio.get_event_loop().run_until_complete(
                council.deliberate("test query")
            )

    @pytest.mark.asyncio
    async def test_full_deliberation_cycle(self):
        council = self.make_council(debate_rounds=1)
        council.add_cell(CellRole.RISK)
        council.add_cell(CellRole.TECHNICAL)

        decision = await council.deliberate(
            query="Should we proceed?",
            context={"urgency": "high"},
        )

        assert decision is not None
        assert decision.query == "Should we proceed?"
        assert decision.council_id == council.id
        assert len(decision.participating_cells) == 2
        assert decision.debate_rounds == 1
        assert 0.0 <= decision.consensus_score <= 1.0
        assert decision.duration_ms is not None
        assert decision.duration_ms > 0

    @pytest.mark.asyncio
    async def test_health_check(self):
        council = self.make_council()
        council.add_cell(CellRole.RISK)
        reports = council.health_check()
        assert len(reports) == 1
        assert reports[0].health_score == 1.0
