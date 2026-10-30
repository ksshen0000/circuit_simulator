"""Analytical regression tests for nonideal opamps and solver correctness."""
import asyncio
import math

import pytest
from pydantic import ValidationError

from app.models.netlist import ACSettings, SimulateRequest, TransientSettings
from app.models.netlist import NetlistElement as E
from app.routers.simulation import _build_node_index, simulate
from app.simulation.ac_analysis import ac_sweep
from app.simulation.dc_analysis import dc_solve
from app.simulation.transient import transient_sim


def device(kind, name, a, b, value=0, **kw):
    return E(type=kind, id=name, node_a=a, node_b=b, value=value, **kw)


def amplifier(value=0.1, **kw):
    return [device("voltage_source", "V1", "in", "GND", value),
            device("opamp", "U1", "in", "fb", node_out="out", **kw),
            device("resistor", "Rf", "out", "fb", 9000),
            device("resistor", "Rg", "fb", "GND", 1000),
            device("resistor", "RL", "out", "GND", 10000)]


def index(elements):
    return _build_node_index(elements, "GND")


def test_finite_gain_and_output_loading():
    elements = amplifier()
    v, i = dc_solve(elements, index(elements))
    gain = 1e5
    # beta=0.1, output sees 10k feedback chain || 10k load.
    expected = gain * 0.1 / (1 + 75 / 5000 + gain / 10)
    assert v["out"] == pytest.approx(expected, rel=2e-7)
    assert i["U1"] == pytest.approx(-v["out"] / 5000)


@pytest.mark.parametrize("value,rail", [(5, 13.5), (-5, -13.5)])
def test_output_saturation(value, rail):
    elements = amplifier(value)
    v, i = dc_solve(elements, index(elements))
    assert v["out"] == pytest.approx(rail / (1 + 75 / 5000))
    assert v["out"] - 75 * i["U1"] == pytest.approx(rail)


def test_voltage_follower_with_offset():
    elements = [device("voltage_source", "V", "in", "GND", 1),
                device("opamp", "U", "in", "out", node_out="out", input_offset=0.002)]
    v, _ = dc_solve(elements, index(elements))
    assert v["out"] == pytest.approx(1.002 * 1e5 / (1 + 1e5), rel=1e-8)


def test_inverting_amplifier():
    elements = [device("voltage_source", "V", "in", "GND", 0.1),
                device("resistor", "Ri", "in", "fb", 1000),
                device("resistor", "Rf", "out", "fb", 10000),
                device("opamp", "U", "GND", "fb", node_out="out")]
    v, _ = dc_solve(elements, index(elements))
    assert v["out"] == pytest.approx(-1, rel=0.001)


def test_ac_gain_bandwidth_and_phase():
    elements = amplifier(0)
    elements[0].ac_amplitude = 1
    settings = ACSettings(mode="ac", f_start=10, f_stop=1e6, points_per_decade=10)
    freqs, mag, phase, *_ = ac_sweep(elements, index(elements), settings)
    assert mag["out"][0] == pytest.approx(10, rel=0.001)
    corner = min(range(len(freqs)), key=lambda k: abs(freqs[k] - 1e5))
    assert mag["out"][corner] == pytest.approx(10 / math.sqrt(2), rel=0.02)
    assert phase["out"][corner] == pytest.approx(-45, abs=1)
    assert mag["out"][-1] < 1.1


def test_ac_saturated_bias_rejected():
    elements = amplifier(5)
    with pytest.raises(ValueError, match="saturated"):
        ac_sweep(elements, index(elements), ACSettings(mode="ac"))


def test_transient_slew_and_rails():
    elements = amplifier(5, slew_rate=1000)
    elements[0].source_waveform = "step"
    times, v, i = transient_sim(elements, index(elements),
        TransientSettings(mode="transient", t_step=1e-4, t_stop=0.02))
    internal = [out - 75 * current for out, current in zip(v["out"], i["U1"], strict=False)]
    assert internal[0] == pytest.approx(0)
    assert internal[1] == pytest.approx(0.1)
    assert max(abs(b - a) / (tb - ta) for a, b, ta, tb in zip(internal, internal[1:], times, times[1:], strict=False)) <= 1000.001
    assert max(internal) <= 13.5 + 1e-8
    assert internal[-1] == pytest.approx(13.5)
    assert all(len(values) == len(times) for values in [*v.values(), *i.values()])


