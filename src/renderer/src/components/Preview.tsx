import { useEffect, useState } from 'react'
import { api, type FileDetail } from '../api'
import { bytes, kindLabel, when } from '../format'
import { Icon } from './Icon'
import { Thumb } from './Thumb'

interface Props {
  fileId: number | null
  reasons?: string[]
  onOpen: (path: string) => void
  onReveal: (path: string) => void
}

export function Preview({ fileId, reasons, onOpen, onReveal }: Props) {
  const [detail, setDetail] = useState<FileDetail | null>(null)

  useEffect(() => {
    if (fileId == null) return setDetail(null)
    let live = true
    api
      .file(fileId)
      .then((d) => live && setDetail(d))
      .catch(() => live && setDetail(null))
    return () => {
      live = false
    }
  }, [fileId])

  if (fileId == null || !detail || detail.id !== fileId) {
    return <aside className="preview preview-empty" aria-hidden={fileId == null} />
  }

  return (
    <aside className="preview" aria-label="Preview">
      <div className="preview-media">
        <Thumb id={detail.id} kind={detail.kind} hasThumb={detail.has_thumb} size={200} />
      </div>
      <h2 className="preview-title">{detail.name}</h2>
      <p className="preview-meta">
        {kindLabel[detail.kind]} · {bytes(detail.size)} · {when(detail.mtime)}
      </p>
      {reasons && reasons.length > 0 && (
        <ul className="chips" aria-label="Why this matched">
          {reasons.map((r) => (
            <li key={r} className="chip">
              {r}
            </li>
          ))}
        </ul>
      )}
      <div className="preview-actions">
        <button className="btn btn-primary" onClick={() => onOpen(detail.path)}>
          <Icon name="open" size={16} /> Open <kbd>↵</kbd>
        </button>
        <button className="btn" onClick={() => onReveal(detail.path)}>
          <Icon name="reveal" size={16} /> Show in folder
        </button>
      </div>
      <p className="preview-path" title={detail.path}>
        {detail.path}
      </p>
      {detail.error && (
        <p className="note note-warn">
          <Icon name="warning" size={14} /> {detail.error}
        </p>
      )}
      {detail.text ? (
        <section className="preview-text">
          <h3>{detail.ocr ? 'Text read from the file (OCR)' : 'Contents'}</h3>
          <p>{detail.text.slice(0, 1400)}</p>
        </section>
      ) : (
        !detail.error && <p className="muted small">No readable text in this file. It's searchable by name and date.</p>
      )}
    </aside>
  )
}
