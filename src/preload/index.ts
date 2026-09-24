import { contextBridge, ipcRenderer } from 'electron'

const api = {
  platform: process.platform,
  sidecar: (): Promise<{ url: string; token: string }> => ipcRenderer.invoke('sidecar:info'),
  restartSidecar: (): Promise<void> => ipcRenderer.invoke('sidecar:restart'),
  onSidecarState: (fn: (state: string, detail?: string) => void): (() => void) => {
    const h = (_: unknown, state: string, detail?: string): void => fn(state, detail)
    ipcRenderer.on('sidecar:state', h)
    return () => ipcRenderer.off('sidecar:state', h)
  },
  onFocusSearch: (fn: () => void): (() => void) => {
    const h = (): void => fn()
    ipcRenderer.on('app:focus-search', h)
    return () => ipcRenderer.off('app:focus-search', h)
  },
  pickFolder: (): Promise<string | null> => ipcRenderer.invoke('dialog:pickFolder'),
  defaultFolders: (): Promise<string[]> => ipcRenderer.invoke('app:defaultFolders'),
  openFile: (path: string): Promise<string> => ipcRenderer.invoke('file:open', path),
  revealFile: (path: string): Promise<void> => ipcRenderer.invoke('file:reveal', path),
  openGroqConsole: (): Promise<void> => ipcRenderer.invoke('app:openGroqConsole'),
  hasKey: (): Promise<boolean> => ipcRenderer.invoke('key:has'),
  setKey: (key: string | null): Promise<boolean> => ipcRenderer.invoke('key:set', key)
}

export type UnlostBridge = typeof api

contextBridge.exposeInMainWorld('unlost', api)
