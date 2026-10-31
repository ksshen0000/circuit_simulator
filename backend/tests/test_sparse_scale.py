"""Public-request scaling check for the sparse DC solver."""
import unittest

from app.models.netlist import NetlistElement as E
from app.models.netlist import SimulateRequest
from app.simulation.engine import run_simulation


class SparseScale(unittest.TestCase):
    def test_5000_node_resistor_ladder(self):
        count = 5000
        elements = [E(id="V", type="voltage_source", node_a="n0", node_b="GND", value=1)]
        elements += [
            E(id=f"R{i}", type="resistor", node_a=f"n{i}",
              node_b=f"n{i + 1}" if i < count - 1 else "GND", value=1000)
            for i in range(count)
        ]
        request = SimulateRequest(elements=elements, settings={"mode": "dc"})
        result = run_simulation(request)
        self.assertEqual(len(result.node_voltages), count)
        self.assertAlmostEqual(result.node_voltages[f"n{count - 1}"][0], 1 / count, places=12)


if __name__ == "__main__":
    unittest.main()
