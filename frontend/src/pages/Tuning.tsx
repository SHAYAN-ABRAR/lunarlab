import clsx from 'clsx'
import { Ban, Play, RotateCcw, Trophy, Wand2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Badge, Button, Card, Dialog, EmptyState, ErrorBanner, Field, Notice, NumberInput, PageHeader, Segmented, Spinner, Table } from '../components/ui'
import { api, idempotencyKey } from '../lib/api'
import { DEMO } from '../lib/demo'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import { PRESET_LABEL } from '../lib/reward'
import type { Job, Preset } from '../lib/types'

interface ParamSpec {
  type: 'float' | 'int' | 'categorical'
  low?: number
  high?: number
  log?: boolean
  choices?: number[]
}

interface Trial {
  number: number
  state: 'running' | 'complete' | 'pruned' | 'fail' | 'waiting'
  value: number | null
  params: Record<string, number>
  run_id: string | null
  best_validation: number | null
  pruned_at: number | null
  cancelled: boolean
  interrupted: boolean
  intermediate: [number, number][]
}

interface Study {
  study_id: string
  name: string
  created_at: string
  algo: 'ppo' | 'dqn'
  preset: Preset
  params: string[]
  space: Record<string, ParamSpec>
  n_trials: number
  trial_transitions: number
  validation_every: number
  warmup_transitions: number
  startup_trials: number
  objective: string
  status: { state?: string; current_trial?: number | null; updated_at?: string; cancel_requested?: boolean }
  counts: Record<string, number>
  finished: number
  best: Trial | null
  trials?: Trial[]
  jobs?: Job[]
}

const STATE_TONE: Record<string, 'good' | 'warn' | 'crit' | 'info' | 'neutral'> = {
  complete: 'good',
  pruned: 'warn',
  fail: 'crit',
  running: 'info',
  waiting: 'neutral',
}

function paramLabel(name: string) {
  return name.replace(/^reward\./, '').replace(/^(ppo|dqn)\./, '')
}

function fmtParam(v: number) {
  return Number.isInteger(v) ? String(v) : Math.abs(v) < 0.01 ? v.toExponential(2) : v.toPrecision(3)
}

