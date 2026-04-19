# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
StreamingCouncil: Async generator for real-time deliberation streaming.
"""

from __future__ import annotations

import asyncio
import enum
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from pydantic import BaseModel

from cca.core.council import Council
from cca.core import CellOutput, CouncilDecision


class StreamEventType(str, enum.Enum):
    SESSION_START = "session_start"
    ROUND_START = "round_start"
    CELL_OUTPUT = "cell_output"
    ROUND_COMPLETE = "round_complete"
    ADVISORY_START = "advisory_start"
    ADVISORY_OUTPUT = "advisory_output"
    CONSENSUS_START = "consensus_start"
    CONSENSUS_COMPLETE = "consensus_complete"
    DECISION = "decision"
    ERROR = "error"


class StreamEvent(BaseModel):
    """An event yielded during a streaming deliberation."""
    type: str
    session_id: str
    timestamp: float
    data: dict[str, Any] | BaseModel | str


class StreamingCouncil(Council):
    """
    Council subclass that adds an async generator for streaming.
    Allows API layers to stream the deliberation process to clients.
    """

    async def deliberate_stream(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Execute deliberation and yield events in real-time.
        """
        if not self._cells:
            raise ValueError(f"Council '{self.name}' has no cells.")

        session_id = session_id or f"session-{str(uuid.uuid4())[:8]}"
        start_time = time.monotonic()
        all_outputs: list[CellOutput] = []

        def _make_event(typ: str, data: Any) -> StreamEvent:
            return StreamEvent(
                type=typ,
                session_id=session_id,
                timestamp=time.time(),
                data=data
            )

        self.log.info("streaming_deliberation.started", session_id=session_id)
        yield _make_event(StreamEventType.SESSION_START, {
            "query": query,
            "council": self.name,
            "cells": [c.role.value for c in self._cells.values()]
        })

        current_outputs: list[CellOutput] = []

        try:
            # --- Round 1: Independent Analysis ---
            yield _make_event(StreamEventType.ROUND_START, {"round": 1, "phase": "analysis"})
            
            tasks = [cell.analyze(query, context) for cell in self._cells.values()]
            for coro in asyncio.as_completed(tasks):
                output = await coro
                current_outputs.append(output)
                all_outputs.append(output)
                yield _make_event(StreamEventType.CELL_OUTPUT, output)
                
            yield _make_event(StreamEventType.ROUND_COMPLETE, {"round": 1})

            # --- Debate Rounds ---
            for round_num in range(2, self.debate_rounds + 2):
                yield _make_event(StreamEventType.ROUND_START, {"round": round_num, "phase": "debate"})
                debate_outputs: list[CellOutput] = []
                tasks = [
                    cell.debate(query, current_outputs, round_num, context)
                    for cell in self._cells.values()
                ]
                for coro in asyncio.as_completed(tasks):
                    output = await coro
                    debate_outputs.append(output)
                    all_outputs.append(output)
                    yield _make_event(StreamEventType.CELL_OUTPUT, output)
                
                current_outputs = debate_outputs
                yield _make_event(StreamEventType.ROUND_COMPLETE, {"round": round_num})

            # --- Advisory Round ---
            advisory_outputs: list[CellOutput] = []
            if self._advisors:
                yield _make_event(StreamEventType.ADVISORY_START, {"count": len(self._advisors)})
                tasks = [
                    advisor.advise(query=query, cell_outputs=current_outputs, context=context)
                    for advisor in self._advisors
                ]
                for coro in asyncio.as_completed(tasks):
                    try:
                        output = await coro
                        advisory_outputs.append(output)
                        yield _make_event(StreamEventType.ADVISORY_OUTPUT, output)
                    except Exception as e:
                        yield _make_event(StreamEventType.ERROR, f"Advisor failed: {e}")

            # --- Consensus ---
            yield _make_event(StreamEventType.CONSENSUS_START, {"strategy": self._consensus_engine.strategy.value})
            
            cell_weights = {cell_id: cell.weight for cell_id, cell in self._cells.items()}
            consensus_result = await self._consensus_engine.compute(
                outputs=current_outputs,
                cell_weights=cell_weights,
                advisory_outputs=advisory_outputs,
            )
            
            yield _make_event(StreamEventType.CONSENSUS_COMPLETE, {"score": consensus_result.consensus_score})

            elapsed_ms = (time.monotonic() - start_time) * 1000

            # --- Assemble Decision ---
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

            yield _make_event(StreamEventType.DECISION, decision)
            self.log.info("streaming_deliberation.complete", session_id=session_id)

        except Exception as e:
            self.log.exception("streaming_deliberation.error", error=str(e), session_id=session_id)
            yield _make_event(StreamEventType.ERROR, str(e))
            raise
