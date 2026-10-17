// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import clsx from 'clsx'
import { Brain, Equal, Network, SkipForward } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Legend } from '../components/charts'
import { useJobWatch } from '../components/Jobs'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Notice, NumberInput, PageHeader, Segmented, Spinner, Table } from '../components/ui'
import { api, idempotencyKey } from '../lib/api'
import { DEMO } from '../lib/demo'
import { fmt } from '../lib/format'
import { useApi, usePrefersReducedMotion } from '../lib/hooks'
import type { Experiment, Job } from '../lib/types'

interface Dataset {
  dataset_id: string
  created_at: string
  n_segments: number
  segment_len: number
  sources: string[]
  human_labels: number
  segment_return: { mean: number; std: number; min: number; max: number }
}

interface Segment {
  index: number
  episode_seed: number
  obs: number[][]
  actions: number[]
  terminal: boolean
  scene: {
    terrain: [number, number][]
    helipad: { x1: number; x2: number; y: number }
    world: { width: number; height: number; fps: number }
    obs_to_world: { x_scale: number; x_offset: number; y_scale: number; y_offset: number }
  }
}

type Strategy = 'random' | 'disagreement'

interface Progress {
  labels: number
  usable_for_training: number
  in_validation_episodes: number
  excluded: number
  training_segments: number
  possible_pairs: number
  since_ensemble: number | null
  ensemble: { model_id: string; created_at: string; members: number; n_human_labels: number; n_simulated_pairs: number; metrics: { val_accuracy_vs_true_order: number | null } } | null
  strategies: Record<Strategy, boolean>
}

interface CurvePointAgg {
  labels: number
  mean: number
  min: number
  max: number
  n_seeds: number
}

interface ActiveStudy {
  study_id: string
  created_at: string
  strategies: string[]
  seeds: number[]
  params: { budget?: number; initial?: number; batch?: number; members?: number; candidates?: number }
  summary: Record<string, CurvePointAgg[]>
}

const STRATEGY_COLOR: Record<string, string> = { random: '#8494a8', disagreement: '#3987e5' }

interface Pair {
  dataset_id: string
  i: number
  j: number
  a: Segment
  b: Segment
  strategy?: Strategy
  score?: number | null
  candidates?: number
  median_score?: number
}

interface Reveal {
  returns: { a: number; b: number }
  sources: { a: string; b: string }
  reward_prefers: 'a' | 'b' | 'tie'
  agrees: boolean
  n_labels: number
}

interface RewardModelMeta {
  model_id: string
  created_at: string
  dataset_id: string
  n_pairs_requested: number
  n_train_pairs: number
  n_human_labels: number
  n_human_excluded?: number
  split?: { method: string; train_episodes: number; val_episodes: number }
  beta: number
  architecture: string
  metrics: {
    val_accuracy_vs_labels: number
    val_accuracy_vs_true_order: number
    label_noise_agreement: number
    step_reward_correlation: number
    segment_return_correlation: number
  }
}

// --------------------------------------------------------------------------- //
// A 2-D flight segment, drawn from its telemetry on the episode's real terrain
// --------------------------------------------------------------------------- //

const HULL: [number, number][] = [[-14, 17], [-17, 0], [-17, -10], [17, -10], [17, 0], [14, 17]].map(([x, y]) => [x / 30, y / 30])

