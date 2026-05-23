from __future__ import annotations
import numpy as np
from .mna import build_mna_transient, _eval_source, _idx
from .dc_analysis import dc_solve


def transient_sim(
    elements: list,
    node_index: dict[str, int],
    settings,
) -> tuple[list[float], dict[str, list[float]], dict[str, list[float]]]:
    """Return (times, node_voltages_history, branch_currents_history)."""
    n = len(node_index)
    v_sources = [e for e in elements if e.type == "voltage_source"]

    # DC operating point for initial conditions: evaluate sources at t_start - epsilon
    # so step sources at t_start=0 give 0V initial condition
    t_ic = settings.t_start - 1e-12
    try:
        v0, j0 = dc_solve(elements, node_index, t=t_ic)
    except Exception:
        v0 = {node: 0.0 for node in node_index}
        j0 = {}

    # Build initial dynamic state from DC solution
    state: dict = {}
    for el in elements:
        va = v0.get(el.node_a, 0.0)
        vb = v0.get(el.node_b, 0.0)
        if el.type == "capacitor":
            state[f"cap_{el.id}"] = {"v": va - vb, "i": j0.get(el.id, 0.0)}
        elif el.type == "inductor":
            state[f"ind_{el.id}"] = {"v": va - vb, "i": j0.get(el.id, 0.0)}

    h = settings.t_step
    t = settings.t_start
    t_stop = settings.t_stop

    times: list[float] = []
    node_hist: dict[str, list[float]] = {node: [] for node in node_index}
    branch_hist: dict[str, list[float]] = {el.id: [] for el in elements if el.type != "ground"}

    # Store previous solution for trapezoidal
    x_prev = np.zeros(n + len(v_sources))
    for node, idx in node_index.items():
        x_prev[idx] = v0.get(node, 0.0)

    max_steps = int((t_stop - t) / h) + 2

    for _ in range(max_steps):
        if t > t_stop + 1e-15:
            break

        A, z = build_mna_transient(elements, node_index, n, t, h, state)

        try:
            x = np.linalg.solve(A, z)
        except np.linalg.LinAlgError:
            break

        times.append(float(t))

        for node, idx in node_index.items():
            node_hist[node].append(float(x[idx]))

        # Update dynamic state (trapezoidal update)
        for el in elements:
            a = _idx(el.node_a, node_index)
            b = _idx(el.node_b, node_index)
            va_new = float(x[a]) if a >= 0 else 0.0
            vb_new = float(x[b]) if b >= 0 else 0.0
            va_old = float(x_prev[a]) if a >= 0 else 0.0
            vb_old = float(x_prev[b]) if b >= 0 else 0.0

            if el.type == "capacitor":
                st = state[f"cap_{el.id}"]
                v_new = va_new - vb_new
                v_old = st["v"]
                i_new = (2 * el.value / h) * (v_new - v_old) - st["i"]
                state[f"cap_{el.id}"] = {"v": v_new, "i": i_new}
                branch_hist[el.id].append(float(i_new))

            elif el.type == "inductor":
                st = state[f"ind_{el.id}"]
                v_new = va_new - vb_new
                i_new = st["i"] + (h / (2 * el.value)) * (v_new + st["v"])
                state[f"ind_{el.id}"] = {"v": v_new, "i": i_new}
                branch_hist[el.id].append(float(i_new))

            elif el.type == "resistor":
                i = (va_new - vb_new) / el.value
                branch_hist[el.id].append(float(i))

            elif el.type == "voltage_source":
                pass  # filled below

            elif el.type == "current_source":
                branch_hist[el.id].append(float(_eval_source(el, t)))

        for k, el in enumerate(v_sources):
            branch_hist[el.id].append(float(x[n + k]))

        x_prev = x
        t += h

    return times, node_hist, branch_hist
