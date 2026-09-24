import { useEffect, useState } from 'react'
import { api, type Settings } from '../api'
import { Icon } from './Icon'

export function Onboarding({ onDone }: { onDone: (s: Settings) => void }) {
  const [folders, setFolders] = useState<{ path: string; on: boolean }[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void window.unlost.defaultFolders().then((ds) => setFolders(ds.map((path) => ({ path, on: true }))))
  }, [])

  async function add() {
    const p = await window.unlost.pickFolder()
    if (p && !folders.some((f) => f.path === p)) setFolders([...folders, { path: p, on: true }])
  }

  async function start() {
    setSaving(true)
    const s = await api.saveSettings({ folders: folders.filter((f) => f.on).map((f) => f.path), onboarded: true })
    onDone(s)
  }

  const count = folders.filter((f) => f.on).length
  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <div className="logo" aria-hidden="true">
          <Icon name="search" size={30} />
        </div>
        <h1>Find files by what you remember</h1>
        <p className="lede">
          “That invoice I sent in March.” “The photo of my WAEC certificate.” unlost reads your documents, PDFs and
          screenshots so you can describe a file instead of remembering its name.
        </p>
        <h2>Where should unlost look?</h2>
        <ul className="folder-picks">
          {folders.map((f, i) => (
            <li key={f.path}>
              <label className="check">
                <input
                  type="checkbox"
                  checked={f.on}
                  onChange={() => setFolders(folders.map((x, j) => (j === i ? { ...x, on: !x.on } : x)))}
                />
                <Icon name="folder" size={16} />
                <span>{f.path}</span>
              </label>
            </li>
          ))}
        </ul>
        <button className="btn" onClick={add}>
          <Icon name="plus" size={15} /> Add another folder
        </button>
        <p className="muted small privacy">
          Indexing and search happen on this computer. Nothing is uploaded unless you add a free Groq API key for answers.
        </p>
        <button className="btn btn-primary btn-large" onClick={start} disabled={count === 0 || saving}>
          {saving ? 'Starting…' : `Start indexing ${count} folder${count === 1 ? '' : 's'}`}
        </button>
      </div>
    </div>
  )
}
