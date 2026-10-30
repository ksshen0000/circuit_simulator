#!/usr/bin/env node
// Compatibility entry point. All parsing and calculation are owned by Python.
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const simulate = args.includes('--simulate');
const result = spawnSync(path.join(root, 'backend/.venv/bin/python'),
  ['-m', 'app.cli', ...args.filter(x => x !== '--simulate').map(x => x.startsWith('-') ? x : path.resolve(x)), ...(simulate ? [] : ['--parse-only'])],
  { cwd: path.join(root, 'backend'), stdio: 'inherit' });
if (result.error) console.error('请先通过 uv 安装后端依赖：', result.error.message);
process.exit(result.status ?? 1);
