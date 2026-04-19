# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
Health Monitor: Tracks the health of all cells in a council.

The HealthMonitor provides a centralized view of cell health, detecting
degraded or fatigued cells and recommending recovery actions. It can be
queried for a dashboard-style report or used for automated remediation.

    ┌─────────────────────────────────────────┐
    │           HealthMonitor                 │
    │                                         │
    │  register_cell(cell)                    │
    │  check_all() → bool (all healthy?)      │
    │  report() → dict (per-cell metrics)     │
    └─────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Any

import structlog

from cca.cells.base import BaseCell
from cca.core import CellHealthReport

logger = structlog.get_logger(__name__)


class HealthMonitor:
    """
    Monitors the health of all registered cells.

    Provides methods to register cells, check overall health status,
    and generate detailed health reports suitable for dashboards or
    automated alerting pipelines.

    Parameters
    ----------
    degraded_threshold : float
        Health score below which a cell is considered degraded. Default: 0.5.
    """

    def __init__(self, degraded_threshold: float = 0.5) -> None:
        self._cells: dict[str, BaseCell] = {}
        self.degraded_threshold = degraded_threshold
        self.log = logger.bind(component="health_monitor")

    def register_cell(self, cell: BaseCell) -> None:
        """
        Register a cell for health monitoring.

        Parameters
        ----------
        cell : BaseCell
            The cell instance to monitor.
        """
        self._cells[cell.id] = cell
        self.log.info("health.cell.registered", cell_id=cell.id, role=cell.role.value)

    def unregister_cell(self, cell_id: str) -> None:
        """Remove a cell from monitoring."""
        self._cells.pop(cell_id, None)

    def check_all(self) -> bool:
        """
        Check if all registered cells are healthy.

        Returns
        -------
        bool
            True if every registered cell has a health score above
            the degraded threshold. False otherwise, or if no cells
            are registered.
        """
        if not self._cells:
            return True

        for cell in self._cells.values():
            if cell.health_score < self.degraded_threshold:
                self.log.warning(
                    "health.cell.degraded",
                    cell_id=cell.id,
                    score=cell.health_score,
                )
                return False
        return True

    def report(self) -> dict[str, Any]:
        """
        Generate a full health report for all registered cells.

        Returns
        -------
        dict
            A dictionary containing:
            - ``healthy``: bool — overall health status
            - ``total_cells``: int — number of monitored cells
            - ``degraded_cells``: int — number of cells below threshold
            - ``cells``: list[dict] — per-cell health details
        """
        cell_reports: list[dict[str, Any]] = []
        degraded_count = 0

        for cell in self._cells.values():
            hr: CellHealthReport = cell.health_report()
            is_degraded = hr.health_score < self.degraded_threshold
            if is_degraded:
                degraded_count += 1

            cell_reports.append({
                "cell_id": hr.cell_id,
                "role": hr.cell_role.value,
                "state": hr.state.value,
                "health_score": round(hr.health_score, 3),
                "response_time_ms": round(hr.response_time_ms or 0.0, 1),
                "error_count": hr.error_count,
                "successful_analyses": hr.successful_analyses,
                "is_degraded": is_degraded,
                "recovery_needed": hr.recovery_needed,
            })

        return {
            "healthy": degraded_count == 0,
            "total_cells": len(self._cells),
            "degraded_cells": degraded_count,
            "cells": cell_reports,
        }

    @property
    def registered_cell_count(self) -> int:
        return len(self._cells)

    def __repr__(self) -> str:
        return f"<HealthMonitor cells={len(self._cells)}>"
