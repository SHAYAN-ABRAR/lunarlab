// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import { ArrowLeft, Camera, Download, FlaskConical, GitBranch, Play, ShieldCheck, Square } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router'
import { LineChartPanel, Sparkline } from '../components/charts'
import { ActiveJobs, useJobWatch } from '../components/Jobs'
import {
  Badge,
  Button,
  Card,
  Dialog,
  EmptyState,
  ErrorBanner,
  EvidenceBadge,
  Field,
  KV,
  Notice,
  NumberInput,
  OutcomeBadge,
  ProgressBar,
  Spinner,
  Stat,
  StateBadge,
  Table,
} from '../components/ui'
import { api, idempotencyKey } from '../lib/api'
import { fmt, secondsSince } from '../lib/format'
import { useApi } from '../lib/hooks'
import { PRESET_COLOR, SERIES, formulaLines } from '../lib/reward'
import type { CheckpointEntry, CurvePoint, EvalSummary, Job, MetricRow, RecordingMeta, RunStatus, RunSummary, RewardConfig, ValidationPoint } from '../lib/types'

interface TestAttempt {
  attempt: number
  state: 'started' | 'completed' | 'interrupted' | 'failed'
  started_at: string
  ended_at?: string
  file?: string
  error?: string
}

interface TestStatus {
  frozen: boolean
  frozen_for_test: { checkpoint: string; frozen_at: string; artifact?: string; checkpoint_sha256: string } | null
  immutable_artifact: boolean
  attempts: TestAttempt[]
  completed: boolean
  completed_count: number
  last_state: string | null
  needs_retry: boolean
}

interface RunDetailData {
  summary: RunSummary
  config: {
    reward: RewardConfig
    ppo: Record<string, unknown>
    dqn?: Record<string, unknown> | null
    algo?: 'ppo' | 'dqn'
    training: Record<string, unknown>
    seed: number
    eval_protocol: Record<string, unknown>
    env_id: string
    env_kwargs: Record<string, unknown>
  }
  config_hash: string
  rollout_size: number
  metadata: Record<string, unknown> & { segments: Record<string, unknown>[]; system: Record<string, unknown>; environment: Record<string, unknown>; frozen_for_test: { checkpoint: string; frozen_at: string; artifact?: string } | null }
  test_status?: TestStatus
  warm_restart?: { preserved: string[]; reset: string[] }
  status: RunStatus
  manifest: { checkpoints: CheckpointEntry[]; best_validation: CheckpointEntry | null }
  evaluations: EvalSummary[]
  jobs: Job[]
  recordings: (RecordingMeta & { run_id: string })[]
}

