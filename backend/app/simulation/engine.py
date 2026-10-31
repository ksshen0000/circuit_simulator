"""Framework-independent simulation API, shared by HTTP and the local CLI."""
from __future__ import annotations

import math

from ..models.netlist import MAX_NODES, SimulateRequest
from ..models.results import SimulationResult
from .ac_analysis import ac_sweep
from .dc_analysis import dc_solve
from .transient import transient_sim


def _build_node_index(elements: list, ground_node: str) -> dict[str, int]:
    nodes: set[str] = set()
    for el in elements:
        for node in (el.node_a, el.node_b, el.control_node_a, el.control_node_b):
            if node is not None and node != ground_node:
                nodes.add(node)
        if el.type == "opamp" and el.node_out is not None and el.node_out != ground_node:
            nodes.add(el.node_out)
    return {node: idx for idx, node in enumerate(sorted(nodes))}


def run_simulation(req: SimulateRequest, options=None) -> SimulationResult:
    non_ground = [e for e in req.elements if e.type != "ground"]
    if len({e.id for e in non_ground}) != len(non_ground):
        raise ValueError("Component IDs must be unique")
    terminals = [
        t
        for e in non_ground
        for t in (e.node_a, e.node_b, e.node_out, e.control_node_a, e.control_node_b)
    ]
    if any(t is not None and "?" in t for t in terminals):
        raise ValueError("Unconnected component terminal")
    node_index = _build_node_index(non_ground, req.ground_node)
    if len(node_index) > MAX_NODES:
        raise ValueError(f"Circuit has {len(node_index)} nodes; at most {MAX_NODES} are supported")

    mode = req.settings.mode

    if mode == "dc":
        node_v, branch_i = dc_solve(non_ground, node_index, options=options)
        return SimulationResult(
            mode="dc",
            x_values=[0.0],
            node_voltages={k: [v] for k, v in node_v.items()},
            branch_currents={k: [v] for k, v in branch_i.items()},
        )

    elif mode == "ac":
        freqs, nv_mag, nv_phase, bi_mag, bi_phase = ac_sweep(
            non_ground, node_index, req.settings, options=options
        )
        nv_real = {k: [m * math.cos(math.radians(p))
                       for m, p in zip(nv_mag[k], nv_phase[k], strict=True)]
                   for k in nv_mag}
        return SimulationResult(
            mode="ac",
            x_values=freqs,
            node_voltages=nv_real,
            node_voltages_mag=nv_mag,
            node_voltages_phase=nv_phase,
            branch_currents={k: bi_mag[k] for k in bi_mag},
            branch_currents_mag=bi_mag,
            branch_currents_phase=bi_phase,
        )

    elif mode == "transient":
        times, nv, bi = transient_sim(non_ground, node_index, req.settings, options=options)
        return SimulationResult(
            mode="transient",
            x_values=times,
            node_voltages=nv,
            branch_currents=bi,
        )

