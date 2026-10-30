"""Run from repository root with backend/.venv/bin/python benchmarks/solver.py."""
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.simulation.engine import run_simulation
from app.spice import parse_spice

text = '* 80-section resistor ladder\nV1 n0 0 DC 1 AC 1\n'
text += '\n'.join(f'R{i} n{i} '+(f'n{i+1}' if i<79 else '0')+' 1k' for i in range(80))
text += '\n.ac dec 40 1 1meg\n.end\n'
request = parse_spice(text).request
run_simulation(request)
times = []
for _ in range(5):
    start = perf_counter()
    result = run_simulation(request)
    times.append(perf_counter()-start)
print(f'80 resistors, {len(result.x_values)} AC points; median {sorted(times)[2]:.6f} s')
