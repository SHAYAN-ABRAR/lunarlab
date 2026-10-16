import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, CircleSlash, FileText, HelpCircle } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { Legend, SeedDotPlot, StackedBars } from '../components/charts'
import { useJobWatch } from '../components/Jobs'
import {
  type GammaAblation,
  GammaAblationCard,
  type PhysicsComparison,
  PhysicsComparisonCard,
  type RobustStats,
  RobustStatsCard,
  type RobustnessTable,
  RobustnessCard,
} from '../components/robust'
import { Badge, Button, Card, EmptyState, ErrorBanner, Notice, PageHeader, Segmented, Spinner, StateBadge, Table } from '../components/ui'
import { api, idempotencyKey } from '../lib/api'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import { PRESET_COLOR, PRESET_DASH, PRESET_SHAPE } from '../lib/reward'
import type { CurvePoint, EvalSummary, Experiment, Job, Preset, RunSummary } from '../lib/types'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface Group {
  group_key?: string
  algo?: string
  gamma?: number | null
  variant?: string
  reward_hash: string
  reward_name: string
  reward_preset: Preset
  active_terms: string[]
  n_runs: number
  n_evaluated_seeds: number
  per_seed: { run_id: string; seed: number; evaluation: EvalSummary | null; checkpoint_transitions: number; state: string }[]
  across_seeds: Record<string, { n: number; mean: number | null; std: number | null; min: number | null; max: number | null }>
  evidence_note: string
}

interface Diagnostic {
  run_id: string
  seed: number
  reward_name: string
  reward_preset: Preset
  evaluation: EvalSummary | null
  training_trend: { original_return_change: number; training_return_change: number; episodes_per_window: number; note: string } | null
  flag: string
  reasons: string[]
}

interface CompareData {
  split: 'test' | 'validation'
  runs: (RunSummary & { ppo_key: Record<string, unknown>; env: Record<string, unknown> })[]
  compatibility: { compatible: boolean; issues: string[] }
  groups: Group[]
  diagnostics: Diagnostic[]
  rules: Record<string, number>
  curves: Record<string, { points: CurvePoint[]; window: number; n_episodes: number }>
  robust_stats?: RobustStats
  robustness?: RobustnessTable
  physics_comparison?: PhysicsComparison[]
  gamma_ablation?: GammaAblation[]
  wall_clock?: { notes: string[] }
}

/** Short group label for compact charts: first two words of the reward name, keeping an algorithm prefix. */
function shortName(name: string): string {
  const m = /^([A-Z]+) · (.*)$/.exec(name)
  const words = (m ? m[2] : name).split(' ').slice(0, 2).join(' ')
  return m ? `${m[1]} ${words}` : words
}

function FlagBadge({ flag }: { flag: string }) {
  if (flag === 'possible reward exploitation') return <Badge tone="warn" icon={<AlertTriangle className="size-3.5" aria-hidden />}>possible reward exploitation</Badge>
  if (flag === 'no evidence of exploitation') return <Badge tone="good" icon={<CheckCircle2 className="size-3.5" aria-hidden />}>no evidence</Badge>
  if (flag === 'insufficient data') return <Badge tone="neutral" icon={<HelpCircle className="size-3.5" aria-hidden />}>insufficient data</Badge>
  return <Badge tone="neutral" icon={<CircleSlash className="size-3.5" aria-hidden />}>{flag}</Badge>
}

/** Groups of the same reward (algorithms, discount factors, training physics) get their own colours. */
const GROUP_PALETTE = ['#3987e5', '#c98500', '#d55181', '#008300', '#9085e9', '#5bb8c9', '#d95926', '#8494a8']

type CurveAxis = 'transitions' | 'elapsed_s'

function axisTime(s: number): string {
  if (s >= 3600) return `${(s / 3600).toFixed(s % 3600 === 0 ? 0 : 1)}h`
  if (s >= 60) return `${Math.round(s / 60)}m`
  return `${Math.round(s)}s`
}

