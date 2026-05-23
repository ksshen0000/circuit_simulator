from __future__ import annotations
import numpy as np
from .mna import build_mna_ac, _idx


def ac_sweep(
    elements: list,
    node_index: dict[str, int],
    settings,
) -> tuple[list[float], dict[str, list[float]], dict[str, list[float]], dict[str, list[float]], dict[str, list[float]]]:
    """Return (freqs, node_mag, node_phase, branch_mag, branch_phase)."""
    n = len(node_index)
    v_sources = [e for e in elements if e.type == "voltage_source"]

    if settings.sweep_type == "log":
        freqs = np.logspace(
            np.log10(settings.f_start),
            np.log10(settings.f_stop),
            int(np.log10(settings.f_stop / settings.f_start) * settings.points_per_decade + 1),
        )
    else:
        freqs = np.linspace(settings.f_start, settings.f_stop, settings.points_per_decade)

    node_mag: dict[str, list[float]] = {node: [] for node in node_index}
    node_phase: dict[str, list[float]] = {node: [] for node in node_index}
    branch_mag: dict[str, list[float]] = {el.id: [] for el in elements if el.type != "ground"}
    branch_phase: dict[str, list[float]] = {el.id: [] for el in elements if el.type != "ground"}

    for f in freqs:
        omega = 2 * np.pi * f
        A, z = build_mna_ac(elements, node_index, n, omega)

        try:
            x = np.linalg.solve(A, z)
        except np.linalg.LinAlgError:
            x = np.zeros(n + len(v_sources), dtype=complex)

        for node, idx in node_index.items():
            node_mag[node].append(float(np.abs(x[idx])))
            node_phase[node].append(float(np.degrees(np.angle(x[idx]))))

        for k, el in enumerate(v_sources):
            j = x[n + k]
            branch_mag[el.id].append(float(np.abs(j)))
            branch_phase[el.id].append(float(np.degrees(np.angle(j))))

        for el in elements:
            if el.type == "ground":
                continue
            if el.type in ("voltage_source",):
                continue
            a_v = x[node_index[el.node_a]] if el.node_a in node_index else 0
            b_v = x[node_index[el.node_b]] if el.node_b in node_index else 0
            vab = a_v - b_v

            if el.type == "resistor":
                i = vab / el.value
            elif el.type == "capacitor" and omega != 0:
                i = vab * (1j * omega * el.value)
            elif el.type == "inductor" and omega != 0:
                i = vab / (1j * omega * el.value)
            elif el.type == "current_source":
                amp = el.ac_amplitude if el.ac_amplitude is not None else el.value
                i = complex(amp * np.cos(np.radians(el.ac_phase)),
                            amp * np.sin(np.radians(el.ac_phase)))
            else:
                i = complex(0)

            branch_mag[el.id].append(float(np.abs(i)))
            branch_phase[el.id].append(float(np.degrees(np.angle(i))))

    return list(map(float, freqs)), node_mag, node_phase, branch_mag, branch_phase
