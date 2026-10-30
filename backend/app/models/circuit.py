from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SaveCircuitRequest(BaseModel):
    name: str
    elements: dict[str, Any]
    wires: dict[str, Any]
    ground_element_id: str | None = None


class CircuitSummary(BaseModel):
    id: str
    name: str
    updated_at: str


class CircuitDetail(BaseModel):
    id: str
    name: str
    elements: dict[str, Any]
    wires: dict[str, Any]
    ground_element_id: str | None
    created_at: str
    updated_at: str
