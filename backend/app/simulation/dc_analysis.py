from __future__ import annotations

from .devices import diode_current, mosfet_current
from .mna import _eval_source, build_mna_dc
from .opamp import output_current, solve


def dc_solve(elements: list, node_index: dict[str, int], t: float | None = None, options=None) -> tuple[dict, dict]:
    """Return operating point using declared DC values.

    Passing an explicit time instead evaluates source waveforms for transient
    initialization; it does not change the independent-source DC specification.
    If plain Newton/gmin stepping fails, independent sources are ramped from a
    small fraction to their final values and the previous solution is reused.
    """
    n = len(node_index)
    v_sources = [e for e in elements if e.type in ("voltage_source", "inductor", "vcvs", "ccvs")]

    A, z = build_mna_dc(elements, node_index, n, t=t)

    try:
        x = solve(A, z, elements, node_index, options=options)
    except ValueError as first_error:
        steps = getattr(options, "source_steps", 5) if options is not None else 5
        if steps <= 0:
            raise
        initial = None
        try:
            for step in range(1, steps + 1):
                scaled_a, scaled_z = build_mna_dc(
                    elements, node_index, n, t=t, source_scale=step / steps,
                )
                initial = solve(
                    scaled_a, scaled_z, elements, node_index, initial=initial, options=options,
                )
        except ValueError as exc:
            raise first_error from exc
        x = initial

    node_voltages = {node: float(x[idx]) for node, idx in node_index.items()}

    branch_currents: dict[str, float] = {}
    # Currents through V sources / inductors are in x[n:]
    for k, el in enumerate(v_sources):
        branch_currents[el.id] = float(x[n + k])

    # Resistor currents: I = (Va - Vb) / R
    for el in elements:
        if el.type == "resistor":
            va = node_voltages.get(el.node_a, 0.0)
            vb = node_voltages.get(el.node_b, 0.0)
            branch_currents[el.id] = (va - vb) / el.value

        elif el.type == "capacitor":
            branch_currents[el.id] = 0.0  # open in DC

        elif el.type == "current_source":
            branch_currents[el.id] = float(_eval_source(el, t))

        elif el.type == "opamp":
            branch_currents[el.id] = float(output_current(x, elements, el))

        elif el.type == "diode":
            va = node_voltages.get(el.node_a, 0.0)
            vb = node_voltages.get(el.node_b, 0.0)
            branch_currents[el.id] = diode_current(el, va - vb)

        elif el.type == "mosfet":
            vg = node_voltages.get(el.node_g, 0.0)
            va = node_voltages.get(el.node_a, 0.0)
            vb = node_voltages.get(el.node_b, 0.0)
            branch_currents[el.id] = mosfet_current(el, vg - vb, va - vb)

        elif el.type == "vccs":
            vca = node_voltages.get(el.control_node_a, 0.0)
            vcb = node_voltages.get(el.control_node_b, 0.0)
            branch_currents[el.id] = el.value * (vca - vcb)

        elif el.type == "cccs":
            branch_currents[el.id] = el.value * branch_currents.get(el.control_element, 0.0)

    return node_voltages, branch_currents
