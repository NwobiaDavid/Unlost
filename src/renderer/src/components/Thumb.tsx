import { useState } from 'react'
import { thumbUrl, type Kind } from '../api'
import { KindIcon } from './Icon'

export function Thumb({ id, kind, hasThumb, size = 44 }: { id: number; kind: Kind; hasThumb: boolean; size?: number }) {
  const [failed, setFailed] = useState(false)
  return (
    <span className="thumb" style={{ width: size, height: size }}>
      {hasThumb && !failed ? (
        <img src={thumbUrl(id)} alt="" width={size} height={size} loading="lazy" draggable={false} onError={() => setFailed(true)} />
      ) : (
        <KindIcon kind={kind} size={Math.round(size * 0.5)} />
      )}
    </span>
  )
}
