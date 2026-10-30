"""Three-terminal, single-pole behavioral opamp with ground-referenced rails.

Branch current is positive into the output; input bias currents are not modeled.
The dominant pole uses backward Euler in transient, including slew limiting.
"""
import numpy as np
from .mna import _idx, _stamp_conductance


def solve(A, z, elements, node_index, *, omega=None, state=None, h=None):
    devices = [e for e in elements if e.type == "opamp"]
    base = len(z)
    size = base + len(devices)
    matrix = np.zeros((size, size), dtype=A.dtype)
    matrix[:base, :base] = A
    rhs = np.zeros(size, dtype=z.dtype)
    rhs[:base] = z
    for k, el in enumerate(devices):
        a, b, out = (_idx(node, node_index) for node in (el.node_a, el.node_b, el.node_out))
        col = base + k
        _stamp_conductance(matrix, a, b, 1 / el.input_resistance)
        if out >= 0:
            matrix[out, col] += 1
            matrix[col, out] += 1
        matrix[col, col] = -el.output_resistance

    def system(x):
        jac = matrix.copy()
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
                    jac[col, a] -= gain
                if b >= 0:
                    jac[col, b] += gain
                target[col] = offset
        return jac, target

    x = np.zeros(size, dtype=A.dtype)
    for _ in range(100):
        jac, target = system(x)
        residual = jac @ x - target
        try:
            candidate = np.linalg.solve(jac, target)
        except np.linalg.LinAlgError as exc:
            raise ValueError("Singular circuit: check ground, floating nodes and conflicting ideal sources") from exc
        if not np.all(np.isfinite(candidate)):
            raise ValueError("Non-finite simulation result")
        delta = candidate - x
        norm = np.linalg.norm(residual, ord=np.inf) if size else 0
        if norm < 1e-9:
            return candidate
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
