from __future__ import annotations
from fastapi import APIRouter, HTTPException
from ..models.netlist import SimulateRequest
from ..models.results import SimulationResult
from ..simulation.dc_analysis import dc_solve
from ..simulation.ac_analysis import ac_sweep
from ..simulation.transient import transient_sim

router = APIRouter()


def _build_node_index(elements: list, ground_node: str) -> dict[str, int]:
    nodes: set[str] = set()
    for el in elements:
        if el.node_a != ground_node:
            nodes.add(el.node_a)
        if el.node_b != ground_node:
            nodes.add(el.node_b)
    return {node: idx for idx, node in enumerate(sorted(nodes))}


@router.post("/simulate", response_model=SimulationResult)
async def simulate(req: SimulateRequest) -> SimulationResult:
    non_ground = [e for e in req.elements if e.type != "ground"]
    node_index = _build_node_index(non_ground, req.ground_node)

    mode = req.settings.mode

    try:
        if mode == "dc":
            node_v, branch_i = dc_solve(non_ground, node_index)
            return SimulationResult(
                mode="dc",
                x_values=[0.0],
                node_voltages={k: [v] for k, v in node_v.items()},
                branch_currents={k: [v] for k, v in branch_i.items()},
            )

        elif mode == "ac":
            freqs, nv_mag, nv_phase, bi_mag, bi_phase = ac_sweep(
                non_ground, node_index, req.settings
            )
            nv_real = {k: [m * __import__("math").cos(__import__("math").radians(p))
                           for m, p in zip(nv_mag[k], nv_phase[k])]
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
            times, nv, bi = transient_sim(non_ground, node_index, req.settings)
            return SimulationResult(
                mode="transient",
                x_values=times,
                node_voltages=nv,
                branch_currents=bi,
            )

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation error: {exc}")


@router.get("/health")
async def health():
    return {"status": "ok"}
