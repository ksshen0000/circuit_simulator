import unittest

from app.models.netlist import NetlistElement as E
from app.simulation.sources import evaluate_source


def source(**kw):
    return E(id='V',type='voltage_source',node_a='a',node_b='GND',**kw)


class Waveforms(unittest.TestCase):
    def test_sine_independent_of_ac(self):
        el=source(value=3,ac_amplitude=100,ac_phase=180,source_waveform='sine',
                  sine_amplitude=2,sine_phase=90,sine_offset=1,sine_frequency=100)
        self.assertEqual(evaluate_source(el,None),3)
        self.assertAlmostEqual(evaluate_source(el,0),3)
        self.assertAlmostEqual(evaluate_source(el,.005),-1)

    def test_pulse_edges_and_delay(self):
        el=source(value=5,source_waveform='pulse',pulse_low=-1,pulse_delay=1,
                  pulse_rise=2,pulse_width=3,pulse_fall=2,pulse_period=10)
        for t,expected in [(-1,-1),(0,-1),(1,-1),(2,2),(3,5),(5,5),(6,5),(7,2),(8,-1),(10,-1),(11,-1),(12,2)]:
            with self.subTest(t=t):
                self.assertAlmostEqual(evaluate_source(el,t),expected)

    def test_legacy_sine_fallback_and_zero_override(self):
        el=source(value=5,source_waveform='sine',ac_amplitude=2,ac_phase=90)
        self.assertAlmostEqual(evaluate_source(el,0),2)
        el.sine_amplitude=0
        self.assertEqual(evaluate_source(el,0),0)

    def test_invalid_pulse_timing(self):
        with self.assertRaises(ValueError):
            source(source_waveform='pulse',pulse_period=1,pulse_width=.8,pulse_rise=.2,pulse_fall=.2)

if __name__ == '__main__':
    unittest.main()
