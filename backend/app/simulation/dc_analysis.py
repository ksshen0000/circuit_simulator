from __future__ import annotations
import numpy as np
from .mna import build_mna_dc, _idx


def dc_solve(elements: list, node_index: dict[str, int], t: float = 0.0) -> tuple[dict, dict]:
    """Return (node_voltages, branch_currents) for DC operating point."""
    n = len(node_index)
    v_sources = [e for e in elements if e.type in ("voltage_source", "inductor")]

    A, z = build_mna_dc(elements, node_index, n, t=t)

    try:
        x = np.linalg.solve(A, z)
    except np.linalg.LinAlgError as exc:
        raise ValueError(f"Singular matrix: {exc}") from exc

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
            branch_currents[el.id] = el.value

    return node_voltages, branch_currents
