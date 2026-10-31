"""Analytical checks for linear controlled sources and the diode model."""
import math
import unittest

from app.models.netlist import NetlistElement as E
from app.models.netlist import SimulateRequest
from app.simulation.engine import run_simulation


def run(elements, **settings):
    return run_simulation(SimulateRequest(elements=elements, settings=settings))


class ControlledSources(unittest.TestCase):
    def test_vcvs_gain(self):
        elements = [
            E(id='V1', type='voltage_source', node_a='in', node_b='GND', value=1),
            E(id='E1', type='vcvs', node_a='out', node_b='GND', control_node_a='in', control_node_b='GND', value=2),
            E(id='R1', type='resistor', node_a='out', node_b='GND', value=1000),
        ]
        result = run(elements, mode='dc')
        self.assertAlmostEqual(result.node_voltages['out'][0], 2.0, places=9)

    def test_vccs_transconductance(self):
        elements = [
            E(id='V1', type='voltage_source', node_a='in', node_b='GND', value=1),
            E(id='G1', type='vccs', node_a='GND', node_b='out', control_node_a='in', control_node_b='GND', value=0.001),
            E(id='R1', type='resistor', node_a='out', node_b='GND', value=1000),
        ]
        result = run(elements, mode='dc')
        # gm*Vin = 1 mA injected into 'out'; through 1 kΩ this yields 1 V.
        self.assertAlmostEqual(result.node_voltages['out'][0], 1.0, places=9)

    def test_cccs_current_gain(self):
        elements = [
            E(id='V1', type='voltage_source', node_a='in', node_b='GND', value=1),
            E(id='R1', type='resistor', node_a='in', node_b='GND', value=1000),
            E(id='F1', type='cccs', node_a='out', node_b='GND', control_element='V1', value=2),
            E(id='R2', type='resistor', node_a='out', node_b='GND', value=100),
        ]
        result = run(elements, mode='dc')
        # I(V1) = -1 mA, so F1 injects 2 mA into 'out': V(out) = 2e-3 * 100 = 0.2 V.
        self.assertAlmostEqual(result.branch_currents['V1'][0], -0.001, places=9)
        self.assertAlmostEqual(result.node_voltages['out'][0], 0.2, places=9)

    def test_ccvs_transresistance(self):
        elements = [
            E(id='V1', type='voltage_source', node_a='in', node_b='GND', value=1),
            E(id='R1', type='resistor', node_a='in', node_b='GND', value=1000),
            E(id='H1', type='ccvs', node_a='out', node_b='GND', control_element='V1', value=500),
        ]
        result = run(elements, mode='dc')
        # V(out) = 500 * I(V1) = 500 * -1e-3 = -0.5 V.
        self.assertAlmostEqual(result.node_voltages['out'][0], -0.5, places=9)


class Diode(unittest.TestCase):
    def test_diode_forward_drop(self):
        elements = [
            E(id='V1', type='voltage_source', node_a='in', node_b='GND', value=1),
            E(id='D1', type='diode', node_a='in', node_b='out', diode_is=1e-14, diode_n=1),
            E(id='R1', type='resistor', node_a='out', node_b='GND', value=1000),
        ]
        result = run(elements, mode='dc')
        vd = result.node_voltages['in'][0] - result.node_voltages['out'][0]
        current = result.branch_currents['D1'][0]
        # Series current equals the resistor current V(out)/R.
        self.assertAlmostEqual(current, result.node_voltages['out'][0] / 1000, places=9)
        self.assertGreater(vd, 0.5)
        self.assertLess(vd, 0.8)
        self.assertAlmostEqual(vd, 0.02585 * math.log(current / 1e-14), delta=0.02)

    def test_diode_ac_small_signal(self):
        elements = [
            E(id='V1', type='voltage_source', node_a='in', node_b='GND', value=1, ac_amplitude=1),
            E(id='D1', type='diode', node_a='in', node_b='out', diode_is=1e-14, diode_n=1),
            E(id='R1', type='resistor', node_a='out', node_b='GND', value=1000),
        ]
        result = run(elements, mode='ac', f_start=1, f_stop=1, points_per_decade=2)
        # Small-signal gain into the resistive load is ~R/(R+1/gd) with gd=Id/Vt.
        dc = run(elements, mode='dc')
        vd = dc.node_voltages['in'][0] - dc.node_voltages['out'][0]
        gd = 1e-14 / 0.02585 * math.exp(vd / 0.02585)
        expected = 1000 / (1000 + 1 / gd)
        self.assertAlmostEqual(result.node_voltages_mag['out'][0], expected, delta=0.05)


if __name__ == '__main__':
    unittest.main()
