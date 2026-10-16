export const fmt = {
  num(v: number | null | undefined, digits = 1): string {
    if (v === null || v === undefined || Number.isNaN(v)) return '—'
    const s = v.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
    return /^-0([.,]0+)?$/.test(s) ? s.slice(1) : s // −0.4 rounds to "0", not "-0"
  },
  signed(v: number | null | undefined, digits = 1): string {
    if (v === null || v === undefined || Number.isNaN(v)) return '—'
    const s = fmt.num(Math.abs(v), digits)
    return v > 0 ? `+${s}` : v < 0 ? `−${s}` : s
  },
  int(v: number | null | undefined): string {
    if (v === null || v === undefined || Number.isNaN(v)) return '—'
    return Math.round(v).toLocaleString()
  },
  pct(v: number | null | undefined, digits = 0): string {
    if (v === null || v === undefined || Number.isNaN(v)) return '—'
    return `${(v * 100).toFixed(digits)}%`
  },
  compact(v: number | null | undefined): string {
    if (v === null || v === undefined) return '—'
    if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(v % 1e6 === 0 ? 0 : 2)}M`
    if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(v % 1e3 === 0 ? 0 : 1)}k`
    return String(Math.round(v))
  },
  duration(seconds: number | null | undefined): string {
    if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—'
    const s = Math.max(0, Math.round(seconds))
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec = s % 60
    if (h) return `${h}h ${String(m).padStart(2, '0')}m`
    if (m) return `${m}m ${String(sec).padStart(2, '0')}s`
    return `${sec}s`
  },
  /** Timestamps are stored in UTC (ISO 8601) and shown in the viewer's local time. */
  time(iso: string | null | undefined): string {
    if (!iso) return '—'
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  },
  ago(iso: string | null | undefined): string {
    if (!iso) return '—'
    const s = (Date.now() - new Date(iso).getTime()) / 1000
    if (!Number.isFinite(s)) return '—'
    if (s < 5) return 'just now'
    if (s < 60) return `${Math.round(s)}s ago`
    if (s < 3600) return `${Math.round(s / 60)}m ago`
    if (s < 86400) return `${Math.round(s / 3600)}h ago`
    return `${Math.round(s / 86400)}d ago`
  },
  deg(rad: number): string {
    return `${((rad * 180) / Math.PI).toFixed(1)}°`
  },
  shortId(id: string): string {
    return id.length > 28 ? `${id.slice(0, 15)}…${id.slice(-11)}` : id
  },
}

export function secondsSince(iso: string | null | undefined): number | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  return Number.isFinite(t) ? (Date.now() - t) / 1000 : null
}
