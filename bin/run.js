#!/usr/bin/env node
const { execSync, spawn } = require('child_process');
const path = require('path');

function checkCommand(cmd) {
    try { execSync(`which ${cmd}`, { stdio: 'ignore' }); return true; }
    catch { return false; }
}

if (!checkCommand('python3') && !checkCommand('python')) {
    console.error('Python 3.11+ is required. Install from https://python.org');
    process.exit(1);
}
if (!checkCommand('uv') && !checkCommand('uvx')) {
    console.error('uv is required. Install: curl -LsSf https://astral.sh/uv/install.sh | sh');
    process.exit(1);
}

const args = process.argv.slice(2);
const child = spawn('uvx', ['clevertech-mcp-server', ...args], {
    stdio: 'inherit',
    env: process.env
});
child.on('exit', code => process.exit(code));
