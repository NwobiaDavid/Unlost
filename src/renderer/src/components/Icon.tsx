import type { Kind } from '../api'

const paths: Record<string, string> = {
  search: 'M10.5 3a7.5 7.5 0 0 1 5.9 12.1l4.2 4.2-1.4 1.4-4.2-4.2A7.5 7.5 0 1 1 10.5 3Zm0 2a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11Z',
  sparkle: 'M12 2l1.9 5.6L19.5 9.5 13.9 11.4 12 17l-1.9-5.6L4.5 9.5l5.6-1.9L12 2Zm6.5 12 .9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9.9-2.6Z',
  mic: 'M12 2a3 3 0 0 1 3 3v6a3 3 0 1 1-6 0V5a3 3 0 0 1 3-3Zm-7 9h2a5 5 0 0 0 10 0h2a7 7 0 0 1-6 6.9V21h-2v-3.1A7 7 0 0 1 5 11Z',
  stop: 'M7 7h10v10H7z',
  folder: 'M3 6a2 2 0 0 1 2-2h4.2l2 2H19a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Z',
  wand: 'M14.7 3.3 20.7 9.3 9.3 20.7 3.3 14.7 14.7 3.3Zm0 2.8-2.1 2.1 3.2 3.2 2.1-2.1-3.2-3.2ZM5 2l.7 1.8L7.5 4.5l-1.8.7L5 7l-.7-1.8L2.5 4.5l1.8-.7L5 2Z',
  gear: 'M12 8.5a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7Zm-1.2-6.5h2.4l.5 2.6 1.6.7 2.2-1.5 1.7 1.7-1.5 2.2.7 1.6 2.6.5v2.4l-2.6.5-.7 1.6 1.5 2.2-1.7 1.7-2.2-1.5-1.6.7-.5 2.6h-2.4l-.5-2.6-1.6-.7-2.2 1.5-1.7-1.7 1.5-2.2-.7-1.6L2 13.2v-2.4l2.6-.5.7-1.6-1.5-2.2 1.7-1.7 2.2 1.5 1.6-.7.5-2.6Z',
  open: 'M14 3h7v7h-2V6.4l-8.3 8.3-1.4-1.4L17.6 5H14V3ZM5 5h6v2H6v11h11v-5h2v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z',
  reveal: 'M3 6a2 2 0 0 1 2-2h4.2l2 2H19a2 2 0 0 1 2 2v2H3V6Zm0 6h18v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6Zm9 1.5-3 3h2V20h2v-3.5h2l-3-3Z',
  check: 'M9.5 16.2 4.8 11.5l-1.4 1.4 6.1 6.1L21 7.5l-1.4-1.4L9.5 16.2Z',
  close: 'M6.4 5 12 10.6 17.6 5 19 6.4 13.4 12l5.6 5.6-1.4 1.4L12 13.4 6.4 19 5 17.6 10.6 12 5 6.4 6.4 5Z',
  plus: 'M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6V5Z',
  undo: 'M12.5 8c-2.6 0-5 1-6.9 2.6L2 7v9h9l-3.6-3.6c1.4-1.2 3.2-1.9 5.1-1.9 3.5 0 6.5 2.3 7.6 5.5l2.4-.8C21 11.9 17.1 8 12.5 8Z',
  refresh: 'M17.7 6.3A8 8 0 1 0 20 12h-2a6 6 0 1 1-1.8-4.2L13 11h8V3l-3.3 3.3Z',
  pdf: 'M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm7 1.5V9h5.5L13 3.5ZM7 13v5h1.5v-1.5h1a1.8 1.8 0 0 0 0-3.5H7Zm1.5 1.2h.9a.6.6 0 0 1 0 1.1h-.9v-1.1ZM12 13v5h1.6a2.5 2.5 0 0 0 0-5H12Zm1.5 1.2a1.3 1.3 0 0 1 0 2.6v-2.6ZM16 13v5h1.5v-2H19v-1.2h-1.5v-.6H19V13h-3Z',
  doc: 'M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm7 1.5V9h5.5L13 3.5ZM7 12v1.5h10V12H7Zm0 3v1.5h10V15H7Zm0 3v1.5h7V18H7Z',
  sheet: 'M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm7 1.5V9h5.5L13 3.5ZM7 12v8h10v-8H7Zm1.5 1.5h3v2h-3v-2Zm4.5 0h2.5v2H13v-2Zm-4.5 3.5h3v1.5h-3V17Zm4.5 0h2.5v1.5H13V17Z',
  slides: 'M3 4h18v12H3V4Zm2 2v8h14V6H5Zm6 11h2v2h4v2H7v-2h4v-2Z',
  image: 'M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Zm0 12.6V18h16v-3.4l-4-4-5 5-3-3-4 4ZM8.5 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z',
  text: 'M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm7 1.5V9h5.5L13 3.5ZM7 12v1.5h10V12H7Zm0 3v1.5h10V15H7Z',
  other: 'M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm7 1.5V9h5.5L13 3.5Z',
  warning: 'M12 2 1 21h22L12 2Zm-1 7h2v6h-2V9Zm0 8h2v2h-2v-2Z'
}

export function Icon({ name, size = 18, className }: { name: string; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" className={className} fill="currentColor">
      <path d={paths[name] ?? paths.other} fillRule="evenodd" />
    </svg>
  )
}

export function KindIcon({ kind, size = 22 }: { kind: Kind; size?: number }) {
  return (
    <span className={`kind-icon kind-${kind}`}>
      <Icon name={kind} size={size} />
    </span>
  )
}
