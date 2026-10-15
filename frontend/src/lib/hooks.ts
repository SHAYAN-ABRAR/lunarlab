import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from './api'
import { DEMO } from './demo'

export interface Resource<T> {
  data: T | undefined
  error: ApiError | null
  loading: boolean
  reload: () => void
}

/**
 * Fetch a resource and optionally poll it. Polling pauses while the tab is hidden, so an
 * unattended browser never hammers the backend. Training never depends on the browser.
 */
export function useApi<T>(path: string | null, pollMsLive?: number): Resource<T> {
  const pollMs = DEMO ? undefined : pollMsLive // a static snapshot never changes
  const [data, setData] = useState<T | undefined>(undefined)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState<boolean>(path !== null)
  const [nonce, setNonce] = useState(0)
  const pathRef = useRef(path)

  useEffect(() => {
    if (pathRef.current !== path) {
      pathRef.current = path
      setData(undefined)
      setError(null)
    }
    if (!path) {
      setLoading(false)
      return
    }
    let cancelled = false
    let timer: number | undefined
    const ctrl = new AbortController()

    const load = async () => {
      if (document.hidden && pollMs) {
        timer = window.setTimeout(load, pollMs)
        return
      }
      try {
        const d = await api.get<T>(path, ctrl.signal)
        if (!cancelled) {
          setData(d)
          setError(null)
        }
      } catch (e) {
        if (!cancelled && (e as Error).name !== 'AbortError') setError(e as ApiError)
      } finally {
        if (!cancelled) setLoading(false)
        if (!cancelled && pollMs) timer = window.setTimeout(load, pollMs)
      }
    }
    setLoading(true)
    load()
    return () => {
      cancelled = true
      ctrl.abort()
      if (timer) window.clearTimeout(timer)
    }
  }, [path, pollMs, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])
  return { data, error, loading, reload }
}

/** Run an async action with pending/error state (for buttons). */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      setPending(true)
      setError(null)
      try {
        return await fn(...args)
      } catch (e) {
        setError((e as Error).message)
        return undefined
      } finally {
        setPending(false)
      }
    },
    [fn],
  )
  return { run, pending, error, clearError: () => setError(null) }
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const on = () => setReduced(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return reduced
}
