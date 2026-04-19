# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Synapse Protocol: Event bus and reliable messaging between cells.

The Synapse Layer manages all asynchronous communication inside a council.
It provides a structured event bus that tracks the entire deliberation
history, enabling real-time visualization and audit trails.

    ┌────────────────────────────────────────────────────────┐
    │                       Synapse                          │
    │                                                        │
    │  [Cell A] ──(send)──▶  [Event Bus]  ──(broadcast)─▶    │
    │                               │                        │
    │  [Cell B] ◀──(history)────────┘                        │
    └────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from cca.core import SignalType


class MessageType(str, Enum):
    """Broad categories of synapse messages."""
    ANALYSIS = "analysis"        # Initial analyses
    DEBATE = "debate"            # Cross-examinations
    ADVISORY = "advisory"        # Non-voting oversight
    HEALTH = "health"            # Health checks and status
    CONTROL = "control"          # Council orchestration (start/stop)


class SynapseMessage(BaseModel):
    """
    Standardized payload for all cell-to-cell communication.
    """
    id: str = Field(default_factory=lambda: f"msg-{str(uuid.uuid4())[:8]}")
    session_id: str | None = None
    sender_id: str
    receiver_id: str | None = None  # None indicates broadcast
    message_type: MessageType
    signal_type: SignalType
    payload: dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    round_number: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class Synapse:
    """
    Centralized event bus for a council.

    Tracks all messages, routes targeted messages, and manages
    subscriptions for visualization and monitoring.
    """

    def __init__(self) -> None:
        self._messages: list[SynapseMessage] = []
        self._subscribers: dict[str, list[Callable[[SynapseMessage], Any]]] = {}

    def send(self, message: SynapseMessage) -> None:
        """
        Send a specific message (targeted or broadcast) and record it.
        """
        self._messages.append(message)
        self._notify_subscribers(message)

    def broadcast(self, message: SynapseMessage) -> None:
        """
        Broadcast a message to all listeners (receiver_id = None).
        """
        message.receiver_id = None
        self.send(message)

    def receive(self, receiver_id: str) -> list[SynapseMessage]:
        """
        Get all messages targeted to a specific receiver (or broadcasts).
        """
        return [
            m for m in self._messages
            if m.receiver_id in (receiver_id, None)
        ]

    def subscribe(
        self,
        subscriber_id: str,
        callback: Callable[[SynapseMessage], Any],
    ) -> None:
        """
        Subscribe to all events passing through the synapse.
        Useful for visualizers, dashboards, and audit loggers.

        Parameters
        ----------
        subscriber_id : str
            Unique ID for the subscriber.
        callback : Callable
            Function/coroutine called with every new message.
        """
        if subscriber_id not in self._subscribers:
            self._subscribers[subscriber_id] = []
        self._subscribers[subscriber_id].append(callback)

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove all subscriptions for an ID."""
        self._subscribers.pop(subscriber_id, None)

    def _notify_subscribers(self, message: SynapseMessage) -> None:
        """Fire callbacks for all subscribers (handles both sync and async)."""
        for callbacks in self._subscribers.values():
            for callback in callbacks:
                # If callback is a coroutine, wrap it in a background task
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(message))
                else:
                    try:
                        callback(message)
                    except Exception as e:
                        # Don't let a bad subscriber break the bus
                        import structlog
                        structlog.get_logger(__name__).error(
                            "synapse.subscriber.failed",
                            error=str(e),
                        )

    def history(self, session_id: str | None = None) -> list[SynapseMessage]:
        """Return the history, optionally filtered by session."""
        if session_id:
            return [m for m in self._messages if m.session_id == session_id]
        return list(self._messages)

    def export_timeline(self, session_id: str | None = None) -> list[dict[str, Any]]:
        """
        Export a simplified, JSON-serializable timeline of events.
        Useful for generating deliberation traces.
        """
        msgs = self.history(session_id)
        msgs.sort(key=lambda x: x.timestamp)

        timeline = []
        for m in msgs:
            timeline.append({
                "id": m.id,
                "timestamp": m.timestamp.isoformat(),
                "sender": m.sender_id,
                "receiver": m.receiver_id or "ALL",
                "type": m.message_type.value,
                "round": m.round_number,
                "summary": m.payload.get("summary", "No summary available"),
            })
        return timeline
