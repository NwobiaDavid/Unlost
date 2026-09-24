// Runs a command with the sidecar's virtualenv Python (cross-platform).
// `node scripts/py.mjs --setup` creates the venv and installs requirements.
import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

const root = join(import.meta.dirname, '..', 'sidecar')
const venvPython =
  process.platform === 'win32'
    ? join(root, '.venv', 'Scripts', 'python.exe')
    : join(root, '.venv', 'bin', 'python')

function run(cmd, args) {
  const r = spawnSync(cmd, args, { stdio: 'inherit' })
  if (r.status !== 0) process.exit(r.status ?? 1)
}

const args = process.argv.slice(2)
if (args[0] === '--setup') {
  if (!existsSync(venvPython)) run(process.platform === 'win32' ? 'python' : 'python3', ['-m', 'venv', join(root, '.venv')])
  run(venvPython, ['-m', 'pip', 'install', '-r', join(root, 'requirements.txt'), '-r', join(root, 'requirements-dev.txt')])
  console.log('\nOptional voice search:  node scripts/py.mjs -m pip install -r sidecar/requirements-voice.txt')
} else {
  run(venvPython, args)
}
