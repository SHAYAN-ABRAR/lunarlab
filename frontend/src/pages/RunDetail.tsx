import { ArrowLeft, Camera, Download, FlaskConical, Play, ShieldCheck, Square } from 'lucide-react'
import { useMemo, useState } from 'react'
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

interface RunDetailData {
  summary: RunSummary
  config: { reward: RewardConfig; ppo: Record<string, unknown>; training: Record<string, unknown>; seed: number; eval_protocol: Record<string, unknown>; env_id: string; env_kwargs: Record<string, unknown> }
  config_hash: string
  rollout_size: number
  metadata: Record<string, unknown> & { segments: Record<string, unknown>[]; system: Record<string, unknown>; environment: Record<string, unknown>; frozen_for_test: { checkpoint: string; frozen_at: string } | null }
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
  useJobWatch(watch, () => {
    setWatch(null)
    onChanged()
  })

  const runId = d.summary.run_id
  const activeJob = d.jobs.find((j) => ['queued', 'starting', 'running', 'stop_requested'].includes(j.state))
  const statusRunning = d.status.state === 'running' && (secondsSince(d.status.updated_at) ?? 999) < 60
  const hasCkpt = d.manifest.checkpoints.length > 0
  const completed = d.manifest.checkpoints.some((c) => c.kind === 'final')
  const resumable = !completed && !activeJob && !statusRunning && d.manifest.checkpoints.some((c) => ['periodic', 'stop'].includes(c.kind))
  const neverStarted = !hasCkpt && !activeJob && !statusRunning && (d.metadata.segments ?? []).length === 0
  const hasBest = !!d.manifest.best_validation

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
          <Button variant="primary" icon={<Play className="size-4" />} pending={busy === 'resume'} onClick={() => call('resume', `/api/runs/${runId}/resume`, { checkpoint: 'latest', idempotency_key: idempotencyKey() })}>
            Resume from latest checkpoint
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
        <Button icon={<ShieldCheck className="size-4" />} disabled={!hasBest || !!activeJob} title={!hasBest ? 'Needs a validation-selected checkpoint' : undefined} onClick={() => setTestOpen(true)}>
          Final test…
        </Button>
        <Button icon={<Camera className="size-4" />} disabled={!hasCkpt || !!activeJob} title={!hasCkpt ? 'No checkpoint yet' : undefined} onClick={() => setRecOpen(true)}>
          Record flight…
        </Button>
        <a href={`/api/runs/${runId}/config.yaml`} className="inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm text-ink-2 hover:bg-surface-3 hover:text-ink">
          <Download className="size-4" aria-hidden /> config.yaml
        </a>
      </div>
      {watch && <p className="text-xs text-ink-3">Job submitted — progress appears under “Jobs for this run”.</p>}
      <ErrorBanner error={error} />
      <Dialog
        open={testOpen}
        title="Run the final test evaluation?"
        onClose={() => setTestOpen(false)}
        actions={
          <Button variant="primary" pending={busy === 'test'} onClick={() => { setTestOpen(false); call('test', `/api/runs/${runId}/evaluate`, { split: 'test', checkpoint: 'best', confirm_test: true, idempotency_key: idempotencyKey() }) }}>
            Freeze and evaluate
          </Button>
        }
      >
        <div className="space-y-2">
          <p>
            The validation-selected checkpoint ({d.manifest.best_validation?.name ?? '—'}, {fmt.int(d.manifest.best_validation?.transitions)} transitions) is evaluated on the{' '}
            {(d.config.eval_protocol.test_seeds as number[]).length} fixed test seeds with the original reward and a deterministic policy.
          </p>
          <p>The first test evaluation freezes this checkpoint for the run. Later test evaluations are flagged as repeats. Do not tune rewards or PPO settings on test results.</p>
          {d.metadata.frozen_for_test && <Notice tone="warn">Already frozen on {fmt.time(d.metadata.frozen_for_test.frozen_at)} with {d.metadata.frozen_for_test.checkpoint}. This will be a repeat evaluation.</Notice>}
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

function EvalRow({ e }: { e: EvalSummary }) {
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
            {smoke && <Badge tone="warn">SMOKE · technical test</Badge>}
          </div>
          <p className="num mt-1 truncate text-xs text-ink-3">
            {s.run_id} · config {d.config_hash} · reward {s.reward_hash}
          </p>
        </div>
      </div>
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
        </Card>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <Card title="Checkpoints" eyebrow="SHA-256 verified on load">
          <Table>
            <thead>
              <tr>
                <th>File</th>
                <th>Kind</th>
                <th className="text-right">Transitions</th>
                <th>SHA-256</th>
              </tr>
            </thead>
            <tbody>
              {d.manifest.checkpoints.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-ink-3">No checkpoints yet.</td>
                </tr>
              )}
              {d.manifest.checkpoints.map((c) => (
                <tr key={c.name}>
                  <td className="num text-xs">{c.name}</td>
                  <td>
                    <Badge tone={c.kind === 'best_validation' ? 'good' : c.kind === 'final' ? 'info' : 'neutral'}>{c.kind === 'best_validation' ? 'validation-selected' : c.kind}</Badge>
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
                    <OutcomeBadge outcome={r.env_outcome} pad={r.pad_landing} />
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
          <pre className="num mb-4 overflow-x-auto rounded-md border border-line bg-bg p-3 text-[12px] leading-relaxed text-ink-2">{formulaLines(cfg.reward, Number(cfg.ppo.gamma)).join('\n')}</pre>
          <div className="grid grid-cols-1 gap-x-8 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <div>
              {['n_envs', 'n_steps', 'batch_size', 'learning_rate', 'gamma', 'gae_lambda', 'n_epochs', 'ent_coef', 'clip_range'].map((k) => (
                <KV key={k} k={k} v={String(cfg.ppo[k])} />
              ))}
              <KV k="policy / value net" v={`${JSON.stringify(cfg.ppo.net_arch_pi)} / ${JSON.stringify(cfg.ppo.net_arch_vf)} ${String(cfg.ppo.activation)}`} />
            </div>
            <div>
              <KV k="environment" v={cfg.env_id} />
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
