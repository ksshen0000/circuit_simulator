"""Analytical checks for the Level-1 MOSFET model."""
import unittest

from app.models.netlist import NetlistElement as E
from app.models.netlist import SimulateRequest
from app.simulation.devices import mosfet_currents
from app.simulation.engine import run_simulation
from app.spice import export_spice, parse_spice


def run(elements, **settings):
    return run_simulation(SimulateRequest(elements=elements, settings=settings))


def nmos(**kw):
    values = dict(id="M1", type="mosfet", node_a="d", node_b="GND", node_g="g",
                  mos_type="nmos", mos_vto=1.0, mos_kp=1e-3, mos_lambda=0.01)
    values.update(kw)
    return E(**values)


def pmos(**kw):
    values = dict(id="M1", type="mosfet", node_a="d", node_b="vdd", node_g="g",
                  mos_type="pmos", mos_vto=-1.0, mos_kp=1e-3, mos_lambda=0.01)
    values.update(kw)
    return E(**values)


class LevelOneModel(unittest.TestCase):
    def test_square_law_regions(self):
        el = nmos()
        cutoff = mosfet_currents(el, vgs=0.5, vds=3.0)
        self.assertEqual(cutoff[0], 0.0)
        triode = mosfet_currents(el, vgs=2.0, vds=0.3)
        expected_triode = 1e-3 * (1.0 * 0.3 - 0.5 * 0.3 ** 2) * (1 + 0.01 * 0.3)
        self.assertAlmostEqual(triode[0], expected_triode, places=15)
        saturation = mosfet_currents(el, vgs=2.0, vds=3.0)
        expected_saturation = 0.5 * 1e-3 * (1.0 ** 2) * (1 + 0.01 * 3.0)
        self.assertAlmostEqual(saturation[0], expected_saturation, places=15)
        self.assertGreater(saturation[1], 0)
        self.assertGreater(saturation[2], 0)

    def test_pmos_polarity(self):
        el = pmos()
        current, gm, _ = mosfet_currents(el, vgs=-2.0, vds=-3.0)
        self.assertAlmostEqual(current, -0.5 * 1e-3 * (1 + 0.01 * 3.0), places=15)
        self.assertGreater(gm, 0)


class OperatingPoint(unittest.TestCase):
    def test_nmos_saturation_bias(self):
        elements = [
            E(id="VDD", type="voltage_source", node_a="vdd", node_b="GND", value=5),
            E(id="VG", type="voltage_source", node_a="g", node_b="GND", value=2),
            E(id="RD", type="resistor", node_a="vdd", node_b="d", value=1000),
            nmos(),
        ]
        result = run(elements, mode="dc")
        current = result.branch_currents["M1"][0]
        vds = result.node_voltages["d"][0]
        expected = 0.5 * 1e-3 * (1.0 ** 2) * (1 + 0.01 * vds)
        self.assertAlmostEqual(current, expected, places=12)
        self.assertAlmostEqual(current, (5.0 - vds) / 1000, places=12)
        self.assertAlmostEqual(vds, 4.4776, delta=0.01)

    def test_nmos_triode_bias(self):
        elements = [
            E(id="VD", type="voltage_source", node_a="d", node_b="GND", value=0.3),
            E(id="VG", type="voltage_source", node_a="g", node_b="GND", value=2),
            nmos(),
        ]
        result = run(elements, mode="dc")
        expected = 1e-3 * (0.3 - 0.5 * 0.3 ** 2) * (1 + 0.01 * 0.3)
        self.assertAlmostEqual(result.branch_currents["M1"][0], expected, places=12)

    def test_pmos_bias(self):
        elements = [
            E(id="VDD", type="voltage_source", node_a="vdd", node_b="GND", value=5),
            E(id="VG", type="voltage_source", node_a="g", node_b="GND", value=3),
            E(id="RD", type="resistor", node_a="d", node_b="GND", value=1000),
            pmos(),
        ]
        result = run(elements, mode="dc")
        current = result.branch_currents["M1"][0]
        self.assertLess(current, 0)
        self.assertAlmostEqual(result.node_voltages["d"][0], -current * 1000, delta=1e-9)
        self.assertAlmostEqual(result.node_voltages["d"][0], 0.5224, delta=0.01)


class SmallSignal(unittest.TestCase):
    def test_common_source_gain(self):
        elements = [
            E(id="VDD", type="voltage_source", node_a="vdd", node_b="GND", value=5, ac_amplitude=0),
            E(id="VG", type="voltage_source", node_a="g", node_b="GND", value=2, ac_amplitude=1),
            E(id="RD", type="resistor", node_a="vdd", node_b="d", value=1000),
            nmos(),
        ]
        result = run(elements, mode="ac", f_start=1, f_stop=1, points_per_decade=2)
        dc = run(elements, mode="dc")
        vds = dc.node_voltages["d"][0]
        gm = 1e-3 * (1.0) * (1 + 0.01 * vds)
        gds = 0.5 * 1e-3 * (1.0 ** 2) * 0.01
        expected = gm * (1000 * (1 / gds) / (1000 + 1 / gds))
        self.assertAlmostEqual(result.node_voltages_mag["d"][0], expected, delta=1e-3)
        self.assertAlmostEqual(abs(result.node_voltages_phase["d"][0]), 180, delta=0.1)

    def test_gate_capacitance_rolls_off(self):
        elements = [
            E(id="VDD", type="voltage_source", node_a="vdd", node_b="GND", value=5, ac_amplitude=0),
            E(id="RG", type="resistor", node_a="g", node_b="in", value=1000),
            E(id="VIN", type="voltage_source", node_a="in", node_b="GND", value=2, ac_amplitude=1),
            E(id="RD", type="resistor", node_a="vdd", node_b="d", value=1000),
            nmos(mos_cgs=1e-9, mos_cgd=0),
        ]
        low = run(elements, mode="ac", f_start=1, f_stop=1, points_per_decade=2)
        high = run(elements, mode="ac", f_start=1e6, f_stop=1e6, points_per_decade=2)
        self.assertGreater(low.node_voltages_mag["d"][0], high.node_voltages_mag["d"][0])


