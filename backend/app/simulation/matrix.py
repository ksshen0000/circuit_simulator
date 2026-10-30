"""Sparse MNA matrix assembly and linear solve.

The solver assembles the modified-nodal matrix by accumulating (row, col, value)
triplets and materialising a compressed-sparse-column matrix for SuperLU. This keeps
memory O(nnz) instead of O(n^2) as circuits grow.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu


class SparseBuilder:
    """Accumulates coordinate-format stamps and converts to CSC on demand."""

    __slots__ = ("size", "dtype", "rows", "cols", "vals")

    def __init__(self, size: int, dtype) -> None:
        self.size = size
        self.dtype = dtype
        self.rows: list[int] = []
        self.cols: list[int] = []
        self.vals: list[float | complex] = []

    def add(self, i: int, j: int, value) -> None:
        """Stamp value at (i, j); ground terminals (index -1) are ignored."""
        if i < 0 or j < 0:
            return
        self.rows.append(i)
        self.cols.append(j)
        self.vals.append(value)

    def build(self) -> sp.csc_matrix:
        # coo_matrix sums duplicate entries when converting to CSC.
        return sp.coo_matrix(
            (self.vals, (self.rows, self.cols)),
            shape=(self.size, self.size),
            dtype=self.dtype,
        ).tocsc()


def solve_linear(A: sp.csc_matrix, b: np.ndarray) -> np.ndarray:
    """Solve A x = b via sparse LU, mapping solver failures to ValueError."""
    try:
        x = splu(A).solve(b)
    except RuntimeError as exc:
        raise ValueError(
            "Singular circuit: check ground, floating nodes and conflicting ideal sources"
        ) from exc
    if not np.all(np.isfinite(x)):
        raise ValueError("Non-finite simulation result")
    return x
