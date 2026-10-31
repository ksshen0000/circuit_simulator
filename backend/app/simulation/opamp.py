"""Three-terminal, single-pole behavioral opamp with ground-referenced rails.

Branch current is positive into the output; input bias currents are not modeled.
The dominant pole uses backward Euler in transient, including slew limiting.
The Newton Jacobian is assembled sparsely and solved with SuperLU. A gmin-stepping
continuation is available as a fallback for hard-to-converge operating points.
"""
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

from .devices import diode_conductance, diode_current
from .matrix import solve_linear
from .mna import _idx


@dataclass(frozen=True)
class SolverOptions:
    """Newton convergence tolerances and continuation options."""

    abstol: float = 1e-9  # absolute residual tolerance (inf-norm)
    itl1: int = 100       # maximum Newton iterations
    itl4: int = 40        # maximum damped backtracking steps
    gmin: float = 1e-12   # final ground conductance used by gmin stepping
    gmin_steps: int = 5   # continuation steps (0 disables the fallback)


def _stamp_coo(rows: list[int], cols: list[int], data: list, a: int, b: int, g) -> None:
    """Stamp a conductance between terminals a and b into coordinate lists."""
    if a >= 0:
        rows.append(a)
        cols.append(a)
        data.append(g)
    if b >= 0:
        rows.append(b)
        cols.append(b)
        data.append(g)
    if a >= 0 and b >= 0:
        rows.append(a)
        cols.append(b)
        data.append(-g)
        rows.append(b)
        cols.append(a)
        data.append(-g)


def solve(A, z, elements, node_index, *, omega=None, state=None, h=None, initial=None, options=None):
    opts = options or SolverOptions()
    devices = [e for e in elements if e.type == "opamp"]
    diodes = [e for e in elements if e.type == "diode"]
    base = len(z)
    size = base + len(devices)
    rhs = np.zeros(size, dtype=z.dtype)
    rhs[:base] = z

    # Constant Jacobian structure: base MNA plus opamp input/output coupling.
    a_coo = A.tocoo()
    const_rows: list[int] = a_coo.row.tolist()
    const_cols: list[int] = a_coo.col.tolist()
    const_data: list = a_coo.data.tolist()
    for k, el in enumerate(devices):
        a, b, out = (_idx(node, node_index) for node in (el.node_a, el.node_b, el.node_out))
        col = base + k
        _stamp_coo(const_rows, const_cols, const_data, a, b, 1 / el.input_resistance)
        if out >= 0:
            const_rows.extend([out, col])
            const_cols.extend([col, out])
            const_data.extend([1.0, 1.0])
        const_rows.append(col)
        const_cols.append(col)
        const_data.append(-el.output_resistance)

    def build_system(x, base_rows, base_cols, base_data):
        rows = base_rows.copy()
        cols = base_cols.copy()
        data = base_data.copy()
        target = rhs.copy()
        for k, el in enumerate(devices):
            a, b = _idx(el.node_a, node_index), _idx(el.node_b, node_index)
            col = base + k
            gain = el.open_loop_gain
            offset = gain * el.input_offset
            low, high = el.output_min, el.output_max
            if omega is not None:
                gain = gain / (1 + 1j * omega * el.open_loop_gain / (2 * np.pi * el.gain_bandwidth))
                offset = 0
            elif h is not None:
                previous = state[f"op_{el.id}"]
                tau = el.open_loop_gain / (2 * np.pi * el.gain_bandwidth)
                gain = gain * h / (tau + h)
                offset = (tau * previous + h * offset) / (tau + h)
                low = max(low, previous - el.slew_rate * h)
                high = min(high, previous + el.slew_rate * h)
            diff = (x[a] if a >= 0 else 0) - (x[b] if b >= 0 else 0)
            raw = gain * diff + offset
            if omega is None and (raw < low or raw > high):
                target[col] = np.clip(raw, low, high)
            else:
                if a >= 0:
                    rows.append(col)
                    cols.append(a)
                    data.append(-gain)
                if b >= 0:
                    rows.append(col)
                    cols.append(b)
                    data.append(gain)
                target[col] = offset
        if omega is None:
            for el in diodes:
                a, b = _idx(el.node_a, node_index), _idx(el.node_b, node_index)
                vd = (x[a] if a >= 0 else 0) - (x[b] if b >= 0 else 0)
                gd = diode_conductance(el, vd)
                idd = diode_current(el, vd)
                _stamp_coo(rows, cols, data, a, b, gd)
                ieq = idd - gd * vd
                if a >= 0:
                    target[a] -= ieq
                if b >= 0:
                    target[b] += ieq
        jac = sp.coo_matrix((data, (rows, cols)), shape=(size, size), dtype=A.dtype).tocsc()
        return jac, target

    def newton(gmin: float, x0: np.ndarray) -> np.ndarray:
        rows = const_rows + list(range(base))
        cols = const_cols + list(range(base))
        data = const_data + [gmin] * base
        x = x0.copy()
        for _ in range(opts.itl1):
            jac, target = build_system(x, rows, cols, data)
            residual = jac @ x - target
            candidate = solve_linear(jac, target)
            # Check the actual piecewise system, not just its local linearization.
            candidate_jac, candidate_rhs = build_system(candidate, rows, cols, data)
            if np.linalg.norm(candidate_jac @ candidate - candidate_rhs, ord=np.inf) < opts.abstol:
                return candidate
            delta = candidate - x
            norm = np.linalg.norm(residual, ord=np.inf) if size else 0
            # Damped Newton prevents alternating between opposite saturation rails.
            alpha = 1.0
            for _ in range(opts.itl4):
                trial = x + alpha * delta
                trial_jac, trial_rhs = build_system(trial, rows, cols, data)
                trial_norm = np.linalg.norm(trial_jac @ trial - trial_rhs, ord=np.inf)
                if trial_norm < norm or trial_norm < opts.abstol:
                    x = trial
                    break
                alpha *= 0.5
            else:
                raise ValueError("Opamp operating point did not converge; check feedback and rails")
        raise ValueError("Opamp operating point did not converge")

    x0 = np.zeros(size, dtype=A.dtype) if initial is None else np.asarray(initial, dtype=A.dtype).copy()
    if x0.shape != (size,) or not np.all(np.isfinite(x0)):
        raise ValueError("Invalid solver initial state")

    if (not devices and not diodes) or omega is not None:
        jac, target = build_system(x0, const_rows, const_cols, const_data)
        return solve_linear(jac, target)

    try:
        return newton(0.0, x0)
    except ValueError:
        if opts.gmin_steps <= 0:
            raise
        # gmin continuation: start with a large ground conductance for easy
        # convergence, then shrink it, reusing each solution as the next guess.
        for step in range(opts.gmin_steps, 0, -1):
            x0 = newton(opts.gmin * (10.0 ** step), x0)
        return newton(opts.gmin, x0)


def output_current(x, elements, el):
    base = len(x) - sum(e.type == "opamp" for e in elements)
    return x[base + [e.id for e in elements if e.type == "opamp"].index(el.id)]
