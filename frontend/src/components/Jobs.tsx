// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import { Square, Zap } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../lib/api'
import { fmt, secondsSince } from '../lib/format'
import { useApi } from '../lib/hooks'
import type { Job } from '../lib/types'
import { Button, Dialog, EmptyState, ErrorBanner, ProgressBar, StateBadge } from './ui'

const KIND_LABEL: Record<Job['kind'], string> = {
  train: 'Training',
  resume: 'Resume training',
  evaluate: 'Evaluation',
  record: 'Recording',
  record_demo: 'Demo recording',
  report: 'Report',
  benchmark: 'Throughput benchmark',
  reward_ensemble: 'Reward-model ensemble',
  tune: 'Tuning study',
}

export const FINAL_JOB_STATES = ['stopped', 'completed', 'failed', 'interrupted']

function jobProgress(job: Job): { value: number | null; text: string } {
  const p = (job.progress ?? {}) as Record<string, number | string | undefined>
  if (job.kind === 'train' || job.kind === 'resume') {
    const t = Number(p.transitions ?? 0)
    const target = Number(p.target_transitions ?? 0)
    const phase = p.phase ? ` · ${p.phase}` : ''
    return { value: target ? t / target : null, text: target ? `${fmt.int(t)} / ${fmt.int(target)} transitions${phase}` : `starting${phase}` }
  }
  if (job.kind === 'evaluate' && p.episodes_total) {
    return { value: Number(p.episodes_done) / Number(p.episodes_total), text: `${p.episodes_done} / ${p.episodes_total} episodes` }
  }
  return { value: null, text: job.state === 'queued' ? 'waiting for a free slot' : 'working…' }
}

export function JobRow({ job, onChanged }: { job: Job; onChanged?: () => void }) {
  const [confirmKill, setConfirmKill] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const prog = jobProgress(job)
  const heartbeat = secondsSince(job.heartbeat_at)
  const stalled = job.state === 'running' && heartbeat !== null && heartbeat > 60
  const stopWaiting = job.state === 'stop_requested'

  const act = async (path: string) => {
    setPending(true)
    setErr(null)
    try {
      await api.post(path)
      onChanged?.()
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setPending(false)
      setConfirmKill(false)
    }
  }

  return (
    <li className="rounded-md border border-line bg-bg/40 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <StateBadge state={job.state} labelOverride={job.state === 'running' && job.kind !== 'train' && job.kind !== 'resume' ? 'running' : undefined} />
          <span className="text-[13px] font-medium text-ink">{KIND_LABEL[job.kind]}</span>
          {job.run_id && (
            <Link to={`/runs/${job.run_id}`} className="num truncate text-xs text-accent hover:underline">
              {fmt.shortId(job.run_id)}
            </Link>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {['queued', 'starting', 'running'].includes(job.state) && (
            <Button size="sm" variant="ghost" icon={<Square className="size-3.5" />} pending={pending} onClick={() => act(`/api/jobs/${job.id}/stop`)}>
              {job.state === 'queued' ? 'Cancel' : 'Stop'}
            </Button>
          )}
          {stopWaiting && (
            <Button size="sm" variant="danger" icon={<Zap className="size-3.5" />} onClick={() => setConfirmKill(true)}>
              Force terminate
            </Button>
          )}
        </div>
      </div>
      {!FINAL_JOB_STATES.includes(job.state) && (
        <div className="mt-2.5 space-y-1.5">
          {prog.value !== null && <ProgressBar value={prog.value} label={`${KIND_LABEL[job.kind]} progress`} />}
          <div className="num flex flex-wrap justify-between gap-2 text-[11px] text-ink-3">
            <span>{prog.text}</span>
            <span>
              {job.pid ? `pid ${job.pid} · ` : ''}heartbeat {fmt.ago(job.heartbeat_at ?? job.started_at)}
            </span>
          </div>
          {stalled && <p className="text-[11px] text-warn">No heartbeat for over a minute. If the laptop slept, training pauses and resumes on wake.</p>}
          {stopWaiting && <p className="text-[11px] text-ink-3">Waiting for the worker to reach a safe boundary and write a checkpoint.</p>}
        </div>
      )}
      {job.error && FINAL_JOB_STATES.includes(job.state) && <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-bg p-2 text-[11px] text-ink-3">{job.error}</pre>}
      <ErrorBanner error={err} />
      <Dialog
        open={confirmKill}
        title="Force-terminate this worker?"
        onClose={() => setConfirmKill(false)}
        actions={
          <Button variant="danger" pending={pending} onClick={() => act(`/api/jobs/${job.id}/terminate`)}>
            Terminate
          </Button>
        }
      >
        <p>
          The worker did not stop cooperatively. Terminating skips the stop checkpoint; a training run can later resume from its
          latest periodic checkpoint. LunarLab verifies the process belongs to this job (PID, start time and command line) before
          terminating it.
        </p>
      </Dialog>
    </li>
  )
}

export function ActiveJobs({ compact = false, runId }: { compact?: boolean; runId?: string }) {
  const { data, error, reload } = useApi<Job[]>('/api/jobs?active=true', 2000)
  const jobs = (data ?? []).filter((j) => !runId || j.run_id === runId)
  if (error && !data) return <ErrorBanner error={error.message} onRetry={reload} />
  if (!data) return <div className="text-[13px] text-ink-3">Loading jobs…</div>
  if (!jobs.length)
    return compact ? (
      <p className="text-[13px] text-ink-3">No active jobs. Training runs in separate worker processes and keeps going if you close the browser.</p>
    ) : (
      <EmptyState title="No active jobs">Training, evaluation and recording jobs appear here while they run.</EmptyState>
    )
  return (
    <ul className="space-y-2">
      {jobs.map((j) => (
        <JobRow key={j.id} job={j} onChanged={reload} />
      ))}
    </ul>
  )
}

/** Follow a submitted job until it reaches a final state, then stop polling. */
export function useJobWatch(jobId: string | null, onDone?: (job: Job) => void): Job | null {
  const [job, setJob] = useState<Job | null>(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone
  useEffect(() => {
    setJob(null)
    if (!jobId) return
    let cancelled = false
    let timer: number | undefined
    const tick = async () => {
      try {
        const j = await api.get<Job>(`/api/jobs/${jobId}`)
        if (cancelled) return
        setJob(j)
        if (FINAL_JOB_STATES.includes(j.state)) {
          onDoneRef.current?.(j)
          return
        }
      } catch {
        /* transient: keep polling */
      }
      if (!cancelled) timer = window.setTimeout(tick, 800)
    }
    tick()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [jobId])
  return job
}
