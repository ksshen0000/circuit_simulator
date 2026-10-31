"""DC source-stepping fallback and scaled MNA assembly."""
import unittest
from unittest.mock import patch

from app.models.netlist import NetlistElement as E
from app.simulation import dc_analysis
from app.simulation.engine import _build_node_index
from app.simulation.mna import build_mna_dc
from app.simulation.opamp import SolverOptions


class SourceStepping(unittest.TestCase):
    def setUp(self):
        self.elements = [
            E(id="V1", type="voltage_source", node_a="in", node_b="GND", value=1),
            E(id="R1", type="resistor", node_a="in", node_b="out", value=1000),
            E(id="R2", type="resistor", node_a="out", node_b="GND", value=1000),
        ]
        self.node_index = _build_node_index(self.elements, "GND")

    def test_scaled_mna_halves_sources(self):
        _a, z = build_mna_dc(self.elements, self.node_index, len(self.node_index), source_scale=0.5)
        # The voltage-source branch equation is stored in the last RHS entry.
        self.assertAlmostEqual(z[-1], 0.5)

    def test_fallback_ramps_sources_and_reuses_solution(self):
        real_solve = dc_analysis.solve
        scaled_rhs = []

        def fake_solve(a, z, *args, **kwargs):
            scaled_rhs.append(float(z[-1]))
            if len(scaled_rhs) == 1:
                raise ValueError("forced first failure")
            return real_solve(a, z, *args, **kwargs)

        options = SolverOptions(source_steps=5)
        with patch.object(dc_analysis, "solve", side_effect=fake_solve):
            voltages, currents = dc_analysis.dc_solve(
                self.elements, self.node_index, options=options,
            )
        self.assertEqual(len(scaled_rhs), 6)
        self.assertAlmostEqual(scaled_rhs[1], 0.2)
        self.assertAlmostEqual(scaled_rhs[-1], 1.0)
        self.assertAlmostEqual(voltages["out"], 0.5)
        self.assertAlmostEqual(currents["V1"], -0.0005)


if __name__ == "__main__":
    unittest.main()
