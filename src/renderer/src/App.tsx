import { useCallback, useEffect, useRef, useState } from 'react'
import { api, connect, reset, type Settings, type Status } from './api'
import { Icon } from './components/Icon'
import { Onboarding } from './components/Onboarding'
import { OrganizeView } from './components/OrganizeView'
import { SearchView } from './components/SearchView'
import { SettingsView } from './components/SettingsView'

type Tab = 'search' | 'organize' | 'settings'
type Toast = { id: number; msg: string; action?: { label: string; run: () => void } }

export function App() {
  const [boot, setBoot] = useState<'connecting' | 'ready' | 'error'>('connecting')
  const [bootError, setBootError] = useState('')
  const [settings, setSettings] = useState<Settings | null>(null)
  const [status, setStatus] = useState<Status | null>(null)
  const [tab, setTab] = useState<Tab>('search')
  const [focusSignal, setFocusSignal] = useState(0)
  const [toastItem, setToastItem] = useState<Toast | null>(null)
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  const toast = useCallback((msg: string, action?: Toast['action']) => {
    clearTimeout(toastTimer.current)
    setToastItem({ id: Date.now(), msg, action })
    toastTimer.current = setTimeout(() => setToastItem(null), action ? 9000 : 4000)
  }, [])

  const load = useCallback(async () => {
    setBoot('connecting')
    try {
      await connect()
      const [s, st] = await Promise.all([api.settings(), api.status()])
      setSettings(s)
      setStatus(st)
      setBoot('ready')
    } catch (e) {
      setBootError((e as Error).message)
      setBoot('error')
    }
  }, [])

  useEffect(() => {
    void load()
    const offState = window.unlost.onSidecarState((state, detail) => {
      if (state === 'crashed') {
        reset()
        setBootError(detail ?? '')
        setBoot('error')
      } else if (state === 'ready') void load()
    })
    const offFocus = window.unlost.onFocusSearch(() => {
      setTab('search')
      setFocusSignal((n) => n + 1)
    })
    return () => {
      offState()
      offFocus()
    }
  }, [load])

  // Poll status: quickly while indexing, slowly otherwise.
  useEffect(() => {
    if (boot !== 'ready') return
    const running = status?.progress.running
    const t = setTimeout(() => void api.status().then(setStatus).catch(() => undefined), running ? 1000 : 5000)
    return () => clearTimeout(t)
  }, [boot, status])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return
      if (e.key === 'k' || e.key === 'f') {
        e.preventDefault()
        setTab('search')
        setFocusSignal((n) => n + 1)
      } else if (e.key === ',') {
        e.preventDefault()
        setTab('settings')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  if (boot !== 'ready' || !settings) {
    return (
      <div className="boot">
        <div className="titlebar-spacer drag" />
        {boot === 'error' ? (
          <div className="empty">
            <h2>The search engine didn't start</h2>
            <pre className="error-detail">{bootError}</pre>
            <button className="btn btn-primary" onClick={() => void window.unlost.restartSidecar().then(load)}>
              Try again
            </button>
          </div>
        ) : (
          <div className="empty">
            <span className="spinner spinner-large" aria-label="Starting" />
            <p className="muted">Starting unlost…</p>
          </div>
        )}
      </div>
    )
  }

  if (!settings.onboarded) {
    return (
      <>
        <div className="titlebar drag" />
        <Onboarding
          onDone={(s) => {
            setSettings(s)
            void api.status().then(setStatus)
          }}
        />
      </>
    )
  }

  const p = status?.progress
  const indexing = p?.running
  const pct = p && p.total ? Math.round((p.done / p.total) * 100) : 0

  return (
    <div className={`app platform-${window.unlost.platform}`}>
      <header className="titlebar drag">
        <div className="brand">unlost</div>
        <nav className="tabs no-drag" aria-label="Sections">
          {(
            [
              ['search', 'search', 'Search'],
              ['organize', 'wand', 'Organize'],
              ['settings', 'gear', 'Settings']
            ] as const
          ).map(([id, icon, label]) => (
            <button key={id} className="tab" aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>
              <Icon name={icon} size={15} />
              {label}
            </button>
          ))}
        </nav>
      </header>

      <main className="content">
        {tab === 'search' && (
          <SearchView
            status={status}
            roots={settings.folders}
            focusSignal={focusSignal}
            onGoSettings={() => setTab('settings')}
            toast={toast}
          />
        )}
        {tab === 'organize' && (
          <OrganizeView roots={settings.folders} status={status} toast={toast} onGoSettings={() => setTab('settings')} />
        )}
        {tab === 'settings' && <SettingsView settings={settings} status={status} onSettings={setSettings} toast={toast} />}
      </main>

      <footer className="statusbar" role="status">
        {indexing ? (
          <>
            <div className="progress" aria-hidden="true">
              <div className="progress-fill" style={{ transform: `scaleX(${pct / 100})` }} />
            </div>
            <span>
              {p!.phase === 'scanning'
                ? 'Looking for new and changed files…'
                : p!.phase === 'preparing'
                  ? 'Getting ready: downloading the on-device search model (about 70 MB, first run only)…'
                  : p!.phase === 'ocr'
                    ? `Reading text in images and scans: ${p!.done.toLocaleString()} of ${p!.total.toLocaleString()} (search already works)`
                    : `Reading files: ${p!.done.toLocaleString()} of ${p!.total.toLocaleString()}`}
            </span>
            <span className="statusbar-file" title={p!.current}>
              {p!.current.split(/[\\/]/).pop()}
            </span>
          </>
        ) : p?.fatal ? (
          <span className="statusbar-error" title={p.fatal}>
            Indexing stopped: {p.fatal}{' '}
            <button className="link" onClick={() => void api.rescan(false)}>
              Retry
            </button>
          </span>
        ) : (
          <span>
            {status ? `${status.files.toLocaleString()} files indexed` : ''}
            {p?.phase === 'watching' ? ' · watching for changes' : ''}
          </span>
        )}
        <span className="grow" />
        <span className="muted">
          <kbd>Ctrl</kbd>
          <kbd>Shift</kbd>
          <kbd>Space</kbd> opens unlost from anywhere
        </span>
      </footer>

      {toastItem && (
        <div className="toast" key={toastItem.id} role="status">
          <span>{toastItem.msg}</span>
          {toastItem.action && (
            <button
              className="btn btn-small"
              onClick={() => {
                toastItem.action!.run()
                setToastItem(null)
              }}
            >
              <Icon name="undo" size={14} /> {toastItem.action.label}
            </button>
          )}
          <button className="icon-btn" aria-label="Dismiss" onClick={() => setToastItem(null)}>
            <Icon name="close" size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
