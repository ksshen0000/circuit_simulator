"""Modified Nodal Analysis matrix builder.

Builds the stamp system  A @ x = z  where:
  x[:n]  = non-ground node voltages
  x[n:]  = currents through voltage sources (and inductors treated as 0V sources in DC)

A is assembled sparsely (coordinate triplets) and returned as a CSC matrix; callers
pass it to the sparse linear solver. Ground terminals map to index -1 and are ignored.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .matrix import SparseBuilder
from .sources import evaluate_source as _eval_source


def _idx(node: str, node_index: dict[str, int]) -> int:
    """Return -1 for ground, else the 0-based node index."""
    return node_index.get(node, -1)


def build_mna_dc(
    elements: list,
    node_index: dict[str, int],
    n_nodes: int,
    t: float | None = None,
) -> tuple[sp.csc_matrix, np.ndarray]:
    """Build MNA for DC operating point.
    Capacitors → open circuit (ignored).
    Inductors → short circuit (0 V voltage source).
    t=None uses declared DC values; an explicit time evaluates waveforms.
    """
    v_sources: list[tuple[str, str, float, str]] = []
    for el in elements:
        if el.type == "inductor":
            v_sources.append((el.node_a, el.node_b, 0.0, el.id))
        elif el.type == "voltage_source":
            v_sources.append((el.node_a, el.node_b, _eval_source(el, t), el.id))

    m = len(v_sources)
    size = n_nodes + m
    A = SparseBuilder(size, float)
    z = np.zeros(size, dtype=float)

    for el in elements:
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)

        if el.type == "resistor":
            _stamp_conductance(A, a, b, 1.0 / el.value)

        elif el.type == "current_source":
            val = _eval_source(el, t)
            if a >= 0:
                z[a] -= val
            if b >= 0:
                z[b] += val

        # capacitor: open → no stamp
        # inductor / voltage_source: handled below

    for k, (na, nb, val, _) in enumerate(v_sources):
        a = _idx(na, node_index)
        b = _idx(nb, node_index)
        col = n_nodes + k
        A.add(a, col, 1.0)
        A.add(col, a, 1.0)
        A.add(b, col, -1.0)
        A.add(col, b, -1.0)
        z[col] = val

    return A.build(), z


def build_mna_ac(
    elements: list,
    node_index: dict[str, int],
    n_nodes: int,
    omega: float,
) -> tuple[sp.csc_matrix, np.ndarray]:
    """Build complex MNA for AC analysis at angular frequency omega."""
    v_sources = [
        (el.node_a, el.node_b, el.ac_amplitude if el.ac_amplitude is not None else el.value, el.ac_phase, el.id)
        for el in elements
        if el.type == "voltage_source"
    ]

    m = len(v_sources)
    size = n_nodes + m
    A = SparseBuilder(size, complex)
    z = np.zeros(size, dtype=complex)

    for el in elements:
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)

        if el.type == "resistor":
            _stamp_conductance(A, a, b, 1.0 / el.value)

        elif el.type == "capacitor":
            if omega != 0:
                _stamp_conductance(A, a, b, 1j * omega * el.value)

        elif el.type == "inductor":
            if omega != 0:
                _stamp_conductance(A, a, b, 1.0 / (1j * omega * el.value))

        elif el.type == "current_source":
            amp = el.ac_amplitude if el.ac_amplitude is not None else el.value
            phasor = amp * np.exp(1j * np.radians(el.ac_phase))
            if a >= 0:
                z[a] -= phasor
            if b >= 0:
                z[b] += phasor

    for k, (na, nb, amp, phase_deg, _) in enumerate(v_sources):
        a = _idx(na, node_index)
        b = _idx(nb, node_index)
        col = n_nodes + k
        phasor = amp * np.exp(1j * np.radians(phase_deg))
        A.add(a, col, 1.0)
        A.add(col, a, 1.0)
        A.add(b, col, -1.0)
        A.add(col, b, -1.0)
        z[col] = phasor

    return A.build(), z


def build_mna_transient(
    elements: list,
    node_index: dict[str, int],
    n_nodes: int,
    t: float,
    h: float,
    state: dict,
    method: str = "trapezoidal",
    source_values: dict | None = None,
) -> tuple[sp.csc_matrix, np.ndarray]:
    """Build real MNA for one transient timestep using trapezoidal companion models.

    state: {
      "cap_<id>": {"v": voltage_across, "i": current_through},
      "ind_<id>": {"v": voltage_across, "i": current_through},
    }
    """
    source_values = source_values or {}
    factor = 1.0 if method == "euler" else 2.0
    v_sources = [el for el in elements if el.type == "voltage_source"]

    m = len(v_sources)
    size = n_nodes + m
    A = SparseBuilder(size, float)
    z = np.zeros(size, dtype=float)

    for el in elements:
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)

        if el.type == "resistor":
            _stamp_conductance(A, a, b, 1.0 / el.value)

        elif el.type == "capacitor":
            # Trapezoidal companion: Req = h/(2C), Ieq = i_prev + (2C/h)*v_prev
            C = el.value
            g_eq = factor * C / h
            st = state.get(f"cap_{el.id}", {"v": 0.0, "i": 0.0})
            Ieq = (st["i"] if factor == 2 else 0.0) + (factor * C / h) * st["v"]
            _stamp_conductance(A, a, b, g_eq)
            if a >= 0:
                z[a] += Ieq
            if b >= 0:
                z[b] -= Ieq

        elif el.type == "inductor":
            # Trapezoidal companion: Req = 2L/h, Ieq = i_prev + (h/(2L))*v_prev
            L = el.value
            g_eq = 1.0 / (factor * L / h)
            st = state.get(f"ind_{el.id}", {"v": 0.0, "i": 0.0})
            Ieq = st["i"] + (h / (factor * L)) * st["v"] if factor == 2 else st["i"]
            _stamp_conductance(A, a, b, g_eq)
            if a >= 0:
                z[a] -= Ieq
            if b >= 0:
                z[b] += Ieq

        elif el.type == "current_source":
            val = source_values.get(el.id, _eval_source(el, t))
            if a >= 0:
                z[a] -= val
            if b >= 0:
                z[b] += val

    for k, el in enumerate(v_sources):
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)
        col = n_nodes + k
        val = source_values.get(el.id, _eval_source(el, t))
        A.add(a, col, 1.0)
        A.add(col, a, 1.0)
        A.add(b, col, -1.0)
        A.add(col, b, -1.0)
        z[col] = val

    return A.build(), z


def _stamp_conductance(A: SparseBuilder, a: int, b: int, g) -> None:
    # SparseBuilder.add already ignores ground terminals (index -1).
    A.add(a, a, g)
    A.add(b, b, g)
    A.add(a, b, -g)
    A.add(b, a, -g)
