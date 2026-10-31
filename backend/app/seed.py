"""Seed a fresh database with classic example circuits under an "示例" project.

Canvas data mirrors the frontend editor schema (grid coordinates, rotations,
terminals and wires) so the seeded circuits load as editable schematics.
"""
from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _term_positions(center: tuple[int, int], rotation: int):
    cx, cy = center
    offsets = {
        0: ((-2, 0), (2, 0)),
        90: ((0, -2), (0, 2)),
        180: ((2, 0), (-2, 0)),
        270: ((0, 2), (0, -2)),
    }
    (ax, ay), (bx, by) = offsets[rotation]
    return {"gx": cx + ax, "gy": cy + ay}, {"gx": cx + bx, "gy": cy + by}


def _opamp_terminals(center: tuple[int, int], rotation: int):
    cx, cy = center
    angle = rotation * math.pi / 180

    def rot(x: int, y: int):
        return {
            "gx": cx + round(x * math.cos(angle) - y * math.sin(angle)),
            "gy": cy + round(x * math.sin(angle) + y * math.cos(angle)),
        }

    return rot(-2, -1), rot(-2, 1), rot(2, 0)


def _element(label, type_, gx, gy, value=0, rotation=0, **extra):
    position = {"gx": gx, "gy": gy}
    if type_ == "ground":
        term_a = term_b = position
        term_out = None
    elif type_ == "opamp":
        term_a, term_b, term_out = _opamp_terminals((gx, gy), rotation)
    else:
        term_a, term_b = _term_positions((gx, gy), rotation)
        term_out = None

    el = {
        "id": label,
        "type": type_,
        "label": label,
        "position": position,
        "rotation": rotation,
        "terminalA": term_a,
        "terminalB": term_b,
        "terminalOut": term_out,
        "value": value,
        "sourceWaveform": "dc",
        "acPhase": 0,
    }
    if type_ == "opamp":
        el.update(
            openLoopGain=1e5,
            gainBandwidth=1e6,
            inputResistance=1e9,
            outputResistance=75,
            outputMin=-13.5,
            outputMax=13.5,
            slewRate=5e5,
            inputOffset=0,
        )
    if type_ == "voltage_source":
        el["acAmplitude"] = 1
        el["sineFrequency"] = 1000
    el.update(extra)
    return el


def _wire(wires, key, *points):
    wires[key] = {"id": key, "points": [{"gx": x, "gy": y} for x, y in points]}


def _noninverting():
    elements, wires = {}, {}
    elements["V1"] = _element("V1", "voltage_source", 4, 6, 0.1, 90)
    elements["GND1"] = _element("GND1", "ground", 4, 9)
    _wire(wires, "W1", (4, 8), (4, 9))
    elements["U1"] = _element("U1", "opamp", 14, 5)
    elements["RL"] = _element("RL", "resistor", 26, 8, 10000, 90)
    elements["GND2"] = _element("GND2", "ground", 26, 12)
    _wire(wires, "W2", (16, 5), (26, 5), (26, 6))
    _wire(wires, "W3", (26, 10), (26, 12))
    elements["R1"] = _element("R1", "resistor", 17, 10, 9000)
    _wire(wires, "W4", (12, 6), (12, 10), (15, 10))
    _wire(wires, "W5", (19, 10), (22, 10), (22, 5))
    _wire(wires, "W6", (4, 4), (12, 4))
    elements["R2"] = _element("R2", "resistor", 12, 14, 1000, 90)
    elements["GND3"] = _element("GND3", "ground", 12, 17)
    _wire(wires, "W7", (12, 10), (12, 12))
    _wire(wires, "W8", (12, 16), (12, 17))
    return {"name": "同相放大器 ×10", "elements": elements, "wires": wires, "ground_element_id": "GND1"}


def _rc_lowpass():
    elements, wires = {}, {}
    elements["V1"] = _element("V1", "voltage_source", 2, 6, 1, 90)
    elements["GND1"] = _element("GND1", "ground", 2, 10)
    _wire(wires, "W1", (2, 8), (2, 10))
    elements["R1"] = _element("R1", "resistor", 8, 4, 1000)
    _wire(wires, "W2", (2, 4), (6, 4))
    elements["C1"] = _element("C1", "capacitor", 10, 8, 1e-6, 90)
    _wire(wires, "W3", (10, 4), (10, 6))
    elements["GND2"] = _element("GND2", "ground", 10, 12)
    _wire(wires, "W4", (10, 10), (10, 12))
    return {"name": "RC 低通滤波器", "elements": elements, "wires": wires, "ground_element_id": "GND1"}


def _rlc_step():
    elements, wires = {}, {}
    elements["V1"] = _element("V1", "voltage_source", 2, 6, 1, 90, sourceWaveform="step")
    elements["GND1"] = _element("GND1", "ground", 2, 10)
    _wire(wires, "W1", (2, 8), (2, 10))
    elements["R1"] = _element("R1", "resistor", 8, 4, 10)
    _wire(wires, "W2", (2, 4), (6, 4))
    elements["L1"] = _element("L1", "inductor", 14, 4, 0.01)
    _wire(wires, "W3", (10, 4), (12, 4))
    elements["C1"] = _element("C1", "capacitor", 16, 8, 1e-6, 90)
    _wire(wires, "W4", (16, 4), (16, 6))
    elements["GND2"] = _element("GND2", "ground", 16, 12)
    _wire(wires, "W5", (16, 10), (16, 12))
    return {"name": "RLC 阶跃响应", "elements": elements, "wires": wires, "ground_element_id": "GND1"}


_EXAMPLES = [_noninverting, _rc_lowpass, _rlc_step]


def seed_examples(conn) -> None:
    """Insert example circuits under an 示例 project if the database is empty."""
    existing = conn.execute("SELECT COUNT(*) FROM circuits").fetchone()[0]
    if existing:
        return
    now = _now()
    project_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO projects (id, name, created_at, updated_at) VALUES (?,?,?,?)",
        (project_id, "示例", now, now),
    )
    for build in _EXAMPLES:
        data = build()
        cid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO circuits (id, name, elements, wires, ground_element_id, project_id,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (cid, data["name"], json.dumps(data["elements"]), json.dumps(data["wires"]),
             data["ground_element_id"], project_id, now, now),
        )
