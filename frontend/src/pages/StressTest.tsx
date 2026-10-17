// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import { FlaskConical } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'
import { LineChartPanel } from '../components/charts'
import { DemoButton } from '../components/Launch'
import { Badge, Button, Card, EmptyState, ErrorBanner, Field, Notice, NumberInput, OutcomeBadge, PageHeader, PolicyBadge, Spinner, Table } from '../components/ui'
import { api } from '../lib/api'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import { PRESET_COLOR, PRESET_DASH, PRESET_LABEL, TERM_LABEL } from '../lib/reward'
import type { Preset, RecordingMeta, RewardConfigRow } from '../lib/types'

interface RescoreConfig {
  name: string
  preset: Preset
  reward_hash: string
  active_terms: string[]
  undiscounted: { original: number; training: number; terms: Record<string, number> }
  discounted: { original: number; training: number; terms: Record<string, number> }
  by_phase: Record<string, Record<string, number>>
  cumulative_training: number[]
  explanations: string[]
}

interface RescoreResult {
  kind: string
  disclaimer: string
  recording_id: string
  gamma: number
  steps: number
  outcome: string
  phase_steps: Record<string, number>
  phase_labels: Record<string, string>
  series_index: number[]
  cumulative_original: number[]
  configs: RescoreConfig[]
}

const PHASES = ['hover', 'airborne', 'ground_contact', 'final_step']

