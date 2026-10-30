import io
import json
from pathlib import Path
import pytest
from app.spice import parse_spice, export_spice, spice_number
from app.simulation.engine import run_simulation
from app.cli import main

EXAMPLE = Path(__file__).resolve().parents[2] / 'examples/noninverting.cir'

def test_roundtrip():
    parsed = parse_spice(EXAMPLE.read_text())
    rebuilt = parse_spice(export_spice(parsed.request, parsed.title))
    assert rebuilt == parsed
    assert run_simulation(parsed.request).node_voltages['OUT'][0] == pytest.approx(1, abs=.001)

@pytest.mark.parametrize('text', ['.include vendor.lib', 'R1 a 0 0', 'V1 a 0 SIN(0 1 1k)', 'R1 a 0 1k\nr1 a 0 2k'])
def test_invalid(text):
    with pytest.raises(ValueError, match='第'):
        parse_spice('* test\n' + text)

def test_suffixes():
    assert spice_number('1M') == .001
    assert spice_number('1meg') == 1e6

def test_cli(tmp_path):
    output = tmp_path / 'result.json'
    assert main([str(EXAMPLE), '-o', str(output)]) == 0
    assert json.loads(output.read_text())['node_voltages']['OUT'][0] == pytest.approx(1, abs=.001)
    assert main([str(EXAMPLE), '--format', 'csv', '-o', str(output)]) == 0
    assert 'V(OUT)_V' in output.read_text()

def test_routes():
    from app.models.spice import SpiceTextRequest, SpiceExportRequest
    from app.routers.simulation import parse_text, export_text, simulate_text
    body = SpiceTextRequest(text=EXAMPLE.read_text())
    parsed = parse_text(body)
    assert parse_spice(export_text(SpiceExportRequest(request=parsed.request)).text).request == parsed.request
    assert simulate_text(body).node_voltages['OUT'][0] == pytest.approx(1, abs=.001)
