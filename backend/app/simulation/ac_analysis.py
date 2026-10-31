from __future__ import annotations

import numpy as np

from .dc_analysis import dc_solve
from .devices import diode_conductance, mosfet_currents
from .mna import build_mna_ac
from .opamp import output_current, solve
from .sources import ac_amplitude


def ac_sweep(
    elements: list,
    node_index: dict[str, int],
    settings,
    options=None,
) -> tuple[list[float], dict[str, list[float]], dict[str, list[float]], dict[str, list[float]], dict[str, list[float]]]:
    """Return (freqs, node_mag, node_phase, branch_mag, branch_phase)."""
    # Small-signal analysis is only meaningful around an unsaturated bias point.
    bias: dict[str, float] | None = None
    if any(e.type in ("opamp", "diode", "mosfet") for e in elements):
        bias, currents = dc_solve(elements, node_index, options=options)
        for el in elements:
            if el.type == "opamp":
                internal = bias.get(el.node_out, 0) - el.output_resistance * currents[el.id]
                if internal <= el.output_min + 1e-8 or internal >= el.output_max - 1e-8:
                    raise ValueError(f"{el.id} is saturated at DC; adjust source bias before AC analysis")
    # Diode small-signal conductance and MOSFET (vgs, vds) at the DC bias point.
    diode_gd: dict[str, float] | None = None
    if bias is not None:
        diode_gd = {
            el.id: diode_conductance(el, bias.get(el.node_a, 0.0) - bias.get(el.node_b, 0.0))
            for el in elements if el.type == "diode"
        }
    mos_bias: dict[str, tuple[float, float]] | None = None
    if bias is not None:
        mos_bias = {
            el.id: (
                bias.get(el.node_g, 0.0) - bias.get(el.node_b, 0.0),
                bias.get(el.node_a, 0.0) - bias.get(el.node_b, 0.0),
            )
            for el in elements if el.type == "mosfet"
        }

    n = len(node_index)
    v_sources = [e for e in elements if e.type in ("voltage_source", "vcvs", "ccvs")]

    if settings.sweep_type == "log":
        start, stop = np.log10(settings.f_start), np.log10(settings.f_stop)
        count = 1 if settings.f_start == settings.f_stop else max(2, int(np.ceil((stop - start) * settings.points_per_decade)) + 1)
        freqs = np.logspace(start, stop, count)
        # Preserve user-specified boundaries, including sub-decade sweeps.
        freqs[0], freqs[-1] = settings.f_start, settings.f_stop
    else:
        freqs = np.linspace(settings.f_start, settings.f_stop, settings.points_per_decade)

    node_mag: dict[str, list[float]] = {node: [] for node in node_index}
    node_phase: dict[str, list[float]] = {node: [] for node in node_index}
    branch_mag: dict[str, list[float]] = {el.id: [] for el in elements if el.type != "ground"}
    branch_phase: dict[str, list[float]] = {el.id: [] for el in elements if el.type != "ground"}

    for f in freqs:
        omega = 2 * np.pi * f
        A, z = build_mna_ac(elements, node_index, n, omega, diode_gd, mos_bias)

        x = solve(A, z, elements, node_index, omega=omega, options=options)

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
            if el.type in ("voltage_source", "vcvs", "ccvs"):
                continue
            a_v = x[node_index[el.node_a]] if el.node_a in node_index else 0
            b_v = x[node_index[el.node_b]] if el.node_b in node_index else 0
            vab = a_v - b_v

            if el.type == "opamp":
                i = output_current(x, elements, el)
            elif el.type == "diode":
                i = vab * (diode_gd.get(el.id, 0.0) if diode_gd else 0.0)
            elif el.type == "mosfet":
                gate_v = x[node_index[el.node_g]] if el.node_g in node_index else 0
                vgs = gate_v - b_v
                _id, gm, gds = mosfet_currents(el, *(mos_bias or {}).get(el.id, (0.0, 0.0)))
                i = gm * vgs + gds * vab
            elif el.type == "resistor":
                i = vab / el.value
            elif el.type == "capacitor" and omega != 0:
                i = vab * (1j * omega * el.value)
            elif el.type == "inductor" and omega != 0:
                i = vab / (1j * omega * el.value)
            elif el.type == "current_source":
                amp = ac_amplitude(el)
                i = complex(amp * np.cos(np.radians(el.ac_phase)),
                            amp * np.sin(np.radians(el.ac_phase)))
            elif el.type == "vccs":
                ca = x[node_index[el.control_node_a]] if el.control_node_a in node_index else 0
                cb = x[node_index[el.control_node_b]] if el.control_node_b in node_index else 0
                i = el.value * (ca - cb)
            elif el.type == "cccs":
                i = el.value * x[n + next(k for k, e in enumerate(v_sources) if e.id == el.control_element)]
            else:
                i = complex(0)

            branch_mag[el.id].append(float(np.abs(i)))
            branch_phase[el.id].append(float(np.degrees(np.angle(i))))

    return list(map(float, freqs)), node_mag, node_phase, branch_mag, branch_phase
