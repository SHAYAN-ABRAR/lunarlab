// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import clsx from 'clsx'
import { CheckCircle2, Circle, CircleDot, GitCompareArrows, SlidersHorizontal, XCircle } from 'lucide-react'
import { Link } from 'react-router'
import { ActiveJobs } from '../components/Jobs'
import { DemoButton, TrainPresetButton } from '../components/Launch'
import { Card, EmptyState, ErrorBanner, EvidenceBadge, PageHeader, Spinner, StateBadge, Table } from '../components/ui'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import { PRESET_COLOR, PRESET_LABEL } from '../lib/reward'
import type { Experiment, Job, Preset, RecordingMeta, RunSummary } from '../lib/types'

interface OverviewData {
  runs: RunSummary[]
  n_runs: number
  active_jobs: Job[]
  recordings: number
  experiments: Experiment[]
  by_preset: Record<string, { runs: number; evaluations: { run_id: string; seed: number; profile: string; split: string; mean_original_return: number; pad_landing_rate: number }[] }>
  readiness: Record<string, { ok: boolean; detail: string } | boolean>
  queue_paused: boolean
}

type StepState = 'done' | 'active' | 'todo'

function presetStatus(preset: Preset, runs: RunSummary[], jobs: Job[]) {
  const mine = runs.filter((r) => r.reward_preset === preset && (r.algo ?? 'ppo') === 'ppo' && !r.variant)
  const real = mine.filter((r) => r.profile !== 'smoke')
  const training = mine.some((r) => r.state === 'running') || jobs.some((j) => mine.some((r) => r.run_id === j.run_id) && (j.kind === 'train' || j.kind === 'resume'))
  const evaluated = real.filter((r) => r.latest_test || r.latest_validation)
  const tested = real.filter((r) => r.latest_test)
  let label: string
  let tone: 'neutral' | 'active' | 'warn' | 'good'
  if (training) {
    label = 'training'
    tone = 'active'
  } else if (tested.length >= 3) {
    label = 'evaluated'
    tone = 'good'
  } else if (evaluated.length) {
    label = 'insufficient evidence'
    tone = 'warn'
  } else if (mine.length && mine.every((r) => r.profile === 'smoke')) {
    label = 'smoke tests only'
    tone = 'warn'
  } else {
    label = 'not trained'
    tone = 'neutral'
  }
  return { label, tone, mine, real, evaluated, tested }
}

function Step({ n, title, state, children }: { n: number; title: string; state: StepState; children: React.ReactNode }) {
  const Icon = state === 'done' ? CheckCircle2 : state === 'active' ? CircleDot : Circle
  return (
    <li className={clsx('relative rounded-lg border p-4', state === 'active' ? 'border-accent/45 bg-accent/[0.05]' : 'border-line bg-surface')}>
      <div className="flex items-center gap-2">
        <Icon className={clsx('size-4', state === 'done' ? 'text-good' : state === 'active' ? 'text-accent' : 'text-ink-3')} aria-hidden />
        <span className="num text-xs text-ink-3">0{n}</span>
        <span className="sr-only">{state === 'done' ? 'completed step' : state === 'active' ? 'next step' : 'not started'}</span>
      </div>
      <h3 className="mt-2 text-[13.5px] font-semibold leading-snug text-ink">{title}</h3>
      <div className="mt-1.5 text-xs leading-relaxed text-ink-3">{children}</div>
    </li>
  )
}

