from __future__ import annotations
from pydantic import BaseModel
from typing import Optional


class SimulationResult(BaseModel):
    mode: str
    x_values: list[float]
    node_voltages: dict[str, list[float]]
    node_voltages_mag: Optional[dict[str, list[float]]] = None
    node_voltages_phase: Optional[dict[str, list[float]]] = None
    branch_currents: dict[str, list[float]]
    branch_currents_mag: Optional[dict[str, list[float]]] = None
    branch_currents_phase: Optional[dict[str, list[float]]] = None
    error: Optional[str] = None
