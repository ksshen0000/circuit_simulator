"""Verify seeded example circuits are electrically correct.

Reimplements the frontend's grid union-find (computeNodes) minimally so we can
convert stored canvas data to a netlist and run the actual solver against it.
"""
import unittest

from app.models.netlist import NetlistElement, SimulateRequest, TransientSettings
from app.seed import _EXAMPLES, _opamp_terminals
from app.simulation.engine import run_simulation


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, key):
        self.parent.setdefault(key, key)
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != root:
            self.parent[key], key = root, self.parent[key]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _key(p):
    return f"{p['gx']},{p['gy']}"


def _terminals(el):
    if el["type"] == "ground":
        return [el["terminalA"]]
    if el["type"] == "opamp":
        return list(_opamp_terminals((el["position"]["gx"], el["position"]["gy"]), el["rotation"]))
    return [el["terminalA"], el["terminalB"]]


def canvas_to_netlist(data):
    uf = _UnionFind()
    for wire in data["wires"].values():
        points = wire["points"]
        for i in range(len(points) - 1):
            p1, p2 = points[i], points[i + 1]
            prev = None
            if p1["gx"] == p2["gx"]:
                for gy in range(min(p1["gy"], p2["gy"]), max(p1["gy"], p2["gy"]) + 1):
                    k = _key({"gx": p1["gx"], "gy": gy})
                    uf.find(k)
                    if prev is not None:
                        uf.union(prev, k)
                    prev = k
            else:
                for gx in range(min(p1["gx"], p2["gx"]), max(p1["gx"], p2["gx"]) + 1):
                    k = _key({"gx": gx, "gy": p1["gy"]})
                    uf.find(k)
                    if prev is not None:
                        uf.union(prev, k)
                    prev = k

    for el in data["elements"].values():
        for pin in _terminals(el):
            uf.find(_key(pin))

    ground_root = None
    for el in data["elements"].values():
        if el["type"] == "ground":
            r = uf.find(_key(el["terminalA"]))
            ground_root = r if ground_root is None else ground_root
            if ground_root != r:
                uf.union(ground_root, r)
    ground_root = uf.find(ground_root) if ground_root is not None else None

    node_ids = {}
    counter = 1
    roots = {}
    for k in list(uf.parent):
        roots.setdefault(uf.find(k), None)
    if ground_root is not None:
        node_ids[ground_root] = "GND"
    for root in roots:
        if root == ground_root:
            continue
        node_ids[root] = f"N{counter}"
        counter += 1

    def node_of(p):
        return node_ids.get(uf.find(_key(p)), "?")

    elements = []
    for el in data["elements"].values():
        terms = _terminals(el)
        dto = {
            "id": el["id"],
            "type": el["type"],
            "node_a": node_of(terms[0]),
            "node_b": "GND" if el["type"] == "ground" else node_of(terms[1]),
            "value": el.get("value", 0),
            "source_waveform": el.get("sourceWaveform", "dc"),
            "ac_amplitude": el.get("acAmplitude"),
            "ac_phase": el.get("acPhase", 0),
        }
        if el["type"] == "opamp":
            dto["node_out"] = node_of(terms[2])
            dto.update(
                open_loop_gain=el["openLoopGain"],
                gain_bandwidth=el["gainBandwidth"],
                input_resistance=el["inputResistance"],
                output_resistance=el["outputResistance"],
                output_min=el["outputMin"],
                output_max=el["outputMax"],
                slew_rate=el["slewRate"],
                input_offset=el["inputOffset"],
            )
        elements.append(NetlistElement(**dto))
    return elements


class SeedCircuits(unittest.TestCase):
    def test_noninverting_amplifier_dc(self):
        elements = canvas_to_netlist(_EXAMPLES[0]())
        op = next(e for e in elements if e.type == "opamp")
        result = run_simulation(SimulateRequest(elements=elements, settings={"mode": "dc"}))
        self.assertAlmostEqual(result.node_voltages[op.node_out][0], 1.0, delta=0.01)

    def test_rc_lowpass_dc(self):
        elements = canvas_to_netlist(_EXAMPLES[1]())
        cap = next(e for e in elements if e.type == "capacitor")
        result = run_simulation(SimulateRequest(elements=elements, settings={"mode": "dc"}))
        self.assertAlmostEqual(result.node_voltages[cap.node_a][0], 1.0, delta=1e-6)

    def test_rlc_step_rings_and_settles(self):
        elements = canvas_to_netlist(_EXAMPLES[2]())
        cap = next(e for e in elements if e.type == "capacitor")
        result = run_simulation(
            SimulateRequest(
                elements=elements,
                settings=TransientSettings(mode="transient", t_step=2e-6, t_stop=0.02),
            )
        )
        out = result.node_voltages[cap.node_a]
        self.assertGreater(max(out), 1.0)
        self.assertAlmostEqual(out[-1], 1.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
