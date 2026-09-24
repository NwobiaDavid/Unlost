import { Fragment, type ReactNode } from 'react'
import type { Source } from '../api'

interface Props {
  text: string
  streaming: boolean
  sources: Source[]
  onCite: (n: number) => void
}

/** Renders the model's answer: paragraphs, bullet lists, **bold**, and [n] citations as buttons. */
export function Answer({ text, streaming, sources, onCite }: Props) {
  const blocks = text.split(/\n{2,}/)
  return (
    <div className="answer-body" aria-live="polite" aria-busy={streaming}>
      {blocks.map((block, i) => {
        const lines = block.split('\n')
        const isList = lines.every((l) => /^\s*([-*•]|\d+\.)\s+/.test(l) || !l.trim())
        const last = i === blocks.length - 1
        if (isList) {
          return (
            <ul key={i}>
              {lines
                .filter((l) => l.trim())
                .map((l, j) => (
                  <li key={j}>{inline(l.replace(/^\s*([-*•]|\d+\.)\s+/, ''), sources, onCite)}</li>
                ))}
              {last && streaming && <span className="caret" />}
            </ul>
          )
        }
        return (
          <p key={i}>
            {lines.map((l, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {inline(l.replace(/^#+\s*/, ''), sources, onCite)}
              </Fragment>
            ))}
            {last && streaming && <span className="caret" />}
          </p>
        )
      })}
    </div>
  )
}

function inline(line: string, sources: Source[], onCite: (n: number) => void): ReactNode[] {
  const out: ReactNode[] = []
  const re = /\*\*(.+?)\*\*|\[(\d+(?:\s*,\s*\d+)*)\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(line))) {
    if (m.index > last) out.push(line.slice(last, m.index))
    if (m[1]) {
      out.push(<strong key={m.index}>{m[1]}</strong>)
    } else {
      for (const n of m[2].split(',').map((s) => Number(s.trim()))) {
        const src = sources.find((s) => s.n === n)
        out.push(
          <button
            key={`${m.index}-${n}`}
            className="cite"
            onClick={() => onCite(n)}
            title={src ? src.name : undefined}
            aria-label={src ? `Source ${n}: ${src.name}` : `Source ${n}`}
          >
            {n}
          </button>
        )
      }
    }
    last = re.lastIndex
  }
  if (last < line.length) out.push(line.slice(last))
  return out
}