function CurvesChart({ data }: { data: CompareData }) {
  const [axis, setAxis] = useState<CurveAxis>('transitions')
  // Preset colours while every preset is one group; otherwise one colour per group, DQN dashed.
  const byPreset = new Set(data.groups.map((g) => g.reward_preset)).size === data.groups.length
  const groupOf = new Map(data.groups.flatMap((g, i) => g.per_seed.map((p) => [p.run_id, { g, i }] as const)))
  const series = data.runs
    .filter((r) => data.curves[r.run_id]?.points.length)
    .map((r) => {
      const hit = groupOf.get(r.run_id)
      const group = hit?.g.reward_name ?? r.reward_name
      const all = data.curves[r.run_id].points
      return {
        id: r.run_id,
        group,
        label: `${group} · s${r.seed}`,
        color: byPreset || !hit ? PRESET_COLOR[r.reward_preset] : GROUP_PALETTE[hit.i % GROUP_PALETTE.length],
        dashed: byPreset || !hit ? PRESET_DASH[r.reward_preset] : hit.g.algo === 'dqn' ? '6 3' : undefined,
        points: axis === 'transitions' ? all : all.filter((p) => p.elapsed_s != null),
      }
    })
    .filter((s) => s.points.length)
  if (!series.length) return <div className="py-8 text-center text-[13px] text-ink-3">No training episodes recorded for these runs yet.</div>
  const legendItems = [...new Map(series.map((s) => [s.group, { label: s.group, color: s.color, dashed: !!s.dashed }])).values()]
  const notes = data.wall_clock?.notes ?? []
  return (
    <figure aria-label="Original episode return during training for each selected run">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <Legend items={legendItems} />
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[11px] text-ink-3">one line per training seed · rolling mean of 100 training episodes</span>
          <Segmented<CurveAxis>
            label="Training-curve x-axis"
            value={axis}
            onChange={setAxis}
            options={[
              { value: 'transitions', label: 'Transitions' },
              { value: 'elapsed_s', label: 'Wall-clock time' },
            ]}
          />
        </div>
      </div>
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart margin={{ top: 6, right: 12, bottom: 16, left: 4 }}>
            <CartesianGrid stroke="#1b2532" vertical={false} />
            <XAxis
              dataKey={axis}
              type="number"
              domain={['dataMin', 'dataMax']}
              allowDuplicatedCategory={false}
              tick={{ fill: '#8494a8', fontSize: 11, fontFamily: 'IBM Plex Mono' }}
              tickFormatter={(v: number) => (axis === 'transitions' ? fmt.compact(v) : axisTime(v))}
              stroke="#2d3e52"
              tickLine={false}
              label={{ value: axis === 'transitions' ? 'transitions' : 'wall-clock training time', position: 'insideBottom', offset: -10, fill: '#8494a8', fontSize: 11 }}
            />
            <YAxis tick={{ fill: '#8494a8', fontSize: 11, fontFamily: 'IBM Plex Mono' }} stroke="#2d3e52" tickLine={false} width={52} />
            <ReferenceLine y={200} stroke="#5b6f88" strokeDasharray="3 4" />
            <Tooltip
              isAnimationActive={false}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="rounded-md border border-line-strong bg-surface-2/95 px-3 py-2 text-xs shadow-xl">
                    <div className="num mb-1 text-ink-3">{axis === 'transitions' ? `transitions ≈ ${fmt.compact(Number(label))}` : `time ≈ ${fmt.duration(Number(label))}`}</div>
                    {payload.slice(0, 12).map((p) => (
                      <div key={String(p.name)} className="num flex justify-between gap-4">
                        <span className="text-ink-2">{p.name}</span>
                        <span className="text-ink">{fmt.num(Number(p.value), 1)}</span>
                      </div>
                    ))}
                  </div>
                ) : null
              }
            />
            {series.map((s) => (
              <Line key={s.id} data={s.points} dataKey="original_return" name={s.label} stroke={s.color} strokeDasharray={s.dashed} strokeWidth={1.75} dot={false} isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {axis === 'elapsed_s' && (
        <figcaption className="mt-2 text-xs text-ink-3">
          Wall-clock time from the start of training, including validation passes. It depends on the machine and on how many runs trained at the same time, so it compares speed only
          between runs trained under the same conditions.
          {notes.length > 0 && (
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-warn">
              {notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}
        </figcaption>
      )}
    </figure>
  )
}

function Reports({ runIds, experimentId, split }: { runIds: string[]; experimentId?: string; split: string }) {
  const reports = useApi<{ report_id: string; files: string[]; modified: number }[]>('/api/reports')
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  useJobWatch(jobId, (j) => {
    setJobId(null)
    if (j.state !== 'completed') setError(j.error ?? `report ${j.state}`)
    reports.reload()
  })
  return (
    <div className="space-y-3">
      <p className="text-[13px] text-ink-2">Generates a Markdown + HTML report with figures from the stored data of the selected runs ({split} split). Nothing is filled in where data is missing.</p>
      <Button
        icon={<FileText className="size-4" />}
        pending={!!jobId}
        disabled={!runIds.length}
        onClick={async () => {
          setError(null)
          try {
            setJobId((await api.post<Job>('/api/reports', { run_ids: runIds, experiment_id: experimentId || null, split, title: 'LunarLab experiment report', idempotency_key: idempotencyKey() })).id)
          } catch (e) {
            setError((e as Error).message)
          }
        }}
      >
        {jobId ? 'Generating…' : 'Generate report'}
      </Button>
      <ErrorBanner error={error} />
      <ul className="divide-y divide-line text-[13px]">
        {(reports.data ?? []).slice(0, 8).map((r) => (
          <li key={r.report_id} className="flex flex-wrap items-center justify-between gap-2 py-2">
            <span className="num truncate text-xs text-ink-2">{r.report_id}</span>
            <span className="flex gap-3">
              <a className="text-accent hover:underline" href={`/api/reports/${r.report_id}/report.html`} target="_blank" rel="noreferrer">HTML</a>
              <a className="text-accent hover:underline" href={`/api/reports/${r.report_id}/report.md`} target="_blank" rel="noreferrer">Markdown</a>
            </span>
          </li>
        ))}
        {reports.data && !reports.data.length && <li className="py-2 text-xs text-ink-3">No reports yet.</li>}
      </ul>
    </div>
  )
}

export default function Compare() {
  const [params, setParams] = useSearchParams()
  const runs = useApi<RunSummary[]>('/api/runs')
  const experiments = useApi<Experiment[]>('/api/experiments')
  const [selected, setSelected] = useState<string[]>([])
  const [split, setSplitState] = useState<'test' | 'validation'>('validation')
  const [splitChosen, setSplitChosen] = useState(false)
  const setSplit = (v: 'test' | 'validation') => {
    setSplitChosen(true)
    setSplitState(v)
  }
  const [data, setData] = useState<CompareData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const experimentId = params.get('experiment') ?? ''

  // Default selection: the chosen experiment, else every non-smoke run (or all runs if only smoke runs exist).
  useEffect(() => {
    if (!runs.data) return
    if (experimentId && experiments.data) {
      const exp = experiments.data.find((e) => e.experiment_id === experimentId)
      if (exp) setSelected(exp.run_ids.filter((id) => runs.data!.some((r) => r.run_id === id)))
      return
    }
    if (!selected.length) {
      const real = runs.data.filter((r) => r.profile !== 'smoke')
      setSelected((real.length ? real : runs.data).slice(0, 16).map((r) => r.run_id))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs.data, experiments.data, experimentId])

  // Default split: the final test once every selected run that has been evaluated has a frozen test result.
  useEffect(() => {
    if (splitChosen || !runs.data) return
    const chosen = runs.data.filter((r) => selected.includes(r.run_id) && (r.latest_test || r.latest_validation))
    setSplitState(chosen.length > 0 && chosen.every((r) => r.latest_test) ? 'test' : 'validation')
  }, [selected, runs.data, splitChosen])

  useEffect(() => {
    if (!selected.length) {
      setData(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .post<CompareData>('/api/compare', { run_ids: selected, split })
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError((e as Error).message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [selected, split])

  const outcomeRows = useMemo(
    () =>
      (data?.diagnostics ?? [])
        .filter((d) => d.evaluation)
        .map((d) => {
          const e = d.evaluation!
          const v2 = (e.outcome_classifier_version ?? 1) >= 2
          // Classifier v2 keeps where the lander came to rest apart from how well it landed. Older results
          // use categories derived from their stored episode fields (marked †); without those, only the
          // undivided "at rest, not strict pad" remainder is shown.
          const src = v2
            ? { onpad: e.on_pad_not_strict_rate, off: e.landed_not_within_pad_rate, body: e.at_rest_after_body_contact_rate, unk: e.at_rest_geometry_unknown_rate }
            : e.derived_v2
              ? { onpad: e.derived_v2.on_pad_not_strict_rate, off: e.derived_v2.landed_not_within_pad_rate, body: e.derived_v2.at_rest_after_body_contact_rate, unk: e.derived_v2.at_rest_geometry_unknown_rate }
              : null
          return {
            name: `${shortName(d.reward_name)} · s${d.seed}${v2 ? '' : ' †'}`,
            pad: e.pad_landing_rate,
            onpad: src ? (src.onpad ?? 0) : 0,
            off: src ? (src.off ?? 0) : 0,
            body: src ? (src.body ?? 0) : 0,
            rest: src ? (src.unk ?? 0) : Math.max(0, e.env_success_rate - e.pad_landing_rate),
            crash: e.crash_rate,
            oob: e.out_of_bounds_rate,
            timeout: e.timeout_rate,
          }
        }),
    [data],
  )

  if (runs.error && !runs.data) return <ErrorBanner error={runs.error.message} onRetry={runs.reload} />
  if (runs.data && !runs.data.length)
    return (
      <>
        <PageHeader title="Compare & Diagnose" />
        <EmptyState title="Nothing to compare yet" action={<Link className="text-accent hover:underline" to="/training">Go to the Training Console</Link>}>
          Train at least two reward configurations (ideally three seeds each, STANDARD profile) and evaluate them. Comparisons only use evaluations with the original reward on shared seeds.
        </EmptyState>
      </>
    )

  return (
    <>
      <PageHeader
        title="Compare & Diagnose"
        subtitle="Original-reward performance on shared evaluation seeds, every training seed shown individually, and an explicit check for reward exploitation."
        actions={<Segmented label="Evaluation split" value={split} onChange={setSplit} options={[{ value: 'validation', label: 'Validation' }, { value: 'test', label: 'Final test' }]} />}
      />

      <Card title="Runs in this comparison" className="mb-6" actions={
        <select aria-label="Select experiment" className="field w-[280px]" value={experimentId} onChange={(e) => { setParams(e.target.value ? { experiment: e.target.value } : {}); if (!e.target.value) setSelected([]) }}>
          <option value="">Manual selection</option>
          {(experiments.data ?? []).map((e) => (
            <option key={e.experiment_id} value={e.experiment_id}>{e.name} · {e.run_ids.length} runs</option>
          ))}
        </select>
      }>
        {!runs.data ? <Spinner /> : (
          <div className="max-h-64 overflow-auto">
            <Table>
              <thead>
                <tr>
                  <th className="w-8"><span className="sr-only">Include</span></th>
                  <th>Run</th>
                  <th>Reward</th>
                  <th className="text-right">Seed</th>
                  <th>Profile</th>
                  <th>State</th>
                  <th>Evaluations</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.map((r) => (
                  <tr key={r.run_id}>
                    <td>
                      <input type="checkbox" aria-label={`Include ${r.run_id}`} className="accent-[#3cc8d4]" checked={selected.includes(r.run_id)} onChange={(e) => setSelected((cur) => (e.target.checked ? [...cur, r.run_id] : cur.filter((x) => x !== r.run_id)))} />
                    </td>
                    <td><Link className="num text-xs text-accent hover:underline" to={`/runs/${r.run_id}`}>{fmt.shortId(r.run_id)}</Link></td>
                    <td><span className="inline-flex items-center gap-1.5"><span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[r.reward_preset] }} />{r.reward_name}</span></td>
                    <td className="num text-right">{r.seed}</td>
                    <td className="text-xs uppercase text-ink-2">{r.profile}</td>
                    <td><StateBadge state={r.state} /></td>
                    <td className="text-xs text-ink-3">{[r.latest_validation && 'validation', r.latest_test && 'test'].filter(Boolean).join(' · ') || 'none'}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        )}
      </Card>

      <ErrorBanner error={error} />
      {loading && !data && <Spinner label="Comparing" />}
      {data && (
        <div className={clsx('space-y-6', loading && 'opacity-60')}>
          {data.compatibility.compatible ? (
            <Notice tone="good" title="Comparable">All selected runs share environment, PPO settings, training budget and evaluation protocol.</Notice>
          ) : (
            <Notice tone="warn" title="Not directly comparable">
              <ul className="list-disc pl-4">{data.compatibility.issues.map((i) => <li key={i}>{i}</li>)}</ul>
            </Notice>
          )}

          <Card title="Is the agent earning more training reward without doing the actual landing task better?" eyebrow="Reward-hacking diagnostic">
            <p className="mb-4 max-w-[100ch] text-[13px] text-ink-2">
              A gap between shaped and original return is expected whenever bonuses are added and is not, by itself, evidence. A run is flagged only when (1) its extra terms pay out on evaluation episodes, (2) behaviour shows what they pay for — sustained hover ≥ {fmt.pct(data.rules.hover_rate)}, hover fraction ≥ {fmt.pct(data.rules.hover_fraction)}, or time-limit rate ≥ {fmt.pct(data.rules.timeout_rate)} — and (3) pad landing is no better than the original-reward baseline.
            </p>
            <Table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th className="text-right">Training return (rescored)</th>
                  <th className="text-right">Original return</th>
                  <th className="text-right">Pad landing</th>
                  <th className="text-right">Hover fraction</th>
                  <th className="text-right">Sustained hover</th>
                  <th className="text-right">Time limit</th>
                  <th className="text-right">Mean length</th>
                  <th className="text-right">Main engine</th>
                  <th>Assessment</th>
                </tr>
              </thead>
              <tbody>
                {data.diagnostics.map((d) => {
                  const e = d.evaluation
                  return (
                    <tr key={d.run_id} className="align-top">
                      <td>
                        <span className="inline-flex items-center gap-1.5"><span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[d.reward_preset] }} />{d.reward_name}</span>
                        <div className="text-[11px] text-ink-3">seed {d.seed}</div>
                      </td>
                      <td className="num text-right">{fmt.num(e?.training_return_rescored_mean, 1)}</td>
                      <td className="num text-right">{fmt.num(e?.mean_original_return, 1)}</td>
                      <td className="num text-right">{fmt.pct(e?.pad_landing_rate)}</td>
                      <td className="num text-right">{fmt.num(e?.hover_fraction_mean, 3)}</td>
                      <td className="num text-right">{fmt.pct(e?.sustained_hover_rate)}</td>
                      <td className="num text-right">{fmt.pct(e?.timeout_rate)}</td>
                      <td className="num text-right">{fmt.num(e?.mean_length, 0)}</td>
                      <td className="num text-right">{fmt.pct(e?.main_engine_fraction)}</td>
                      <td>
                        <FlagBadge flag={d.flag} />
                        <details className="mt-1 text-[11px] text-ink-3">
                          <summary className="cursor-pointer">evidence</summary>
                          <ul className="mt-1 list-disc space-y-0.5 pl-4">{d.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                          {d.training_trend && <p className="mt-1">Training trend (first→last 20%): original {fmt.signed(d.training_trend.original_return_change, 1)}, training {fmt.signed(d.training_trend.training_return_change, 1)}. {d.training_trend.note}</p>}
                        </details>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </Table>
          </Card>

          <Card title="Original-reward performance per training seed" eyebrow={`${data.split} split · CI = 95% bootstrap over evaluation episodes of that one policy`}>
            <Table>
              <thead>
                <tr>
                  <th>Reward</th>
                  <th className="text-right">Seed</th>
                  <th className="text-right">Episodes</th>
                  <th className="text-right">Mean [95% CI]</th>
                  <th className="text-right">Median</th>
                  <th className="text-right">Return ≥ 200</th>
                  <th className="text-right">Env success</th>
                  <th className="text-right">Strict pad</th>
                  <th className="text-right">Crash</th>
                  <th className="text-right">OOB</th>
                  <th className="text-right">Time limit</th>
                </tr>
              </thead>
              <tbody>
                {data.groups.flatMap((g) =>
                  g.per_seed.map((ps, i) => {
                    const e = ps.evaluation
                    return (
                      <tr key={ps.run_id} className={clsx(i === 0 && 'border-t-2 border-line-strong')}>
                        <td>{i === 0 ? <span className="inline-flex items-center gap-1.5"><span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[g.reward_preset] }} />{g.reward_name}</span> : null}</td>
                        <td className="num text-right">{ps.seed}</td>
                        {e ? (
                          <>
                            <td className="num text-right">{e.n_episodes}</td>
                            <td className="num text-right">{fmt.num(e.mean_original_return, 1)}{e.ci && <span className="text-ink-3"> [{fmt.num(e.ci[0], 0)}, {fmt.num(e.ci[1], 0)}]</span>}</td>
                            <td className="num text-right">{fmt.num(e.median_original_return, 1)}</td>
                            <td className="num text-right">{fmt.pct(e.score_rate)}</td>
                            <td className="num text-right">{fmt.pct(e.env_success_rate)}</td>
                            <td className="num text-right">{fmt.pct(e.pad_landing_rate)}</td>
                            <td className="num text-right">{fmt.pct(e.crash_rate)}</td>
                            <td className="num text-right">{fmt.pct(e.out_of_bounds_rate)}</td>
                            <td className="num text-right">{fmt.pct(e.timeout_rate)}</td>
                          </>
                        ) : (
                          <td colSpan={9} className="text-ink-3">not evaluated on the {data.split} split</td>
                        )}
                      </tr>
                    )
                  }),
                )}
              </tbody>
            </Table>
          </Card>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <Card title="Variability across independently trained policies" eyebrow="one dot = one training seed's mean original return">
              <SeedDotPlot
                ariaLabel="Mean original return of each trained policy, grouped by reward"
                groups={data.groups.map((g) => ({
                  name: shortName(g.reward_name),
                  color: PRESET_COLOR[g.reward_preset],
                  shape: PRESET_SHAPE[g.reward_preset],
                  points: g.per_seed.filter((p) => p.evaluation).map((p) => ({ seed: p.seed, value: p.evaluation!.mean_original_return, runId: p.run_id })),
                }))}
              />
              <Table className="mt-3">
                <thead><tr><th>Reward</th><th className="text-right">Seeds</th><th className="text-right">Mean of means</th><th className="text-right">SD across seeds</th><th>Note</th></tr></thead>
                <tbody>
                  {data.groups.map((g) => {
                    const a = g.across_seeds.mean_original_return
                    return (
                      <tr key={g.group_key ?? g.reward_hash}>
                        <td>{g.reward_name}</td>
                        <td className="num text-right">{g.n_evaluated_seeds}</td>
                        <td className="num text-right">{fmt.num(a?.mean, 1)}</td>
                        <td className="num text-right">{fmt.num(a?.std, 1)}</td>
                        <td className="text-xs text-ink-3">{g.evidence_note}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </Table>
            </Card>
            <Card title="Episode outcomes" eyebrow={`${data.split} split · original environment`}>
              <StackedBars
                ariaLabel="Outcome rates per run"
                rows={outcomeRows}
                parts={[
                  { key: 'pad', label: 'Strict pad landing', color: '#3987e5' },
                  { key: 'onpad', label: 'On pad, not strict', color: '#5bb8c9' },
                  { key: 'off', label: 'Landed off pad', color: '#199e70' },
                  { key: 'body', label: 'At rest after body contact', color: '#b07aa1' },
                  { key: 'rest', label: 'At rest, other', color: '#8494a8' },
                  { key: 'crash', label: 'Crash', color: '#d95926' },
                  { key: 'oob', label: 'Out of bounds', color: '#9085e9' },
                  { key: 'timeout', label: 'Time limit', color: '#c98500' },
                ]}
              />
              <p className="mt-2 text-xs text-ink-3">
                “At rest” is the environment’s own success signal (+100). A strict pad landing additionally requires both legs between the flags, no body contact, leg contact
                seen and an upright finish; “on pad, not strict” came to rest between the flags but failed the angle or contact criterion, “landed off pad” is not wholly between
                them (beside the pad or straddling its edge).
                {outcomeRows.some((r) => r.name.endsWith('†')) &&
                  ' † Evaluated with outcome classifier v1: the stored results are unchanged and these categories are derived from their episode fields (v1 did not store leg positions).'}
              </p>
            </Card>
          </div>

          {data.robust_stats && (
            <RobustStatsCard stats={data.robust_stats} styles={data.groups.map((g) => ({ name: g.reward_name, preset: g.reward_preset, algo: g.algo ?? 'ppo' }))} />
          )}

          {data.robustness && <RobustnessCard table={data.robustness} experimentId={experimentId || undefined} />}

          {data.physics_comparison && data.robustness && <PhysicsComparisonCard rows={data.physics_comparison} conditions={data.robustness.conditions} />}

          {data.gamma_ablation && <GammaAblationCard blocks={data.gamma_ablation} />}

          <Card title="Training curves (original reward)">
            <CurvesChart data={data} />
          </Card>

          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <Card title="Configurations" eyebrow="what differs between runs">
              <Table>
                <thead><tr><th>Run</th><th>Reward hash</th><th>Active terms</th><th className="text-right">Planned</th><th>Protocol</th><th>Profile</th></tr></thead>
                <tbody>
                  {data.runs.map((r) => (
                    <tr key={r.run_id}>
                      <td className="num text-xs">{fmt.shortId(r.run_id)}</td>
                      <td className="num text-xs">{r.reward_hash}</td>
                      <td className="text-xs">{r.active_terms.join(', ') || 'none'}</td>
                      <td className="num text-right">{fmt.compact(r.planned_transitions)}</td>
                      <td className="num text-xs">{r.protocol_hash.slice(0, 8)}</td>
                      <td className="text-xs uppercase">{r.profile}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
            <Card title="Reports">
              <Reports runIds={selected} experimentId={experimentId || undefined} split={split} />
            </Card>
          </div>
        </div>
      )}
    </>
  )
}
