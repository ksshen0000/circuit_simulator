"""SPICE `.param` expressions, text waveforms and `.model` cards."""
import math
import unittest

from app.models.netlist import NetlistElement as E
from app.models.netlist import SimulateRequest
from app.simulation.engine import run_simulation
from app.spice import export_spice, parse_spice
from app.spice_expr import ParameterTable, evaluate, spice_number


class Expressions(unittest.TestCase):
    def test_number_suffixes_and_functions(self):
        self.assertEqual(spice_number("1M"), 0.001)
        self.assertEqual(spice_number("1meg"), 1e6)
        self.assertAlmostEqual(evaluate("2 * sqrt(4) + pow(2, 3)"), 12.0)
        self.assertAlmostEqual(evaluate("{1k / (2 * pi * 1u)}"), 1e3 / (2 * math.pi * 1e-6))
        self.assertAlmostEqual(evaluate("10^(-3)"), 1e-3)

    def test_parameters_are_lazy_and_detect_cycles(self):
        table = ParameterTable()
        table.define("a", "{2*b}")
        table.define("b", "3k")
        self.assertAlmostEqual(table.value("a"), 6000.0)
        cycle = ParameterTable()
        cycle.define("x", "{y}")
        cycle.define("y", "{x}")
        with self.assertRaisesRegex(ValueError, "循环引用"):
            cycle.value("x")

    def test_unknown_parameter_and_function(self):
        with self.assertRaisesRegex(ValueError, "未定义参数"):
            evaluate("{missing * 2}")
        with self.assertRaisesRegex(ValueError, "不支持的函数"):
            evaluate("nosuch(1)")


class TextWaveforms(unittest.TestCase):
    def test_sin_and_pulse_parse(self):
        text = """* sources
.param f=1k
V1 in 0 DC 1 AC 2 30 SIN(0.5 3 {f})
V2 p 0 DC 0 PULSE(-1 5 1m 2u 3u 0.4m 1m)
R1 in 0 1k
R2 p 0 1k
.op
.end
"""
        parsed = parse_spice(text)
        by_id = {el.id: el for el in parsed.request.elements}
        sine = by_id["V1"]
        self.assertEqual(sine.source_waveform, "sine")
        self.assertEqual(sine.dc_value, 1)
        self.assertEqual(sine.sine_offset, 0.5)
        self.assertEqual(sine.sine_amplitude, 3)
        self.assertEqual(sine.sine_frequency, 1000)
        self.assertEqual(sine.ac_amplitude, 2)
        self.assertEqual(sine.ac_phase, 30)
        pulse = by_id["V2"]
        self.assertEqual(pulse.source_waveform, "pulse")
        self.assertEqual(pulse.dc_value, 0)
        self.assertEqual(pulse.pulse_low, -1)
        self.assertEqual(pulse.value, 5)
        self.assertEqual(pulse.pulse_delay, 1e-3)
        self.assertEqual(pulse.pulse_rise, 2e-6)
        self.assertEqual(pulse.pulse_fall, 3e-6)
        self.assertEqual(pulse.pulse_width, 4e-4)
        self.assertEqual(pulse.pulse_period, 1e-3)

    def test_text_waveform_matches_json_path(self):
        text = """* rc pulse
V1 in 0 DC 0 PULSE(0 1 0.00001 0.000001 0.000001 0.0002 0.001)
R1 in out 1k
C1 out 0 0.0000001
.tran 0.000005 0.001
.end
"""
        parsed = parse_spice(text)
        reference = SimulateRequest(
            elements=[
                E(id="V1", type="voltage_source", node_a="IN", node_b="GND",
                  value=1, dc_value=0, source_waveform="pulse", pulse_low=0,
                  pulse_delay=10e-6, pulse_rise=1e-6, pulse_fall=1e-6,
                  pulse_width=200e-6, pulse_period=1e-3),
                E(id="R1", type="resistor", node_a="IN", node_b="OUT", value=1000),
                E(id="C1", type="capacitor", node_a="OUT", node_b="GND", value=0.1e-6),
            ],
            settings={"mode": "transient", "t_step": 5e-6, "t_stop": 1e-3, "method": "trapezoidal"},
        )
        a, b = run_simulation(parsed.request), run_simulation(reference)
        self.assertEqual(a.x_values, b.x_values)
        for node in ("IN", "OUT"):
            for left, right in zip(a.node_voltages[node], b.node_voltages[node], strict=True):
                self.assertAlmostEqual(left, right, places=9)

    def test_pulse_before_dc_keeps_high_level(self):
        parsed = parse_spice("""* order
V1 a 0 PULSE(0 5 0 0 0 0.5m 1m) DC 1
R1 a 0 1k
.op
.end
""")
        source = parsed.request.elements[0]
        self.assertEqual(source.value, 5)
        self.assertEqual(source.dc_value, 1)

    def test_waveform_roundtrip(self):
        text = """* roundtrip
V1 in 0 DC 0 AC 1 0 SIN(0.2 2 1k 1u 0.5 30)
V2 p 0 DC 0 PULSE(-1 5 1m 2u 3u 0.4m 1m)
R1 in out 1k
R2 p out 1k
.op
.end
"""
        parsed = parse_spice(text)
        again = parse_spice(export_spice(parsed.request, parsed.title))
        self.assertEqual(again.request.elements, parsed.request.elements)

    def test_unsupported_waveforms_rejected(self):
        for waveform in ("EXP(0 1 1u 1u 2u 3u)", "PWL(0 0 1u 1)"):
            with self.subTest(waveform=waveform), self.assertRaisesRegex(ValueError, "第"):
                parse_spice(f"* test\nV1 a 0 {waveform}\nR1 a 0 1k\n.op\n.end\n")


