import math
import unittest
from app.models.netlist import SimulateRequest
from app.simulation.engine import run_simulation


class PulseIntegration(unittest.TestCase):
    def test_narrow_pulse_is_not_skipped_or_integrated_before_start(self):
        request = SimulateRequest(elements=[
            dict(id='V',type='voltage_source',node_a='in',node_b='GND',value=1,
                 source_waveform='pulse',pulse_delay=.0012,pulse_width=.0001,pulse_period=.01),
            dict(id='R',type='resistor',node_a='in',node_b='out',value=1000),
            dict(id='C',type='capacitor',node_a='out',node_b='GND',value=1e-6),
        ],settings=dict(mode='transient',t_step=.001,t_stop=.003))
        result=run_simulation(request)
        peak=max(result.node_voltages['out'])
        self.assertAlmostEqual(peak,1-math.exp(-.0001/.001),delta=.003)
        for t,v in zip(result.x_values,result.node_voltages['out']):
            if t<=.0012:
                self.assertAlmostEqual(v,0,places=12)
        self.assertGreater(max(result.node_voltages['in']),.9)
        self.assertTrue(all(b>a for a,b in zip(result.x_values,result.x_values[1:])))

if __name__ == '__main__':
    unittest.main()
