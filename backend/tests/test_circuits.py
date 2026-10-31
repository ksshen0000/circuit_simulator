"""Persistence validation and schema migration tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app import db as db_module
from app.db import get_conn, init_db
from app.models.circuit import SaveCircuitRequest


def valid_element(**overrides):
    el = {
        "id": "R1",
        "type": "resistor",
        "position": {"gx": 0, "gy": 0},
        "rotation": 0,
        "terminalA": {"gx": 0, "gy": 0},
        "terminalB": {"gx": 2, "gy": 0},
        "value": 1000,
        "label": "R1",
        "sourceWaveform": "dc",
        "acPhase": 0,
    }
    el.update(overrides)
    return el


class CircuitValidation(unittest.TestCase):
    def test_valid_payload(self):
        req = SaveCircuitRequest(name="c", elements={"R1": valid_element()}, wires={})
        self.assertEqual(req.elements["R1"].value, 1000)

    def test_rejects_non_object_element(self):
        with self.assertRaises(ValidationError):
            SaveCircuitRequest(name="c", elements={"R1": "not-an-object"}, wires={})

    def test_rejects_element_missing_value(self):
        el = valid_element()
        del el["value"]
        with self.assertRaises(ValidationError):
            SaveCircuitRequest(name="c", elements={"R1": el}, wires={})

    def test_rejects_wire_without_points(self):
        with self.assertRaises(ValidationError):
            SaveCircuitRequest(name="c", elements={}, wires={"w1": {"id": "w1"}})


class SchemaMigration(unittest.TestCase):
    def test_init_db_sets_version_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(db_module, "DB_PATH", str(Path(tmp) / "circuit.db")):
                init_db()
                with get_conn() as conn:
                    version = conn.execute("PRAGMA user_version").fetchone()[0]
                    self.assertEqual(version, 2)
                    projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
                    seeded = conn.execute("SELECT COUNT(*) FROM circuits").fetchone()[0]
                    self.assertEqual(projects, 1)
                    self.assertEqual(seeded, 3)  # classic example circuits
                    conn.execute(
                        "INSERT INTO circuits (id, name, elements, wires, ground_element_id,"
                        " created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                        ("1", "n", "{}", "{}", None, "t", "t"),
                    )
                # Re-running must not fail or duplicate the seeded examples.
                init_db()
                with get_conn() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM circuits").fetchone()[0], 4)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