export default function Overview() {
  const { data, error, reload } = useApi<OverviewData>('/api/overview', 4000)
  const recs = useApi<RecordingMeta[]>('/api/recordings', 15000)

  const runs = data?.runs ?? []
  const jobs = data?.active_jobs ?? []
  const hasRandom = (recs.data ?? []).some((r) => r.policy.kind === 'random')
  const st = (p: Preset) => presetStatus(p, runs, jobs)
  const base = st('baseline')
  const hover = st('hover-bonus')
  const pot = st('potential')

  const steps: { title: string; state: StepState; body: React.ReactNode }[] = [
    { title: 'Watch a random agent fail', state: hasRandom ? 'done' : 'active', body: hasRandom ? 'Random flights recorded. Replay them to see the dynamics.' : 'Record one real episode of uniformly random actions.' },
    { title: 'Train a baseline', state: base.real.some((r) => r.completed) ? 'done' : base.mine.length ? 'active' : hasRandom ? 'active' : 'todo', body: 'PPO with the original environment reward. Start with SMOKE to verify the pipeline, then STANDARD.' },
    { title: 'Introduce a bad reward', state: hover.real.some((r) => r.completed) ? 'done' : hover.mine.length ? 'active' : 'todo', body: 'Train the flawed hover bonus, which pays for an intermediate state rather than the landing.' },
    { title: 'Investigate reward hacking', state: hover.evaluated.length ? 'done' : 'todo', body: 'Compare training reward with original-reward performance, hover occupancy and timeouts.' },
    { title: 'Apply a better reward design', state: pot.real.some((r) => r.completed) ? 'done' : pot.mine.length ? 'active' : 'todo', body: 'Potential-based shaping: α(γΦ(s′) − Φ(s)) with Φ(terminal) = 0.' },
    { title: 'Compare the actual results', state: (['baseline', 'hover-bonus', 'potential'] as Preset[]).filter((p) => st(p).tested.length).length >= 2 ? 'done' : 'todo', body: 'Final-test evaluation on 100 fixed seeds, every training seed shown.' },
  ]

  return (
    <>
      <PageHeader
        title="Mission Overview"
        subtitle="Watch a random agent fail, train a baseline, introduce a bad reward, investigate reward hacking, apply a better reward design, and compare what actually happened."
        actions={
          <>
            <DemoButton policy="random" label="Watch Random Agent" />
            <TrainPresetButton preset="baseline" label="Train Baseline" />
            <Link to="/studio" className="inline-flex h-9 items-center gap-2 rounded-md border border-line-strong bg-surface-3 px-4 text-sm font-medium text-ink hover:bg-[#213043]">
              <SlidersHorizontal className="size-4" aria-hidden /> Open Reward Studio
            </Link>
            <Link to="/compare" className="inline-flex h-9 items-center gap-2 rounded-md border border-line-strong bg-surface-3 px-4 text-sm font-medium text-ink hover:bg-[#213043]">
              <GitCompareArrows className="size-4" aria-hidden /> Compare Experiments
            </Link>
          </>
        }
      />
      <ErrorBanner error={error?.message} onRetry={reload} />

      <ol className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6" aria-label="Experiment storyline">
        {steps.map((s, i) => (
          <Step key={s.title} n={i + 1} title={s.title} state={s.state}>
            {s.body}
          </Step>
        ))}
      </ol>

      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-4">
        {(['baseline', 'time-penalty', 'hover-bonus', 'potential'] as Preset[]).map((p) => {
          const s = st(p)
          const evs = data?.by_preset[p]?.evaluations ?? []
          const testEvs = evs.filter((e) => e.split === 'test')
          const pool = testEvs.length ? testEvs : evs
          // One training budget per card: the profile with the most evaluated runs.
          const counts = new Map<string, number>()
          for (const e of pool) counts.set(e.profile, (counts.get(e.profile) ?? 0) + 1)
          const profile = [...counts.entries()].toSorted((a, b) => b[1] - a[1])[0]?.[0]
          const shown = pool.filter((e) => e.profile === profile)
          const others = pool.length - shown.length
          const mean = shown.length ? shown.reduce((a, e) => a + e.mean_original_return, 0) / shown.length : null
          const pad = shown.length ? shown.reduce((a, e) => a + e.pad_landing_rate, 0) / shown.length : null
          return (
            <Card key={p} bodyClassName="p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="inline-block size-2.5 rounded-full" style={{ background: PRESET_COLOR[p] }} aria-hidden />
                  <h2 className="text-[14px] font-semibold">{PRESET_LABEL[p]}</h2>
                </div>
                <span className={clsx('rounded-full border px-2 py-0.5 text-[11px] font-medium', {
                  'border-line-strong text-ink-3': s.tone === 'neutral',
                  'border-accent/40 bg-accent/10 text-accent': s.tone === 'active',
                  'border-warn/35 bg-warn/10 text-warn': s.tone === 'warn',
                  'border-good/35 bg-good/10 text-good': s.tone === 'good',
                })}>
                  {s.label}
                </span>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div>
                  <div className="eyebrow">Original return</div>
                  <div className="num mt-1 text-lg text-ink">{fmt.num(mean, 1)}</div>
                </div>
                <div>
                  <div className="eyebrow">Pad landing</div>
                  <div className="num mt-1 text-lg text-ink">{fmt.pct(pad)}</div>
                </div>
              </div>
              <p className="mt-2 text-[11px] text-ink-3">
                {shown.length
                  ? `Mean over ${shown.length} ${String(profile).toUpperCase()} seed(s), ${testEvs.length ? 'final test' : 'validation'} split.${others ? ` ${others} run(s) with another budget not included.` : ''} ${shown.length < 3 ? 'Too few seeds for conclusions.' : ''}`
                  : 'No non-smoke evaluation yet.'}
              </p>
            </Card>
          )
        })}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card title="Recent runs" actions={<Link to="/training" className="text-[13px] text-accent hover:underline">All runs →</Link>}>
          {!data ? (
            <Spinner />
          ) : runs.length === 0 ? (
            <EmptyState title="No experiments yet" action={<><DemoButton policy="random" label="Watch Random Agent" /><TrainPresetButton preset="baseline" label="Train a SMOKE baseline" /></>}>
              Start by watching a real random-policy flight, then run a SMOKE baseline (about 15 seconds) to verify the training pipeline on this machine.
            </EmptyState>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Reward</th>
                  <th>Seed</th>
                  <th>State</th>
                  <th className="text-right">Transitions</th>
                  <th className="text-right">Best val. return</th>
                  <th>Evidence</th>
                </tr>
              </thead>
              <tbody>
                {runs.slice(0, 8).map((r) => (
                  <tr key={r.run_id}>
                    <td>
                      <Link to={`/runs/${r.run_id}`} className="num text-xs text-accent hover:underline">
                        {fmt.shortId(r.run_id)}
                      </Link>
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-1.5">
                        <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[r.reward_preset] }} />
                        {r.reward_name}
                      </span>
                    </td>
                    <td className="num">{r.seed}</td>
                    <td>
                      <StateBadge state={r.state} />
                    </td>
                    <td className="num text-right">{fmt.compact(r.checkpoint_transitions)} / {fmt.compact(r.planned_transitions)}</td>
                    <td className="num text-right">{fmt.num(r.best_validation?.validation_mean_original_return, 1)}</td>
                    <td>
                      <EvidenceBadge evidence={r.evidence} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
        <div className="space-y-6">
          <Card title="Active jobs">
            <ActiveJobs compact />
          </Card>
          <Card title="Readiness">
            <ul className="space-y-2 text-[13px]">
              {[
                ['environment', 'LunarLander-v3 + Box2D'],
                ['video', 'Video encoding'],
              ].map(([k, label]) => {
                const r = data?.readiness?.[k] as { ok: boolean; detail: string } | undefined
                return (
                  <li key={k} className="flex items-start gap-2">
                    {r === undefined ? <Circle className="mt-0.5 size-4 text-ink-3" aria-hidden /> : r.ok ? <CheckCircle2 className="mt-0.5 size-4 text-good" aria-hidden /> : <XCircle className="mt-0.5 size-4 text-warn" aria-hidden />}
                    <div>
                      <div className="text-ink">{label}</div>
                      <div className="text-xs text-ink-3">{r ? r.detail : 'checking…'}</div>
                    </div>
                  </li>
                )
              })}
              <li className="flex items-start gap-2">
                <CheckCircle2 className="mt-0.5 size-4 text-good" aria-hidden />
                <div>
                  <div className="text-ink">Recordings</div>
                  <div className="text-xs text-ink-3">{data ? `${data.recordings} saved flight(s)` : '—'}</div>
                </div>
              </li>
            </ul>
            <p className="mt-3 text-xs text-ink-3">
              Full diagnostics: <code className="num">python -m lunarlab doctor</code>
            </p>
          </Card>
        </div>
      </div>
    </>
  )
}
