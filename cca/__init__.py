# Copyright 2026 Hakan (CCA Framework Contributors)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Cellular Council Architecture (CCA)
====================================

A hierarchical multi-agent AI decision-making framework that combines
biological cell specialization with corporate governance principles.

Key Concepts
------------
- **Cells**: Specialized AI agents that analyze problems from unique perspectives
- **Clusters**: Groups of cells that engage in structured debate
- **Synapses**: Communication channels between cells
- **Apex Layer**: Final consensus and decision formation
- **Advisors**: Independent oversight roles without decision authority
- **Stem Cells**: Undifferentiated cells that specialize on demand

Quick Start
-----------
    >>> from cca import Council, CellRole
    >>> from cca.llm import OllamaBackend
    >>>
    >>> council = Council(
    ...     name="AlertMindCouncil",
    ...     llm_backend=OllamaBackend(model="llama3.2"),
    ... )
    >>> council.add_cell(CellRole.RISK)
    >>> council.add_cell(CellRole.TECHNICAL)
    >>> council.add_cell(CellRole.ETHICS)
    >>>
    >>> result = await council.deliberate("Should we escalate this alarm?")
    >>> print(result.decision)

"""

__version__ = "0.1.0"
__author__ = "Hakan"
__license__ = "Apache-2.0"

from cca.advisors.base import AdvisorRole, BaseAdvisor
from cca.apex.layer import ApexLayer
from cca.cells.base import BaseCell, CellRole, CellState
from cca.cells.specialized import (
    EthicsCell,
    FinancialCell,
    RiskCell,
    TechnicalCell,
)
from cca.cells.stem import StemCell
from cca.cells.pool import StemCellPool
from cca.cluster.manager import Cluster
from cca.consensus.engine import ConsensusEngine, ConsensusResult
from cca.core.council import Council
from cca.core.streaming import StreamingCouncil, StreamEvent
from cca.health.monitor import HealthMonitor
from cca.synapse.protocol import SynapseMessage, MessageType, Synapse
from cca.synapse.visualization import SynapseVisualizer

__all__ = [
    # Top-level
    "Council",
    # Cells
    "BaseCell",
    "CellRole",
    "CellState",
    "RiskCell",
    "EthicsCell",
    "TechnicalCell",
    "FinancialCell",
    # Stem Cell
    "StemCell",
    "StemCellPool",
    # Cluster
    "Cluster",
    # Apex
    "ApexLayer",
    # Advisors
    "BaseAdvisor",
    "AdvisorRole",
    # Consensus
    "ConsensusEngine",
    "ConsensusResult",
    # Synapse
    "Synapse",
    "SynapseMessage",
    "MessageType",
    "SynapseVisualizer",
    # Streaming
    "StreamingCouncil",
    "StreamEvent",
    # Health
    "HealthMonitor",
]
