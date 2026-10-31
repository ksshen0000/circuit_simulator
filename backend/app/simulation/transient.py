from __future__ import annotations

import numpy as np

from .dc_analysis import dc_solve
from .devices import diode_current
from .mna import _eval_source, _idx, build_mna_transient
from .opamp import output_current, solve
from .time_grid import transient_breakpoints


def _lte_error(x_corr: np.ndarray, x_pred: np.ndarray, reltol: float, abstol: float) -> float:
    scale = reltol * np.abs(x_corr) + abstol
    return float(np.max(np.abs(x_corr - x_pred) / scale))


def _fp_tol(x: float) -> float:
    """A few ULPs of tolerance for snapping onto forced time points."""
    return 4.0 * np.spacing(abs(x) if x != 0 else 1.0)


def transient_sim(
    elements: list,
    node_index: dict[str, int],
    settings,
    options=None,
) -> tuple[list[float], dict[str, list[float]], dict[str, list[float]]]:
    """Return (times, node_voltages_history, branch_currents_history).

    Trapezoidal integration uses an adaptive step controller: after each step a
    predictor-corrector estimate of the local truncation error decides whether to
    accept the step and how to size the next one. Euler integration keeps the
    fixed-step behaviour. Known source breakpoints are always hit exactly.
    """
    n = len(node_index)
    v_sources = [e for e in elements if e.type in ("voltage_source", "vcvs", "ccvs")]
    vsource_index = {el.id: k for k, el in enumerate(v_sources)}

    # DC operating point for initial conditions: evaluate sources at t_start - epsilon
    # so step sources at t_start=0 give 0V initial condition.
    t_ic = np.nextafter(settings.t_start, -np.inf)
    v0, j0 = dc_solve(elements, node_index, t=t_ic, options=options)

    # Build initial dynamic state from DC solution.
    state: dict = {}
    for el in elements:
        va = v0.get(el.node_a, 0.0)
        vb = v0.get(el.node_b, 0.0)
        if el.type == "capacitor":
            state[f"cap_{el.id}"] = {"v": va - vb, "i": j0.get(el.id, 0.0)}
        elif el.type == "opamp":
            state[f"op_{el.id}"] = v0.get(el.node_out, 0.0) - el.output_resistance * j0[el.id]
        elif el.type == "inductor":
            state[f"ind_{el.id}"] = {"v": va - vb, "i": j0.get(el.id, 0.0)}

    t = settings.t_start
    h = settings.t_step
    h_prev: float | None = None

    times = [float(t)]
    node_hist = {node: [v0[node]] for node in node_index}
    branch_hist = {el.id: [j0.get(el.id, 0.0)] for el in elements if el.type != "ground"}
    devices = [e for e in elements if e.type == "opamp"]
    previous = np.zeros(n + len(v_sources) + len(devices))
    for node, idx in node_index.items():
        previous[idx] = v0[node]
    for k, el in enumerate(v_sources + devices):
        previous[n + k] = j0[el.id]
    prev_prev: np.ndarray | None = None  # solution one step before `previous`

    breakpoints, jumps = transient_breakpoints(elements, settings)
    bp_idx = 0
    while bp_idx < len(breakpoints) and breakpoints[bp_idx] <= t:
        bp_idx += 1

    adaptive = settings.method == "trapezoidal"
    step_budget = 200000
    step_count = 0

    while t < settings.t_stop:
        step_count += 1
        if step_count > step_budget:
            raise ValueError("Transient exceeded 200000 steps; relax reltol or increase t_step")
        next_forced = breakpoints[bp_idx] if bp_idx < len(breakpoints) else settings.t_stop
        if next_forced - t <= _fp_tol(next_forced):
            bp_idx += 1
            continue
        h = min(h, settings.t_step, next_forced - t)
        if h <= 0:
            bp_idx += 1
            continue

        method = "euler" if t in jumps else settings.method
        factor = 1.0 if method == "euler" else 2.0
        t_next = t + h
        # Snap exactly onto a forced point to avoid floating-point drift.
        if abs(t_next - next_forced) <= _fp_tol(next_forced):
            t_next = next_forced
        source_values = jumps.get(t_next, {})

        A, z = build_mna_transient(elements, node_index, n, t_next, h, state, method, source_values)
        try:
            x = solve(A, z, elements, node_index, state=state, h=h, initial=previous, options=options)
        except ValueError as exc:
            raise ValueError(f"Transient failed at t={t_next:.12g} s (step={h:.12g} s): {exc}") from exc

        # Predictor-corrector LTE estimate; reject the step if it exceeds tolerance.
        err = 0.0
        if adaptive and method == "trapezoidal" and prev_prev is not None and h_prev is not None:
            x_pred = previous + (h / h_prev) * (previous - prev_prev)
            err = _lte_error(x, x_pred, settings.reltol, settings.abstol)
            if err > 1.0:
                h = h * max(0.2, 0.9 * err ** (-1 / 3))
                continue  # reject and retry with a smaller step

        # Accept the step.
        t = t_next
        prev_prev = previous
        previous = x
        h_prev = h
        times.append(float(t))
        for node, idx in node_index.items():
            node_hist[node].append(float(x[idx]))

        # Update dynamic state (trapezoidal/BE companion update).
        for el in elements:
            a = _idx(el.node_a, node_index)
            b = _idx(el.node_b, node_index)
            va_new = float(x[a]) if a >= 0 else 0.0
            vb_new = float(x[b]) if b >= 0 else 0.0

            if el.type == "capacitor":
                st = state[f"cap_{el.id}"]
                v_new = va_new - vb_new
                v_old = st["v"]
                i_new = (factor * el.value / h) * (v_new - v_old) - (st["i"] if factor == 2 else 0.0)
                state[f"cap_{el.id}"] = {"v": v_new, "i": i_new}
                branch_hist[el.id].append(float(i_new))

            elif el.type == "inductor":
                st = state[f"ind_{el.id}"]
                v_new = va_new - vb_new
                i_new = st["i"] + (h / (factor * el.value)) * (v_new + (st["v"] if factor == 2 else 0.0))
                state[f"ind_{el.id}"] = {"v": v_new, "i": i_new}
                branch_hist[el.id].append(float(i_new))

            elif el.type == "opamp":
                current = float(output_current(x, elements, el))
                state[f"op_{el.id}"] = float(x[node_index[el.node_out]]) - el.output_resistance * current if el.node_out in node_index else -el.output_resistance * current
                branch_hist[el.id].append(current)

            elif el.type == "resistor":
                branch_hist[el.id].append(float((va_new - vb_new) / el.value))

            elif el.type == "voltage_source":
                pass  # filled below

            elif el.type == "current_source":
                branch_hist[el.id].append(float(source_values.get(el.id, _eval_source(el, t))))

            elif el.type == "diode":
                branch_hist[el.id].append(diode_current(el, va_new - vb_new))

            elif el.type == "vccs":
                ca = x[node_index[el.control_node_a]] if el.control_node_a in node_index else 0
                cb = x[node_index[el.control_node_b]] if el.control_node_b in node_index else 0
                branch_hist[el.id].append(float(el.value * (ca - cb)))

            elif el.type == "cccs":
                branch_hist[el.id].append(float(el.value * x[n + vsource_index[el.control_element]]))

        for k, el in enumerate(v_sources):
            branch_hist[el.id].append(float(x[n + k]))

        # Reset the predictor history after a discontinuity (Euler restart).
        if method == "euler":
            prev_prev = None

        # Choose the next step size; never exceed the user's maximum step.
        if adaptive and err > 0.0:
            h = h * min(2.0, max(0.2, 0.9 * err ** (-1 / 3)))
        else:
            h = settings.t_step
        h = min(h, settings.t_step)

        while bp_idx < len(breakpoints) and breakpoints[bp_idx] - t <= _fp_tol(breakpoints[bp_idx]):
            bp_idx += 1

    return times, node_hist, branch_hist