function NewStudy({ onCreated }: { onCreated: (id: string) => void }) {
  const [name, setName] = useState('study')
  const [algo, setAlgo] = useState<'ppo' | 'dqn'>('ppo')
  const [preset, setPreset] = useState<Preset>('potential')
  const space = useApi<{ params: Record<string, ParamSpec>; defaults: string[] }>(`/api/tuning/space?algo=${algo}&preset=${preset}`)
  const [chosen, setChosen] = useState<string[]>([])
  const [trials, setTrials] = useState(20)
  const [transitions, setTransitions] = useState(200_000)
  const [validationEvery, setValidationEvery] = useState(25_000)
  const [warmup, setWarmup] = useState(50_000)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (space.data) setChosen(space.data.defaults)
  }, [space.data])

  const valid = chosen.length > 0 && trials >= 1 && trials <= 200 && transitions >= 4096 && validationEvery >= 4096 && validationEvery <= transitions && warmup >= 0
  const create = async () => {
    setPending(true)
    setError(null)
    try {
      const res = await api.post<{ study: Study; job: Job | null }>('/api/tuning', {
        name,
        algo,
        preset,
        params: chosen,
        n_trials: trials,
        trial_transitions: transitions,
        validation_every: validationEvery,
        warmup_transitions: warmup,
        start: true,
        idempotency_key: idempotencyKey(),
      })
      onCreated(res.study.study_id)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(false)
    }
  }

  return (
    <Card title="New study" eyebrow="Optuna · TPE sampler · median pruner">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Field label="Name" htmlFor="tune-name">
          <input id="tune-name" className="field" value={name} maxLength={48} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Algorithm">
          <Segmented label="Algorithm" value={algo} onChange={setAlgo} options={[{ value: 'ppo', label: 'PPO' }, { value: 'dqn', label: 'DQN' }]} />
        </Field>
        <Field label="Reward" htmlFor="tune-preset">
          <select id="tune-preset" className="field" value={preset} onChange={(e) => setPreset(e.target.value as Preset)}>
            {(['baseline', 'time-penalty', 'hover-bonus', 'potential'] as Preset[]).map((p) => (
              <option key={p} value={p}>
                {PRESET_LABEL[p]}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <fieldset className="mt-4">
        <legend className="mb-2 text-[13px] font-medium text-ink-2">Parameters to tune</legend>
        {!space.data ? (
          <Spinner />
        ) : (
          <div className="flex flex-wrap gap-2">
            {Object.entries(space.data.params).map(([n, sp]) => (
              <label key={n} className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-line-strong px-3 py-1.5 text-[13px] has-[:checked]:border-accent/50 has-[:checked]:bg-accent/[0.06]">
                <input type="checkbox" className="accent-[#3cc8d4]" checked={chosen.includes(n)} onChange={(e) => setChosen((c) => (e.target.checked ? [...c, n] : c.filter((x) => x !== n)))} />
                <span className="font-mono text-xs">{n}</span>
                <span className="text-[11px] text-ink-3">{sp.type === 'categorical' ? `{${(sp.choices ?? []).join(', ')}}` : `${sp.low}–${sp.high}${sp.log ? ' (log)' : ''}`}</span>
              </label>
            ))}
          </div>
        )}
      </fieldset>
      <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Field label="Trials" htmlFor="tune-trials">
          <NumberInput id="tune-trials" value={trials} onChange={setTrials} min={1} max={200} step={1} />
        </Field>
        <Field label="Transitions per trial" htmlFor="tune-tr">
          <NumberInput id="tune-tr" value={transitions} onChange={setTransitions} min={4096} max={3_000_000} step={4096} />
        </Field>
        <Field label="Validate every" htmlFor="tune-ve" hint="Each validation is reported to the pruner.">
          <NumberInput id="tune-ve" value={validationEvery} onChange={setValidationEvery} min={4096} step={4096} />
        </Field>
        <Field label="No pruning before" htmlFor="tune-wu" hint="Transitions of warm-up.">
          <NumberInput id="tune-wu" value={warmup} onChange={setWarmup} min={0} step={4096} />
        </Field>
      </div>
      <p className="mt-3 text-xs text-ink-3">
        Up to {fmt.int(trials * transitions)} training transitions in total (pruned trials stop early). Every trial is a normal run with the same training seed, judged by its best validation
        return on the default-physics validation seeds. Trial runs are never evaluated on the final-test seeds.
      </p>
      <ErrorBanner error={error} />
      <div className="mt-3">
        <Button variant="primary" icon={<Play className="size-4" aria-hidden />} pending={pending} disabled={!valid || DEMO} onClick={create}>
          Create and start
        </Button>
      </div>
    </Card>
  )
}

function TrialCurves({ trials }: { trials: Trial[] }) {
  const series = trials.filter((t) => t.intermediate.length)
  if (!series.length) return <div className="py-8 text-center text-[13px] text-ink-3">No validation reported yet.</div>
  const best = trials.reduce<Trial | null>((b, t) => (t.state === 'complete' && t.value != null && (!b || (b.value ?? -Infinity) < t.value) ? t : b), null)
  return (
    <figure aria-label="Validation return of every trial against training transitions">
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart margin={{ top: 6, right: 12, bottom: 16, left: 4 }}>
            <CartesianGrid stroke="#1b2532" vertical={false} />
            <XAxis dataKey="x" type="number" domain={['dataMin', 'dataMax']} allowDuplicatedCategory={false} tick={{ fill: '#8494a8', fontSize: 11, fontFamily: 'IBM Plex Mono' }} tickFormatter={(v) => fmt.compact(v)} stroke="#2d3e52" tickLine={false} label={{ value: 'transitions', position: 'insideBottom', offset: -10, fill: '#8494a8', fontSize: 11 }} />
            <YAxis tick={{ fill: '#8494a8', fontSize: 11, fontFamily: 'IBM Plex Mono' }} stroke="#2d3e52" tickLine={false} width={48} />
            <ReferenceLine y={200} stroke="#5b6f88" strokeDasharray="3 4" />
            <Tooltip
              isAnimationActive={false}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="rounded-md border border-line-strong bg-surface-2/95 px-3 py-2 text-xs shadow-xl">
                    <div className="num mb-1 text-ink-3">{fmt.compact(Number(label))} transitions</div>
                    {payload.slice(0, 10).map((p) => (
                      <div key={String(p.name)} className="num flex justify-between gap-4">
                        <span className="text-ink-2">{p.name}</span>
                        <span className="text-ink">{fmt.num(Number(p.value), 1)}</span>
                      </div>
                    ))}
                  </div>
                ) : null
              }
            />
            {series.map((t) => (
              <Line
                key={t.number}
                data={t.intermediate.map(([x, y]) => ({ x, y }))}
                dataKey="y"
                name={`trial ${t.number}`}
                stroke={best && t.number === best.number ? '#3cc8d4' : t.state === 'pruned' ? '#c98500' : t.state === 'fail' ? '#d95926' : '#8494a8'}
                strokeDasharray={t.state === 'pruned' ? '4 3' : undefined}
                strokeWidth={best && t.number === best.number ? 2.4 : 1.2}
                strokeOpacity={best && t.number === best.number ? 1 : 0.75}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-ink-3">Validation mean original return reported after each validation. Cyan: best trial; amber dashed: pruned; grey: other completed trials.</figcaption>
    </figure>
  )
}

function StudyView({ id }: { id: string }) {
  const study = useApi<Study>(`/api/tuning/${id}`, 3000)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [apply, setApply] = useState(false)
  const [seedsText, setSeedsText] = useState('0, 1, 2')
  const [profile, setProfile] = useState<'smoke' | 'standard' | 'extended'>('standard')
  const [created, setCreated] = useState<string | null>(null)
  const s = study.data
  const running = !!s?.jobs?.length
  const seeds = useMemo(() => seedsText.split(/[\s,]+/).filter(Boolean).map(Number), [seedsText])
  const seedsValid = seeds.length > 0 && seeds.length <= 10 && seeds.every((x) => Number.isInteger(x) && x >= 0 && x <= 999)

  const call = async (what: string, path: string, body: unknown = {}) => {
    setBusy(what)
    setError(null)
    try {
      const r = await api.post<{ experiment_id?: string }>(path, body)
      if (what === 'apply' && r.experiment_id) {
        setCreated(r.experiment_id)
        setApply(false)
      }
      study.reload()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(null)
    }
  }

  if (!s) return study.error ? <ErrorBanner error={study.error.message} /> : <Spinner />
  const trials = (s.trials ?? []).toSorted((a, b) => a.number - b.number)
  return (
    <Card
      title={s.name}
      eyebrow={`${s.algo.toUpperCase()} · ${PRESET_LABEL[s.preset]} · ${s.study_id}`}
      actions={
        <>
          {running ? (
            <Button size="sm" variant="danger" icon={<Ban className="size-4" aria-hidden />} pending={busy === 'cancel'} onClick={() => call('cancel', `/api/tuning/${id}/cancel`)}>
              Cancel
            </Button>
          ) : (
            s.finished < s.n_trials && (
              <Button size="sm" icon={<RotateCcw className="size-4" aria-hidden />} pending={busy === 'resume'} disabled={DEMO} onClick={() => call('resume', `/api/tuning/${id}/resume`)}>
                Resume
              </Button>
            )
          )}
          <Button size="sm" variant="primary" icon={<Trophy className="size-4" aria-hidden />} disabled={!s.best || DEMO} onClick={() => setApply(true)}>
            Normal runs from best
          </Button>
        </>
      }
    >
      <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <div className="eyebrow">State</div>
          <div className="mt-1 text-[13px] text-ink">{running ? 'running' : (s.status.state ?? '—')}</div>
        </div>
        <div>
          <div className="eyebrow">Trials</div>
          <div className="num mt-1 text-[13px] text-ink">
            {s.finished} / {s.n_trials}{' '}
            <span className="text-ink-3">
              ({s.counts.complete ?? 0} complete · {s.counts.pruned ?? 0} pruned · {s.counts.fail ?? 0} failed)
            </span>
          </div>
        </div>
        <div>
          <div className="eyebrow">Best validation</div>
          <div className="num mt-1 text-[13px] text-ink">{s.best ? `${fmt.num(s.best.value, 1)} (trial ${s.best.number})` : '—'}</div>
        </div>
        <div>
          <div className="eyebrow">Budget per trial</div>
          <div className="num mt-1 text-[13px] text-ink">
            {fmt.compact(s.trial_transitions)} · validate {fmt.compact(s.validation_every)} · prune after {fmt.compact(s.warmup_transitions)}
          </div>
        </div>
      </div>
      <ErrorBanner error={error} />
      {created && (
        <Notice tone="good" title="Normal runs created">
          Experiment <span className="num">{created}</span> uses the best settings; its runs train as normal jobs and can be final-tested.{' '}
          <Link className="text-accent hover:underline" to={`/compare?experiment=${created}`}>
            Compare
          </Link>
        </Notice>
      )}
      <TrialCurves trials={trials} />
      <Table className="mt-4">
        <thead>
          <tr>
            <th>#</th>
            <th>State</th>
            <th className="text-right">Value</th>
            {s.params.map((p) => (
              <th key={p} className="text-right">
                {paramLabel(p)}
              </th>
            ))}
            <th>Run</th>
          </tr>
        </thead>
        <tbody>
          {trials.map((t) => (
            <tr key={t.number} className={clsx(s.best?.number === t.number && 'bg-accent/[0.05]')}>
              <td className="num">{t.number}</td>
              <td>
                <Badge tone={STATE_TONE[t.state] ?? 'neutral'}>{t.cancelled ? 'cancelled' : t.interrupted ? 'interrupted' : t.state}</Badge>
                {t.pruned_at != null && <div className="text-[11px] text-ink-3">at {fmt.compact(t.pruned_at)}</div>}
              </td>
              <td className="num text-right">{t.value != null ? fmt.num(t.value, 1) : t.best_validation != null ? <span className="text-ink-3">{fmt.num(t.best_validation, 1)}</span> : '—'}</td>
              {s.params.map((p) => (
                <td key={p} className="num text-right">
                  {t.params[p] != null ? fmtParam(t.params[p]) : '—'}
                </td>
              ))}
              <td>
                {t.run_id ? (
                  <Link className="num text-xs text-accent hover:underline" to={`/runs/${t.run_id}`}>
                    {fmt.shortId(t.run_id)}
                  </Link>
                ) : (
                  '—'
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      <p className="mt-2 text-xs text-ink-3">Objective: {s.objective}. Grey values on pruned or failed trials are their best validation before stopping; Optuna does not rank them.</p>
      <Dialog
        open={apply}
        title="Create normal runs from the best trial?"
        onClose={() => setApply(false)}
        actions={
          <Button variant="primary" pending={busy === 'apply'} disabled={!seedsValid} onClick={() => call('apply', `/api/tuning/${id}/apply`, { seeds, profile, start: true })}>
            Create and queue {seeds.length} run{seeds.length === 1 ? '' : 's'}
          </Button>
        }
      >
        <p className="mb-3 text-[13px]">
          New runs with trial {s.best?.number}&apos;s settings, fresh training seeds and a normal budget. Unlike the trials, they can be evaluated on the final-test seeds.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Training seeds" htmlFor="apply-seeds" error={seedsValid ? null : '1–10 integers, 0–999'}>
            <input id="apply-seeds" className="field num" value={seedsText} onChange={(e) => setSeedsText(e.target.value)} />
          </Field>
          <Field label="Profile">
            <Segmented label="Profile" value={profile} onChange={setProfile} options={[{ value: 'smoke', label: 'Smoke' }, { value: 'standard', label: 'Standard' }, { value: 'extended', label: 'Extended' }]} />
          </Field>
        </div>
      </Dialog>
    </Card>
  )
}

export default function Tuning() {
  const [params, setParams] = useSearchParams()
  const studies = useApi<Study[]>('/api/tuning', 5000)
  const selected = params.get('study') ?? studies.data?.[0]?.study_id ?? null
  const select = (id: string) => setParams({ study: id })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Automatic Tuning"
        subtitle={
          <>
            Optuna searches algorithm settings and reward weights. Each trial is a normal training run judged only on validation episodes; trials that fall behind after a warm-up are pruned.
            The final-test seeds stay untouched until you create normal runs from the best settings.
          </>
        }
      />
      <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="min-w-0 space-y-6">
          <NewStudy onCreated={(id) => { studies.reload(); select(id) }} />
          <Card title="Studies">
            {studies.data && studies.data.length === 0 && (
              <EmptyState icon={<Wand2 className="size-5" />} title="No tuning studies yet">
                Create one above, or from the command line: <span className="font-mono">python -m lunarlab tune --algo ppo --preset potential --trials 20</span>
              </EmptyState>
            )}
            {studies.data && studies.data.length > 0 && (
              <Table>
                <thead>
                  <tr>
                    <th>Study</th>
                    <th>Setup</th>
                    <th>State</th>
                    <th className="text-right">Trials</th>
                    <th className="text-right">Best</th>
                  </tr>
                </thead>
                <tbody>
                  {studies.data.map((st) => (
                    <tr key={st.study_id} className={clsx('cursor-pointer', st.study_id === selected && 'bg-accent/[0.05]')} onClick={() => select(st.study_id)}>
                      <td>
                        <button type="button" className="text-left text-accent hover:underline" onClick={() => select(st.study_id)}>
                          {st.name}
                        </button>
                        <div className="text-[11px] text-ink-3">{fmt.time(st.created_at)}</div>
                      </td>
                      <td className="text-xs">
                        {st.algo.toUpperCase()} · {PRESET_LABEL[st.preset]}
                      </td>
                      <td className="text-xs">{st.status.state ?? '—'}</td>
                      <td className="num text-right">
                        {st.finished}/{st.n_trials}
                      </td>
                      <td className="num text-right">{st.best ? fmt.num(st.best.value, 1) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
            {!studies.data && !studies.error && <Spinner />}
            {studies.error && <ErrorBanner error={studies.error.message} />}
          </Card>
        </div>
        <div className="min-w-0">{selected ? <StudyView id={selected} /> : <Card title="Study">Select or create a study.</Card>}</div>
      </div>
    </div>
  )
}
