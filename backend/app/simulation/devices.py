"""Nonlinear device models shared by the solver and result post-processing."""
from __future__ import annotations

import math

# Thermal voltage at ~300 K.
VT = 25.85e-3

# Clamp the junction voltage to keep exp() finite and Newton well-behaved.
_MAX_EXP_ARG = 40.0


def diode_current(el, vd: float) -> float:
    """Shockley diode current (anode → cathode)."""
    vd_safe = min(vd, _MAX_EXP_ARG * el.diode_n * VT)
    return el.diode_is * (math.exp(vd_safe / (el.diode_n * VT)) - 1.0)


def diode_conductance(el, vd: float) -> float:
    """Small-signal conductance dI/dV at the given junction voltage."""
    vd_safe = min(vd, _MAX_EXP_ARG * el.diode_n * VT)
    return el.diode_is / (el.diode_n * VT) * math.exp(vd_safe / (el.diode_n * VT))
