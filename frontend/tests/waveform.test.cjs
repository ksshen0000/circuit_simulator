const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const ts = require('typescript');

require.extensions['.ts'] = (module, filename) => {
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  module._compile(output.outputText, filename);
};

const { lttb } = require('../src/utils/downsample.ts');
const { resultToCsv } = require('../src/utils/csv.ts');
const { buildSignal, signalValues } = require('../src/utils/signals.ts');
const { formatEngineering, nearestSample, sampleIndex } = require('../src/utils/display.ts');
const { computeNodes } = require('../src/utils/graphUtils.ts');
const { buildNetlist } = require('../src/utils/netlist.ts');
const { createElement } = require('../src/store/circuitStore.ts');

function transientResult() {
  return {
    mode: 'transient',
    xValues: [0, 1, 2],
    nodeVoltages: { N1: [0, 1, 2] },
    branchCurrents: { R1: [0, 0.001, 0.002] },
  };
}

function acResult() {
  return {
    mode: 'ac',
    xValues: [1, 10],
    nodeVoltages: { OUT: [1, 1] },
    nodeVoltagesMag: { OUT: [1, 0.1] },
    nodeVoltagesPhase: { OUT: [0, -45] },
    branchCurrents: { R1: [0.001, 0.0001] },
    branchCurrentsMag: { R1: [0.001, 0.0001] },
    branchCurrentsPhase: { R1: [0, -90] },
  };
}

test('LTTB keeps endpoints and requested size', () => {
  const data = Array.from({ length: 1000 }, (_, i) => ({ x: i, y: Math.sin(i / 30) }));
  const sampled = lttb(data, 100);
  assert.equal(sampled.length, 100);
  assert.deepEqual(sampled[0], data[0]);
  assert.deepEqual(sampled[sampled.length - 1], data[data.length - 1]);
  const originalMax = Math.max(...data.map((p) => p.y));
  const sampledMax = Math.max(...sampled.map((p) => p.y));
  assert.ok(sampledMax > originalMax * 0.9);
  assert.equal(lttb(data, 2000), data);
});

test('AC signal modes build magnitude, dB and phase data', () => {
  const result = acResult();
  assert.deepEqual(signalValues(result, 'V(OUT)', 'mag').values, [1, 0.1]);
  assert.equal(signalValues(result, 'V(OUT)', 'phase').unit, '°');
  assert.deepEqual(signalValues(result, 'V(OUT)', 'phase').values, [0, -45]);
  const db = buildSignal(result, 'V(OUT)', 'db');
  assert.equal(db.unit, 'dB');
  assert.ok(Math.abs(db.data[0].y) < 1e-9);
  assert.ok(db.data[1].y < 0);
  assert.deepEqual(signalValues(result, 'I(R1)', 'mag').values, [0.001, 0.0001]);
});

test('transient signals and CSV include every node and branch', () => {
  const result = transientResult();
  const signal = buildSignal(result, 'V(N1)', 'mag');
  assert.deepEqual(signal.data, [{ x: 0, y: 0 }, { x: 1, y: 1 }, { x: 2, y: 2 }]);
  const csv = resultToCsv(result);
  const lines = csv.trim().split('\n');
  assert.equal(lines[0], 'x,V(N1),I(R1)');
  assert.equal(lines[1], '0,0,0');
  assert.equal(lines[3], '2,2,0.002');
});

test('AC CSV includes magnitude and phase columns', () => {
  const lines = resultToCsv(acResult()).trim().split('\n');
  assert.equal(lines[0], 'x,V(OUT)_mag,V(OUT)_phase,I(R1)_mag,I(R1)_phase');
  // Magnitude must come from node_voltages_mag, not the real part.
  assert.equal(lines[1], '1,1,0,0.001,0');
  assert.equal(lines[2], '10,0.1,-45,0.0001,-90');
});

test('display helpers sample by mode and format engineering units', () => {
  const transient = transientResult();
  assert.equal(sampleIndex(transient, null), 2);
  assert.equal(sampleIndex(transient, 1), 1);
  const ac = acResult();
  assert.equal(sampleIndex(ac, null), 0);
  assert.equal(nearestSample([0, 10, 20], 11), 1);
  assert.equal(formatEngineering(0.001, 'A'), '1.00mA');
  assert.equal(formatEngineering(1e6, 'Hz'), '1.00MHz');
});

test('diode netlist carries the Shockley parameters', () => {
  const el = createElement('diode', 'D1', 'D1', { gx: 2, gy: 2 });
  el.nodeNames = ['A', 'K'];
  const request = buildNetlist({ D1: el }, computeNodes({ D1: el }, {}, null), { mode: 'dc' });
  const dto = request.elements[0];
  assert.equal(dto.type, 'diode');
  assert.equal(dto.node_a, 'A');
  assert.equal(dto.node_b, 'K');
  assert.equal(dto.diode_is, 1e-14);
  assert.equal(dto.diode_n, 1);
});

test('MOSFET netlist carries the gate node', () => {
  const el = createElement('mosfet', 'M1', 'M1', { gx: 5, gy: 5 });
  el.nodeNames = ['D', 'S', 'G'];
  const elements = { M1: el };
  const nodes = computeNodes(elements, {}, null);
  const request = buildNetlist(elements, nodes, { mode: 'dc' });
  const dto = request.elements[0];
  assert.equal(dto.type, 'mosfet');
  assert.equal(dto.node_a, 'D');
  assert.equal(dto.node_b, 'S');
  assert.equal(dto.node_g, 'G');
  assert.equal(dto.mos_type, 'nmos');
});
