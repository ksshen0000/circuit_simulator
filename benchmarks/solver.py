"""Run from repository root with backend/.venv/bin/python benchmarks/solver.py.

Benchmarks the sparse MNA solver on a resistor ladder. Bump LADDER_SECTIONS to
measure scaling; the solver uses SuperLU (sparse), so memory stays O(n).
"""
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.models.netlist import ACSettings, NetlistElement, SimulateRequest
from app.simulation.engine import run_simulation

LADDER_SECTIONS = 1000


def build_request(count: int) -> SimulateRequest:
    elements = [NetlistElement(id='V', type='voltage_source', node_a='n0', node_b='GND', value=1, ac_amplitude=1)]
    elements += [
        NetlistElement(id=f'R{i}', type='resistor', node_a=f'n{i}',
                       node_b=f'n{i + 1}' if i < count - 1 else 'GND', value=1000)
        for i in range(count)
    ]
    return SimulateRequest(elements=elements, settings=ACSettings(mode='ac', f_start=1, f_stop=1e6, points_per_decade=40))


request = build_request(LADDER_SECTIONS)
run_simulation(request)  # warm up

times = []
for _ in range(5):
    start = perf_counter()
    result = run_simulation(request)
    times.append(perf_counter() - start)

print(f'{LADDER_SECTIONS} resistors, {len(result.x_values)} AC points; '
      f'median {sorted(times)[2]:.6f} s')
