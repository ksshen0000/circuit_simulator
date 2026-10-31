"""Independent analytical checks for larger circuits; also runnable with unittest."""
import unittest

import numpy as np

from app.models.netlist import ACSettings, SimulateRequest
from app.models.netlist import NetlistElement as E
from app.simulation.engine import run_simulation


def part(kind, name, a, b, value=0, **kw):
    return E(type=kind, id=name, node_a=a, node_b=b, value=value, **kw)


def run(elements, **settings):
    return run_simulation(SimulateRequest(elements=elements, settings=settings))


class ComplexCircuits(unittest.TestCase):
    def test_four_stage_buffered_lowpass(self):
        elements = [part('voltage_source', 'V', 'in', 'GND', ac_amplitude=1)]
        previous = 'in'
        for stage in range(4):
            filtered, output = f'f{stage}', f'o{stage}'
            elements.extend([
                part('resistor', f'R{stage}', previous, filtered, 1000),
                part('capacitor', f'C{stage}', filtered, 'GND', 1e-6),
                part('opamp', f'U{stage}', filtered, output, node_out=output,
                     input_resistance=1e15, output_resistance=1e-6),
            ])
            previous = output
        result = run(elements, mode='ac', f_start=1, f_stop=1e5, points_per_decade=20)
        w = 2 * np.pi * np.array(result.x_values)
        gain = 1e5 / (1 + 1j * w * 1e5 / (2 * np.pi * 1e6))
        expected = ((gain / (1 + gain)) / (1 + 1j * w * .001)) ** 4
        actual = np.array(result.node_voltages_mag['o3']) * np.exp(1j * np.radians(result.node_voltages_phase['o3']))
        np.testing.assert_allclose(actual, expected, rtol=1e-7, atol=1e-12)

    def test_capacitive_load_feedback(self):
        elements = [part('voltage_source', 'V', 'in', 'GND', ac_amplitude=1),
                    part('opamp', 'U', 'in', 'out', node_out='out', input_resistance=1e15),
                    part('capacitor', 'C', 'out', 'GND', 1e-6),
                    part('resistor', 'R', 'out', 'GND', 10000)]
        result = run(elements, mode='ac', f_start=10, f_stop=1e6, points_per_decade=30)
        w = 2*np.pi*np.array(result.x_values)
        gain = 1e5/(1+1j*w*1e5/(2*np.pi*1e6))
        expected = gain/(1+gain+75*(1/10000+1j*w*1e-6))
        actual = np.array(result.node_voltages_mag['out'])*np.exp(1j*np.radians(result.node_voltages_phase['out']))
        np.testing.assert_allclose(actual, expected, rtol=1e-9)

    def test_underdamped_rlc_step_and_refinement(self):
        elements = [part('voltage_source', 'V', 'in', 'GND', 1, source_waveform='step'),
                    part('resistor', 'R', 'in', 'mid', 10),
                    part('inductor', 'L', 'mid', 'out', .01),
                    part('capacitor', 'C', 'out', 'GND', 1e-6)]
        errors = []
        for step in (2e-6, 1e-6):
            result = run(elements, mode='transient', t_step=step, t_stop=.003)
            t = np.array(result.x_values)
            alpha = 10/(2*.01)
            wd = np.sqrt(1/(.01*1e-6)-alpha**2)
            expected = 1-np.exp(-alpha*t)*(np.cos(wd*t)+alpha/wd*np.sin(wd*t))
            errors.append(np.max(np.abs(np.array(result.node_voltages['out'])-expected)))
            np.testing.assert_allclose(result.branch_currents['L'], result.branch_currents['C'], atol=1e-11)
        self.assertLess(errors[1], .5*errors[0]+1e-12)
        self.assertLess(errors[1], .005)

    def test_cascaded_opamps_saturation_recovery(self):
        elements = [part('voltage_source', 'V', 'in', 'GND', 2,
                         source_waveform='sine', sine_frequency=1000, ac_amplitude=2)]
        previous = 'in'
        for stage in range(3):
            output, fb = f'o{stage}', f'fb{stage}'
            elements.extend([
                part('opamp', f'U{stage}', previous, fb, node_out=output,
                     output_min=-10, output_max=10, slew_rate=2e5),
                part('resistor', f'Rf{stage}', output, fb, 2000),
                part('resistor', f'Rg{stage}', fb, 'GND', 1000),
                part('capacitor', f'C{stage}', output, 'GND', 1e-9),
            ])
            previous = output
        result = run(elements, mode='transient', t_step=2e-6, t_stop=.003)
        for stage in range(3):
            voltage = np.array(result.node_voltages[f'o{stage}'])
            current = np.array(result.branch_currents[f'U{stage}'])
            internal = voltage - 75 * current
            self.assertTrue(np.all(np.isfinite(internal)))
            self.assertLessEqual(np.max(np.abs(internal)), 10 + 1e-8)
            self.assertLessEqual(np.max(np.abs(np.diff(internal))/np.diff(result.x_values)), 2e5 + 1e-3)
        output = np.array(result.node_voltages['o2'])
        self.assertGreater(output.max(), 9)
        self.assertLess(output.min(), -9)
        # Both polarities continue to recover on the third period.
        self.assertGreater(output[-500:].max(), 9)
        self.assertLess(output[-500:].min(), -9)

    def test_adaptive_transient_uses_fewer_points_for_looser_tolerance(self):
        elements = [part('voltage_source', 'V', 'in', 'GND', 1, source_waveform='step'),
                    part('resistor', 'R', 'in', 'mid', 10),
                    part('inductor', 'L', 'mid', 'out', .01),
                    part('capacitor', 'C', 'out', 'GND', 1e-6)]
        loose = run(elements, mode='transient', t_step=1e-3, t_stop=.02, reltol=1e-2)
        tight = run(elements, mode='transient', t_step=1e-3, t_stop=.02, reltol=1e-6)
        # Looser tolerance accepts larger steps, so it needs fewer time points.
        self.assertLess(len(loose.x_values), len(tight.x_values))
        # Both settle near the 1 V final value.
        self.assertAlmostEqual(loose.node_voltages['out'][-1], 1.0, delta=0.05)
        self.assertAlmostEqual(tight.node_voltages['out'][-1], 1.0, delta=0.02)

    def test_short_log_sweep_keeps_both_endpoints(self):
        elements = [part('voltage_source','V','in','GND',1), part('resistor','R','in','GND',1000)]
        result = run(elements, mode='ac', f_start=100, f_stop=101, points_per_decade=20)
        self.assertEqual(result.x_values[0],100)
        self.assertEqual(result.x_values[-1],101)
        self.assertGreaterEqual(len(result.x_values),2)

    def test_reject_excessive_ac_grid(self):
        with self.assertRaises(ValueError):
            ACSettings(mode='ac', f_start=1e-30, f_stop=1e30, points_per_decade=10000)

    def test_long_resistor_ladder(self):
        count = 80
        elements = [part('voltage_source','V','n0','GND',1)]
        elements += [part('resistor',f'R{i}',f'n{i}',f'n{i+1}' if i<count-1 else 'GND',1000) for i in range(count)]
        result = run(elements, mode='dc')
        for i in range(count):
            self.assertAlmostEqual(result.node_voltages[f'n{i}'][0],1-i/count,places=10)

    def test_large_resistor_ladder_sparse(self):
        """1000-node ladder exercises the sparse solver path (dense would be O(n^2))."""
        count = 1000
        elements = [part('voltage_source','V','n0','GND',1)]
        elements += [part('resistor',f'R{i}',f'n{i}',f'n{i+1}' if i<count-1 else 'GND',1000) for i in range(count)]
        result = run(elements, mode='dc')
        # Uniform ladder: node i is a 1 - i/count voltage divider.
        self.assertAlmostEqual(result.node_voltages['n0'][0], 1.0, places=9)
        self.assertAlmostEqual(result.node_voltages[f'n{count//2}'][0], 0.5, places=9)
        self.assertAlmostEqual(result.node_voltages[f'n{count-1}'][0], 1 / count, places=9)


if __name__ == '__main__':
    unittest.main()
