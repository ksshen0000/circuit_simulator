from pydantic import BaseModel, Field

from .netlist import SimulateRequest


class SpiceTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1_000_000)


class ParsedSpice(BaseModel):
    title: str
    request: SimulateRequest


class SpiceExportRequest(BaseModel):
    request: SimulateRequest
    title: str = "Circuit Simulator"


class SpiceExportResponse(BaseModel):
    text: str
