import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ask, type FileHit, type Source, type Status } from '../api'
import { shortFolder, when } from '../format'
import { useVoice } from '../useVoice'
import { Answer } from './Answer'
import { Icon } from './Icon'
import { Preview } from './Preview'
import { Thumb } from './Thumb'

type Mode = 'find' | 'ask'

const FIND_EXAMPLES = [
  'that invoice I sent in March',
  'the photo of my WAEC certificate',
  "the slides from last week's meeting",
  'screenshot of my flight booking'
]
const ASK_EXAMPLES = [
  'How much did I pay for rent last year?',
  'When does my passport expire?',
  'What was the total on my last electricity bill?'
]
const QUESTION = /^(how|what|when|where|which|who|why|did|do|does|is|are|was|were|can|list|summari[sz]e)\b|\?\s*$/i

interface Props {
  status: Status | null
  roots: string[]
  focusSignal: number
  onGoSettings: () => void
  toast: (msg: string) => void
}

export function SearchView({ status, roots, focusSignal, onGoSettings, toast }: Props) {
  const [mode, setMode] = useState<Mode>('find')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<FileHit[]>([])
  const [searched, setSearched] = useState('')
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(0)

  const [answer, setAnswer] = useState('')
  const [sources, setSources] = useState<Source[]>([])
  const [askError, setAskError] = useState<{ code: string; message: string } | null>(null)
  const [asking, setAsking] = useState(false)
  const [asked, setAsked] = useState('')

  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => inputRef.current?.focus(), [focusSignal, mode])

  // ---- Find: live search as you type --------------------------------------------------------------
  useEffect(() => {
    if (mode !== 'find') return
    const q = query.trim()
    if (!q) {
      setResults([])
      setSearched('')
      return
    }
    const ctl = new AbortController()
    const t = setTimeout(() => {
      setLoading(true)
      api
        .search(q, ctl.signal)
        .then((r) => {
          setResults(r)
          setSearched(q)
          setSelected(0)
        })
        .catch((e) => e.name !== 'AbortError' && toast(e.message))
        .finally(() => !ctl.signal.aborted && setLoading(false))
    }, 160)
    return () => {
      clearTimeout(t)
      ctl.abort()
    }
  }, [query, mode, toast])

  // ---- Ask: stream an answer ---------------------------------------------------------------------
  const runAsk = useCallback(
    async (question: string) => {
      const q = question.trim()
      if (!q) return
      abortRef.current?.abort()
      const ctl = new AbortController()
      abortRef.current = ctl
      setAsked(q)
      setAnswer('')
      setSources([])
      setAskError(null)
      setAsking(true)
      setSelected(0)
      try {
        await ask(
          q,
          (ev) => {
            if (ev.type === 'sources') setSources(ev.sources)
            else if (ev.type === 'token') setAnswer((a) => a + ev.text)
            else if (ev.type === 'error') setAskError({ code: ev.code, message: ev.message })
          },
          ctl.signal
        )
      } catch (e) {
        if ((e as Error).name !== 'AbortError') setAskError({ code: 'api', message: (e as Error).message })
      } finally {
        if (abortRef.current === ctl) setAsking(false)
      }
    },
    []
  )

  const voice = useVoice(
    useCallback(
      (text: string) => {
        setQuery(text)
        if (QUESTION.test(text)) {
          setMode('ask')
          void runAsk(text)
        }
      },
      [runAsk]
    ),
    toast
  )

  const items: { id: number; path: string; reasons?: string[] }[] = mode === 'find' ? results : sources
  const current = items[selected]

  const open = useCallback(
    async (path: string) => {
      const err = await window.unlost.openFile(path)
      if (err) toast(err)
    },
    [toast]
  )
  const reveal = useCallback((path: string) => void window.unlost.revealFile(path), [])

  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${selected}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [selected])

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const d = e.key === 'ArrowDown' ? 1 : -1
      setSelected((s) => Math.max(0, Math.min(items.length - 1, s + d)))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (mode === 'ask' && query.trim() !== asked) return void runAsk(query)
      if (current) (e.ctrlKey || e.metaKey ? reveal : open)(current.path)
    } else if (e.key === 'Tab' && !e.shiftKey && query.trim()) {
      e.preventDefault()
      switchMode(mode === 'find' ? 'ask' : 'find')
    } else if (e.key === 'Escape') {
      setQuery('')
      abortRef.current?.abort()
    }
  }

  function switchMode(m: Mode) {
    setMode(m)
    setSelected(0)
    if (m === 'ask' && query.trim() && query.trim() !== asked) void runAsk(query)
  }

  const empty = !query.trim()
  const noIndex = status && status.files === 0 && !status.progress.running
  const looksLikeQuestion = mode === 'find' && QUESTION.test(query.trim())

  return (
    <div className="search-view">
      <div className="search-bar">
        <div className="segmented" role="tablist" aria-label="Mode">
          <button role="tab" aria-selected={mode === 'find'} onClick={() => switchMode('find')}>
            <Icon name="search" size={15} /> Find
          </button>
          <button role="tab" aria-selected={mode === 'ask'} onClick={() => switchMode('ask')}>
            <Icon name="sparkle" size={15} /> Ask
          </button>
        </div>
        <div className="search-field">
          <Icon name={mode === 'find' ? 'search' : 'sparkle'} size={20} className="search-glyph" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={mode === 'find' ? 'Describe the file you remember…' : 'Ask a question about your files…'}
            aria-label={mode === 'find' ? 'Describe the file' : 'Ask a question'}
            spellCheck={false}
            autoComplete="off"
            name="query"
            role="combobox"
            aria-expanded={items.length > 0}
            aria-controls="result-list"
            aria-activedescendant={current ? `result-${selected}` : undefined}
            autoFocus
          />
          {(loading || asking) && <span className="spinner" aria-label="Working" />}
          {status?.voice_available && (
            <button
              className={`icon-btn mic ${voice.state}`}
              onClick={voice.toggle}
              aria-label={voice.state === 'recording' ? 'Stop recording' : 'Search by voice'}
              title={voice.state === 'recording' ? 'Stop' : 'Say what you remember'}
              disabled={voice.state === 'transcribing'}
            >
              <Icon name={voice.state === 'recording' ? 'stop' : 'mic'} size={18} />
            </button>
          )}
        </div>
      </div>

      {looksLikeQuestion && (
        <button className="hint" onClick={() => switchMode('ask')}>
          <Icon name="sparkle" size={14} /> Sounds like a question: <strong>ask your files instead</strong> <kbd>Tab</kbd>
        </button>
      )}

      <div className="split">
        <div className="results-pane">
          {noIndex ? (
            <div className="empty">
              <h2>Nothing indexed yet</h2>
              <p>Choose the folders unlost should look through.</p>
              <button className="btn btn-primary" onClick={onGoSettings}>
                Choose folders
              </button>
            </div>
          ) : mode === 'ask' && asked ? (
            <>
              <section className="answer" aria-label="Answer">
                <p className="answer-q">{asked}</p>
                {askError ? (
                  <div className={`note ${askError.code === 'no_api_key' ? '' : 'note-warn'}`}>
                    <p>{askError.message}</p>
                    {(askError.code === 'no_api_key' || askError.code === 'auth') && (
                      <button className="btn btn-small" onClick={onGoSettings}>
                        Open Settings
                      </button>
                    )}
                  </div>
                ) : answer ? (
                  <Answer text={answer} streaming={asking} sources={sources} onCite={(n) => setSelected(n - 1)} />
                ) : (
                  asking && <p className="muted shimmer">{sources.length ? `Reading ${sources.length} passages…` : 'Searching your files…'}</p>
                )}
              </section>
              {sources.length > 0 && (
                <>
                  <h3 className="list-heading">Sources</h3>
                  <ul className="results" id="result-list" ref={listRef} role="listbox" aria-label="Sources">
                    {sources.map((s, i) => (
                      <li
                        key={s.n}
                        id={`result-${i}`}
                        data-index={i}
                        role="option"
                        aria-selected={i === selected}
                        className="result"
                        onMouseDown={() => setSelected(i)}
                        onDoubleClick={() => open(s.path)}
                      >
                        <span className="source-n">{s.n}</span>
                        <Thumb id={s.id} kind={s.kind} hasThumb={s.has_thumb} size={40} />
                        <div className="result-main">
                          <div className="result-name">
                            {s.name}
                            {s.page ? <span className="muted"> · page {s.page}</span> : null}
                          </div>
                          <div className="result-snippet">{s.excerpt}</div>
                        </div>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          ) : empty || (mode === 'ask' && !asked) ? (
            <div className="empty">
              <h2>{mode === 'find' ? 'What are you looking for?' : 'Ask across your files'}</h2>
              <p>
                {mode === 'find'
                  ? "Describe it however you remember it: what it's about, what's in it, roughly when."
                  : 'Answers come from your own documents, with the source file cited.'}
              </p>
              <div className="examples">
                {(mode === 'find' ? FIND_EXAMPLES : ASK_EXAMPLES).map((ex) => (
                  <button
                    key={ex}
                    className="example"
                    onClick={() => {
                      setQuery(ex)
                      if (mode === 'ask') void runAsk(ex)
                      inputRef.current?.focus()
                    }}
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          ) : results.length === 0 && searched === query.trim() && !loading ? (
            <div className="empty">
              <h2>No matches</h2>
              <p>Try describing what's inside the file, or a different time: “the receipt from the phone shop.”</p>
            </div>
          ) : (
            <ul className="results" id="result-list" ref={listRef} role="listbox" aria-label="Results">
              {results.map((r, i) => (
                <li
                  key={r.id}
                  id={`result-${i}`}
                  data-index={i}
                  role="option"
                  aria-selected={i === selected}
                  className="result"
                  onMouseDown={() => setSelected(i)}
                  onDoubleClick={() => open(r.path)}
                >
                  <Thumb id={r.id} kind={r.kind} hasThumb={r.has_thumb} />
                  <div className="result-main">
                    <div className="result-name">{r.name}</div>
                    {r.snippet && <div className="result-snippet">{r.snippet}</div>}
                    <div className="result-meta">
                      <span>{shortFolder(r.folder, roots)}</span>
                      <span>·</span>
                      <span>{when(r.mtime)}</span>
                      {r.reasons.slice(0, 3).map((x) => (
                        <span key={x} className="chip chip-small">
                          {x}
                        </span>
                      ))}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
        <Preview
          fileId={current?.id ?? null}
          reasons={mode === 'find' ? (current as FileHit | undefined)?.reasons : undefined}
          onOpen={open}
          onReveal={reveal}
        />
      </div>
    </div>
  )
}
