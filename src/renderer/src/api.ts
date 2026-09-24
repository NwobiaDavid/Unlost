export type Kind = 'pdf' | 'doc' | 'sheet' | 'slides' | 'image' | 'text' | 'other'

export interface FileHit {
  id: number
  path: string
  name: string
  folder: string
  kind: Kind
  ext: string
  size: number
  mtime: number
  status: string
  has_thumb: boolean
  score: number
  snippet: string
  page: number | null
  reasons: string[]
}

export interface FileDetail extends Omit<FileHit, 'score' | 'snippet' | 'page' | 'reasons'> {
  text: string
  ocr: boolean
  error: string | null
  months: string[]
}

export interface Source {
  n: number
  id: number
  name: string
  path: string
  folder: string
  kind: Kind
  page: number | null
  excerpt: string
  has_thumb: boolean
}

export interface Settings {
  folders: string[]
  model: string
  model_choices: string[]
  photo_understanding: boolean
  tesseract_path: string
  onboarded: boolean
}

export interface Status {
  progress: {
    running: boolean
    phase: 'idle' | 'scanning' | 'preparing' | 'indexing' | 'ocr' | 'watching'
    total: number
    done: number
    current: string
    errors: number
    recent_errors: string[]
    fatal: string
    last_finished: number | null
  }
  files: number
  errors: number
  ocr_files: number
  images: number
  has_api_key: boolean
  ocr_available: boolean
  voice_available: boolean
  voice_on_device: boolean
  last_organize: { batch_id: string; n: number; ts: number } | null
}

export interface OrganizeItem {
  file_id: number
  path: string
  name: string
  kind: Kind
  new_name: string
  folder: string
  reason: string
  has_thumb: boolean
}

export type AskEvent =
  | { type: 'sources'; sources: Source[] }
  | { type: 'token'; text: string }
  | { type: 'error'; code: string; message: string }
  | { type: 'done' }

let conn: { url: string; token: string } | null = null

export async function connect(): Promise<void> {
  conn = await window.unlost.sidecar()
}

export function reset(): void {
  conn = null
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!conn) await connect()
  const res = await fetch(conn!.url + path, {
    ...init,
    headers: { 'content-type': 'application/json', 'x-unlost-token': conn!.token, ...(init.headers ?? {}) }
  })
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`
    try {
      msg = ((await res.json()) as { detail?: string }).detail ?? msg
    } catch {
      /* not JSON */
    }
    throw new Error(msg)
  }
  return (await res.json()) as T
}

export const api = {
  status: () => req<Status>('/status'),
  settings: () => req<Settings>('/settings'),
  saveSettings: (s: Partial<Settings>) => req<Settings>('/settings', { method: 'PUT', body: JSON.stringify(s) }),
  rescan: (force = false) => req<{ started: boolean }>(`/index/scan?force=${force}`, { method: 'POST' }),
  search: (q: string, signal?: AbortSignal) =>
    req<{ results: FileHit[] }>(`/search?q=${encodeURIComponent(q)}`, { signal }).then((r) => r.results),
  file: (id: number) => req<FileDetail>(`/files/${id}`),
  suggest: (folder: string, includeAll: boolean) =>
    req<{ items: OrganizeItem[]; used_ai: boolean; root?: string }>('/organize/suggest', {
      method: 'POST',
      body: JSON.stringify({ folder, include_all: includeAll })
    }),
  applyOrganize: (folder: string, items: OrganizeItem[]) =>
    req<{ batch_id: string; moved: { file_id: number; from: string; to: string }[]; skipped: { file_id: number; error: string }[] }>(
      '/organize/apply',
      { method: 'POST', body: JSON.stringify({ folder, items }) }
    ),
  undoOrganize: (batch_id: string) =>
    req<{ restored: number; failed: string[] }>('/organize/undo', { method: 'POST', body: JSON.stringify({ batch_id }) }),
  transcribe: (audio: Blob) =>
    req<{ text: string }>('/transcribe', { method: 'POST', body: audio, headers: { 'content-type': audio.type } })
}

export function thumbUrl(id: number): string {
  return conn ? `${conn.url}/thumb/${id}?token=${encodeURIComponent(conn.token)}` : ''
}

/** Streams server-sent events from /ask. */
export async function ask(question: string, onEvent: (e: AskEvent) => void, signal: AbortSignal): Promise<void> {
  if (!conn) await connect()
  const res = await fetch(conn!.url + '/ask', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-unlost-token': conn!.token },
    body: JSON.stringify({ question }),
    signal
  })
  if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`)
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buf = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += value
    let i: number
    while ((i = buf.indexOf('\n\n')) >= 0) {
      const frame = buf.slice(0, i)
      buf = buf.slice(i + 2)
      if (frame.startsWith('data: ')) onEvent(JSON.parse(frame.slice(6)) as AskEvent)
    }
  }
}
