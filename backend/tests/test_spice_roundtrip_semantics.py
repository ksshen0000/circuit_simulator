"""Export must not silently merge distinct JSON nodes."""
import unittest

from app.models.netlist import SimulateRequest
from app.spice import export_spice, parse_spice


class ExportSemantics(unittest.TestCase):
    def request(self, a, b, ground='GND'):
        return SimulateRequest(elements=[dict(id='R1',type='resistor',node_a=a,node_b=b,value=1000),
                                        dict(id='R2',type='resistor',node_a=b,node_b=ground,value=1000)],
                               ground_node=ground,settings=dict(mode='dc'))

    def test_case_collision_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '节点'):
            export_spice(self.request('signal','SIGNAL'))

    def test_reserved_ground_alias_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '节点'):
            export_spice(self.request('0','signal',ground='earth'))

    def test_custom_reference_survives(self):
        parsed=parse_spice(export_spice(self.request('in','out',ground='earth')))
        self.assertEqual(parsed.request.elements[-1].node_b,'GND')
        self.assertEqual(parsed.request.elements[0].node_b,'OUT')

if __name__ == '__main__':
    unittest.main()
