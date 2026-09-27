// Starts electron-vite with a clean environment. Some editors (e.g. VS Code's extension host)
// export ELECTRON_RUN_AS_NODE=1, which makes Electron behave like plain Node and fail with "bad option".
import { spawn } from 'node:child_process'

const env = { ...process.env }
delete env.ELECTRON_RUN_AS_NODE
const mode = process.argv[2] ?? 'dev' // dev | preview
const child = spawn('npx', ['electron-vite', mode], { stdio: 'inherit', env, shell: true })
child.on('exit', (code) => process.exit(code ?? 0))
