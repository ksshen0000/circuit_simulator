"""
Backend simulation tests.

Covers:
  - Bug: ground not connected (? node) → singular matrix
  - Fix: ground correctly connected → DC works
  - Transient: sine source waveform shape
  - AC: purely resistive circuit frequency-independent response
"""
import pytest

from app.models.netlist import ACSettings, NetlistElement, TransientSettings
from app.routers.simulation import _build_node_index
from app.simulation.ac_analysis import ac_sweep
from app.simulation.dc_analysis import dc_solve
from app.simulation.transient import transient_sim

# ── helpers ──────────────────────────────────────────────────────────────────

def _r(id, na, nb, val=1000.0):
    return NetlistElement(id=id, type="resistor", node_a=na, node_b=nb, value=val)

def _v(id, na, nb, val=5.0, **kw):
    return NetlistElement(id=id, type="voltage_source", node_a=na, node_b=nb, value=val, **kw)


# ── 场景1：旧 ground 接线点错误 → ?节点 → singular matrix ───────────────────

class TestGroundNotConnected:
    """Reproduces the bug: ground element terminal at wrong position.

    The old frontend placed ground's terminal at (center.gx-2, center.gy) while
    the symbol's visual connection is at center. Wires drawn to the visual point
    don't match the stored terminal, so pointToNode() returns null and the
    serialised netlist contains '?' as a node name.
    """

    def _make_bad_netlist(self):
        # Simulate what the old frontend sent: V1.node_b='?' because ground
        # terminal was in the wrong grid cell.
        return [
            _v("V1", "N1", "?"),
            _r("R1", "N1", "?"),
        ]

    def test_bad_netlist_creates_question_mark_node(self):
        elems = self._make_bad_netlist()
        node_index = _build_node_index(elems, "GND")
        assert "?" in node_index, f"Expected '?' in node_index, got {node_index}"

    def test_question_mark_node_causes_singular_matrix(self):
        elems = self._make_bad_netlist()
        node_index = _build_node_index(elems, "GND")
        with pytest.raises(ValueError, match="(?i)singular"):
            dc_solve(elems, node_index)


# ── 场景2：修复后 ground 在正确位置 → DC 仿真正常 ────────────────────────────

class TestGroundCorrectlyConnected:
    """After fix: ground terminal is at element center.

    A wire from another element landing on that center point is recognised as
    connected to GND. No '?' nodes, matrix is well-conditioned.
    """

    def _make_good_netlist(self):
        return [
            _v("V1", "N1", "GND"),
            _r("R1", "N1", "GND"),
        ]

    def test_good_netlist_has_no_question_mark_node(self):
        elems = self._make_good_netlist()
        node_index = _build_node_index(elems, "GND")
        assert "?" not in node_index

    def test_dc_node_voltage(self):
        elems = self._make_good_netlist()
        node_index = _build_node_index(elems, "GND")
        nv, _ = dc_solve(elems, node_index)
        assert abs(nv["N1"] - 5.0) < 1e-9

    def test_dc_branch_current(self):
        elems = self._make_good_netlist()
        node_index = _build_node_index(elems, "GND")
        _, bi = dc_solve(elems, node_index)
        # R1 = 1 kΩ across 5 V → 5 mA
        assert abs(bi["R1"] - 0.005) < 1e-9


# ── 场景3：Sine 电压源 + 电阻，Transient ─────────────────────────────────────

class TestSineTransient:
    """V1 = 5 V sin(2π·100·t), R1 = 1 kΩ in parallel → V(N1) tracks V1 exactly."""

    F_HZ = 100.0
    AMP  = 5.0

    def _run(self):
        elems = [
            _v("V1", "N1", "GND", val=self.AMP,
               source_waveform="sine", ac_amplitude=self.AMP,
               sine_frequency=self.F_HZ),
            _r("R1", "N1", "GND"),
        ]
        ni = _build_node_index(elems, "GND")
        settings = TransientSettings(mode="transient", t_stop=0.03, t_step=1e-4)
        times, nv, bi = transient_sim(elems, ni, settings)
        return times, nv, bi

    def test_peak_voltage(self):
        _, nv, _ = self._run()
        assert abs(max(nv["N1"]) - self.AMP) < 0.05

    def test_trough_voltage(self):
        _, nv, _ = self._run()
        assert abs(min(nv["N1"]) + self.AMP) < 0.05

    def test_peak_current(self):
        _, _, bi = self._run()
        expected_peak = self.AMP / 1000.0  # Ohm's law
        assert abs(max(bi["R1"]) - expected_peak) < 5e-5

    def test_zero_crossing_count(self):
        """100 Hz × 0.03 s = 3 periods → ~6 zero crossings.

        Starts from IC=0 (sine at t=0 is 0), so the initial positive half-wave
        has no negative→positive crossing → typically 5 sign changes.
        Acceptable range: 4–8.
        """
        _, nv, _ = self._run()
        v = nv["N1"]
        crossings = sum(1 for i in range(1, len(v)) if v[i - 1] * v[i] < 0)
        assert 4 <= crossings <= 8, f"Expected 4–8 zero crossings, got {crossings}"


# ── 场景4：AC 仿真 — 纯阻性，幅值不随频率变化 ───────────────────────────────

class TestACResistive:
    """Purely resistive circuit: V(N1) magnitude = 1 V at all frequencies, phase = 0°."""

    def _run(self):
        elems = [
            _v("V1", "N1", "GND", val=1.0, ac_amplitude=1.0),
            _r("R1", "N1", "GND"),
        ]
        ni = _build_node_index(elems, "GND")
        settings = ACSettings(mode="ac", f_start=10, f_stop=100_000, points_per_decade=10)
        return ac_sweep(elems, ni, settings)

    def test_magnitude_frequency_independent(self):
        freqs, nv_mag, *_ = self._run()
        for f, mag in zip(freqs, nv_mag["N1"], strict=False):
            assert abs(mag - 1.0) < 1e-3, f"At {f:.0f} Hz: |V(N1)|={mag:.4f}, expected 1.0"

    def test_phase_zero(self):
        _, _, nv_phase, *_ = self._run()
        for phase in nv_phase["N1"]:
            assert abs(phase) < 0.01, f"Phase={phase:.3f}°, expected 0°"
