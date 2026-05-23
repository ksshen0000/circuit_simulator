from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal, Optional, Annotated, Union


class NetlistElement(BaseModel):
    id: str
    type: Literal[
        "resistor", "capacitor", "inductor",
        "voltage_source", "current_source", "ground",
    ]
    node_a: str
    node_b: str
    value: float = 0.0
    ac_amplitude: Optional[float] = None
    ac_phase: float = 0.0
    source_waveform: Literal["dc", "sine", "pulse", "step"] = "dc"
    sine_frequency: Optional[float] = None
    pulse_period: Optional[float] = None
    pulse_width: Optional[float] = None


class DCSettings(BaseModel):
    mode: Literal["dc"]


class ACSettings(BaseModel):
    mode: Literal["ac"]
    f_start: float = 1.0
    f_stop: float = 1e6
    points_per_decade: int = 20
    sweep_type: Literal["log", "linear"] = "log"


class TransientSettings(BaseModel):
    mode: Literal["transient"]
    t_stop: float
    t_step: float
    t_start: float = 0.0
    method: Literal["euler", "trapezoidal"] = "trapezoidal"


SimSettings = Annotated[
    Union[DCSettings, ACSettings, TransientSettings],
    Field(discriminator="mode"),
]


class SimulateRequest(BaseModel):
    elements: list[NetlistElement]
    ground_node: str = "GND"
    settings: SimSettings
