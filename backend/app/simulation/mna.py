"""Modified Nodal Analysis matrix builder.

Builds the stamp system  A @ x = z  where:
  x[:n]  = non-ground node voltages
  x[n:]  = currents through voltage sources (and inductors treated as 0V sources in DC)

A is assembled sparsely (coordinate triplets) and returned as a CSC matrix. Ground
terminals map to index -1 and are ignored. Linear controlled sources (VCVS/VCCS/
CCCS/CCVS) are stamped directly; the diode is handled by the nonlinear solver.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from .matrix import SparseBuilder
from .sources import evaluate_source as _eval_source


def _idx(node: str, node_index: dict[str, int]) -> int:
    """Return -1 for ground, else the 0-based node index."""
    return node_index.get(node, -1)


def _stamp_conductance(A: SparseBuilder, a: int, b: int, g) -> None:
    # SparseBuilder.add already ignores ground terminals (index -1).
    A.add(a, a, g)
    A.add(b, b, g)
    A.add(a, b, -g)
    A.add(b, a, -g)


def _collect_voltage_sources(elements, node_index, n_nodes, t, include_inductors, source_values=None):
    """Return (v_sources, col_of) where v_sources are (na, nb, value, id) tuples."""
    source_values = source_values or {}
    v_sources = []
    col_of = {}
    for el in elements:
        if el.type == "inductor" and include_inductors:
            col_of[el.id] = n_nodes + len(v_sources)
            v_sources.append((el.node_a, el.node_b, 0.0, el.id))
        elif el.type == "voltage_source":
            col_of[el.id] = n_nodes + len(v_sources)
            v_sources.append((el.node_a, el.node_b, source_values.get(el.id, _eval_source(el, t)), el.id))
        elif el.type in ("vcvs", "ccvs"):
            col_of[el.id] = n_nodes + len(v_sources)
            v_sources.append((el.node_a, el.node_b, 0.0, el.id))
    return v_sources, col_of


def _stamp_voltage_source_pins(A: SparseBuilder, z, node_index, n_nodes, v_sources) -> None:
    for k, (na, nb, val, _) in enumerate(v_sources):
        a = _idx(na, node_index)
        b = _idx(nb, node_index)
        col = n_nodes + k
        A.add(a, col, 1.0)
        A.add(col, a, 1.0)
        A.add(b, col, -1.0)
        A.add(col, b, -1.0)
        z[col] = val


def _stamp_controlled_sources(A: SparseBuilder, z, elements, node_index, col_of) -> None:
    """Stamp linear controlled sources (VCVS/VCCS/CCCS/CCVS)."""
    for el in elements:
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)
        if el.type == "vccs":
            ca = _idx(el.control_node_a, node_index)
            cb = _idx(el.control_node_b, node_index)
            gm = el.value
            A.add(a, ca, gm)
            A.add(a, cb, -gm)
            A.add(b, ca, -gm)
            A.add(b, cb, gm)
        elif el.type == "vcvs":
            ca = _idx(el.control_node_a, node_index)
            cb = _idx(el.control_node_b, node_index)
            gain = el.value
            col = col_of[el.id]
            A.add(col, ca, -gain)
            A.add(col, cb, gain)
            z[col] = 0.0
        elif el.type == "cccs":
            if el.control_element not in col_of:
                raise ValueError(f"{el.id}: control element {el.control_element} is not a voltage source")
            A.add(a, col_of[el.control_element], el.value)
            A.add(b, col_of[el.control_element], -el.value)
        elif el.type == "ccvs":
            if el.control_element not in col_of:
                raise ValueError(f"{el.id}: control element {el.control_element} is not a voltage source")
            col = col_of[el.id]
            A.add(col, col_of[el.control_element], -el.value)
            z[col] = 0.0


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
    v_sources, col_of = _collect_voltage_sources(elements, node_index, n_nodes, t, include_inductors=True)
    size = n_nodes + len(v_sources)
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
        # inductor / voltage_source / vcvs / ccvs: handled below

    _stamp_voltage_source_pins(A, z, node_index, n_nodes, v_sources)
    _stamp_controlled_sources(A, z, elements, node_index, col_of)

    return A.build(), z


def build_mna_ac(
    elements: list,
    node_index: dict[str, int],
    n_nodes: int,
    omega: float,
    diode_gd: dict[str, float] | None = None,
) -> tuple[sp.csc_matrix, np.ndarray]:
    """Build complex MNA for AC analysis at angular frequency omega.

    diode_gd maps diode ids to their small-signal conductance at the DC bias point.
    """
    v_sources, col_of = _collect_voltage_sources(elements, node_index, n_nodes, None, include_inductors=False)
    by_id = {e.id: e for e in elements}
    size = n_nodes + len(v_sources)
    A = SparseBuilder(size, complex)
    z = np.zeros(size, dtype=complex)

    for el in elements:
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)

        if el.type == "diode" and diode_gd is not None:
            _stamp_conductance(A, a, b, diode_gd.get(el.id, 0.0))

        elif el.type == "resistor":
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

    for k, (na, nb, _value, el_id) in enumerate(v_sources):
        a = _idx(na, node_index)
        b = _idx(nb, node_index)
        col = n_nodes + k
        el = by_id[el_id]
        if el.type == "voltage_source":
            amp = el.ac_amplitude if el.ac_amplitude is not None else el.value
            z[col] = amp * np.exp(1j * np.radians(el.ac_phase))
        else:
            z[col] = 0.0
        A.add(a, col, 1.0)
        A.add(col, a, 1.0)
        A.add(b, col, -1.0)
        A.add(col, b, -1.0)

    _stamp_controlled_sources(A, z, elements, node_index, col_of)

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
    v_sources, col_of = _collect_voltage_sources(elements, node_index, n_nodes, t, include_inductors=False, source_values=source_values)
    size = n_nodes + len(v_sources)
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

    _stamp_voltage_source_pins(A, z, node_index, n_nodes, v_sources)
    _stamp_controlled_sources(A, z, elements, node_index, col_of)

    return A.build(), z
