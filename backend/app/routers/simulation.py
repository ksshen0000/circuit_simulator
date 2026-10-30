from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from ..models.netlist import SimulateRequest
from ..models.results import SimulationResult
from ..models.spice import ParsedSpice, SpiceExportRequest, SpiceExportResponse, SpiceTextRequest
from ..simulation.engine import _build_node_index, run_simulation  # noqa: F401  # _build_node_index re-exported for compatibility
from ..spice import export_spice, parse_spice

router = APIRouter()


@router.post("/simulate", response_model=SimulationResult)
async def simulate(req: SimulateRequest) -> SimulationResult:
    try:
        return await run_in_threadpool(run_simulation, req)
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
        return run_simulation(parse_spice(req.text).request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/health")
async def health():
    return {"status": "ok"}
