// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import clsx from 'clsx'
import { PauseCircle, WifiOff } from 'lucide-react'
import { api } from '../lib/api'
import { useApi } from '../lib/hooks'
import type { SystemInfo } from '../lib/types'

function Meter({ label, value, text }: { label: string; value: number; text: string }) {
  const tone = value >= 90 ? 'bg-crit' : value >= 75 ? 'bg-warn' : 'bg-accent'
  return (
    <div>
      <div className="flex items-baseline justify-between text-[11px]">
        <span className="text-ink-3">{label}</span>
        <span className="num text-ink-2">{text}</span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-3" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(value)}>
        <div className={clsx('h-full rounded-full', tone)} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
    </div>
  )
}

/** CPU / RAM / disk / job status, polled every 5 s (modest frequency). */
export function SystemStatus() {
  const { data, error, reload } = useApi<SystemInfo>('/api/system', 5000)
  if (error && !data) {
    return (
      <div className="m-3 flex items-center gap-2 rounded-md border border-crit/40 bg-crit/10 px-3 py-2 text-xs text-ink-2" role="alert">
        <WifiOff className="size-4 text-crit" aria-hidden /> Backend unreachable
      </div>
    )
  }
  if (!data) return <div className="px-5 py-4 text-xs text-ink-3">Reading system status…</div>
  const running = (data.jobs.running ?? 0) + (data.jobs.starting ?? 0) + (data.jobs.stop_requested ?? 0)
  return (
    <div className="space-y-2.5 border-t border-line px-5 py-4" aria-label="System status">
      <div className="flex items-center justify-between text-[11px]">
        <span className="eyebrow">System</span>
        {error && <span className="text-warn">stale</span>}
      </div>
      <Meter label="CPU" value={data.cpu_percent} text={`${data.cpu_percent.toFixed(0)}% · ${data.cpu_count} threads`} />
      <Meter label="RAM" value={data.ram.percent} text={`${data.ram.used_gb.toFixed(1)} / ${data.ram.total_gb.toFixed(0)} GB`} />
      <Meter label="Disk" value={data.disk.percent} text={`${data.disk.free_gb.toFixed(0)} GB free`} />
      <div className="flex items-center justify-between pt-1 text-[11px]">
        <span className="text-ink-3">Jobs</span>
        <span className="num text-ink-2">
          {running} active · {data.jobs.queued ?? 0} queued
        </span>
      </div>
      {data.queue_paused && (
        <div className="rounded-md border border-warn/40 bg-warn/10 p-2 text-[11px] text-ink-2">
          <div className="flex items-center gap-1.5 font-medium text-warn">
            <PauseCircle className="size-3.5" aria-hidden /> Queue paused
          </div>
          <p className="mt-1">Jobs queued before the last restart are waiting.</p>
          <button
            type="button"
            className="mt-1.5 text-accent underline-offset-2 hover:underline"
            onClick={async () => {
              await api.post('/api/queue', { paused: false })
              reload()
            }}
          >
            Resume queue
          </button>
        </div>
      )}
    </div>
  )
}
