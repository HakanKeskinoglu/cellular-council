# Copyright 2026 Hakan (CCA Framework Contributors)
# SPDX-License-Identifier: Apache-2.0

"""
StemCellPool: Pre-allocated pool of undifferentiated StemCells.

Provides efficient on-demand cell allocation and recycling,
avoiding repeated instantiation overhead during deliberation.

    ┌─────────────────────────────────────────────────────┐
    │                StemCellPool                         │
    │                                                     │
    │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     │
    │  │ Stem │ │ Stem │ │ Stem │ │ Stem │ │ Stem │     │
    │  │(idle)│ │(idle)│ │(used)│ │(idle)│ │(idle)│     │
    │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘     │
    │                                                     │
    │  acquire() → StemCell  (take from pool)             │
    │  release(cell)         (reset + return to pool)     │
    │  grow(n)               (expand the pool)            │
    └─────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Any

import structlog

from cca.cells.stem import StemCell

logger = structlog.get_logger(__name__)


class StemCellPool:
    """
    Pre-allocated pool of undifferentiated StemCells.

    Manages a fixed-size pool of StemCell instances for efficient
    on-demand differentiation and recycling.

    Parameters
    ----------
    llm_backend : Any
        LLM backend for all cells in the pool.
    pool_size : int
        Initial number of StemCells to pre-allocate. Default: 5.
    max_size : int
        Maximum pool size (prevents unbounded growth). Default: 20.

    Examples
    --------
    >>> pool = StemCellPool(llm_backend=backend, pool_size=3)
    >>> cell = pool.acquire()
    >>> await cell.differentiate("database")
    >>> output = await cell.analyze("Check replication lag")
    >>> pool.release(cell)  # cell.reset() is called automatically
    """

    def __init__(
        self,
        llm_backend: Any,
        pool_size: int = 5,
        max_size: int = 20,
    ) -> None:
        self.llm_backend = llm_backend
        self.max_size = max_size
        self._available: list[StemCell] = []
        self._in_use: set[str] = set()  # Track cell IDs that are checked out

        self.log = logger.bind(component="stem_cell_pool")

        # Pre-allocate
        for _ in range(pool_size):
            self._available.append(StemCell(llm_backend=llm_backend))

        self.log.info("pool.initialized", size=pool_size, max_size=max_size)

    def acquire(self) -> StemCell:
        """
        Acquire an undifferentiated StemCell from the pool.

        If the pool is exhausted but hasn't reached max_size, a new
        StemCell is allocated. If the pool is at max_size, raises RuntimeError.

        Returns
        -------
        StemCell
            An undifferentiated, dormant StemCell ready for use.

        Raises
        ------
        RuntimeError
            If the pool is exhausted and at maximum capacity.
        """
        if self._available:
            cell = self._available.pop()
        elif self.total_count < self.max_size:
            cell = StemCell(llm_backend=self.llm_backend)
            self.log.info("pool.expanded", new_total=self.total_count + 1)
        else:
            raise RuntimeError(
                f"StemCellPool exhausted: {len(self._in_use)} cells in use, "
                f"max_size={self.max_size}. Release cells or increase max_size."
            )

        self._in_use.add(cell.id)
        self.log.debug("pool.acquired", cell_id=cell.id)
        return cell

    def release(self, cell: StemCell) -> None:
        """
        Return a StemCell to the pool after use.

        The cell is automatically reset (undifferentiated) before
        being returned to the available pool.

        Parameters
        ----------
        cell : StemCell
            The cell to return. Must have been acquired from this pool.
        """
        if cell.id not in self._in_use:
            self.log.warning("pool.release.unknown_cell", cell_id=cell.id)
            return

        cell.reset()
        self._in_use.discard(cell.id)
        self._available.append(cell)
        self.log.debug("pool.released", cell_id=cell.id)

    def grow(self, count: int = 1) -> None:
        """
        Add more undifferentiated cells to the pool.

        Parameters
        ----------
        count : int
            Number of cells to add. Respects max_size.
        """
        added = 0
        for _ in range(count):
            if self.total_count >= self.max_size:
                break
            self._available.append(StemCell(llm_backend=self.llm_backend))
            added += 1

        if added > 0:
            self.log.info("pool.grown", added=added, total=self.total_count)

    @property
    def available_count(self) -> int:
        """Number of immediately available (idle) cells."""
        return len(self._available)

    @property
    def in_use_count(self) -> int:
        """Number of cells currently checked out."""
        return len(self._in_use)

    @property
    def total_count(self) -> int:
        """Total number of cells (available + in use)."""
        return len(self._available) + len(self._in_use)

    def __repr__(self) -> str:
        return (
            f"<StemCellPool available={self.available_count} "
            f"in_use={self.in_use_count} max={self.max_size}>"
        )
