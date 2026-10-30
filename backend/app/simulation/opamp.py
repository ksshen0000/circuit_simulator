"""Three-terminal, single-pole behavioral opamp with ground-referenced rails.

Branch current is positive into the output; input bias currents are not modeled.
The dominant pole uses backward Euler in transient, including slew limiting.
The Newton Jacobian is assembled sparsely and solved with SuperLU.
"""
import numpy as np
import scipy.sparse as sp

from .matrix import solve_linear
from .mna import _idx


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


def solve(A, z, elements, node_index, *, omega=None, state=None, h=None, initial=None):
    devices = [e for e in elements if e.type == "opamp"]
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

    def system(x):
        rows = const_rows.copy()
        cols = const_cols.copy()
        data = const_data.copy()
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
        jac = sp.coo_matrix((data, (rows, cols)), shape=(size, size), dtype=A.dtype).tocsc()
        return jac, target

    def linear_solve(jac, target):
        return solve_linear(jac, target)

    x = np.zeros(size, dtype=A.dtype) if initial is None else np.asarray(initial, dtype=A.dtype).copy()
    if x.shape != (size,) or not np.all(np.isfinite(x)):
        raise ValueError("Invalid solver initial state")
    if not devices or omega is not None:
        return linear_solve(*system(x))
    for _ in range(100):
        jac, target = system(x)
        residual = jac @ x - target
        candidate = linear_solve(jac, target)
        # Check the actual piecewise system, not just its local linearization.
        candidate_jac, candidate_rhs = system(candidate)
        if np.linalg.norm(candidate_jac @ candidate - candidate_rhs, ord=np.inf) < 1e-9:
            return candidate
        delta = candidate - x
        norm = np.linalg.norm(residual, ord=np.inf) if size else 0
        # Damped Newton prevents alternating between opposite saturation rails.
        alpha = 1.0
        for _ in range(40):
            trial = x + alpha * delta
            trial_jac, trial_rhs = system(trial)
            trial_norm = np.linalg.norm(trial_jac @ trial - trial_rhs, ord=np.inf)
            if trial_norm < norm or trial_norm < 1e-9:
                x = trial
                break
            alpha *= 0.5
        else:
            raise ValueError("Opamp operating point did not converge; check feedback and rails")
    raise ValueError("Opamp operating point did not converge")


def output_current(x, elements, el):
    base = len(x) - sum(e.type == "opamp" for e in elements)
    return x[base + [e.id for e in elements if e.type == "opamp"].index(el.id)]