class Transient(unittest.TestCase):
    def test_pulse_switches_drain(self):
        elements = [
            E(id="VDD", type="voltage_source", node_a="vdd", node_b="GND", value=5),
            E(id="VG", type="voltage_source", node_a="g", node_b="GND", value=3,
              source_waveform="pulse", pulse_low=0, pulse_delay=0, pulse_rise=0,
              pulse_fall=0, pulse_width=0.5e-3, pulse_period=1e-3),
            E(id="RD", type="resistor", node_a="vdd", node_b="d", value=1000),
            nmos(mos_cgs=1e-12, mos_cgd=1e-13),
        ]
        result = run(elements, mode="transient", t_stop=1e-3, t_step=1e-5, method="trapezoidal")
        times = result.x_values
        values = result.node_voltages["d"]

        def at(time):
            index = min(range(len(times)), key=lambda i: abs(times[i] - time))
            return values[index]

        self.assertLess(at(0.25e-3), 3.5)     # gate high: transistor on
        self.assertGreater(at(0.75e-3), 4.5)  # gate low: transistor off


class TransientRegressions(unittest.TestCase):
    @staticmethod
    def at(result, time):
        index = min(range(len(result.x_values)), key=lambda i: abs(result.x_values[i] - time))
        return result.node_voltages["d"][index]

    def test_pmos_pulse_without_gate_caps(self):
        elements = [
            E(id="VDD", type="voltage_source", node_a="vdd", node_b="GND", value=5),
            E(id="VG", type="voltage_source", node_a="g", node_b="GND", value=3,
              source_waveform="pulse", pulse_low=5, pulse_delay=0,
              pulse_rise=1e-9, pulse_fall=1e-9, pulse_width=0.5e-3, pulse_period=1e-3),
            E(id="RD", type="resistor", node_a="d", node_b="GND", value=1000),
            pmos(),
        ]
        result = run(elements, mode="transient", t_stop=1e-3, t_step=1e-5, method="trapezoidal")
        self.assertLess(self.at(result, 0.25e-3), 1.0)
        self.assertLess(self.at(result, 0.75e-3), 0.1)

    def test_nmos_pulse_with_large_cgd(self):
        elements = [
            E(id="VDD", type="voltage_source", node_a="vdd", node_b="GND", value=5),
            E(id="VG", type="voltage_source", node_a="g", node_b="GND", value=2,
              source_waveform="pulse", pulse_low=0, pulse_delay=0,
              pulse_rise=1e-9, pulse_fall=1e-9, pulse_width=0.5e-3, pulse_period=1e-3),
            E(id="RD", type="resistor", node_a="vdd", node_b="d", value=1000),
            nmos(mos_cgs=1e-12, mos_cgd=1e-12),
        ]
        result = run(elements, mode="transient", t_stop=1e-3, t_step=1e-5, method="trapezoidal")
        self.assertLess(self.at(result, 0.25e-3), 5.0)
        self.assertGreater(self.at(result, 0.25e-3), 4.0)
        self.assertGreater(self.at(result, 0.75e-3), 4.9)


class Connectivity(unittest.TestCase):
    def test_floating_gate_is_rejected(self):
        elements = [
            E(id="VDD", type="voltage_source", node_a="vdd", node_b="GND", value=5),
            E(id="RD", type="resistor", node_a="vdd", node_b="d", value=1000),
            nmos(),
        ]
        with self.assertRaisesRegex(ValueError, "Floating node"):
            run(elements, mode="dc")


class SpiceCards(unittest.TestCase):
    def test_model_and_instance_override_roundtrip(self):
        text = """* mosfet
.param vto=1
.param beta=1m
.model NM NMOS (LEVEL=1 VTO={vto} KP={beta} LAMBDA=0.01 CGSO=1p CGDO=2p)
VDD vdd 0 DC 5
VG g 0 DC 2 AC 1
RD vdd d 1k
M1 d g 0 NM LAMBDA=0.02
.op
.end
"""
        parsed = parse_spice(text)
        mos = next(el for el in parsed.request.elements if el.type == "mosfet")
        self.assertEqual(mos.mos_type, "nmos")
        self.assertEqual(mos.mos_vto, 1)
        self.assertEqual(mos.mos_kp, 1e-3)
        self.assertEqual(mos.mos_lambda, 0.02)
        self.assertEqual(mos.mos_cgs, 1e-12)
        self.assertEqual(mos.mos_cgd, 2e-12)
        again = parse_spice(export_spice(parsed.request, "mosfet"))
        self.assertEqual(again.request.elements, parsed.request.elements)
        self.assertGreater(run_simulation(again.request).node_voltages["D"][0], 0)

    def test_pmos_model(self):
        text = """* pmos
.model PM PMOS (VTO=-1 KP=1m LAMBDA=0.01)
VDD vdd 0 DC 5
VG g 0 DC 3
RD d 0 1k
M1 d g vdd PM
.op
.end
"""
        parsed = parse_spice(text)
        mos = next(el for el in parsed.request.elements if el.type == "mosfet")
        self.assertEqual(mos.mos_type, "pmos")
        result = run_simulation(parsed.request)
        self.assertAlmostEqual(result.node_voltages["D"][0], 0.5224, delta=0.01)


if __name__ == "__main__":
    unittest.main()
