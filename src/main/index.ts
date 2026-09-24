import { existsSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { join, resolve, sep } from 'node:path'
import {
  app,
  BrowserWindow,
  dialog,
  globalShortcut,
  ipcMain,
  nativeTheme,
  safeStorage,
  session,
  shell
} from 'electron'
import { Sidecar } from './sidecar'

// Lets tests and demos run against a throwaway profile instead of the real index.
if (process.env.UNLOST_USER_DATA) app.setPath('userData', process.env.UNLOST_USER_DATA)

const sidecar = new Sidecar()
let win: BrowserWindow | null = null

const SHOW_SHORTCUT = 'CommandOrControl+Shift+Space'
const keyFile = (): string => join(app.getPath('userData'), 'groq-key.bin')

// ---- API key: encrypted at rest with the OS keychain (DPAPI / Keychain / libsecret) ----------------

function loadKey(): string | null {
  try {
    if (!existsSync(keyFile()) || !safeStorage.isEncryptionAvailable()) return null
    return safeStorage.decryptString(readFileSync(keyFile()))
  } catch {
    return null
  }
}

async function pushKeyToSidecar(): Promise<void> {
  const key = loadKey()
  await sidecar.request('/api-key', { method: 'POST', body: JSON.stringify({ key }) }).catch(() => undefined)
}

// ---- only open files that live inside folders the user chose to index ------------------------------

async function isInsideIndexedFolders(target: string): Promise<boolean> {
  const res = await sidecar.request('/settings')
  if (!res.ok) return false
  const { folders } = (await res.json()) as { folders: string[] }
  const full = resolve(target)
  const norm = (p: string): string => (process.platform === 'win32' ? p.toLowerCase() : p)
  return existsSync(full) && folders.some((f) => norm(full).startsWith(norm(resolve(f) + sep)))
}

function createWindow(): void {
  const dark = nativeTheme.shouldUseDarkColors
  win = new BrowserWindow({
    width: 1120,
    height: 760,
    minWidth: 720,
    minHeight: 520,
    show: false,
    title: 'unlost',
    backgroundColor: dark ? '#1c1c1e' : '#f5f5f7',
    titleBarStyle: 'hidden',
    ...(process.platform === 'darwin'
      ? { trafficLightPosition: { x: 16, y: 18 } }
      : { titleBarOverlay: { color: '#00000000', symbolColor: dark ? '#f5f5f7' : '#1d1d1f', height: 52 } }),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false
    }
  })
  win.once('ready-to-show', () => win?.show())
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  win.webContents.on('will-navigate', (e, url) => {
    if (url !== win?.webContents.getURL()) e.preventDefault()
  })
  nativeTheme.on('updated', () => {
    if (process.platform !== 'darwin') {
      win?.setTitleBarOverlay({ color: '#00000000', symbolColor: nativeTheme.shouldUseDarkColors ? '#f5f5f7' : '#1d1d1f' })
    }
  })

  if (!app.isPackaged && process.env.ELECTRON_RENDERER_URL) {
    void win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    void win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

function registerIpc(): void {
  ipcMain.handle('sidecar:info', async () => {
    const info = await sidecar.ready()
    return info
  })
  ipcMain.handle('sidecar:restart', async () => {
    await sidecar.restart()
    await sidecar.ready()
    await pushKeyToSidecar()
  })
  ipcMain.handle('dialog:pickFolder', async () => {
    const r = await dialog.showOpenDialog(win!, { properties: ['openDirectory'] })
    return r.canceled ? null : r.filePaths[0]
  })
  ipcMain.handle('app:defaultFolders', () =>
    (['downloads', 'documents', 'desktop', 'pictures'] as const)
      .map((k) => {
        try {
          return app.getPath(k)
        } catch {
          return null
        }
      })
      .filter((p): p is string => !!p && existsSync(p))
  )
  ipcMain.handle('file:open', async (_e, path: string) => {
    if (!(await isInsideIndexedFolders(path))) return 'Not an indexed file'
    return shell.openPath(path)
  })
  ipcMain.handle('file:reveal', async (_e, path: string) => {
    if (await isInsideIndexedFolders(path)) shell.showItemInFolder(path)
  })
  // Fixed URL only: the renderer can't ask main to open arbitrary links.
  ipcMain.handle('app:openGroqConsole', () => shell.openExternal('https://console.groq.com/keys'))
  ipcMain.handle('key:has', () => loadKey() !== null)
  ipcMain.handle('key:set', async (_e, key: string | null) => {
    if (key && key.trim()) {
      if (!safeStorage.isEncryptionAvailable()) throw new Error('Secure storage is not available on this system.')
      writeFileSync(keyFile(), safeStorage.encryptString(key.trim()))
    } else {
      rmSync(keyFile(), { force: true })
    }
    await pushKeyToSidecar()
    return loadKey() !== null
  })
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  app.whenReady().then(() => {
    // Only the microphone (for voice search) may be requested by the page.
    session.defaultSession.setPermissionRequestHandler((_wc, permission, cb) => cb(permission === 'media'))
    session.defaultSession.setPermissionCheckHandler((_wc, permission) => permission === 'media')

    registerIpc()
    sidecar.onState((state, detail) => {
      win?.webContents.send('sidecar:state', state, detail)
      if (state === 'ready') void pushKeyToSidecar()
    })
    void sidecar.start()
    createWindow()

    // Spotlight-style: summon unlost from anywhere.
    globalShortcut.register(SHOW_SHORTCUT, () => {
      if (!win) return createWindow()
      if (win.isMinimized()) win.restore()
      win.show()
      win.focus()
      win.webContents.send('app:focus-search')
    })

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
  })

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
  })
  app.on('will-quit', () => {
    globalShortcut.unregisterAll()
    sidecar.stop()
  })
}