function RunActions({ d, onChanged }: { d: RunDetailData; onChanged: () => void }) {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [testOpen, setTestOpen] = useState(false)
  const [recOpen, setRecOpen] = useState(false)
  const [seed, setSeed] = useState(20000)
  const [ckpt, setCkpt] = useState('best')
  const [watch, setWatch] = useState<string | null>(null)
  const [warmOpen, setWarmOpen] = useState(false)
  const [warmStart, setWarmStart] = useState(false)
  const [warmChild, setWarmChild] = useState<string | null>(null)
  useJobWatch(watch, () => {
    setWatch(null)
    onChanged()
  })

  const runId = d.summary.run_id
  const activeJob = d.jobs.find((j) => ['queued', 'starting', 'running', 'stop_requested'].includes(j.state))
  const statusRunning = d.status.state === 'running' && (secondsSince(d.status.updated_at) ?? 999) < 60
  const hasCkpt = d.manifest.checkpoints.length > 0
  const resume = d.summary.resume
  const idle = !activeJob && !statusRunning
  // The server decides whether a GENUINE resume is possible (frozen runs and DQN checkpoints without
  // replay state never resume); the worker checks again under the run lock.
  const resumable = idle && !!resume?.available
  const frozen = !!d.metadata.frozen_for_test
  const ts = d.test_status
  const neverStarted = !hasCkpt && idle && (d.metadata.segments ?? []).length === 0 && !frozen
  const hasBest = !!d.manifest.best_validation
  const warmAllowed = idle && hasCkpt && !!resume?.warm_restart_available

  const warmRestart = async () => {
    setBusy('warm')
    setError(null)
    try {
      const res = await api.post<{ run: { run_id: string }; job: Job | null }>(`/api/runs/${runId}/warm-restart`, {
        checkpoint: frozen ? 'frozen' : 'latest',
        confirm: true,
        start: warmStart,
        idempotency_key: idempotencyKey(),
      })
      setWarmOpen(false)
      setWarmChild(res.run.run_id)
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  const call = async (label: string, path: string, body?: unknown) => {
    setBusy(label)
    setError(null)
    try {
      const res = await api.post<Job | { job?: Job }>(path, body ?? {})
      const id = (res as Job).id ?? (res as { job?: Job }).job?.id
      if (id) setWatch(id)
      onChanged()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {neverStarted && (
          <Button variant="primary" icon={<Play className="size-4" />} pending={busy === 'train'} onClick={() => call('train', `/api/runs/${runId}/train`, { idempotency_key: idempotencyKey() })}>
            Start training
          </Button>
        )}
        {(activeJob || statusRunning) && (
          <Button variant="danger" icon={<Square className="size-4" />} pending={busy === 'stop'} disabled={activeJob?.state === 'stop_requested'} onClick={() => call('stop', `/api/runs/${runId}/stop`)}>
            {activeJob?.state === 'stop_requested' ? 'Stopping at safe boundary…' : activeJob?.state === 'queued' ? 'Cancel queued job' : 'Stop (writes checkpoint)'}
          </Button>
        )}
        {resumable && (
          <Button
            variant="primary"
            icon={<Play className="size-4" />}
            pending={busy === 'resume'}
            title={resume?.contract ? `Continues this run from ${resume.checkpoint}: ${resume.contract}` : undefined}
            onClick={() => call('resume', `/api/runs/${runId}/resume`, { checkpoint: 'latest', idempotency_key: idempotencyKey() })}
          >
            Resume from latest checkpoint
          </Button>
        )}
        {warmAllowed && (
          <Button icon={<GitBranch className="size-4" />} onClick={() => setWarmOpen(true)}>
            Warm restart as a new run…
          </Button>
        )}
        <Button
          icon={<FlaskConical className="size-4" />}
          disabled={!hasBest || !!activeJob}
          title={!hasBest ? 'Needs a validation-selected checkpoint (validation runs during training)' : activeJob ? 'Wait for the active job on this run' : undefined}
          pending={busy === 'val'}
          onClick={() => call('val', `/api/runs/${runId}/evaluate`, { split: 'validation', checkpoint: 'best', idempotency_key: idempotencyKey() })}
        >
          Evaluate (validation)
        </Button>
        <Button icon={<ShieldCheck className="size-4" />} disabled={(!hasBest && !frozen) || !!activeJob} title={!hasBest && !frozen ? 'Needs a validation-selected checkpoint' : undefined} onClick={() => setTestOpen(true)}>
          {ts?.needs_retry ? 'Retry final test…' : 'Final test…'}
        </Button>
        <Button icon={<Camera className="size-4" />} disabled={!hasCkpt || !!activeJob} title={!hasCkpt ? 'No checkpoint yet' : undefined} onClick={() => setRecOpen(true)}>
          Record flight…
        </Button>
        <a href={`/api/runs/${runId}/config.yaml`} className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm text-ink-2 hover:bg-surface-3 hover:text-ink">
          <Download className="size-4" aria-hidden /> config.yaml
        </a>
      </div>
      {watch && <p className="text-xs text-ink-3">Job submitted — progress appears under “Jobs for this run”.</p>}
      {warmChild && (
        <Notice tone="good" title="Warm restart created">
          New run <Link to={`/runs/${warmChild}`} className="num text-accent hover:underline">{warmChild}</Link>. It is compared separately from this run.
        </Notice>
      )}
      {resume?.reason === 'legacy_dqn' && idle && (
        <Notice tone="warn" title="Resume unavailable: this DQN checkpoint has no replay state">
          {resume.message}
        </Notice>
      )}
      {frozen && (
        <Notice tone="info" title="Frozen for the final test">
          Since {fmt.time(d.metadata.frozen_for_test!.frozen_at)} this run never trains again under its run ID; evaluation, recordings and replays use the frozen
          checkpoint {d.metadata.frozen_for_test!.checkpoint}
          {d.metadata.frozen_for_test!.artifact ? ` (immutable copy ${d.metadata.frozen_for_test!.artifact})` : ' (legacy record: no immutable copy yet, see freeze-migrate)'}.{' '}
          {ts?.completed
            ? `Final test completed${ts.completed_count > 1 ? ` (${ts.completed_count} evaluations)` : ''}.`
            : ts?.last_state
              ? `The last final-test attempt was ${ts.last_state}: no completed final test yet. Retry it on the same frozen checkpoint.`
              : 'No completed final test yet.'}
        </Notice>
      )}
      <ErrorBanner error={error} />
      <Dialog
        open={warmOpen}
        title="Create a warm restart?"
        onClose={() => setWarmOpen(false)}
        actions={
          <Button variant="primary" pending={busy === 'warm'} onClick={warmRestart}>
            Create new run
          </Button>
        }
      >
        <div className="space-y-3">
          <p>
            A warm restart is a <strong className="text-ink">new run</strong> whose networks start from {frozen ? 'the frozen checkpoint' : `checkpoint ${resume?.checkpoint ?? 'latest'}`} of this
            run. It is not a continuation: it gets its own run ID, its lineage is recorded, and comparisons keep it apart from uninterrupted runs.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <div className="eyebrow mb-1">Preserved</div>
              <ul className="list-disc space-y-0.5 pl-4 text-[13px] text-ink-2">{(d.warm_restart?.preserved ?? []).map((x) => <li key={x}>{x}</li>)}</ul>
            </div>
            <div>
              <div className="eyebrow mb-1">Reset</div>
              <ul className="list-disc space-y-0.5 pl-4 text-[13px] text-ink-2">{(d.warm_restart?.reset ?? []).map((x) => <li key={x}>{x}</li>)}</ul>
            </div>
          </div>
          {frozen && <Notice tone="warn">This run was frozen for its final test. Results of the new run on the same test seeds are exploratory, not a new held-out test.</Notice>}
          <label className="flex items-center gap-2 text-[13px] text-ink-2">
            <input type="checkbox" className="accent-[#3cc8d4]" checked={warmStart} onChange={(e) => setWarmStart(e.target.checked)} /> Start training the new run now
          </label>
        </div>
      </Dialog>
      <Dialog
        open={testOpen}
        title="Run the final test evaluation?"
        onClose={() => setTestOpen(false)}
        actions={
          <Button variant="primary" pending={busy === 'test'} onClick={() => { setTestOpen(false); call('test', `/api/runs/${runId}/evaluate`, { split: 'test', checkpoint: 'best', confirm_test: true, idempotency_key: idempotencyKey() }) }}>
            {frozen ? 'Evaluate the frozen checkpoint' : 'Freeze and evaluate'}
          </Button>
        }
      >
        <div className="space-y-2">
          <p>
            The validation-selected checkpoint ({d.manifest.best_validation?.name ?? '—'}, {fmt.int(d.manifest.best_validation?.transitions)} transitions) is evaluated on the{' '}
            {(d.config.eval_protocol.test_seeds as number[]).length} fixed test seeds with the original reward and a deterministic policy.
          </p>
          <p>
            The first test evaluation freezes this checkpoint: an immutable copy is kept, the run never trains again, and every later final-test evaluation, robustness
            evaluation and recording uses those exact bytes. Do not tune rewards or algorithm settings on test results.
          </p>
          {d.metadata.frozen_for_test && (
            <Notice tone="warn">
              Already frozen on {fmt.time(d.metadata.frozen_for_test.frozen_at)} with {d.metadata.frozen_for_test.checkpoint}.{' '}
              {ts?.needs_retry ? 'No final test has completed yet: this retries it on the same frozen checkpoint.' : 'This will be a repeat evaluation.'}
            </Notice>
          )}
          {d.summary.profile === 'smoke' && <Notice tone="warn">This is a SMOKE run: a technical test, not a trained agent.</Notice>}
        </div>
      </Dialog>
      <Dialog
        open={recOpen}
        title="Record one flight"
        onClose={() => setRecOpen(false)}
        actions={
          <Button variant="primary" pending={busy === 'rec'} onClick={() => { setRecOpen(false); call('rec', `/api/runs/${runId}/record`, { episode_seed: seed, checkpoint: ckpt, idempotency_key: idempotencyKey() }) }}>
            Record
          </Button>
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Episode seed" htmlFor="rec-seed" hint="20000 is the shared demonstration seed (first test seed).">
            <NumberInput id="rec-seed" value={seed} onChange={setSeed} min={0} step={1} />
          </Field>
          <Field label="Checkpoint" htmlFor="rec-ckpt">
            <select id="rec-ckpt" className="field" value={ckpt} onChange={(e) => setCkpt(e.target.value)}>
              {hasBest && <option value="best">validation-selected (best)</option>}
              {d.manifest.checkpoints.filter((c) => c.kind !== 'best_validation').map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} · {fmt.compact(c.transitions)}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <p className="mt-3 text-xs text-ink-3">The policy flies one deterministic episode in the unmodified environment. Real frames and telemetry are saved; recording runs in the analysis lane, not during training.</p>
      </Dialog>
    </div>
  )
}

function LegacyMark({ e }: { e: EvalSummary }) {
  if ((e.outcome_classifier_version ?? 1) >= 2) return null
  return (
    <span className="ml-1 text-warn" title="Recorded with outcome classifier v1. The stored file is unchanged; v2 categories are derived from its episode fields.">
      †
    </span>
  )
}

function EvalRow({ e }: { e: EvalSummary }) {
  const v2 = (e.outcome_classifier_version ?? 1) >= 2
  const onPad = v2 ? e.on_pad_not_strict_rate : e.derived_v2?.on_pad_not_strict_rate
  return (
    <tr>
      <td>
        <Badge tone={e.split === 'test' ? 'info' : 'neutral'}>{e.split}</Badge>
        {e.repeat_index ? <span className="ml-1 text-[11px] text-warn">repeat #{e.repeat_index + 1}</span> : null}
      </td>
      <td className="num text-xs">{e.checkpoint}</td>
      <td className="num text-right">{e.n_episodes}</td>
      <td className="num text-right">
        {fmt.num(e.mean_original_return, 1)}
        {e.ci && <span className="text-ink-3"> [{fmt.num(e.ci[0], 0)}, {fmt.num(e.ci[1], 0)}]</span>}
      </td>
      <td className="num text-right">{fmt.pct(e.score_rate)}</td>
      <td className="num text-right">{fmt.pct(e.env_success_rate)}</td>
      <td className="num text-right">{fmt.pct(e.pad_landing_rate)}</td>
      <td className="num text-right">
        {fmt.pct(onPad)}
        <LegacyMark e={e} />
      </td>
      <td className="num text-right">{fmt.pct(e.crash_rate)} / {fmt.pct(e.out_of_bounds_rate)} / {fmt.pct(e.timeout_rate)}</td>
      <td className="num text-right">{fmt.num(e.hover_fraction_mean, 3)}</td>
      <td className="text-xs text-ink-3">{fmt.time(e.created_at)}</td>
    </tr>
  )
}

export default function RunDetail() {
  const { runId = '' } = useParams()
  const base = `/api/runs/${encodeURIComponent(runId)}`
  const detail = useApi<RunDetailData>(base, 3000)
  const live = detail.data?.status.state === 'running'
  const curve = useApi<{ points: CurvePoint[]; window: number; n_episodes: number }>(`${base}/curve`, live ? 4000 : 20000)
  const metrics = useApi<MetricRow[]>(`${base}/metrics`, live ? 5000 : 30000)
  const validation = useApi<ValidationPoint[]>(`${base}/validation`, live ? 5000 : 30000)
  const events = useApi<{ time: string; level: string; message: string }[]>(`${base}/events?limit=120`, live ? 4000 : 20000)
  const latestJob = detail.data?.jobs[0]
  // A short job can start and finish between two status polls, so `live` never turns on: refresh the run's
  // records whenever its state or its latest job changes, or the event log and charts lag by up to 20-30 s.
  const changeKey = `${detail.data?.status.state ?? ''}|${latestJob?.id ?? ''}|${latestJob?.state ?? ''}`
  const { reload: reloadEvents } = events
  const { reload: reloadCurve } = curve
  const { reload: reloadMetrics } = metrics
  const { reload: reloadValidation } = validation
  useEffect(() => {
    reloadEvents()
    reloadCurve()
    reloadMetrics()
    reloadValidation()
  }, [changeKey, reloadEvents, reloadCurve, reloadMetrics, reloadValidation])

  const curvePts = useMemo(() => curve.data?.points ?? [], [curve.data])
  const valPts = useMemo(() => (validation.data ?? []).map((v) => ({ ...v })), [validation.data])

  if (detail.error && !detail.data) return <ErrorBanner error={detail.error.status === 404 ? `Run ${runId} not found.` : detail.error.message} onRetry={detail.reload} />
  if (!detail.data) return <Spinner label="Loading run" />
  const d = detail.data
  const s = d.summary
  const st = d.status
  const cfg = d.config
  const smoke = s.profile === 'smoke'
  const eta = st.throughput_tps && st.target_transitions && st.transitions && live ? (st.target_transitions - st.transitions) / st.throughput_tps : null
  const stale = live && (secondsSince(st.updated_at) ?? 0) > 60

  return (
    <>
      <Link to="/training" className="mb-3 inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> Training Console
      </Link>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-block size-3 rounded-full" style={{ background: PRESET_COLOR[s.reward_preset] }} aria-hidden />
            <h1 className="text-xl font-semibold">{s.reward_name}</h1>
            <span className="text-ink-3">· seed {s.seed}</span>
            <StateBadge state={st.state ?? s.state} />
            <EvidenceBadge evidence={s.evidence} />
            {s.evidence_role === 'exploratory' && (
              <span title={s.evidence_note ?? undefined}>
                <Badge tone="warn">exploratory</Badge>
              </span>
            )}
            {s.protocol_valid === false && <Badge tone="crit">invalid protocol</Badge>}
            {smoke && <Badge tone="warn">SMOKE · technical test</Badge>}
          </div>
          <p className="num mt-1 truncate text-xs text-ink-3">
            {s.run_id} · config {d.config_hash} · reward {s.reward_hash}
          </p>
        </div>
      </div>
      {s.lineage && (
        <div className="mb-4">
          <Notice tone={s.lineage.post_test ? 'warn' : 'info'} title={`Warm restart of ${s.lineage.parent_run_id}`}>
            Initialised from <Link to={`/runs/${s.lineage.parent_run_id}`} className="text-accent hover:underline">{s.lineage.parent_checkpoint}</Link> of that run. Preserved:{' '}
            {s.lineage.preserved.join('; ')}. Reset: {s.lineage.reset.join('; ')}. {s.lineage.note}
          </Notice>
        </div>
      )}
      {s.protocol_valid === false && (
        <div className="mb-4">
          <Notice tone="warn" title="Invalid evaluation protocol">
            {(s.protocol_problems ?? []).join(' ')} This run can be inspected but not trained or evaluated.
          </Notice>
        </div>
      )}
      {smoke && (
        <div className="mb-4">
          <Notice tone="warn" title="SMOKE profile">
            About 8k transitions to verify the pipeline: training, checkpoints, validation, evaluation, recording. A smoke-trained model is not evidence that the landing task is solved.
          </Notice>
        </div>
      )}
      {stale && (
        <div className="mb-4">
          <Notice tone="warn" title="No recent heartbeat">
            The worker has not reported for {fmt.duration(secondsSince(st.updated_at))}. If the laptop slept, training resumes on wake; if the worker died, the supervisor marks it interrupted and you can resume from the latest checkpoint.
          </Notice>
        </div>
      )}

      <Card className="mb-6" bodyClassName="p-5 space-y-5">
        <RunActions d={d} onChanged={detail.reload} />
        <div>
          <ProgressBar value={(st.transitions ?? s.checkpoint_transitions) / (st.target_transitions ?? s.planned_transitions)} label="Training progress" />
          <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 xl:grid-cols-6">
            <Stat testId="transitions" label="Transitions" value={fmt.int(st.transitions ?? s.checkpoint_transitions)} sub={`of ${fmt.int(st.target_transitions ?? s.planned_transitions)} (requested ${fmt.int(s.requested_transitions)})`} />
            <Stat label="Elapsed (segment)" value={fmt.duration(st.elapsed_s)} sub={eta ? `ETA ${fmt.duration(eta)}` : st.phase ? `phase: ${st.phase}` : undefined} />
            <Stat label="Throughput" value={st.throughput_tps ? `${fmt.int(st.throughput_tps)}/s` : '—'} sub="measured transitions per second" />
            <Stat label="Episodes" value={fmt.int(st.episodes)} sub={st.recent_window ? `last ${st.recent_window} below` : undefined} />
            <Stat label="Recent original return" value={fmt.num(st.recent_original_return_mean, 1)} sub={`training return ${fmt.num(st.recent_training_return_mean, 1)}`} />
            <Stat label="Recent pad landing" value={fmt.pct(st.recent_pad_landing_rate)} sub={`time-limit ${fmt.pct(st.recent_timeout_rate)} · length ${fmt.num(st.recent_mean_length, 0)}`} />
          </div>
          {st.process && live && <p className="num mt-3 text-[11px] text-ink-3">worker pid {st.pid} · CPU {st.process.cpu_percent.toFixed(0)}% · RSS {st.process.rss_mb.toFixed(0)} MB · heartbeat {fmt.ago(st.updated_at)}</p>}
          {st.error && <div className="mt-3"><ErrorBanner error={st.error} /></div>}
        </div>
      </Card>

      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Episode return during training" eyebrow={`rolling mean of ${curve.data?.window ?? 100} training episodes`}>
          <LineChartPanel
            ariaLabel="Original and training episode return versus environment transitions"
            data={curvePts as unknown as Record<string, number>[]}
            x="transitions"
            xLabel="transitions"
            series={[
              { key: 'original_return', label: 'Original return (environment reward)', color: SERIES.original },
              ...(s.active_terms.length ? [{ key: 'training_return', label: 'Training return (what PPO optimised)', color: SERIES.shaped, dashed: true }] : []),
            ]}
            refY={[{ y: 200, label: '200' }]}
            emptyText="No completed training episodes yet."
          />
          <p className="mt-2 text-xs text-ink-3">
            {s.active_terms.length
              ? 'Training return includes the additional reward terms, so it is on a different scale from the original return. SB3’s own ep_rew_mean would show the training return.'
              : 'Original reward only: training return equals original return.'}{' '}
            Training episodes use a stochastic policy; validation below is deterministic.
          </p>
        </Card>
        <Card title="Validation (original reward, deterministic)" eyebrow={`${(cfg.eval_protocol.validation_seeds as number[]).length} fixed seeds · selects the checkpoint`}>
          <LineChartPanel
            ariaLabel="Validation mean original return versus transitions"
            data={valPts as unknown as Record<string, number>[]}
            x="transitions"
            xLabel="transitions"
            series={[{ key: 'mean_original_return', label: 'Validation mean original return', color: SERIES.original }]}
            refY={[{ y: 200, label: '200' }]}
            refX={d.manifest.best_validation ? [{ x: d.manifest.best_validation.transitions, label: 'selected' }] : undefined}
            emptyText="Validation runs at the start and every few rollouts."
          />
          <p className="mt-2 text-xs text-ink-3">The validation-selected checkpoint maximises mean original return on validation seeds; shaped reward never selects checkpoints.</p>
        </Card>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Behaviour during training" eyebrow="rolling rates over training episodes">
          <LineChartPanel
            ariaLabel="Pad landing, time-limit and hover rates during training"
            data={curvePts as unknown as Record<string, number>[]}
            x="transitions"
            xLabel="transitions"
            yFormat={(v) => fmt.pct(v)}
            yDomain={[0, 1]}
            series={[
              { key: 'pad_landing_rate', label: 'Strict pad landing', color: '#3987e5' },
              { key: 'timeout_rate', label: 'Time limit reached', color: '#d95926' },
              { key: 'hover_fraction', label: 'Hover fraction (detector)', color: '#199e70' },
            ]}
            emptyText="No completed training episodes yet."
          />
        </Card>
        <Card title="PPO diagnostics" eyebrow="per update (SB3 logger values)">
          {(metrics.data ?? []).length === 0 ? (
            <EmptyState title="No PPO updates yet">Diagnostics appear after the first rollout of {fmt.int(d.rollout_size)} transitions.</EmptyState>
          ) : (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-2 2xl:grid-cols-3">
              <Sparkline data={metrics.data as unknown as Record<string, number>[]} x="transitions" y="approx_kl" label="approx KL" format={(v) => v.toFixed(4)} />
              <Sparkline data={metrics.data as unknown as Record<string, number>[]} x="transitions" y="clip_fraction" label="clip fraction" />
              <Sparkline data={metrics.data as unknown as Record<string, number>[]} x="transitions" y="entropy_loss" label="entropy loss (−entropy)" />
              <Sparkline data={metrics.data as unknown as Record<string, number>[]} x="transitions" y="value_loss" label="value loss" format={(v) => v.toFixed(1)} />
              <Sparkline data={metrics.data as unknown as Record<string, number>[]} x="transitions" y="explained_variance" label="explained variance" />
              <Sparkline data={metrics.data as unknown as Record<string, number>[]} x="transitions" y="learning_rate" label="learning rate" format={(v) => v.toExponential(1)} />
            </div>
          )}
        </Card>
      </div>

      <div className="mb-6">
        <Card title="Evaluations" eyebrow="original reward · fixed seeds · deterministic policy">
          {d.evaluations.length === 0 ? (
            <EmptyState title="Not evaluated yet">Use “Evaluate (validation)” for a quick check or “Final test” once training is finished.</EmptyState>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Split</th>
                  <th>Checkpoint</th>
                  <th className="text-right">Eps</th>
                  <th className="text-right">Mean return [95% CI]</th>
                  <th className="text-right">≥200</th>
                  <th className="text-right">At rest</th>
                  <th className="text-right">Pad</th>
                  <th className="text-right" title="Came to rest with both legs between the flags but failed another strict criterion (angle or leg contact)">On pad, not strict</th>
                  <th className="text-right">Crash / OOB / limit</th>
                  <th className="text-right">Hover</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {d.evaluations.toReversed().map((e) => (
                  <EvalRow key={e.file} e={e} />
                ))}
              </tbody>
            </Table>
          )}
          {d.evaluations.some((e) => (e.outcome_classifier_version ?? 1) < 2) && (
            <p className="mt-2 text-xs text-ink-3">
              † Legacy outcome metric: evaluated with outcome classifier v1, which called any clean at-rest landing that was not a strict pad landing “off pad”, even on the pad.
              The stored result is unchanged; the value shown is derived from its episode fields (v1 did not store leg positions).
            </p>
          )}
          {d.test_status && d.test_status.attempts.length > 0 && (
            <p className="mt-2 text-xs text-ink-3">
              Final-test attempts: {d.test_status.attempts.map((a) => `#${a.attempt + 1} ${a.state}`).join(' · ')}
            </p>
          )}
        </Card>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <Card title="Checkpoints" eyebrow="SHA-256 verified on load">
          <Table>
            <thead>
              <tr>
                <th>File</th>
                <th>Kind</th>
                <th>Use</th>
                <th className="text-right">Transitions</th>
                <th>SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {d.manifest.checkpoints.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-ink-3">No checkpoints yet.</td>
                </tr>
              )}
              {d.manifest.checkpoints.map((c) => (
                <tr key={c.name}>
                  <td className="num text-xs">{c.name}</td>
                  <td>
                    {c.kind === 'best_validation' && c.name !== d.manifest.best_validation?.name ? (
                      <span title="Selected by an earlier validation; a later checkpoint scored higher. Kept unchanged (checkpoint files are never rewritten).">
                        <Badge tone="neutral">earlier best</Badge>
                      </span>
                    ) : (
                      <Badge tone={c.kind === 'best_validation' ? 'good' : c.kind === 'final' ? 'info' : 'neutral'}>{c.kind === 'best_validation' ? 'validation-selected' : c.kind}</Badge>
                    )}
                  </td>
                  <td className="text-xs text-ink-2" title={c.continuation?.contract}>
                    {c.usable_as ?? '—'}
                  </td>
                  <td className="num text-right">{fmt.int(c.transitions)}</td>
                  <td className="num text-[11px] text-ink-3" title={c.sha256}>{c.sha256.slice(0, 10)}…</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
        <div className="min-w-0 space-y-6">
        <Card title="Recorded flights">
          {d.recordings.length === 0 ? (
            <EmptyState title="No flights recorded">Record an episode of a checkpoint to replay it with synchronized telemetry.</EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {d.recordings.map((r) => (
                <li key={r.recording_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                  <Link to={`/replay/${r.recording_id}`} className="text-[13px] text-accent hover:underline">
                    Seed {r.episode_seed} · {String(r.source.checkpoint ?? '')}
                  </Link>
                  <div className="flex items-center gap-2">
                    <OutcomeBadge outcome={r.env_outcome} pad={r.pad_landing} category={r.landing_category} />
                    <span className="num text-xs text-ink-2">{fmt.num(r.original_return, 1)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Jobs for this run">
          <ActiveJobs compact runId={s.run_id} />
          {latestJob && ['failed', 'interrupted', 'stopped', 'completed'].includes(latestJob.state) && (
            <div className="mt-3 text-xs text-ink-3">
              Last job: {latestJob.kind} — <StateBadge state={latestJob.state} /> {fmt.time(latestJob.finished_at)}
              {latestJob.error && <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-bg p-2 text-[11px]">{latestJob.error}</pre>}
            </div>
          )}
        </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card title="Configuration" eyebrow="exact config.yaml of this run">
          <pre className="num mb-4 overflow-x-auto rounded-md border border-line bg-bg p-3 text-[12px] leading-relaxed text-ink-2">{formulaLines(cfg.reward, Number(cfg.algo === 'dqn' && cfg.dqn ? cfg.dqn.gamma : cfg.ppo.gamma)).join('\n')}</pre>
          <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <div>
              <KV k="algorithm" v={(cfg.algo ?? 'ppo').toUpperCase()} />
              {cfg.algo === 'dqn' && cfg.dqn ? (
                Object.entries(cfg.dqn).map(([k, v]) => <KV key={k} k={k} v={Array.isArray(v) ? JSON.stringify(v) : String(v)} />)
              ) : (
                <>
                  {['n_envs', 'n_steps', 'batch_size', 'learning_rate', 'gamma', 'gae_lambda', 'n_epochs', 'ent_coef', 'clip_range'].map((k) => (
                    <KV key={k} k={k} v={String(cfg.ppo[k])} />
                  ))}
                  <KV k="policy / value net" v={`${JSON.stringify(cfg.ppo.net_arch_pi)} / ${JSON.stringify(cfg.ppo.net_arch_vf)} ${String(cfg.ppo.activation)}`} />
                </>
              )}
            </div>
            <div>
              <KV k="environment" v={cfg.env_id} />
              <KV k="training physics" v={d.summary.physics_label ?? 'fixed (default physics)'} mono={false} />
              <KV k="action space" v={cfg.env_kwargs.continuous ? 'continuous' : 'discrete (4 actions)'} />
              <KV k="max episode steps" v={String(d.metadata.environment?.max_episode_steps ?? '—')} />
              <KV k="training seed" v={String(cfg.seed)} />
              <KV k="worker seeds (seg. 0)" v={String(((d.metadata.segments[0]?.worker_seeds as number[]) ?? []).join(', ') || '—')} />
              <KV k="device · vec env" v={`${String(cfg.training.device)} · ${String(cfg.training.vec_env)}`} />
              <KV k="checkpoint / validation every" v={`${fmt.compact(Number(cfg.training.checkpoint_every))} / ${fmt.compact(Number(cfg.training.validation_every))}`} />
              <KV k="eval protocol" v={String(cfg.eval_protocol.protocol_id)} />
            </div>
          </div>
          <details className="mt-4 text-[13px]">
            <summary className="cursor-pointer text-ink-2">Lineage and system</summary>
            <div className="mt-2 space-y-2">
              {(d.metadata.segments ?? []).map((seg) => (
                <div key={String(seg.index)} className="rounded border border-line p-2 text-xs text-ink-2">
                  <div className="num">
                    segment {String(seg.index)} · {String(seg.kind)} · {fmt.int(Number(seg.start_transitions))} → {seg.end_transitions !== undefined ? fmt.int(Number(seg.end_transitions)) : '…'} · {String(seg.end_state ?? 'running')}
                  </div>
                  {seg.parent_checkpoint ? <div className="num text-ink-3">parent checkpoint {String(seg.parent_checkpoint)}</div> : null}
                  {seg.discarded_interactions ? (
                    <div className="num text-ink-3">
                      {fmt.int(Number(seg.discarded_interactions))} environment interaction(s) after the last safe boundary were discarded at the stop (not trained on)
                    </div>
                  ) : null}
                </div>
              ))}
              <pre className="num max-h-60 overflow-auto rounded bg-bg p-2 text-[11px] text-ink-3">{JSON.stringify({ system: d.metadata.system }, null, 1)}</pre>
            </div>
          </details>
        </Card>
        <Card title="Event log">
          <ol className="num max-h-[420px] space-y-1 overflow-auto text-[11.5px]" aria-live="polite">
            {(events.data ?? []).toReversed().map((e, i) => (
              <li key={i} className="flex gap-3">
                <span className="shrink-0 text-ink-3">{new Date(e.time).toLocaleTimeString()}</span>
                <span className={e.level === 'error' ? 'text-crit' : e.level === 'warning' ? 'text-warn' : 'text-ink-2'}>{e.message}</span>
              </li>
            ))}
            {!events.data?.length && <li className="text-ink-3">No events.</li>}
          </ol>
        </Card>
      </div>
    </>
  )
}
