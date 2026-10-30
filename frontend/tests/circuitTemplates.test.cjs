const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const ts = require('typescript');

// Load the actual pure TS modules without a browser or another test dependency.
require.extensions['.ts'] = (module, filename) => {
  const output = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  module._compile(output.outputText, filename);
};
const { CIRCUIT_TEMPLATES, createCircuitTemplate } = require('../src/data/circuitTemplates.ts');
const { computeNodes } = require('../src/utils/graphUtils.ts');
const { buildNetlist } = require('../src/utils/netlist.ts');
function netlist(id) {
  const data = createCircuitTemplate(id);
  const nodes = computeNodes(data.elements, data.wires, data.groundElementId);
  return buildNetlist(data.elements, nodes, { mode: 'dc' });
}
for (const { id } of CIRCUIT_TEMPLATES) {
  test(`${id}: fresh circuit and correct terminal connectivity`, () => {
    const first = createCircuitTemplate(id);
    const second = createCircuitTemplate(id);
    first.elements.U1.openLoopGain = 2;
    assert.equal(second.elements.U1.openLoopGain, 1e5);
    const request = netlist(id);
    const byId = Object.fromEntries(request.elements.map((el) => [el.id, el]));
    for (const el of request.elements) {
      assert.notEqual(el.node_a, '?');
      assert.notEqual(el.node_b, '?');
      if (el.type === 'ground') assert.equal(el.node_a, 'GND');
    }
    const op = byId.U1;
    assert.ok(op.node_out && op.node_out !== '?');
    assert.notEqual(op.node_a, op.node_b);
    assert.notEqual(op.node_out, 'GND');
    assert.equal(byId.V1.node_b, 'GND');
    assert.equal(byId.RL.node_a, op.node_out);
    assert.equal(byId.RL.node_b, 'GND');
    if (id === 'follower') {
      assert.equal(op.node_b, op.node_out);
      assert.equal(op.node_a, byId.V1.node_a);
    } else {
      assert.equal(byId.R1.node_a, op.node_b);
      assert.equal(byId.R1.node_b, op.node_out);
      if (id === 'noninverting') {
        assert.equal(op.node_a, byId.V1.node_a);
        assert.equal(byId.R2.node_a, op.node_b);
        assert.equal(byId.R2.node_b, 'GND');
      } else {
        assert.equal(op.node_a, 'GND');
        assert.equal(byId.R2.node_a, byId.V1.node_a);
        assert.equal(byId.R2.node_b, op.node_b);
      }
    }
  });
}
if (process.env.CIRCUIT_TEMPLATE_REQUESTS) {
  fs.writeFileSync(process.env.CIRCUIT_TEMPLATE_REQUESTS, JSON.stringify(
    CIRCUIT_TEMPLATES.map(({ id }) => ({ id, request: netlist(id) })), null, 2));
}
