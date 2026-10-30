import unittest

from app.models.netlist import NetlistElement as E
from app.models.netlist import SimulateRequest
from app.simulation.dc_analysis import dc_solve
from app.simulation.engine import _build_node_index, run_simulation


class SourceSemantics(unittest.TestCase):
    def circuit(self, kind='voltage_source'):
        value = .2 if kind == 'voltage_source' else .0002
        amplitude = 2 if kind == 'voltage_source' else .002
        return [E(id='S',type=kind,node_a='in',node_b='GND',value=value,
                  source_waveform='sine',ac_amplitude=amplitude,ac_phase=90,sine_frequency=1000),
                E(id='R',type='resistor',node_a='in',node_b='GND',value=1000)]

    def test_dc_uses_declared_value_not_sine_phase(self):
        for kind, expected in [('voltage_source',.2), ('current_source',-.2)]:
            with self.subTest(kind=kind):
                circuit=self.circuit(kind)
                result=run_simulation(SimulateRequest(elements=circuit,settings={'mode':'dc'}))
                self.assertAlmostEqual(result.node_voltages['in'][0],expected)

    def test_explicit_time_still_initializes_waveform(self):
        circuit=self.circuit()
        voltage,_=dc_solve(circuit,_build_node_index(circuit,'GND'),t=0)
        self.assertAlmostEqual(voltage['in'],2)

    def test_ac_bias_does_not_depend_on_sine_phase(self):
        circuit=self.circuit()
        circuit += [E(id='U',type='opamp',node_a='in',node_b='fb',node_out='out'),
                    E(id='Rf',type='resistor',node_a='out',node_b='fb',value=9000),
                    E(id='Rg',type='resistor',node_a='fb',node_b='GND',value=1000)]
        result=run_simulation(SimulateRequest(elements=circuit,settings={'mode':'ac','f_start':1,'f_stop':10}))
        self.assertAlmostEqual(result.node_voltages_mag['out'][0],20,delta=.01)

if __name__ == '__main__':
    unittest.main()
