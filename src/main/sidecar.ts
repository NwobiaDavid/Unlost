import { spawn, type ChildProcess } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { existsSync } from 'node:fs'
import { createServer } from 'node:net'
import { join } from 'node:path'
import { app } from 'electron'

export interface SidecarInfo {
  url: string
  token: string
}

type Listener = (state: 'starting' | 'ready' | 'crashed', detail?: string) => void

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const srv = createServer()
    srv.unref()
    srv.on('error', reject)
    srv.listen(0, '127.0.0.1', () => {
      const addr = srv.address()
      srv.close(() => (typeof addr === 'object' && addr ? resolve(addr.port) : reject(new Error('no port'))))
    })
  })
}

function command(port: number): { cmd: string; args: string[]; cwd: string } {
  if (app.isPackaged) {
    const dir = join(process.resourcesPath, 'sidecar')
    const exe = process.platform === 'win32' ? 'unlost-sidecar.exe' : 'unlost-sidecar'
    return { cmd: join(dir, exe), args: ['--port', String(port)], cwd: dir }
  }
  const root = join(app.getAppPath(), 'sidecar')
  const py =
    process.platform === 'win32' ? join(root, '.venv', 'Scripts', 'python.exe') : join(root, '.venv', 'bin', 'python')
  if (!existsSync(py)) throw new Error(`Python sidecar not set up. Run "npm run sidecar:setup" first (looked for ${py}).`)
  return { cmd: py, args: ['-m', 'unlost', '--port', String(port)], cwd: root }
}

export class Sidecar {
  info: SidecarInfo | null = null
  private proc: ChildProcess | null = null
  private restarts = 0
  private stopping = false
  private listeners: Listener[] = []
  private readyWaiters: Array<(info: SidecarInfo) => void> = []
  lastError = ''

  onState(fn: Listener): void {
    this.listeners.push(fn)
  }

  private emit(state: 'starting' | 'ready' | 'crashed', detail?: string): void {
    for (const fn of this.listeners) fn(state, detail)
  }

  ready(): Promise<SidecarInfo> {
    return this.info ? Promise.resolve(this.info) : new Promise((r) => this.readyWaiters.push(r))
  }

  async start(): Promise<void> {
    this.emit('starting')
    this.info = null
    const port = await freePort()
    const token = randomBytes(24).toString('base64url')
    let spec: ReturnType<typeof command>
    try {
      spec = command(port)
    } catch (e) {
      this.lastError = (e as Error).message
      this.emit('crashed', this.lastError)
      return
    }
    const proc = spawn(spec.cmd, spec.args, {
      cwd: spec.cwd,
      env: {
        ...process.env,
        UNLOST_TOKEN: token,
        UNLOST_DATA_DIR: join(app.getPath('userData'), 'data'),
        PYTHONUNBUFFERED: '1',
        PYTHONIOENCODING: 'utf-8',
        // The key is handed over explicitly after startup; never inherit a stray one from the shell.
        GROQ_API_KEY: ''
      },
      windowsHide: true
    })
    this.proc = proc
    let stderrTail = ''

    proc.stdout?.on('data', (buf: Buffer) => {
      if (!this.info && buf.toString().includes('UNLOST_READY')) {
        this.info = { url: `http://127.0.0.1:${port}`, token }
        this.restarts = 0
        this.emit('ready')
        for (const r of this.readyWaiters.splice(0)) r(this.info)
      }
    })
    proc.stderr?.on('data', (buf: Buffer) => {
      const s = buf.toString()
      stderrTail = (stderrTail + s).slice(-4000)
      if (!app.isPackaged) process.stderr.write(`[sidecar] ${s}`)
    })
    proc.on('exit', (code) => {
      if (this.proc !== proc) return
      this.proc = null
      this.info = null
      if (this.stopping) return
      this.lastError = `Search engine stopped (exit ${code}).\n${stderrTail.split('\n').slice(-8).join('\n')}`
      this.emit('crashed', this.lastError)
      if (this.restarts++ < 3) setTimeout(() => void this.start(), 1000 * this.restarts)
    })
  }

  async restart(): Promise<void> {
    this.restarts = 0
    if (this.proc) {
      const old = this.proc
      this.proc = null
      old.kill()
    }
    await this.start()
  }

  stop(): void {
    this.stopping = true
    this.proc?.kill()
  }

  async request(path: string, init: RequestInit = {}): Promise<Response> {
    const info = await this.ready()
    return fetch(info.url + path, {
      ...init,
      headers: { 'content-type': 'application/json', 'x-unlost-token': info.token, ...(init.headers ?? {}) }
    })
  }
}
