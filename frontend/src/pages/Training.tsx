import { Gauge, Layers } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { ActiveJobs, useJobWatch } from '../components/Jobs'
import { LaunchForm } from '../components/Launch'
import { DEFAULT_PHYSICS, PhysicsFields, type PhysicsRanges, physicsError, physicsPayload } from '../components/Physics'
import { Button, Card, Dialog, EmptyState, ErrorBanner, EvidenceBadge, Field, Notice, PageHeader, Segmented, Spinner, StateBadge, Table } from '../components/ui'
import { api, idempotencyKey } from '../lib/api'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import { PRESET_COLOR, PRESET_LABEL } from '../lib/reward'
import type { Job, Preset, RunSummary, SystemInfo } from '../lib/types'

interface Plan {
  n_runs: number
  transitions_per_run: number
  total_transitions: number
  estimated_hours: number | null
  warnings: string[]
  variants?: { name: string; transitions_per_run: number }[]
}

type PhysicsMode = 'fixed' | 'randomized' | 'both'

function SuitePlanner() {
  const [presets, setPresets] = useState<Preset[]>(['baseline', 'time-penalty', 'hover-bonus', 'potential'])
  const [seedsText, setSeedsText] = useState('0, 1, 2')
  const [profile, setProfile] = useState<'smoke' | 'standard' | 'extended'>('standard')
  const [name, setName] = useState('reward-shaping-suite')
  const [algos, setAlgos] = useState<('ppo' | 'dqn')[]>(['ppo'])
  const [gammasText, setGammasText] = useState('')
  const [budgetText, setBudgetText] = useState('')
  const [physicsMode, setPhysicsMode] = useState<PhysicsMode>('fixed')
  const [physics, setPhysics] = useState<PhysicsRanges>(DEFAULT_PHYSICS)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [confirm, setConfirm] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<string | null>(null)

  const seeds = useMemo(() => seedsText.split(/[\s,]+/).filter(Boolean).map(Number), [seedsText])
  const seedsValid = seeds.length > 0 && seeds.length <= 10 && seeds.every((s) => Number.isInteger(s) && s >= 0 && s <= 999) && new Set(seeds).size === seeds.length
  const gammas = useMemo(() => gammasText.split(/[\s,]+/).filter(Boolean).map(Number), [gammasText])
  const gammasValid = gammas.length <= 3 && gammas.every((g) => g > 0.9 && g < 1)
  const budget = budgetText.trim() === '' ? null : Number(budgetText)
  const budgetValid = budget === null || (Number.isInteger(budget) && budget >= 4096 && budget <= 20_000_000)
  const physicsValid = physicsMode === 'fixed' || physicsError(physics) === null
  const body = {
    presets,
    seeds,
    profile,
    algos,
    gammas,
    physics: physicsMode,
    ...(physicsMode !== 'fixed' ? { physics_config: physicsPayload(physics) } : {}),
    ...(budget !== null ? { total_transitions: budget } : {}),
  }

  const doPlan = async () => {
    setError(null)
    try {
      setPlan(await api.post<Plan>('/api/experiments/plan', body))
      setConfirm(true)
    } catch (e) {
      setError((e as Error).message)
    }
  }
  const create = async () => {
    setPending(true)
    setError(null)
    try {
      const exp = await api.post<{ experiment_id: string }>('/api/experiments', { ...body, name, start: true, confirm_large: true, idempotency_key: idempotencyKey() })
      setCreated(exp.experiment_id)
      setConfirm(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="space-y-4">
      <fieldset>
        <legend className="mb-2 text-[13px] font-medium text-ink-2">Reward presets</legend>
        <div className="flex flex-wrap gap-2">
          {(['baseline', 'time-penalty', 'hover-bonus', 'potential'] as Preset[]).map((p) => (
            <label key={p} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line-strong px-3 py-1.5 text-[13px] has-[:checked]:border-accent/50 has-[:checked]:bg-accent/[0.06]">
              <input type="checkbox" className="accent-[#3cc8d4]" checked={presets.includes(p)} onChange={(e) => setPresets((cur) => (e.target.checked ? [...cur, p] : cur.filter((x) => x !== p)))} />
              <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[p] }} />
              {PRESET_LABEL[p]}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Field label="Training seeds" htmlFor="suite-seeds" hint="Comma-separated, distinct, 0–999. At least 3 recommended." error={seedsValid ? null : 'Enter 1–10 distinct integers between 0 and 999'}>
          <input id="suite-seeds" className="field num" value={seedsText} onChange={(e) => setSeedsText(e.target.value)} aria-invalid={!seedsValid} />
        </Field>
        <Field label="Profile">
          <Segmented label="Suite profile" value={profile} onChange={setProfile} options={[{ value: 'smoke', label: 'Smoke' }, { value: 'standard', label: 'Standard' }, { value: 'extended', label: 'Extended' }]} />
        </Field>
        <Field label="Experiment name" htmlFor="suite-name">
          <input id="suite-name" className="field" value={name} maxLength={64} onChange={(e) => setName(e.target.value)} />
        </Field>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <fieldset>
          <legend className="mb-2 text-[13px] font-medium text-ink-2">Algorithms</legend>
          <div className="flex flex-wrap gap-2">
            {(['ppo', 'dqn'] as const).map((a) => (
              <label key={a} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line-strong px-3 py-1.5 text-[13px] has-[:checked]:border-accent/50 has-[:checked]:bg-accent/[0.06]">
                <input type="checkbox" className="accent-[#3cc8d4]" checked={algos.includes(a)} onChange={(e) => setAlgos((cur) => (e.target.checked ? [...cur, a] : cur.filter((x) => x !== a)))} />
                {a.toUpperCase()}
              </label>
            ))}
          </div>
          <p className="mt-1 text-xs text-ink-3">With both, every run gets exactly the same number of transitions.</p>
        </fieldset>
        <Field label="Discount factors (optional)" htmlFor="suite-gammas" hint="e.g. 0.99, 0.999: one variant per value per algorithm (controlled ablation). Empty: each algorithm's reference value." error={gammasValid ? null : 'Up to 3 values between 0.9 and 1'}>
          <input id="suite-gammas" className="field num" value={gammasText} onChange={(e) => setGammasText(e.target.value)} aria-invalid={!gammasValid} />
        </Field>
        <Field label="Transitions per run (optional)" htmlFor="suite-budget" hint="Overrides the profile's budget." error={budgetValid ? null : '4,096 – 20,000,000'}>
          <input id="suite-budget" className="field num" inputMode="numeric" placeholder="profile default" value={budgetText} onChange={(e) => setBudgetText(e.target.value)} aria-invalid={!budgetValid} />
        </Field>
      </div>
      <Field label="Training physics">
        <Segmented
          label="Training physics"
          value={physicsMode}
          onChange={setPhysicsMode}
          options={[
            { value: 'fixed', label: 'Fixed (default)' },
            { value: 'randomized', label: 'Randomized' },
            { value: 'both', label: 'Both: fixed vs randomized' },
          ]}
        />
      </Field>
      {physicsMode !== 'fixed' && <PhysicsFields value={physics} onChange={setPhysics} idPrefix="suite-physics" />}
      <ErrorBanner error={error} />
      {created && (
        <Notice tone="good" title="Suite queued">
          Experiment <span className="num">{created}</span> created; its runs train one at a time. Compare them when they finish:{' '}
          <Link className="text-accent hover:underline" to={`/compare?experiment=${created}`}>open comparison</Link>.
        </Notice>
      )}
      <Button icon={<Layers className="size-4" />} disabled={!presets.length || !seedsValid || !algos.length || !gammasValid || !budgetValid || !physicsValid} onClick={doPlan}>
        Plan suite…
      </Button>
      <Dialog
        open={confirm}
        title="Create this multi-seed suite?"
        onClose={() => setConfirm(false)}
        actions={
          <Button variant="primary" pending={pending} onClick={create}>
            Create {plan?.n_runs} runs and queue them
          </Button>
        }
      >
        {plan && (
          <div className="space-y-3">
            <p className="num text-ink">
              {plan.n_runs} runs, up to {fmt.int(plan.transitions_per_run)} transitions each = {fmt.int(plan.total_transitions)} transitions
            </p>
            {plan.variants && plan.variants.length > 1 && (
              <ul className="list-disc pl-5 text-[13px]">
                {plan.variants.map((v) => (
                  <li key={v.name}>
                    {v.name}: <span className="num">{fmt.int(v.transitions_per_run)}</span> transitions per run
                  </li>
                ))}
              </ul>
            )}
            <p>{plan.estimated_hours ? `Estimated ${plan.estimated_hours.toFixed(1)} h of training at the benchmarked throughput, one run at a time.` : 'No benchmark yet, so no time estimate. Run the throughput benchmark first.'}</p>
            {plan.warnings.map((w) => (
              <Notice key={w} tone="warn">
                {w}
              </Notice>
            ))}
            <p className="text-xs text-ink-3">Final-test evaluation is not run automatically; trigger it per run once training ends, after which checkpoints are frozen.</p>
          </div>
        )}
      </Dialog>
    </div>
  )
}

function Benchmark() {
  const sys = useApi<SystemInfo>('/api/system')
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const job = useJobWatch(jobId, (j) => {
    setJobId(null)
    if (j.state !== 'completed') setError(j.error ?? `benchmark ${j.state}`)
    sys.reload()
  })
  const b = sys.data?.benchmark
  return (
    <div className="space-y-3">
      <p className="text-[13px] text-ink-2">Measure transitions per second before changing worker counts. Runs in the analysis lane for about a minute.</p>
      <Button
        icon={<Gauge className="size-4" />}
        pending={!!jobId}
        onClick={async () => {
          setError(null)
          try {
            setJobId((await api.post<Job>('/api/benchmark', { n_envs: [1, 2, 4, 8], ppo: true, idempotency_key: idempotencyKey() })).id)
          } catch (e) {
            setError((e as Error).message)
          }
        }}
      >
        {jobId ? (job?.state === 'queued' ? 'Queued…' : 'Measuring…') : 'Run throughput benchmark'}
      </Button>
      <ErrorBanner error={error} />
      {b ? (
        <Table>
          <thead>
            <tr>
              <th>Vector env</th>
              <th className="text-right">n_envs</th>
              <th className="text-right">Env only</th>
              <th className="text-right">PPO collect + update</th>
            </tr>
          </thead>
          <tbody>
            {b.rows.map((r) => (
              <tr key={`${r.vec_env}-${r.n_envs}`}>
                <td>{r.vec_env === 'dummy' ? 'in-process' : 'subprocess'}</td>
                <td className="num text-right">{r.n_envs}</td>
                <td className="num text-right">{fmt.int(r.env_tps)}/s</td>
                <td className="num text-right">{r.ppo_tps ? `${fmt.int(r.ppo_tps)}/s` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      ) : (
        <p className="text-xs text-ink-3">No benchmark recorded yet.</p>
      )}
      {b && <p className="text-xs text-ink-3">Measured {fmt.time(b.created_at)}. Primary comparisons keep n_envs = 4 regardless of speed so PPO settings stay identical.</p>}
    </div>
  )
}

export default function Training() {
  const runs = useApi<RunSummary[]>('/api/runs', 5000)
  const [filter, setFilter] = useState<'all' | Preset>('all')
  const list = (runs.data ?? []).filter((r) => filter === 'all' || r.reward_preset === filter)

  return (
    <>
      <PageHeader title="Training Console" subtitle="Launch PPO runs, follow live jobs, and open any run for its full telemetry. Budgets are counted in environment transitions." />
      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card title="Launch a training run" eyebrow="Single run">
          <LaunchForm />
        </Card>
        <Card title="Active jobs">
          <ActiveJobs compact />
        </Card>
      </div>
      <div className="mb-6 grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card title="Multi-seed experiment suite" eyebrow="Presets × seeds">
          <SuitePlanner />
        </Card>
        <Card title="Throughput benchmark">
          <Benchmark />
        </Card>
      </div>
      <Card
        title="All runs"
        actions={
          <Segmented
            label="Filter by reward"
            value={filter}
            onChange={setFilter}
            options={[{ value: 'all', label: 'All' }, ...(['baseline', 'time-penalty', 'hover-bonus', 'potential', 'custom'] as Preset[]).map((p) => ({ value: p, label: PRESET_LABEL[p].split(' ')[0] }))]}
          />
        }
      >
        <ErrorBanner error={runs.error?.message} onRetry={runs.reload} />
        {!runs.data ? (
          <Spinner />
        ) : list.length === 0 ? (
          <EmptyState title={runs.data.length ? 'No runs match this filter' : 'No training runs yet'}>
            {runs.data.length ? 'Choose another reward filter.' : 'Use the launcher above. A SMOKE run takes about 15 seconds and verifies the whole pipeline.'}
          </EmptyState>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Reward</th>
                <th className="text-right">Seed</th>
                <th>Profile</th>
                <th>State</th>
                <th className="text-right">Checkpointed</th>
                <th className="text-right">Best val. return</th>
                <th className="text-right">Test return</th>
                <th>Evidence</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.run_id} className="hover:bg-surface-2/50">
                  <td>
                    <Link to={`/runs/${r.run_id}`} className="num text-xs text-accent hover:underline">
                      {fmt.shortId(r.run_id)}
                    </Link>
                  </td>
                  <td>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[r.reward_preset] }} />
                      {r.reward_name}
                      {r.reward_revision && r.reward_preset === 'custom' ? <span className="text-xs text-ink-3">rev {r.reward_revision}</span> : null}
                    </span>
                    {(r.algo === 'dqn' || r.variant) && (
                      <div className="pl-3.5 text-[11px] text-ink-3">{[r.algo === 'dqn' ? 'DQN' : null, r.variant || null].filter(Boolean).join(' · ')}</div>
                    )}
                  </td>
                  <td className="num text-right">{r.seed}</td>
                  <td className="uppercase text-xs tracking-wide text-ink-2">{r.profile}</td>
                  <td>
                    <StateBadge state={r.state} />
                  </td>
                  <td className="num text-right">
                    {fmt.compact(r.checkpoint_transitions)} / {fmt.compact(r.planned_transitions)}
                  </td>
                  <td className="num text-right">{fmt.num(r.best_validation?.validation_mean_original_return, 1)}</td>
                  <td className="num text-right">{fmt.num(r.latest_test?.mean_original_return, 1)}</td>
                  <td>
                    <EvidenceBadge evidence={r.evidence} />
                  </td>
                  <td className="text-xs text-ink-3">{fmt.time(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </>
  )
}
