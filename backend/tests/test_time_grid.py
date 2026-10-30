import unittest

from app.models.netlist import NetlistElement as E
from app.models.netlist import TransientSettings
from app.simulation.time_grid import transient_grid


def pulse(name='V', **kw):
    return E(id=name,type='voltage_source',node_a='a',node_b='GND',value=1,source_waveform='pulse',**kw)


class TimeGrid(unittest.TestCase):
    def test_roundoff_duplicates_are_removed(self):
        grid,jumps=transient_grid([pulse(pulse_period=.1,pulse_width=.02)],
                                  TransientSettings(mode='transient',t_step=.01,t_stop=1))
        self.assertGreater(min(b-a for a,b in zip(grid,grid[1:], strict=False)),.009)
        self.assertEqual(grid[-1],1)
        self.assertTrue(set(jumps).issubset(grid))

    def test_coincident_sources_keep_both_left_values(self):
        elements=[pulse('V1',pulse_period=.1,pulse_width=.02),pulse('V2',pulse_period=.1,pulse_width=.02)]
        grid,jumps=transient_grid(elements,TransientSettings(mode='transient',t_step=.01,t_stop=1))
        self.assertTrue(all(set(values)=={'V1','V2'} for values in jumps.values()))

    def test_tiny_but_resolvable_pulse_remains(self):
        grid,_=transient_grid([pulse(pulse_period=1e-12,pulse_width=1e-15)],
                              TransientSettings(mode='transient',t_step=1e-12,t_stop=2e-12))
        self.assertIn(1e-15,grid)
        self.assertIn(5e-16,grid)

    def test_unrepresentable_step_rejected(self):
        with self.assertRaises(ValueError):
            TransientSettings(mode='transient',t_start=1e16,t_stop=1e16+10,t_step=.1)

if __name__ == '__main__':
    unittest.main()
