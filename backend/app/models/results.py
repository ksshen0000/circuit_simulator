from __future__ import annotations

from pydantic import BaseModel


class SimulationResult(BaseModel):
    mode: str
    x_values: list[float]
    node_voltages: dict[str, list[float]]
    node_voltages_mag: dict[str, list[float]] | None = None
    node_voltages_phase: dict[str, list[float]] | None = None
    branch_currents: dict[str, list[float]]
    branch_currents_mag: dict[str, list[float]] | None = None
    branch_currents_phase: dict[str, list[float]] | None = None
    error: str | None = None
