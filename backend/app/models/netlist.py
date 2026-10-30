from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    ac_amplitude: float | None = None
    ac_phase: float = 0.0
    source_waveform: Literal["dc", "sine", "pulse", "step"] = "dc"
    sine_frequency: float | None = None
    sine_amplitude: float | None = None
    sine_phase: float | None = None
    sine_offset: float = 0.0
    pulse_low: float = 0.0
    pulse_delay: float = Field(default=0.0, ge=0)
    pulse_rise: float = Field(default=0.0, ge=0)
    pulse_fall: float = Field(default=0.0, ge=0)
    pulse_period: float | None = None
    pulse_width: float | None = None

    node_out: str | None = None
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
        if self.source_waveform == "pulse":
            period = self.pulse_period or 1.0
            width = self.pulse_width if self.pulse_width is not None else period / 2
            if self.pulse_rise + width + self.pulse_fall > period:
                raise ValueError("Pulse rise + width + fall cannot exceed period")
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
        decades = math.log10(self.f_stop) - math.log10(self.f_start)
        if self.sweep_type == "log" and math.ceil(decades * self.points_per_decade) + 1 > 200000:
            raise ValueError("At most 200000 AC points are allowed")
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
        if self.t_start + self.t_step == self.t_start:
            raise ValueError("Time step is too small to represent at start time")
        if self.t_stop <= self.t_start:
            raise ValueError("Stop time must be after start time")
        if (self.t_stop - self.t_start) / self.t_step > 200000:
            raise ValueError("At most 200000 transient steps are allowed")
        return self


SimSettings = Annotated[
    DCSettings | ACSettings | TransientSettings,
    Field(discriminator="mode"),
]


class SimulateRequest(BaseModel):
    elements: list[NetlistElement]
    ground_node: str = "GND"
    settings: SimSettings
