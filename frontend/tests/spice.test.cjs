const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const ts = require('typescript');
require.extensions['.ts'] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8').replace('import.meta.env.VITE_API_URL', 'undefined');
  module._compile(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
};
const { parseSpice, exportSpice } = require('../src/utils/spice.ts');
test('frontend delegates SPICE parsing and export to Python API', async () => {
  const original = global.fetch;
  const request = { elements: [{ id:'R1', type:'resistor', node_a:'IN', node_b:'GND', value:1000, source_waveform:'dc', ac_phase:0 }], settings:{mode:'dc'}, ground_node:'GND' };
  try {
    global.fetch = async (url, options) => {
      assert.ok(url.endsWith('/spice/parse'));
      assert.equal(JSON.parse(options.body).text, 'example');
      return {ok:true,json:async()=>({title:'Test',request})};
    };
    const canvas = await parseSpice('example');
    assert.deepEqual(canvas.elements.R1.nodeNames, ['IN','GND']);
    global.fetch = async (url) => { assert.ok(url.endsWith('/spice/export')); return {ok:true,json:async()=>({text:'* exported'})}; };
    assert.equal(await exportSpice(request), '* exported');
  } finally { global.fetch = original; }
});
