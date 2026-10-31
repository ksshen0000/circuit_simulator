from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GridPoint(BaseModel):
    gx: int
    gy: int


class CanvasElement(BaseModel):
    """Validated canvas element as produced by the frontend editor."""

    id: str
    type: str
    position: GridPoint | None = None
    rotation: int | None = None
    terminalA: GridPoint | None = None
    terminalB: GridPoint | None = None
    terminalOut: GridPoint | None = None
    nodeNames: list[str] | None = None
    openLoopGain: float | None = None
    gainBandwidth: float | None = None
    inputResistance: float | None = None
    outputResistance: float | None = None
    outputMin: float | None = None
    outputMax: float | None = None
    slewRate: float | None = None
    inputOffset: float | None = None
    value: float
    label: str
    sourceWaveform: str = "dc"
    acAmplitude: float | None = None
    acPhase: float = 0.0
    sineFrequency: float | None = None
    sineAmplitude: float | None = None
    sinePhase: float | None = None
    sineOffset: float | None = None
    pulseLow: float | None = None
    pulseDelay: float | None = None
    pulseRise: float | None = None
    pulseFall: float | None = None
    pulsePeriod: float | None = None
    pulseWidth: float | None = None


class CanvasWire(BaseModel):
    id: str
    points: list[GridPoint]


class SaveCircuitRequest(BaseModel):
    name: str
    elements: dict[str, CanvasElement]
    wires: dict[str, CanvasWire]
    ground_element_id: str | None = None
    project_id: str | None = None


class CircuitSummary(BaseModel):
    id: str
    name: str
    project_id: str | None
    updated_at: str


class ProjectCreate(BaseModel):
    name: str


class ProjectSummary(BaseModel):
    id: str
    name: str
    circuit_count: int
    updated_at: str


class ProjectDetail(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    circuits: list[CircuitSummary]


class CircuitDetail(BaseModel):
    id: str
    name: str
    elements: dict[str, Any]
    wires: dict[str, Any]
    ground_element_id: str | None
    project_id: str | None = None
    created_at: str
    updated_at: str
