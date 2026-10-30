import os
import threading

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..models.netlist import SimulateRequest
from ..models.results import SimulationResult
from ..models.spice import ParsedSpice, SpiceExportRequest, SpiceExportResponse, SpiceTextRequest
from ..simulation.engine import _build_node_index, run_simulation  # noqa: F401  # _build_node_index re-exported for compatibility
from ..spice import export_spice, parse_spice

router = APIRouter()

# Bound CPU-heavy simulations so a burst of requests cannot exhaust the process.
_SIM_CONCURRENCY = int(os.environ.get("SIM_CONCURRENCY", "2"))
_sim_slots = threading.Semaphore(_SIM_CONCURRENCY)


def _run_sim(req: SimulateRequest) -> SimulationResult:
    with _sim_slots:
        return run_simulation(req)


@router.post("/simulate", response_model=SimulationResult)
async def simulate(req: SimulateRequest) -> SimulationResult:
    try:
        return await run_in_threadpool(_run_sim, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/spice/parse", response_model=ParsedSpice)
def parse_text(req: SpiceTextRequest) -> ParsedSpice:
    try:
        return parse_spice(req.text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/spice/export", response_model=SpiceExportResponse)
def export_text(req: SpiceExportRequest) -> SpiceExportResponse:
    try:
        return SpiceExportResponse(text=export_spice(req.request, req.title))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/simulate/spice", response_model=SimulationResult)
def simulate_text(req: SpiceTextRequest) -> SimulationResult:
    try:
        return _run_sim(parse_spice(req.text).request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/health")
async def health():
    return {"status": "ok"}