export default function StressTest() {
  const recs = useApi<RecordingMeta[]>('/api/recordings')
  const configs = useApi<RewardConfigRow[]>('/api/reward-configs')
  const [recId, setRecId] = useState('')
  const [chosen, setChosen] = useState<string[]>(['preset:baseline', 'preset:time-penalty', 'preset:hover-bonus', 'preset:potential'])
  const [gamma, setGamma] = useState(0.999)
  const [result, setResult] = useState<RescoreResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (!recId && recs.data?.length) setRecId(recs.data[0].recording_id)
  }, [recs.data, recId])
  const rec = recs.data?.find((r) => r.recording_id === recId)
  const custom = (configs.data ?? []).filter((c) => !c.builtin)
  const gammaInvalid = !(gamma > 0 && gamma <= 1)

  const run = async () => {
    setPending(true)
    setError(null)
    try {
      const presets = chosen.filter((c) => c.startsWith('preset:')).map((c) => c.slice(7))
      const config_ids = chosen.filter((c) => c.startsWith('config:')).map((c) => c.slice(7))
      setResult(await api.post<RescoreResult>(`/api/recordings/${recId}/rescore`, { presets, config_ids, gamma }))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(false)
    }
  }

  const chart = useMemo(() => {
    if (!result) return null
    const data = result.series_index.map((t, i) => {
      const row: Record<string, number> = { t, original: result.cumulative_original[i] }
      result.configs.forEach((c, ci) => (row[`c${ci}`] = c.cumulative_training[i]))
      return row
    })
    const series = result.configs.map((c, ci) => ({ key: `c${ci}`, label: c.name, color: PRESET_COLOR[c.preset], dashed: !!PRESET_DASH[c.preset] }))
    return { data, series }
  }, [result])

  if (recs.data && !recs.data.length)
    return (
      <>
        <PageHeader title="Reward Stress Test" />
        <EmptyState title="Record a flight first" action={<DemoButton policy="heuristic" label="Record heuristic flight" />}>
          The stress test re-scores an existing trajectory. Record any flight (random, heuristic or a trained policy) and come back.
        </EmptyState>
      </>
    )

  return (
    <>
      <PageHeader title="Reward Stress Test" subtitle="Score one recorded flight under several reward designs to see which parts of the behaviour each term pays for." />
      <div className="mb-6">
        <Notice tone="warn" title="Re-scoring an existing trajectory — not retraining, not a prediction">
          The flight is not re-simulated and no policy is trained. These numbers show how each reward would score behaviour that already happened. They do not predict what PPO would learn under that reward, and they are not causal evidence that a reward produces any behaviour.
        </Notice>
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Card title="Set up">
          <div className="space-y-4">
            <Field label="Trajectory" htmlFor="st-rec">
              <select id="st-rec" className="field" value={recId} onChange={(e) => { setRecId(e.target.value); setResult(null) }}>
                {(recs.data ?? []).map((r) => (
                  <option key={r.recording_id} value={r.recording_id}>
                    {r.policy.kind.toUpperCase()} · seed {r.episode_seed} · {r.length} steps · {r.pad_landing ? 'pad landing' : r.env_outcome.replaceAll('_', ' ')}
                  </option>
                ))}
              </select>
            </Field>
            {rec && (
              <div className="flex flex-wrap items-center gap-2">
                <PolicyBadge kind={rec.policy.kind} />
                <OutcomeBadge outcome={rec.env_outcome} pad={rec.pad_landing} category={rec.landing_category} />
                <Link to={`/replay/${rec.recording_id}`} className="text-xs text-accent hover:underline">open in replay</Link>
              </div>
            )}
            <fieldset>
              <legend className="mb-1.5 text-[13px] font-medium text-ink-2">Reward configurations</legend>
              <ul className="space-y-1">
                {(['baseline', 'time-penalty', 'hover-bonus', 'potential'] as Preset[]).map((p) => (
                  <li key={p}>
                    <label className="flex cursor-pointer items-center gap-2 text-[13px]">
                      <input type="checkbox" className="accent-[#3cc8d4]" checked={chosen.includes(`preset:${p}`)} onChange={(e) => setChosen((c) => (e.target.checked ? [...c, `preset:${p}`] : c.filter((x) => x !== `preset:${p}`)))} />
                      <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[p] }} />
                      {PRESET_LABEL[p]}
                    </label>
                  </li>
                ))}
                {custom.map((c) => (
                  <li key={c.id}>
                    <label className="flex cursor-pointer items-center gap-2 text-[13px]">
                      <input type="checkbox" className="accent-[#3cc8d4]" checked={chosen.includes(`config:${c.id}`)} onChange={(e) => setChosen((cur) => (e.target.checked ? [...cur, `config:${c.id}`] : cur.filter((x) => x !== `config:${c.id}`)))} />
                      <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR.custom }} />
                      {c.name} · rev {c.revision}
                    </label>
                  </li>
                ))}
              </ul>
            </fieldset>
            <Field label="Discount γ for the discounted return" htmlFor="st-gamma" hint="PPO uses 0.999 here; potential shaping uses this γ too." error={gammaInvalid ? '0 < γ ≤ 1' : null}>
              <NumberInput id="st-gamma" value={gamma} onChange={setGamma} min={0.5} max={1} step={0.001} invalid={gammaInvalid} />
            </Field>
            <Button variant="primary" icon={<FlaskConical className="size-4" />} pending={pending} disabled={!recId || !chosen.length || gammaInvalid} onClick={run}>
              Re-score trajectory
            </Button>
            <ErrorBanner error={error} />
          </div>
        </Card>
        <div className="min-w-0 space-y-6">
          {!result ? (
            recs.data ? <EmptyState title="Choose a trajectory and reward configurations">Results appear here: returns under each reward, discounted and undiscounted, and which phases of the flight each term pays for.</EmptyState> : <Spinner />
          ) : (
            <>
              <Card title="Returns under each reward" eyebrow={`${result.steps} steps · outcome ${result.outcome} · γ = ${result.gamma}`}>
                <Table>
                  <thead>
                    <tr>
                      <th>Reward</th>
                      <th className="text-right">Undiscounted</th>
                      <th className="text-right">Discounted</th>
                      <th>Additional terms (undiscounted · discounted)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.configs.map((c) => (
                      <tr key={c.reward_hash + c.name}>
                        <td>
                          <span className="inline-flex items-center gap-1.5">
                            <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[c.preset] }} />
                            {c.name}
                          </span>
                        </td>
                        <td className="num text-right">{fmt.num(c.undiscounted.training, 2)}</td>
                        <td className="num text-right">{fmt.num(c.discounted.training, 2)}</td>
                        <td className="text-xs">
                          {Object.keys(c.undiscounted.terms).length === 0 ? (
                            <span className="text-ink-3">none (original reward only)</span>
                          ) : (
                            Object.keys(c.undiscounted.terms).map((k) => (
                              <span key={k} className="num mr-3 inline-block">
                                {TERM_LABEL[k] ?? k}: {fmt.signed(c.undiscounted.terms[k], 2)} · {fmt.signed(c.discounted.terms[k], 2)}
                              </span>
                            ))
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <p className="mt-2 text-xs text-ink-3">Shaped totals of different rewards are on different scales; compare how each changes the ranking of behaviours, not the raw numbers.</p>
              </Card>
              {chart && (
                <Card title="Cumulative training return along the flight">
                  <LineChartPanel ariaLabel="Cumulative training return per reward configuration versus step" data={chart.data} x="t" xLabel="step" xFormat={(v) => String(v)} series={chart.series} />
                </Card>
              )}
              <Card title="Which parts of the flight each term pays for" eyebrow="sum of each component by flight phase (detector-defined)">
                <div className="mb-3 flex flex-wrap gap-2 text-xs">
                  {PHASES.map((p) => (
                    <Badge key={p} tone="neutral">
                      {result.phase_labels[p]?.split(' (')[0]}: {result.phase_steps[p]} steps
                    </Badge>
                  ))}
                </div>
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                  {result.configs.map((c) => (
                    <div key={c.reward_hash + c.name} className="rounded-md border border-line p-3">
                      <div className="mb-2 flex items-center gap-1.5 text-[13px] font-medium">
                        <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[c.preset] }} />
                        {c.name}
                      </div>
                      <Table>
                        <thead>
                          <tr>
                            <th>Component</th>
                            {PHASES.map((p) => (
                              <th key={p} className="text-right">{p.replace('_', ' ')}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(c.by_phase).map(([comp, phases]) => (
                            <tr key={comp}>
                              <td className="text-xs">{comp === 'original' ? 'original reward' : TERM_LABEL[comp] ?? comp}</td>
                              {PHASES.map((p) => (
                                <td key={p} className="num text-right text-xs">{fmt.signed(phases[p], 1)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                      {c.explanations.length > 0 && (
                        <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-ink-2">
                          {c.explanations.map((e) => <li key={e}>{e}</li>)}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
                <p className="mt-3 text-xs text-ink-3">“Final step” isolates the last transition: under potential shaping it carries −α·Φ(s) (absorbing Φ = 0), which cancels the potential gathered earlier, so a crash can show a positive shaping step without the episode being rewarded overall.</p>
              </Card>
            </>
          )}
        </div>
      </div>
    </>
  )
}