function SegmentCanvas({ seg, label, slow }: { seg: Segment; label: string; slow: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const reduced = usePrefersReducedMotion()

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const W = canvas.clientWidth
    const H = canvas.clientHeight
    canvas.width = W * dpr
    canvas.height = H * dpr
    const { world, terrain, helipad, obs_to_world: o } = seg.scene
    const sx = W / world.width
    const sy = H / world.height
    const px = (x: number) => x * sx
    const py = (y: number) => H - y * sy
    const toWorld = (ob: number[]) => [ob[0] * o.x_scale + o.x_offset, ob[1] * o.y_scale + o.y_offset] as const
    const L = seg.actions.length

    const draw = (k: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.fillStyle = '#05080d'
      ctx.fillRect(0, 0, W, H)
      // terrain
      ctx.beginPath()
      ctx.moveTo(px(terrain[0][0]), H)
      for (const [x, y] of terrain) ctx.lineTo(px(x), py(y))
      ctx.lineTo(px(terrain[terrain.length - 1][0]), H)
      ctx.closePath()
      ctx.fillStyle = '#2a2f37'
      ctx.fill()
      ctx.strokeStyle = '#4b5563'
      ctx.lineWidth = 1
      ctx.stroke()
      // pad flags
      for (const fx of [helipad.x1, helipad.x2]) {
        ctx.strokeStyle = '#cbd5e1'
        ctx.beginPath()
        ctx.moveTo(px(fx), py(helipad.y))
        ctx.lineTo(px(fx), py(helipad.y + 50 / 30))
        ctx.stroke()
        ctx.fillStyle = '#f5b544'
        ctx.beginPath()
        ctx.moveTo(px(fx), py(helipad.y + 50 / 30))
        ctx.lineTo(px(fx + 25 / 30), py(helipad.y + 45 / 30))
        ctx.lineTo(px(fx), py(helipad.y + 40 / 30))
        ctx.fill()
      }
      // the whole segment's path (faint) and the part flown so far
      ctx.lineWidth = 1.5
      ctx.strokeStyle = 'rgba(60,200,212,0.22)'
      ctx.beginPath()
      seg.obs.forEach((ob, n) => {
        const [x, y] = toWorld(ob)
        if (n === 0) ctx.moveTo(px(x), py(y))
        else ctx.lineTo(px(x), py(y))
      })
      ctx.stroke()
      ctx.strokeStyle = 'rgba(60,200,212,0.75)'
      ctx.beginPath()
      seg.obs.slice(0, k + 1).forEach((ob, n) => {
        const [x, y] = toWorld(ob)
        if (n === 0) ctx.moveTo(px(x), py(y))
        else ctx.lineTo(px(x), py(y))
      })
      ctx.stroke()
      // lander
      const ob = seg.obs[k]
      const [x, y] = toWorld(ob)
      const action = k > 0 ? seg.actions[k - 1] : 0
      ctx.save()
      ctx.translate(px(x), py(y))
      ctx.rotate(-ob[4]) // world angles are counter-clockwise with y up; the canvas y axis points down
      ctx.scale(sx, -sy) // local coordinates in world orientation (y up)
      if (action === 2) {
        ctx.fillStyle = '#ff9a4a'
        ctx.beginPath()
        ctx.moveTo(-0.15, -0.33)
        ctx.lineTo(0.15, -0.33)
        ctx.lineTo(0, -0.95)
        ctx.fill()
      }
      if (action === 1 || action === 3) {
        const side = action === 1 ? 1 : -1
        ctx.fillStyle = '#bfdcff'
        ctx.beginPath()
        ctx.moveTo(side * 0.55, 0.35)
        ctx.lineTo(side * 0.95, 0.42)
        ctx.lineTo(side * 0.55, 0.49)
        ctx.fill()
      }
      ctx.strokeStyle = '#94a3b8'
      ctx.lineWidth = 2 / sx
      for (const side of [1, -1]) {
        ctx.beginPath()
        ctx.moveTo(side * 0.35, -0.2)
        ctx.lineTo(side * 0.7, -0.7)
        ctx.stroke()
      }
      ctx.fillStyle = '#e2e8f0'
      ctx.beginPath()
      HULL.forEach(([hx, hy], n) => (n === 0 ? ctx.moveTo(hx, hy) : ctx.lineTo(hx, hy)))
      ctx.closePath()
      ctx.fill()
      ctx.restore()
    }

    if (reduced) {
      draw(L)
      return
    }
    let raf = 0
    const t0 = performance.now()
    const period = ((L + 1) / world.fps) * slow + 0.6
    const loop = (now: number) => {
      // rAF timestamps are frame start times and can precede t0 slightly: clamp at 0
      const t = (Math.max(0, now - t0) / 1000) % period
      draw(Math.min(L, Math.floor((t / slow) * world.fps)))
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [seg, slow, reduced])

  return <canvas ref={ref} role="img" aria-label={label} className="block aspect-[3/2] w-full rounded-md border border-line" />
}

// --------------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------------- //

export default function LearnedRewards() {
  const datasets = useApi<Dataset[]>('/api/preferences')
  const models = useApi<RewardModelMeta[]>('/api/reward-models')
  const experiments = useApi<Experiment[]>('/api/experiments')
  const [datasetId, setDatasetId] = useState('')
  const [pair, setPair] = useState<Pair | null>(null)
  const [reveal, setReveal] = useState<(Reveal & { choice: string }) | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tally, setTally] = useState({ n: 0, agree: 0 })
  const [strategy, setStrategy] = useState<Strategy>('random')
  const [simulated, setSimulated] = useState(0)
  const [ensembleJob, setEnsembleJob] = useState<string | null>(null)
  const progress = useApi<Progress>(datasetId && !DEMO ? `/api/preferences/${datasetId}/progress` : null)
  const studies = useApi<ActiveStudy[]>(datasetId ? `/api/preferences/${datasetId}/active-studies` : null)
  const reloadProgress = progress.reload
  useJobWatch(ensembleJob, (j: Job) => {
    setEnsembleJob(null)
    if (j.state !== 'completed') setError(j.error ?? `ensemble job ${j.state}`)
    reloadProgress()
    models.reload()
  })

  useEffect(() => {
    if (!datasetId && datasets.data?.length) setDatasetId(datasets.data[0].dataset_id)
  }, [datasets.data, datasetId])

  const next = useCallback(async () => {
    if (!datasetId) return
    setBusy(true)
    setError(null)
    setReveal(null)
    try {
      setPair(await api.get<Pair>(`/api/preferences/${datasetId}/pair?strategy=${strategy}`))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }, [datasetId, strategy])

  useEffect(() => {
    if (datasetId) next()
  }, [datasetId, next])

  const fitEnsemble = async () => {
    setError(null)
    try {
      const job = await api.post<Job>(`/api/preferences/${datasetId}/ensemble`, { simulated_pairs: simulated, members: 5, idempotency_key: idempotencyKey() })
      setEnsembleJob(job.id)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const choose = useCallback(
    async (choice: 'a' | 'b' | 'tie') => {
      if (!pair || reveal || busy) return
      setBusy(true)
      try {
        const r = await api.post<Reveal>(`/api/preferences/${pair.dataset_id}/labels`, { i: pair.i, j: pair.j, choice })
        setReveal({ ...r, choice })
        reloadProgress()
        if (choice !== 'tie') setTally((t) => ({ n: t.n + 1, agree: t.agree + (r.agrees ? 1 : 0) }))
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setBusy(false)
      }
    },
    [pair, reveal, busy, reloadProgress],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (el && (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA')) return
      if (!reveal && (e.key === 'ArrowLeft' || e.key === '1')) choose('a')
      else if (!reveal && (e.key === 'ArrowRight' || e.key === '2')) choose('b')
      else if (!reveal && (e.key === 'ArrowDown' || e.key === '0')) choose('tie')
      else if (reveal && (e.key === 'Enter' || e.key === 'n' || e.key === 'N')) next()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [choose, next, reveal])

  const rlhfExperiments = (experiments.data ?? []).filter((e) => e.name.toLowerCase().includes('rlhf'))
  const ds = datasets.data?.find((d) => d.dataset_id === datasetId)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Learned Rewards"
        subtitle={
          <>
            RLHF in miniature. Short flight segments are compared in pairs, a small network learns a reward that agrees with the preferences, and PPO is trained with that learned reward
            as its only training signal (checkpoints are still chosen on validation episodes by the real reward). The trained policies are then judged by the environment&apos;s
            real reward, which shows how much of the task the learned reward captured.
          </>
        }
      />

      <ol className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {[
          ['1 · Segments', '40-step windows (0.8 s) from random, heuristic and PPO flights at several training stages.'],
          ['2 · Preferences', 'A simulated human prefers the segment with the higher real return, noisily (Bradley–Terry). Your labels are stored too.'],
          ['3 · Reward model', 'An MLP r(s, a, s′) trained so that summed rewards predict the preferences. Validated on unseen segments.'],
          ['4 · PPO on r̂', 'PPO optimizes the learned reward only (environment reward weight 0), then is evaluated on the true reward.'],
        ].map(([t, d]) => (
          <li key={t} className="rounded-[10px] border border-line bg-surface p-4">
            <div className="eyebrow">{t}</div>
            <p className="mt-1 text-[13px] text-ink-2">{d}</p>
          </li>
        ))}
      </ol>

      <Card
        title="Be the human in the loop"
        eyebrow="Which flight is better?"
        actions={
          datasets.data && datasets.data.length > 1 ? (
            <select aria-label="Preference dataset" className="field w-[300px]" value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
              {datasets.data.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  {d.dataset_id} · {d.n_segments} segments
                </option>
              ))}
            </select>
          ) : undefined
        }
      >
        {datasets.error && <ErrorBanner error={datasets.error.message} onRetry={datasets.reload} />}
        {!datasets.data && !datasets.error && <Spinner />}
        {datasets.data && datasets.data.length === 0 && (
          <EmptyState icon={<Brain className="size-5" />} title="No preference dataset yet">
            Create one (and the whole learned-reward study) from the command line:
            <pre className="mt-2 overflow-x-auto rounded-md border border-line bg-bg p-3 text-left font-mono text-xs text-ink">python -m lunarlab rlhf-study --from-experiment &lt;experiment-id&gt; --parallel 4</pre>
          </EmptyState>
        )}
        <ErrorBanner error={error} />
        {datasets.data && datasets.data.length > 0 && (
          <div className="mb-5 grid grid-cols-1 gap-4 rounded-md border border-line bg-bg/40 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <div className="space-y-2">
              <Field label="Which pairs to show">
                <Segmented
                  label="Pair selection strategy"
                  value={strategy}
                  onChange={setStrategy}
                  options={[
                    { value: 'random', label: 'Random pairs' },
                    { value: 'disagreement', label: 'Where the ensemble disagrees', disabled: DEMO || !progress.data?.strategies.disagreement },
                  ]}
                />
              </Field>
              <p className="text-xs text-ink-3">
                {strategy === 'random'
                  ? 'Uniformly random pairs of training segments (the baseline). '
                  : 'Among 2,000 random candidate pairs, the one the reward-model ensemble disagrees about most (spread of its members’ P(A preferred)). '}
                A pair you have labelled is never shown again; pairs always come from training episodes.
              </p>
            </div>
            <div className="space-y-2 text-[13px]">
              {DEMO ? (
                <p className="text-xs text-ink-3">The labelling progress and the ensemble live in the local app.</p>
              ) : progress.data ? (
                <>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    <span>
                      <span className="num text-ink">{progress.data.labels}</span> <span className="text-ink-3">labels</span>
                    </span>
                    <span>
                      <span className="num text-ink">{progress.data.usable_for_training}</span> <span className="text-ink-3">usable for training</span>
                    </span>
                    {progress.data.in_validation_episodes + progress.data.excluded > 0 && (
                      <span className="text-ink-3" title="Older labels whose segments lie in validation episodes are kept out of training">
                        {progress.data.in_validation_episodes + progress.data.excluded} kept out of training
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-ink-3">
                    {progress.data.ensemble
                      ? `Labelling ensemble: ${progress.data.ensemble.members} networks fitted on ${progress.data.ensemble.n_human_labels} of your labels${progress.data.ensemble.n_simulated_pairs ? ` + ${progress.data.ensemble.n_simulated_pairs} simulated` : ''} (${fmt.ago(progress.data.ensemble.created_at)}); ${progress.data.since_ensemble ?? 0} new labels since.`
                      : 'No labelling ensemble yet: fit one (from at least 10 labelled pairs) to unlock the disagreement strategy.'}
                  </p>
                  <div className="flex flex-wrap items-end gap-2">
                    <div className="w-36">
                      <Field label="+ simulated labels" htmlFor="ens-sim">
                        <NumberInput id="ens-sim" value={simulated} onChange={(v) => setSimulated(Number.isFinite(v) ? Math.max(0, Math.min(5000, Math.round(v))) : 0)} min={0} max={5000} step={50} />
                      </Field>
                    </div>
                    <Button size="sm" icon={<Network className="size-4" aria-hidden />} pending={!!ensembleJob} onClick={fitEnsemble}>
                      {progress.data.ensemble ? 'Refit ensemble' : 'Fit ensemble'}
                    </Button>
                  </div>
                </>
              ) : (
                <Spinner label="Loading progress" />
              )}
            </div>
          </div>
        )}
        {pair && (
          <>
            {pair.strategy === 'disagreement' && pair.score != null && (
              <p className="mb-3 text-xs text-ink-2">
                Ensemble disagreement on this pair: <span className="num text-ink">{fmt.num(pair.score, 3)}</span>
                {pair.median_score != null && (
                  <span className="text-ink-3">
                    {' '}
                    (median over {fmt.int(pair.candidates ?? 0)} candidates: {fmt.num(pair.median_score, 3)})
                  </span>
                )}
              </p>
            )}
            <p className="mb-4 max-w-[100ch] text-[13px] text-ink-2">
              Judge the landing attempt: getting closer to the pad between the flags, slowing down, staying upright and touching down gently are good; crashing, drifting away and wasting fuel are
              bad. The source policy and the score stay hidden until you answer. Keys: <kbd className="font-mono">←</kbd> / <kbd className="font-mono">→</kbd> pick a side,{' '}
              <kbd className="font-mono">↓</kbd> can&apos;t tell, <kbd className="font-mono">Enter</kbd> next pair.
            </p>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {(['a', 'b'] as const).map((side) => (
                <div key={side} className="min-w-0">
                  <div className="mb-1.5 flex items-center justify-between text-[13px]">
                    <span className="font-medium text-ink">Flight {side.toUpperCase()}</span>
                    <span className="num text-xs text-ink-3">
                      episode seed {pair[side].episode_seed} · {pair[side].actions.length} steps{pair[side].terminal ? ' · episode ends' : ''}
                    </span>
                  </div>
                  <SegmentCanvas seg={pair[side]} slow={1.6} label={`Flight segment ${side.toUpperCase()}`} />
                  {reveal && (
                    <div className={clsx('mt-2 rounded-md border px-3 py-2 text-[13px]', reveal.reward_prefers === side ? 'border-good/40 bg-good/5' : 'border-line')}>
                      <div className="num text-ink">real return {fmt.signed(reveal.returns[side], 1)}</div>
                      <div className="text-xs text-ink-3">flown by: {reveal.sources[side]}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {!reveal ? (
                <>
                  <Button variant="primary" disabled={busy} onClick={() => choose('a')}>
                    ← A is better
                  </Button>
                  <Button disabled={busy} icon={<Equal className="size-4" aria-hidden />} onClick={() => choose('tie')}>
                    Can&apos;t tell
                  </Button>
                  <Button variant="primary" disabled={busy} onClick={() => choose('b')}>
                    B is better →
                  </Button>
                </>
              ) : (
                <>
                  <Badge tone={reveal.choice === 'tie' ? 'neutral' : reveal.agrees ? 'good' : 'warn'}>
                    {reveal.choice === 'tie' ? 'recorded as a tie' : reveal.agrees ? 'you agreed with the environment reward' : 'the environment reward disagreed'}
                  </Badge>
                  <Button variant="primary" icon={<SkipForward className="size-4" aria-hidden />} onClick={next} pending={busy}>
                    Next pair
                  </Button>
                </>
              )}
              <span className="ml-auto text-xs text-ink-3">
                this session: {tally.n} judged · {tally.n ? `${fmt.pct(tally.agree / tally.n)} agree with the real reward` : '—'}
                {DEMO ? ' · demo: labels are not saved' : reveal ? ` · ${reveal.n_labels} saved labels in this dataset` : ds ? ` · ${ds.human_labels} saved labels in this dataset` : ''}
              </span>
            </div>
          </>
        )}
      </Card>

      <Card title="Reward models" eyebrow="validation on unseen segments">
        {models.data && models.data.length === 0 && <p className="text-[13px] text-ink-3">No reward models trained yet.</p>}
        {models.data && models.data.length > 0 && (
          <>
            <Table>
              <thead>
                <tr>
                  <th>Model</th>
                  <th className="text-right">Training pairs</th>
                  <th className="text-right">Human labels</th>
                  <th title="How validation data was held out">Validation split</th>
                  <th className="text-right" title="Validation pairs ordered like the noisy simulated human">Acc. vs labels</th>
                  <th className="text-right" title="Validation pairs ordered like the true segment returns">Acc. vs true order</th>
                  <th className="text-right" title="Correlation of summed predicted reward with the true segment return">Return corr.</th>
                  <th className="text-right" title="Correlation of per-step predicted reward with the true per-step reward">Step corr.</th>
                </tr>
              </thead>
              <tbody>
                {models.data.map((m) => (
                  <tr key={m.model_id}>
                    <td className="num text-xs">{m.model_id}</td>
                    <td className="num text-right">{fmt.int(m.n_train_pairs)}</td>
                    <td className="num text-right">{m.n_human_labels}</td>
                    <td className="text-xs text-ink-2">
                      {m.split ? `${m.split.val_episodes} of ${m.split.train_episodes + m.split.val_episodes} episodes` : <span title="Trained before validation was split by episode: overlapping windows could sit on both sides">by segment (older)</span>}
                    </td>
                    <td className="num text-right">{fmt.pct(m.metrics.val_accuracy_vs_labels, 1)}</td>
                    <td className="num text-right">{fmt.pct(m.metrics.val_accuracy_vs_true_order, 1)}</td>
                    <td className="num text-right">{fmt.num(m.metrics.segment_return_correlation, 2)}</td>
                    <td className="num text-right">{fmt.num(m.metrics.step_reward_correlation, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <p className="mt-2 text-xs text-ink-3">
              The simulated human itself agrees with the true order on only part of the pairs (label noise), so accuracy against the true order can exceed accuracy against the labels.
              A reward model can rank segments well (return correlation) while its per-step reward differs a lot from the environment&apos;s (step correlation): PPO optimizes the per-step
              signal, which is where learned rewards get exploited.
            </p>
          </>
        )}
      </Card>

      {studies.data && studies.data.length > 0 && <ActiveStudies study={studies.data[0]} />}

      <Notice title="Did PPO learn to land from the learned reward?">
        {rlhfExperiments.length ? (
          <>
            The policies trained on learned rewards are evaluated like every other run.{' '}
            {rlhfExperiments.map((e) => (
              <Link key={e.experiment_id} className="text-accent hover:underline" to={`/compare?experiment=${e.experiment_id}`}>
                Compare {e.name} ({e.run_ids.length} runs)
              </Link>
            ))}
          </>
        ) : (
          <>No learned-reward training runs yet. The study command above trains them after building the dataset and reward models.</>
        )}
      </Notice>
    </div>
  )
}

function ActiveStudies({ study }: { study: ActiveStudy }) {
  const strategies = Object.keys(study.summary)
  const labels = [...new Set(strategies.flatMap((k) => study.summary[k].map((p) => p.labels)))].toSorted((a, b) => a - b)
  const rows = labels.map((n) => {
    const row: Record<string, number | [number, number]> = { labels: n }
    for (const k of strategies) {
      const pt = study.summary[k].find((p) => p.labels === n)
      if (pt) {
        row[k] = pt.mean
        row[`${k}_band`] = [pt.min, pt.max]
      }
    }
    return row
  })
  const last = Object.fromEntries(strategies.map((k) => [k, study.summary[k][study.summary[k].length - 1]]))
  return (
    <Card title="Active vs random selection" eyebrow={`simulated labeller · ${study.seeds.length} seeds · ${fmt.time(study.created_at)}`}>
      <p className="mb-3 max-w-[110ch] text-[13px] text-ink-2">
        Reward-model accuracy against the true order of held-out validation pairs, as labels accumulate. Each seed starts both strategies from the same {study.params.initial ?? '?'} random
        labels; then every round adds {study.params.batch ?? '?'} labels chosen at random or where a {study.params.members ?? '?'}-network ensemble disagrees most. Band: min–max over seeds.
      </p>
      <figure aria-label="Validation accuracy against the number of labels, per selection strategy">
        <Legend items={strategies.map((k) => ({ label: k === 'disagreement' ? 'ensemble disagreement' : k, color: STRATEGY_COLOR[k] ?? '#8494a8' }))} />
        <div style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rows} margin={{ top: 6, right: 12, bottom: 16, left: 4 }}>
              <CartesianGrid stroke="#1b2532" vertical={false} />
              <XAxis dataKey="labels" type="number" domain={['dataMin', 'dataMax']} tick={{ fill: '#8494a8', fontSize: 11, fontFamily: 'IBM Plex Mono' }} stroke="#2d3e52" tickLine={false} label={{ value: 'labels', position: 'insideBottom', offset: -10, fill: '#8494a8', fontSize: 11 }} />
              <YAxis domain={['auto', 'auto']} tick={{ fill: '#8494a8', fontSize: 11, fontFamily: 'IBM Plex Mono' }} stroke="#2d3e52" tickLine={false} width={44} tickFormatter={(v) => fmt.pct(v)} />
              <Tooltip
                isAnimationActive={false}
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-line-strong bg-surface-2/95 px-3 py-2 text-xs shadow-xl">
                      <div className="num mb-1 text-ink-3">{label} labels</div>
                      {payload
                        .filter((p) => !String(p.dataKey).endsWith('_band'))
                        .map((p) => (
                          <div key={String(p.dataKey)} className="num flex justify-between gap-4">
                            <span className="text-ink-2">{String(p.dataKey)}</span>
                            <span className="text-ink">{fmt.pct(Number(p.value), 1)}</span>
                          </div>
                        ))}
                    </div>
                  ) : null
                }
              />
              {strategies.map((k) => (
                <Area key={`${k}_band`} dataKey={`${k}_band`} stroke="none" fill={STRATEGY_COLOR[k] ?? '#8494a8'} fillOpacity={0.12} isAnimationActive={false} legendType="none" />
              ))}
              {strategies.map((k) => (
                <Line key={k} dataKey={k} stroke={STRATEGY_COLOR[k] ?? '#8494a8'} strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </figure>
      <p className="mt-2 text-xs text-ink-3">
        After {last[strategies[0]]?.labels ?? '?'} labels:{' '}
        {strategies.map((k, i) => (
          <span key={k}>
            {i > 0 && ' · '}
            {k} {fmt.pct(last[k]?.mean, 1)} (seeds {fmt.pct(last[k]?.min, 1)}–{fmt.pct(last[k]?.max, 1)})
          </span>
        ))}
        . These are reward-model accuracies; whether a policy trained on either model lands better is a separate (PPO) experiment:{' '}
        <span className="font-mono">rlhf-active --register</span>, then <span className="font-mono">rlhf-study --reward-models</span>.
      </p>
    </Card>
  )
}
