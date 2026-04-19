# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Synapse Visualization Layer.

Provides a WebSocket server that broadcasts Synapse events to connected
clients in real-time. This forms the backend for the CCA Dashboard,
allowing humans to observe council deliberations live.
"""

import asyncio
import json
from typing import Any

import structlog

from cca.synapse.protocol import Synapse, SynapseMessage

logger = structlog.get_logger(__name__)


class SynapseVisualizer:
    """
    WebSocket broadcaster for Synapse events.

    Subscribes to a Council's Synapse and forwards all messages
    to connected WebSocket clients. Format is JSON.

    Parameters
    ----------
    synapse : Synapse
        The event bus to monitor.
    host : str
        Host binding. Default: 127.0.0.1
    port : int
        Port for the WebSocket server. Default: 8765
    """

    def __init__(self, synapse: Synapse, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.synapse = synapse
        self.host = host
        self.port = port
        self.clients: set[Any] = set()
        self.log = logger.bind(component="synapse_viz", host=host, port=port)
        self._server = None

    async def _handle_client(self, websocket: Any) -> None: # websocket type is websockets.server.WebSocketServerProtocol
        """Handle a new WebSocket connection."""
        import websockets.exceptions
        self.clients.add(websocket)
        self.log.info("viz.client.connected", total_clients=len(self.clients))
        try:
            # Keep connection alive until client disconnects
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            self.log.info("viz.client.disconnected", total_clients=len(self.clients))

    async def _on_synapse_message(self, message: SynapseMessage) -> None:
        """Callback fired when a message hits the Synapse bus."""
        if not self.clients:
            return

        payload = {
            "id": message.id,
            "session_id": message.session_id,
            "sender_id": message.sender_id,
            "receiver_id": message.receiver_id or "ALL",
            "message_type": message.message_type.value,
            "signal_type": message.signal_type.value,
            "timestamp": message.timestamp.isoformat(),
            "round_number": message.round_number,
            "payload": message.payload,
        }

        def json_serial(obj):
            from datetime import datetime
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        json_data = json.dumps(payload, default=json_serial)

        disconnected = set()
        for client in self.clients:
            try:
                await client.send(json_data)
            except Exception:
                disconnected.add(client)

        # Cleanup dead clients
        for client in disconnected:
            self.clients.discard(client)

    async def start_server(self) -> None:
        """
        Start the WebSocket server and subscribe to the Synapse.

        Requires the `websockets` library to be installed.
        """
        try:
            import websockets
        except ImportError:
            raise ImportError(
                "The 'websockets' library is required for SynapseVisualizer. "
                "Install it with: pip install websockets (or pip install cellular-council[viz])"
            )

        self.synapse.subscribe("viz_server", self._on_synapse_message)
        
        self._server = await websockets.serve(self._handle_client, self.host, self.port) # type: ignore
        self.log.info("viz.server.started")

    async def stop_server(self) -> None:
        """Stop the WebSocket server and unsubscribe."""
        self.synapse.unsubscribe("viz_server")
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self.log.info("viz.server.stopped")
