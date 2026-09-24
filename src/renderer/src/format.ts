const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
const dateFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

export function when(epochSeconds: number): string {
  const days = Math.round((epochSeconds * 1000 - Date.now()) / 86_400_000)
  if (days > -1) return 'Today'
  if (days > -7) return rtf.format(days, 'day')
  return dateFmt.format(new Date(epochSeconds * 1000))
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB']
  let v = n / 1024
  let u = 0
  while (v >= 1024 && u < units.length - 1) {
    v /= 1024
    u++
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[u]}`
}

/** "C:\Users\ada\Downloads\Receipts" -> "Downloads › Receipts" */
export function shortFolder(folder: string, roots: string[]): string {
  const norm = (p: string): string => p.replace(/\\/g, '/').replace(/\/$/, '')
  const f = norm(folder)
  const root = roots.map(norm).find((r) => f === r || f.startsWith(r + '/'))
  const rel = root ? root.split('/').pop() + f.slice(root.length) : f.split('/').slice(-2).join('/')
  return rel.split('/').filter(Boolean).join(' › ')
}

export const kindLabel: Record<string, string> = {
  pdf: 'PDF',
  doc: 'Word',
  sheet: 'Spreadsheet',
  slides: 'Slides',
  image: 'Image',
  text: 'Text',
  other: 'File'
}
