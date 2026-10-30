from __future__ import annotations
from pydantic import BaseModel, Field, model_validator, ConfigDict
from typing import Literal, Optional, Annotated, Union


class NetlistElement(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    id: str
    type: Literal[
        "resistor", "capacitor", "inductor",
        "voltage_source", "current_source", "ground", "opamp",
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

    node_out: Optional[str] = None
    open_loop_gain: float = Field(default=100000.0, gt=0)
    gain_bandwidth: float = Field(default=1e6, gt=0)
    input_resistance: float = Field(default=1e9, gt=0)
    output_resistance: float = Field(default=75.0, gt=0)
    output_min: float = -13.5
    output_max: float = 13.5
    slew_rate: float = Field(default=5e5, gt=0)  # V/s
    input_offset: float = 0.0

    @model_validator(mode="after")
    def validate_device(self):
        if self.type in ("resistor", "capacitor", "inductor") and self.value <= 0:
            raise ValueError("R, L and C values must be positive")
        if self.type == "opamp":
            if not self.node_out or self.node_out == "?":
                raise ValueError("Opamp requires an output node")
            if not self.output_min < self.output_max:
                raise ValueError("Output minimum must be below maximum")
        for name in ("sine_frequency", "pulse_period", "pulse_width"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.pulse_period and self.pulse_width and self.pulse_width > self.pulse_period:
            raise ValueError("Pulse width cannot exceed period")
        return self


class DCSettings(BaseModel):
    mode: Literal["dc"]


class ACSettings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    mode: Literal["ac"]
    f_start: float = Field(default=1.0, gt=0)
    f_stop: float = Field(default=1e6, gt=0)
    points_per_decade: int = Field(default=20, ge=2, le=10000)
    sweep_type: Literal["log", "linear"] = "log"

    @model_validator(mode="after")
    def validate_range(self):
        if self.f_stop < self.f_start:
            raise ValueError("Stop frequency must be at least start frequency")
        return self


class TransientSettings(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    mode: Literal["transient"]
    t_stop: float
    t_step: float = Field(gt=0)
    t_start: float = 0.0
    method: Literal["euler", "trapezoidal"] = "trapezoidal"

    @model_validator(mode="after")
    def validate_range(self):
        if self.t_stop <= self.t_start:
            raise ValueError("Stop time must be after start time")
        if (self.t_stop - self.t_start) / self.t_step > 200000:
            raise ValueError("At most 200000 transient steps are allowed")
        return self


SimSettings = Annotated[
    Union[DCSettings, ACSettings, TransientSettings],
    Field(discriminator="mode"),
]


class SimulateRequest(BaseModel):
    elements: list[NetlistElement]
    ground_node: str = "GND"
    settings: SimSettings
