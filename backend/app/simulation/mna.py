"""Modified Nodal Analysis matrix builder.

Builds the stamp system  A @ x = z  where:
  x[:n]  = non-ground node voltages
  x[n:]  = currents through voltage sources (and inductors treated as 0V sources in DC)

Caller is responsible for choosing real vs complex dtype (pass dtype=complex for AC).
"""
from __future__ import annotations
import numpy as np
from typing import Optional


def _idx(node: str, node_index: dict[str, int]) -> int:
    """Return -1 for ground, else the 0-based node index."""
    return node_index.get(node, -1)


def build_mna_dc(
    elements: list,
    node_index: dict[str, int],
    n_nodes: int,
    t: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Build MNA for DC operating point.
    Capacitors → open circuit (ignored).
    Inductors → short circuit (0 V voltage source).
    Returns (A, z) real arrays.
    t: evaluate time-varying sources at this time (use t<0 for t=0- initial conditions).
    """
    v_sources: list[tuple[str, str, float]] = []
    for el in elements:
        if el.type == "inductor":
            v_sources.append((el.node_a, el.node_b, 0.0, el.id))
        elif el.type == "voltage_source":
            v_sources.append((el.node_a, el.node_b, _eval_source(el, t), el.id))

    m = len(v_sources)
    size = n_nodes + m
    A = np.zeros((size, size), dtype=float)
    z = np.zeros(size, dtype=float)

    for el in elements:
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)

        if el.type == "resistor":
            g = 1.0 / el.value
            _stamp_conductance(A, a, b, g)

        elif el.type == "current_source":
            val = _eval_source(el, t)
            if a >= 0:
                z[a] += val
            if b >= 0:
                z[b] -= val

        # capacitor: open → no stamp
        # inductor / voltage_source: handled below

    for k, (na, nb, val, _) in enumerate(v_sources):
        a = _idx(na, node_index)
        b = _idx(nb, node_index)
        col = n_nodes + k
        if a >= 0:
            A[a, col] += 1.0
            A[col, a] += 1.0
        if b >= 0:
            A[b, col] -= 1.0
            A[col, b] -= 1.0
        z[col] = val

    return A, z


def build_mna_ac(
    elements: list,
    node_index: dict[str, int],
    n_nodes: int,
    omega: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Build complex MNA for AC analysis at angular frequency omega."""
    v_sources = [
        (el.node_a, el.node_b, el.ac_amplitude or el.value, el.ac_phase, el.id)
        for el in elements
        if el.type == "voltage_source"
    ]

    m = len(v_sources)
    size = n_nodes + m
    A = np.zeros((size, size), dtype=complex)
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
                z[a] += phasor
            if b >= 0:
                z[b] -= phasor

    for k, (na, nb, amp, phase_deg, _) in enumerate(v_sources):
        a = _idx(na, node_index)
        b = _idx(nb, node_index)
        col = n_nodes + k
        phasor = amp * np.exp(1j * np.radians(phase_deg))
        if a >= 0:
            A[a, col] += 1.0
            A[col, a] += 1.0
        if b >= 0:
            A[b, col] -= 1.0
            A[col, b] -= 1.0
        z[col] = phasor

    return A, z


def build_mna_transient(
    elements: list,
    node_index: dict[str, int],
    n_nodes: int,
    t: float,
    h: float,
    state: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Build real MNA for one transient timestep using trapezoidal companion models.

    state: {
      "cap_<id>": {"v": voltage_across, "i": current_through},
      "ind_<id>": {"v": voltage_across, "i": current_through},
    }
    """
    v_sources = [
        el for el in elements
        if el.type == "voltage_source"
    ]

    m = len(v_sources)
    size = n_nodes + m
    A = np.zeros((size, size), dtype=float)
    z = np.zeros(size, dtype=float)

    for el in elements:
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)

        if el.type == "resistor":
            _stamp_conductance(A, a, b, 1.0 / el.value)

        elif el.type == "capacitor":
            # Trapezoidal companion: Req = h/(2C), Ieq = i_prev + (2C/h)*v_prev
            C = el.value
            Req = h / (2.0 * C)
            g_eq = 1.0 / Req
            st = state.get(f"cap_{el.id}", {"v": 0.0, "i": 0.0})
            Ieq = st["i"] + (2.0 * C / h) * st["v"]
            _stamp_conductance(A, a, b, g_eq)
            if a >= 0:
                z[a] += Ieq
            if b >= 0:
                z[b] -= Ieq

        elif el.type == "inductor":
            # Trapezoidal companion: Req = 2L/h, Ieq = i_prev + (h/(2L))*v_prev
            # Inductor: i_{k+1} = G*v_{k+1} + Ieq  → current source flows a→b
            # (opposite sign to capacitor's b→a source)
            L = el.value
            Req = 2.0 * L / h
            g_eq = 1.0 / Req
            st = state.get(f"ind_{el.id}", {"v": 0.0, "i": 0.0})
            Ieq = st["i"] + (h / (2.0 * L)) * st["v"]
            _stamp_conductance(A, a, b, g_eq)
            if a >= 0:
                z[a] -= Ieq
            if b >= 0:
                z[b] += Ieq

        elif el.type == "current_source":
            val = _eval_source(el, t)
            if a >= 0:
                z[a] += val
            if b >= 0:
                z[b] -= val

    for k, el in enumerate(v_sources):
        a = _idx(el.node_a, node_index)
        b = _idx(el.node_b, node_index)
        col = n_nodes + k
        val = _eval_source(el, t)
        if a >= 0:
            A[a, col] += 1.0
            A[col, a] += 1.0
        if b >= 0:
            A[b, col] -= 1.0
            A[col, b] -= 1.0
        z[col] = val

    return A, z


def _stamp_conductance(A: np.ndarray, a: int, b: int, g) -> None:
    if a >= 0:
        A[a, a] += g
    if b >= 0:
        A[b, b] += g
    if a >= 0 and b >= 0:
        A[a, b] -= g
        A[b, a] -= g


def _eval_source(el, t: float) -> float:
    wf = el.source_waveform
    if wf == "dc":
        return el.value
    elif wf == "sine":
        freq = el.sine_frequency or 60.0
        amp = el.ac_amplitude if el.ac_amplitude is not None else el.value
        phase = np.radians(el.ac_phase)
        return amp * np.sin(2 * np.pi * freq * t + phase)
    elif wf == "step":
        return el.value if t > 0 else 0.0
    elif wf == "pulse":
        period = el.pulse_period or 1.0
        width = el.pulse_width or period / 2
        t_mod = t % period
        return el.value if t_mod < width else 0.0
    return el.value
