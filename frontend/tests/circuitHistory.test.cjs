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

const { useCircuitStore } = require('../src/store/circuitStore.ts');

function reset() {
  const store = useCircuitStore.getState();
  store.loadFromData({ elements: {}, wires: {}, groundElementId: null });
}

test('add, undo, redo and delete are history-tracked', () => {
  reset();
  const id = useCircuitStore.getState().addElement('resistor', { gx: 2, gy: 3 });
  assert.equal(Object.keys(useCircuitStore.getState().elements).length, 1);
  assert.equal(useCircuitStore.getState().past.length, 1);

  useCircuitStore.getState().undo();
  assert.equal(Object.keys(useCircuitStore.getState().elements).length, 0);
  assert.equal(useCircuitStore.getState().future.length, 1);

  useCircuitStore.getState().redo();
  assert.equal(Object.keys(useCircuitStore.getState().elements).length, 1);
  assert.ok(useCircuitStore.getState().elements[id]);

  useCircuitStore.getState().deleteElement(id);
  assert.equal(Object.keys(useCircuitStore.getState().elements).length, 0);
  useCircuitStore.getState().undo();
  assert.ok(useCircuitStore.getState().elements[id]);
});

test('drag moves are coalesced into a single undo step', () => {
  reset();
  const id = useCircuitStore.getState().addElement('resistor', { gx: 2, gy: 3 });
  const historyBeforeDrag = useCircuitStore.getState().past.length;
  useCircuitStore.getState().moveElement(id, { gx: 3, gy: 3 });
  useCircuitStore.getState().moveElement(id, { gx: 4, gy: 3 });
  useCircuitStore.getState().moveElement(id, { gx: 5, gy: 3 });
  assert.equal(useCircuitStore.getState().past.length, historyBeforeDrag + 1);
  useCircuitStore.getState().undo();
  assert.deepEqual(useCircuitStore.getState().elements[id].position, { gx: 2, gy: 3 });
});

test('undo restores label counters and clearAll can be undone', () => {
  reset();
  useCircuitStore.getState().addElement('resistor', { gx: 0, gy: 0 });
  useCircuitStore.getState().addElement('resistor', { gx: 3, gy: 0 });
  assert.equal(useCircuitStore.getState().labelCounters.R, 2);
  useCircuitStore.getState().clearAll();
  assert.equal(Object.keys(useCircuitStore.getState().elements).length, 0);
  useCircuitStore.getState().undo();
  assert.equal(Object.keys(useCircuitStore.getState().elements).length, 2);
  assert.equal(useCircuitStore.getState().labelCounters.R, 2);
});

test('loading a saved circuit starts a fresh history', () => {
  reset();
  useCircuitStore.getState().addElement('resistor', { gx: 0, gy: 0 });
  useCircuitStore.getState().loadFromData({ elements: {}, wires: {}, groundElementId: null });
  assert.equal(useCircuitStore.getState().past.length, 0);
  assert.equal(useCircuitStore.getState().future.length, 0);
});

test('MOSFET gets three terminals and defaults', () => {
  reset();
  const id = useCircuitStore.getState().addElement('mosfet', { gx: 10, gy: 10 });
  const el = useCircuitStore.getState().elements[id];
  assert.equal(el.type, 'mosfet');
  assert.equal(el.label, 'M1');
  assert.equal(el.mosType, 'nmos');
  assert.notDeepEqual(el.terminalA, el.terminalB);
  assert.ok(el.terminalOut);
  assert.equal(useCircuitStore.getState().labelCounters.M, 1);
});
