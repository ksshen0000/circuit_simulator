"""Nonlinear device models shared by the solver and result post-processing."""
from __future__ import annotations

import math

# Thermal voltage at ~300 K.
VT = 25.85e-3

# Clamp the junction voltage to keep exp() finite and Newton well-behaved.
_MAX_EXP_ARG = 40.0

# A tiny drain-source conductance keeps an off MOSFET from making the matrix
# singular. It is far below any meaningful leakage current.
_MOS_GMIN = 1e-12


def diode_current(el, vd: float) -> float:
    """Shockley diode current (anode → cathode)."""
    vd_safe = min(vd, _MAX_EXP_ARG * el.diode_n * VT)
    return el.diode_is * (math.exp(vd_safe / (el.diode_n * VT)) - 1.0)


def diode_conductance(el, vd: float) -> float:
    """Small-signal conductance dI/dV at the given junction voltage."""
    vd_safe = min(vd, _MAX_EXP_ARG * el.diode_n * VT)
    return el.diode_is / (el.diode_n * VT) * math.exp(vd_safe / (el.diode_n * VT))


def mosfet_currents(el, vgs: float, vds: float) -> tuple[float, float, float]:
    """Level-1 (Shichman-Hodges) MOSFET drain current and derivatives.

    Returns ``(id, gm, gds)`` for the current flowing from drain to source.
    ``mos_kp`` is the effective beta (A/V²); body effect and reverse
    conduction are not modeled. PMOS uses the same equations after flipping
    the polarity of the terminal voltages.
    """
    polarity = 1.0 if el.mos_type == "nmos" else -1.0
    vgs_eff = polarity * vgs
    vds_eff = polarity * vds
    # Enhancement-mode Level 1: use the threshold magnitude. SPICE PMOS
    # models normally give VTO as a negative number, but accepting the
    # magnitude is friendlier and electrically equivalent here.
    vov = vgs_eff - abs(el.mos_vto)
    if vov <= 0.0 or vds_eff <= 0.0:
        return 0.0, 0.0, _MOS_GMIN
    kp, lam = el.mos_kp, el.mos_lambda
    if vds_eff < vov:
        # Triode / linear region.
        id_eff = kp * (vov * vds_eff - 0.5 * vds_eff * vds_eff) * (1.0 + lam * vds_eff)
        gm_eff = kp * vds_eff * (1.0 + lam * vds_eff)
        gds_eff = kp * (vov - vds_eff) * (1.0 + lam * vds_eff) + kp * (
            vov * vds_eff - 0.5 * vds_eff * vds_eff
        ) * lam
    else:
        # Saturation / active region.
        id_eff = 0.5 * kp * vov * vov * (1.0 + lam * vds_eff)
        gm_eff = kp * vov * (1.0 + lam * vds_eff)
        gds_eff = 0.5 * kp * vov * vov * lam
    return polarity * id_eff, gm_eff, max(gds_eff, _MOS_GMIN)


def mosfet_current(el, vgs: float, vds: float) -> float:
    return mosfet_currents(el, vgs, vds)[0]
