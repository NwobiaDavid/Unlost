import { useMemo, useState } from 'react'
import { api, type OrganizeItem, type Status } from '../api'
import { Icon } from './Icon'
import { Thumb } from './Thumb'

interface Props {
  roots: string[]
  status: Status | null
  toast: (msg: string, action?: { label: string; run: () => void }) => void
  onGoSettings: () => void
}

export function OrganizeView({ roots, status, toast, onGoSettings }: Props) {
  const [folder, setFolder] = useState(roots.find((r) => /downloads$/i.test(r)) ?? roots[0] ?? '')
  const [includeAll, setIncludeAll] = useState(false)
  const [items, setItems] = useState<OrganizeItem[] | null>(null)
  const [checked, setChecked] = useState<Set<number>>(new Set())
  const [usedAi, setUsedAi] = useState(false)
  const [busy, setBusy] = useState<'suggest' | 'apply' | null>(null)
  const [error, setError] = useState('')

  const folderOptions = useMemo(() => Array.from(new Set([...roots, folder].filter(Boolean))), [roots, folder])
  const suggestedFolders = useMemo(() => Array.from(new Set(items?.map((i) => i.folder).filter(Boolean))), [items])

  async function find() {
    setBusy('suggest')
    setError('')
    try {
      const res = await api.suggest(folder, includeAll)
      setItems(res.items)
      setUsedAi(res.used_ai)
      setChecked(new Set(res.items.map((i) => i.file_id)))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  async function apply() {
    if (!items) return
    const chosen = items.filter((i) => checked.has(i.file_id))
    setBusy('apply')
    try {
      const res = await api.applyOrganize(folder, chosen)
      setItems(items.filter((i) => !res.moved.some((m) => m.file_id === i.file_id)))
      const skipped = res.skipped.length ? ` ${res.skipped.length} skipped.` : ''
      toast(`Tidied ${res.moved.length} file${res.moved.length === 1 ? '' : 's'}.${skipped}`, {
        label: 'Undo',
        run: async () => {
          const u = await api.undoOrganize(res.batch_id)
          toast(`Restored ${u.restored} file${u.restored === 1 ? '' : 's'} to where they were.`)
          setItems(null)
        }
      })
    } catch (e) {
      toast((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  function update(id: number, patch: Partial<OrganizeItem>) {
    setItems((its) => its?.map((i) => (i.file_id === id ? { ...i, ...patch } : i)) ?? null)
  }

  function toggle(id: number) {
    setChecked((c) => {
      const n = new Set(c)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }

  async function pickOther() {
    const p = await window.unlost.pickFolder()
    if (p) {
      setFolder(p)
      setItems(null)
    }
  }

  if (!roots.length) {
    return (
      <div className="page">
        <div className="empty">
          <h2>Add a folder first</h2>
          <p>unlost can only tidy folders it has indexed.</p>
          <button className="btn btn-primary" onClick={onGoSettings}>
            Choose folders
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="page organize">
      <header className="page-header">
        <div>
          <h1>Organize</h1>
          <p className="muted">
            Finds files with names like <code>IMG_4821.jpg</code> or <code>document(3).pdf</code> and suggests clear names
            and folders. Nothing moves until you apply it, and you can undo.
          </p>
        </div>
      </header>

      <div className="toolbar">
        <label className="field-inline">
          <span>Folder</span>
          <select
            value={folder}
            onChange={(e) => (e.target.value === '__other' ? void pickOther() : (setFolder(e.target.value), setItems(null)))}
          >
            {folderOptions.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
            <option value="__other">Another folder inside these…</option>
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={includeAll} onChange={(e) => setIncludeAll(e.target.checked)} />
          Include files that already have good names
        </label>
        <button className="btn btn-primary" onClick={find} disabled={!folder || busy !== null}>
          <Icon name="wand" size={16} /> {busy === 'suggest' ? 'Reading files…' : 'Suggest names'}
        </button>
      </div>

      <p className="note small">
        {status?.has_api_key ? (
          <>Suggestions use Groq: the first ~500 characters of each file's text are sent to Groq.</>
        ) : (
          <>
            Using on-device rules. <button className="link" onClick={onGoSettings}>Add a free Groq API key</button> for
            smarter names based on what each file is.
          </>
        )}
      </p>

      {error && <p className="note note-warn">{error}</p>}

      {items && items.length === 0 && (
        <div className="empty">
          <h2>This folder looks tidy</h2>
          <p>No messy filenames found at the top level of this folder.</p>
        </div>
      )}

      {items && items.length > 0 && (
        <>
          <datalist id="folder-suggestions">
            {suggestedFolders.map((f) => (
              <option key={f} value={f} />
            ))}
          </datalist>
          <ul className="org-list">
            {items.map((it) => (
              <li key={it.file_id} className={`org-row ${checked.has(it.file_id) ? '' : 'off'}`}>
                <input
                  type="checkbox"
                  checked={checked.has(it.file_id)}
                  onChange={() => toggle(it.file_id)}
                  aria-label={`Include ${it.name}`}
                />
                <Thumb id={it.file_id} kind={it.kind} hasThumb={it.has_thumb} size={48} />
                <div className="org-main">
                  <div className="org-old" title={it.path}>
                    {it.name}
                  </div>
                  <div className="org-new">
                    <label>
                      <span className="sr-only">New folder</span>
                      <input
                        className="org-folder"
                        value={it.folder}
                        list="folder-suggestions"
                        onChange={(e) => update(it.file_id, { folder: e.target.value })}
                        placeholder="(stay here)"
                        name={`folder-${it.file_id}`}
                        autoComplete="off"
                      />
                    </label>
                    <span className="sep">/</span>
                    <label className="grow">
                      <span className="sr-only">New name</span>
                      <input
                        value={it.new_name}
                        name={`name-${it.file_id}`}
                        autoComplete="off"
                        spellCheck={false}
                        onChange={(e) => update(it.file_id, { new_name: e.target.value })}
                      />
                    </label>
                  </div>
                  <div className="org-reason">{it.reason}</div>
                </div>
              </li>
            ))}
          </ul>
          <footer className="sticky-footer">
            <span className="muted">
              {checked.size} of {items.length} selected {usedAi ? '· suggested by AI' : '· on-device suggestions'}
            </span>
            <button className="btn btn-primary" onClick={apply} disabled={checked.size === 0 || busy !== null}>
              <Icon name="check" size={16} /> {busy === 'apply' ? 'Moving…' : `Rename & move ${checked.size}`}
            </button>
          </footer>
        </>
      )}
    </div>
  )
}