@pytest.mark.parametrize("method", ["euler", "trapezoidal"])
def test_rc_step_matches_analytic_response(method):
    elements = [device("voltage_source", "V", "in", "GND", 1, source_waveform="step"),
                device("resistor", "R", "in", "out", 1000),
                device("capacitor", "C", "out", "GND", 1e-6)]
    times, v, _ = transient_sim(elements, index(elements),
        TransientSettings(mode="transient", t_step=1e-5, t_stop=0.001005, method=method))
    assert times[-1] == pytest.approx(0.001005)
    assert v["out"][0] == 0
    assert v["out"][-1] == pytest.approx(1 - math.exp(-times[-1] / 0.001), abs=0.004)


def test_ac_zero_amplitude_is_zero():
    elements = [device("voltage_source", "V", "in", "GND", 5, ac_amplitude=0),
                device("resistor", "R", "in", "GND", 1000)]
    _, mag, *_ = ac_sweep(elements, index(elements), ACSettings(mode="ac"))
    assert max(mag["in"]) == 0


def test_ac_singular_circuit_is_error():
    elements = [device("resistor", "R", "a", "b", 1000)]
    with pytest.raises(ValueError, match="Singular"):
        ac_sweep(elements, index(elements), ACSettings(mode="ac"))


@pytest.mark.parametrize("settings", [dict(t_step=0, t_stop=1), dict(t_step=1, t_stop=-1), dict(t_step=1e-12, t_stop=1)])
def test_invalid_time_settings(settings):
    with pytest.raises(ValidationError):
        TransientSettings(mode="transient", **settings)


def test_api_opamp_and_invalid_component():
    request = SimulateRequest(elements=amplifier(), settings={"mode": "dc"})
    result = asyncio.run(simulate(request))
    assert result.node_voltages["out"][0] == pytest.approx(1, rel=0.001)
    with pytest.raises(ValidationError):
        SimulateRequest(elements=[dict(id="R", type="resistor", node_a="a", node_b="GND", value=0)], settings={"mode": "dc"})



@pytest.mark.parametrize("mode", ["dc", "ac", "transient"])
def test_current_source_arrow_and_kcl(mode):
    elements = [device("current_source", "I", "a", "GND", 0.001),
                device("resistor", "R", "a", "GND", 1000)]
    if mode == "dc":
        v, i = dc_solve(elements, index(elements))
        assert v["a"] == pytest.approx(-1)
        assert i["I"] + i["R"] == pytest.approx(0)
    elif mode == "ac":
        _, mag, phase, *_ = ac_sweep(elements, index(elements), ACSettings(mode="ac"))
        assert mag["a"][0] == pytest.approx(1)
        assert abs(phase["a"][0]) == pytest.approx(180)
    else:
        _, v, i = transient_sim(elements, index(elements), TransientSettings(mode="transient", t_step=1e-4, t_stop=0.001))
        assert v["a"][-1] == pytest.approx(-1)
        assert i["I"][-1] + i["R"][-1] == pytest.approx(0)


@pytest.mark.parametrize("method", ["euler", "trapezoidal"])
def test_rl_step_matches_analytic_response(method):
    elements = [device("voltage_source", "V", "in", "GND", 1, source_waveform="step"),
                device("resistor", "R", "in", "out", 1000),
                device("inductor", "L", "out", "GND", 1)]
    times, _, i = transient_sim(elements, index(elements),
        TransientSettings(mode="transient", t_step=1e-5, t_stop=0.001, method=method))
    assert i["L"][0] == 0
    assert i["L"][-1] == pytest.approx((1 - math.exp(-times[-1] / 0.001)) / 1000, abs=4e-6)


def test_opamp_dominant_pole_step():
    elements = [device("voltage_source", "V", "in", "GND", 1, source_waveform="step"),
                device("opamp", "U", "in", "out", node_out="out", gain_bandwidth=1000, slew_rate=1e9)]
    times, v, _ = transient_sim(elements, index(elements),
        TransientSettings(mode="transient", t_step=1e-6, t_stop=0.001))
    k = 100
    expected = 1e5 / (1 + 1e5) * (1 - math.exp(-2 * math.pi * 1000 * (1 + 1 / 1e5) * times[k]))
    assert v["out"][k] == pytest.approx(expected, abs=0.002)
