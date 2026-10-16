// Static demo mode (VITE_DEMO=1): the UI reads a snapshot of real API responses exported by
// `python -m lunarlab export-demo` instead of talking to a backend. Nothing is computed or stored.
// File names follow lunarlab/demo.py (demo_name / compare_key); keep the two in sync.

export const DEMO = import.meta.env.VITE_DEMO === '1'

export const DEMO_MESSAGE =
  'Not available in the static demo: it shows a snapshot of real results. Training, recording, flying and saving labels need the local app (see the README).'

const ROOT = `${import.meta.env.BASE_URL}demo-api/`

export function demoName(path: string): string {
  const p = path.replace(/^\/api\//, '')
  let out = ''
  for (const ch of p) out += /^[A-Za-z0-9.-]$/.test(ch) ? ch : `_${ch.charCodeAt(0).toString(16).padStart(2, '0')}`
  return out
}

export function fnv1a(text: string): string {
  let h = 0x811c9dc5
  for (const b of new TextEncoder().encode(text)) {
    h ^= b
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}

export function demoUrl(path: string, ext = 'json'): string {
  return `${ROOT}${demoName(path)}.${ext}`
}

export interface DemoManifest {
  created_at: string
  commit: string | null
  experiments: string[]
  runs: number
  recordings: number
  preference_pairs: Record<string, number>
  hardware: string | null
}

let manifest: Promise<DemoManifest> | null = null
export function demoManifest(): Promise<DemoManifest> {
  manifest ??= fetch(`${ROOT}demo.json`).then((r) => {
    if (!r.ok) throw new Error(`demo manifest: HTTP ${r.status}`)
    return r.json() as Promise<DemoManifest>
  })
  return manifest
}

async function file<T>(url: string, missing: string): Promise<T> {
  const res = await fetch(url)
  if (res.status === 404) throw Object.assign(new Error(missing), { status: 404, detail: missing })
  if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status}`), { status: res.status, detail: null })
  return (await res.json()) as T
}

interface DemoPair {
  dataset_id: string
  demo_reveal: { returns: { a: number; b: number }; sources: { a: string; b: string }; reward_prefers: 'a' | 'b' | 'tie' }
}

const lastPair = new Map<string, DemoPair>()
let labels = 0

/** The demo counterpart of one API request. Errors carry .status like ApiError (wrapped by the caller). */
export async function demoRequest<T>(method: string, path: string, body?: unknown): Promise<T> {
  const pair = /^\/api\/preferences\/([^/]+)\/pair(\?.*)?$/.exec(path)
  if (method === 'GET' && pair) {
    const n = (await demoManifest()).preference_pairs[pair[1]] ?? 0
    if (!n) throw Object.assign(new Error('No demo pairs for this dataset.'), { status: 404, detail: null })
    const base = path.replace(/\?.*$/, '')
    const p = await file<DemoPair>(`${ROOT}${demoName(base)}-${Math.floor(Math.random() * n)}.json`, 'Missing demo pair.')
    lastPair.set(p.dataset_id, p)
    return p as T
  }
  if (method === 'GET') return file<T>(demoUrl(path), 'Not part of the static demo snapshot.')

  const label = /^\/api\/preferences\/([^/]+)\/labels$/.exec(path)
  if (method === 'POST' && label) {
    const p = lastPair.get(label[1])
    const choice = (body as { choice: string }).choice
    if (!p) throw Object.assign(new Error('Load a pair first.'), { status: 400, detail: null })
    labels += 1
    const r = p.demo_reveal
    return { ...r, agrees: choice === r.reward_prefers, n_labels: labels, entry: null } as T
  }
  if (method === 'POST' && path === '/api/compare') {
    const b = body as { run_ids: string[]; split: string }
    const key = fnv1a(`${b.split}:${b.run_ids.toSorted().join(',')}`)
    return file<T>(`${ROOT}compare/${key}.json`, 'The static demo includes comparisons of each published experiment: pick one in the selector above.')
  }
  throw Object.assign(new Error(DEMO_MESSAGE), { status: 0, detail: DEMO_MESSAGE })
}
