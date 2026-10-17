// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
// Tiny typed client. Every mutating request carries X-LunarLab: 1, which the backend requires
// (a custom header cannot be sent cross-origin without a CORS preflight the server never approves).
// In the static demo build (VITE_DEMO=1) requests are answered from exported snapshot files.

import { DEMO, demoRequest, demoUrl } from './demo'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(formatDetail(detail) || `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

function formatDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === 'object' && 'msg' in d) {
          const loc = 'loc' in d && Array.isArray(d.loc) ? d.loc.filter((x: unknown) => x !== 'body').join('.') : ''
          return loc ? `${loc}: ${String(d.msg)}` : String(d.msg)
        }
        return String(d)
      })
      .join('; ')
  }
  return detail ? JSON.stringify(detail) : ''
}

async function request<T>(method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  if (DEMO) {
    try {
      return await demoRequest<T>(method, path, body)
    } catch (e) {
      const err = e as Error & { status?: number; detail?: unknown }
      throw new ApiError(err.status ?? 0, err.detail ?? err.message)
    }
  }
  let res: Response
  try {
    res = await fetch(path, {
      method,
      signal,
      headers: body !== undefined ? { 'Content-Type': 'application/json', 'X-LunarLab': '1' } : { 'X-LunarLab': '1' },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    throw new ApiError(0, 'Cannot reach the LunarLab backend. Is it running? (scripts/start.ps1)')
  }
  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }
  if (!res.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? (data as { detail: unknown }).detail : data
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>('GET', path, undefined, signal),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
  text: async (path: string): Promise<string> => {
    const res = await fetch(path)
    if (!res.ok) throw new ApiError(res.status, await res.text())
    return res.text()
  },
}

/** URL for media and downloads (video, frames, files): the snapshot copy in the static demo. */
export function apiUrl(path: string): string {
  if (!DEMO) return path
  return demoUrl(path, path.endsWith('/video') ? 'mp4' : 'json')
}

export function idempotencyKey(): string {
  const a = new Uint8Array(8)
  crypto.getRandomValues(a)
  return 'ui-' + Array.from(a, (b) => b.toString(16).padStart(2, '0')).join('')
}