class ParameterCards(unittest.TestCase):
    def test_parameter_names_are_case_insensitive(self):
        text = """* params
.param R=1k
V1 in 0 DC 1
R1 in 0 {r}
.op
.end
"""
        self.assertEqual(parse_spice(text).request.elements[1].value, 1000)

    def test_forward_reference_in_element_and_analysis(self):
        text = """* params
.param r={2*k}
.param k=500
V1 in 0 DC 1
R1 in 0 {r}
.ac dec 2 1 {r}
.end
"""
        parsed = parse_spice(text)
        self.assertEqual(parsed.request.elements[1].value, 1000)
        self.assertEqual(parsed.request.settings.f_stop, 1000)

    def test_unknown_parameter_reports_line(self):
        text = "* test\n.param r={nope*2}\nV1 a 0 1\nR1 a 0 {r}\n.op\n.end\n"
        with self.assertRaisesRegex(ValueError, "第 4 行"):
            parse_spice(text)

    def test_unbraced_function_and_braced_spaces(self):
        text = """* params
.param a=max(1, 2, 3)
.param b={2 * 3}
V1 x 0 1
R1 x 0 {a}
R2 x 0 {b}
.op
.end
"""
        parsed = parse_spice(text)
        self.assertEqual(parsed.request.elements[1].value, 3)
        self.assertEqual(parsed.request.elements[2].value, 6)

    def test_unknown_unit_rejected(self):
        with self.assertRaisesRegex(ValueError, "无效数值单位"):
            parse_spice("* t\n.param r=1foo\nV1 a 0 1\nR1 a 0 {r}\n.op\n.end\n")

    def test_deep_parameter_chain_has_clear_error(self):
        count = 100
        lines = ["* chain"] + [f".param p{i}={{p{i + 1}+1}}" for i in range(count)]
        lines += [f".param p{count}=0", "V1 a 0 1", "R1 a 0 {p0}", ".op", ".end"]
        with self.assertRaisesRegex(ValueError, "依赖链过深"):
            parse_spice("\n".join(lines) + "\n")

    def test_param_syntax_errors(self):
        for line in (".param r 1k", ".param =1k", ".param r={1k"):
            with self.subTest(line=line), self.assertRaisesRegex(ValueError, "第 2 行"):
                parse_spice(f"* test\n{line}\nV1 a 0 1\nR1 a 0 1k\n.op\n.end\n")


class OptionsCards(unittest.TestCase):
    def test_transient_tolerances_roundtrip(self):
        from app.models.netlist import TransientSettings
        request = SimulateRequest(
            elements=[
                E(id="V1", type="voltage_source", node_a="A", node_b="GND", value=1),
                E(id="R1", type="resistor", node_a="A", node_b="GND", value=1000),
            ],
            settings=TransientSettings(mode="transient", t_step=1e-6, t_stop=1e-3,
                                        reltol=1e-6, abstol=1e-12),
        )
        parsed = parse_spice(export_spice(request, "tol"))
        self.assertEqual(parsed.request.settings.reltol, 1e-6)
        self.assertEqual(parsed.request.settings.abstol, 1e-12)

    def test_options_before_or_after_tran(self):
        for body in (".tran 1u 1m\n.options RELTOL=1e-6 ABSTOL=1e-12",
                     ".options RELTOL=1e-6 ABSTOL=1e-12\n.tran 1u 1m"):
            with self.subTest(body=body):
                parsed = parse_spice("* t\nV1 a 0 1\nR1 a 0 1k\n" + body + "\n.end\n")
                self.assertEqual(parsed.request.settings.reltol, 1e-6)
                self.assertEqual(parsed.request.settings.abstol, 1e-12)

    def test_unknown_option_rejected(self):
        with self.assertRaisesRegex(ValueError, "第 3 行"):
            parse_spice("* t\nV1 a 0 1\n.options FOO=1\nR1 a 0 1k\n.tran 1u 1m\n.end\n")


class ModelCards(unittest.TestCase):
    def test_diode_model(self):
        text = """* diode model
.model DMOD D (IS=1e-12 N=1.5)
V1 in 0 DC 1
D1 in out DMOD
R1 out 0 1k
.op
.end
"""
        parsed = parse_spice(text)
        diode = next(el for el in parsed.request.elements if el.type == "diode")
        self.assertEqual(diode.diode_is, 1e-12)
        self.assertEqual(diode.diode_n, 1.5)
        result = run_simulation(parsed.request)
        self.assertGreater(result.node_voltages["OUT"][0], 0)

    def test_unknown_model_and_parameter(self):
        cases = (
            "M1 d g 0 NOPE\n",
            ".model N NMOS (VTO=1 BOGUS=2)\nM1 d g 0 N\n",
            ".model N NMOS (LEVEL=2 VTO=1)\nM1 d g 0 N\n",
        )
        for body in cases:
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, "第"):
                parse_spice("* test\nV1 d 0 1\nV2 g 0 1\n" + body + "R1 d 0 1k\n.op\n.end\n")


if __name__ == "__main__":
    unittest.main()
