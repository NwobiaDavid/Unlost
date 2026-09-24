import { useEffect, useState } from 'react'
import { api, type Settings, type Status } from '../api'
import { Icon } from './Icon'

interface Props {
  settings: Settings
  status: Status | null
  onSettings: (s: Settings) => void
  toast: (msg: string) => void
}

const MODEL_LABELS: Record<string, string> = {
  'openai/gpt-oss-120b': 'GPT-OSS 120B: best answers (recommended)',
  'openai/gpt-oss-20b': 'GPT-OSS 20B: faster',
  'llama-3.3-70b-versatile': 'Llama 3.3 70B',
  'llama-3.1-8b-instant': 'Llama 3.1 8B: fastest, highest free limits'
}

export function SettingsView({ settings, status, onSettings, toast }: Props) {
  const [hasKey, setHasKey] = useState(false)
  const [key, setKey] = useState('')
  const [savingKey, setSavingKey] = useState(false)

  useEffect(() => {
    void window.unlost.hasKey().then(setHasKey)
  }, [])

  async function save(patch: Partial<Settings>) {
    try {
      onSettings(await api.saveSettings(patch))
    } catch (e) {
      toast((e as Error).message)
    }
  }

  async function addFolder() {
    const p = await window.unlost.pickFolder()
    if (p) await save({ folders: [...settings.folders, p] })
  }

  async function saveKey(value: string | null) {
    setSavingKey(true)
    try {
      setHasKey(await window.unlost.setKey(value))
      setKey('')
      toast(value ? 'API key saved to your system keychain.' : 'API key removed.')
    } catch (e) {
      toast((e as Error).message)
    } finally {
      setSavingKey(false)
    }
  }

  return (
    <div className="page settings">
      <header className="page-header">
        <h1>Settings</h1>
      </header>

      <section className="group">
        <h2>Folders to search</h2>
        <p className="muted small">unlost reads files in these folders and everything inside them. The index stays on this computer.</p>
        <ul className="folder-list">
          {settings.folders.map((f) => (
            <li key={f}>
              <Icon name="folder" size={16} />
              <span className="grow" title={f}>
                {f}
              </span>
              <button
                className="icon-btn"
                aria-label={`Stop searching ${f}`}
                onClick={() => save({ folders: settings.folders.filter((x) => x !== f) })}
              >
                <Icon name="close" size={14} />
              </button>
            </li>
          ))}
        </ul>
        <div className="row">
          <button className="btn" onClick={addFolder}>
            <Icon name="plus" size={15} /> Add folder
          </button>
          <button className="btn" onClick={() => void api.rescan(false).then(() => toast('Checking for changes…'))}>
            <Icon name="refresh" size={15} /> Rescan
          </button>
        </div>
        {status && status.errors > 0 && (
          <details className="small">
            <summary>
              {status.errors} file{status.errors === 1 ? '' : 's'} couldn't be read
            </summary>
            <ul className="error-list">
              {status.progress.recent_errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <section className="group">
        <h2>Understanding files</h2>
        <div className="setting">
          <div>
            <div className="setting-title">Read text in images and scanned PDFs (OCR)</div>
            <div className="muted small">
              {status?.ocr_available
                ? `On. ${status.ocr_files} file${status.ocr_files === 1 ? '' : 's'} read with OCR so far.`
                : 'Tesseract OCR is not installed, so screenshots and scans are only searchable by name and date.'}
            </div>
          </div>
          <span className={`pill ${status?.ocr_available ? 'pill-on' : ''}`}>{status?.ocr_available ? 'Ready' : 'Missing'}</span>
        </div>
        {!status?.ocr_available && (
          <label className="field">
            <span>Path to tesseract executable</span>
            <input
              defaultValue={settings.tesseract_path}
              placeholder="C:\Program Files\Tesseract-OCR\tesseract.exe…"
              name="tesseract_path"
              autoComplete="off"
              onBlur={(e) => e.target.value !== settings.tesseract_path && save({ tesseract_path: e.target.value })}
            />
          </label>
        )}
        <label className="setting">
          <div>
            <div className="setting-title">Recognise what's in photos</div>
            <div className="muted small">
              Finds photos with no text by what they show (“beach sunset,” “my red car”). Runs on this computer; downloads
              a ~600 MB model the first time.
            </div>
          </div>
          <input
            type="checkbox"
            className="switch"
            checked={settings.photo_understanding}
            onChange={(e) => save({ photo_understanding: e.target.checked })}
          />
        </label>
        <div className="setting">
          <div>
            <div className="setting-title">Voice search</div>
            <div className="muted small">
              {status?.has_api_key
                ? 'On. Click the mic in the search bar; Groq transcribes what you say.'
                : status?.voice_on_device
                  ? 'On. Speech is transcribed on this computer.'
                  : 'Add a Groq API key below to search by voice.'}
            </div>
          </div>
          <span className={`pill ${status?.voice_available ? 'pill-on' : ''}`}>{status?.voice_available ? 'Ready' : 'Off'}</span>
        </div>
      </section>

      <section className="group">
        <h2>Answers, smart organizing and voice (Groq)</h2>
        <p className="muted small">
          Search works fully offline. To answer questions and suggest names, unlost sends the most relevant passages of
          your files (not whole folders) to Groq using your own free key. Voice recordings are also transcribed by Groq.
        </p>
        <div className="setting">
          <div className="grow">
            <div className="setting-title">Groq API key</div>
            {!hasKey && (
              <div className="muted small">
                Free, no card needed: sign in at{' '}
                <button className="link" onClick={() => void window.unlost.openGroqConsole()}>
                  console.groq.com/keys
                </button>{' '}
                and create a key.
              </div>
            )}
            {hasKey ? (
              <div className="row">
                <span className="pill pill-on">Saved in system keychain</span>
                <button className="btn btn-small" onClick={() => saveKey(null)} disabled={savingKey}>
                  Remove
                </button>
              </div>
            ) : (
              <form
                className="row"
                onSubmit={(e) => {
                  e.preventDefault()
                  if (key.trim()) void saveKey(key)
                }}
              >
                <input
                  type="password"
                  className="grow"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="gsk_…"
                  aria-label="Groq API key"
                  name="groq_api_key"
                  autoComplete="off"
                  spellCheck={false}
                />
                <button className="btn btn-primary" disabled={!key.trim() || savingKey}>
                  Save
                </button>
              </form>
            )}
          </div>
        </div>
        <label className="field">
          <span>Model</span>
          <select value={settings.model} onChange={(e) => save({ model: e.target.value })}>
            {settings.model_choices.map((m) => (
              <option key={m} value={m}>
                {MODEL_LABELS[m] ?? m}
              </option>
            ))}
          </select>
        </label>
      </section>
    </div>
  )
}
