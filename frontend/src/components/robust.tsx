// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
/**
 * Aggregate statistics across training seeds (IQM, bootstrap intervals, probability of improvement,
 * performance profiles) and robustness under conditions never seen in training.
 */
import clsx from 'clsx'
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmt } from '../lib/format'
import { PRESET_COLOR, PRESET_DASH } from '../lib/reward'
import type { Preset } from '../lib/types'
import { Legend } from './charts'
import { Card, Table } from './ui'

type CI = [number, number] | null

export interface RobustStats {
  groups: Record<
    string,
    {
      n_runs: number
      run_scores: number[]
      iqm: number | null
      iqm_ci: CI
      mean: number | null
      mean_ci: CI
      pad_rate_mean: number | null
      pad_rate_ci: CI
      profile: { tau: number[]; fraction: number[]; lo: number[]; hi: number[] }
    }
  >
  probability_of_improvement: Record<string, { vs: string; p: number | null; ci: CI }>
  reference: string | null
  note?: string
}

export interface RobustnessTable {
  conditions: Record<string, string>
  rows: {
    reward_name: string
    reward_preset: Preset
    algo: string
    conditions: Record<string, { per_seed: { seed: number; mean_original_return: number; pad_landing_rate: number; crash_rate: number }[]; mean_original_return: number; pad_landing_rate: number; crash_rate: number; n_seeds: number }>
  }[]
  note: string
}

export interface GroupStyle {
  name: string
  preset: Preset
  algo: string
}

const AXIS = { fill: '#8494a8', fontSize: 11, fontFamily: 'IBM Plex Mono' }

function ci(v: CI, digits = 0, pct = false) {
  if (!v) return null
  const f = (x: number) => (pct ? fmt.pct(x) : fmt.num(x, digits))
  return (
    <span className="text-ink-3">
      {' '}
      [{f(v[0])}, {f(v[1])}]
    </span>
  )
}

function styleFor(styles: GroupStyle[], name: string) {
  const s = styles.find((g) => name === g.name || name.startsWith(`${g.name} (`))
  const preset = s?.preset ?? 'custom'
  return { color: PRESET_COLOR[preset], dash: PRESET_DASH[preset], dqn: s?.algo === 'dqn' }
}

export function RobustStatsCard({ stats, styles }: { stats: RobustStats; styles: GroupStyle[] }) {
  const names = Object.keys(stats.groups)
  if (!names.length) return null
  const few = names.some((n) => stats.groups[n].n_runs < 5)
  return (
    <Card title="Aggregate across training seeds" eyebrow="robust statistics · Agarwal et al. 2021">
      <p className="mb-4 max-w-[110ch] text-[13px] text-ink-2">
        One score per trained policy (its mean original return on the selected split). The <strong className="text-ink">IQM</strong> averages the middle 50% of
        policies, so one lucky or unlucky seed moves it less than the mean. Intervals are 95% bootstraps over <em>training seeds</em>. P(improvement) is the chance that a randomly
        chosen policy of a group outscores a randomly chosen policy of the reference group ({stats.reference}).
      </p>
      <Table>
        <thead>
          <tr>
            <th>Group</th>
            <th className="text-right">Policies</th>
            <th className="text-right">IQM [95% CI]</th>
            <th className="text-right">Mean [95% CI]</th>
            <th className="text-right">Pad landing [95% CI]</th>
            <th className="text-right">P(improvement) vs reference</th>
          </tr>
        </thead>
        <tbody>
          {names.map((n) => {
            const g = stats.groups[n]
            const poi = stats.probability_of_improvement[n]
            const st = styleFor(styles, n)
            return (
              <tr key={n}>
                <td>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="inline-block size-2 rounded-full" style={{ background: st.color }} />
                    {n}
                  </span>
                </td>
                <td className="num text-right">{g.n_runs}</td>
                <td className="num text-right">
                  {fmt.num(g.iqm, 1)}
                  {ci(g.iqm_ci)}
                </td>
                <td className="num text-right">
                  {fmt.num(g.mean, 1)}
                  {ci(g.mean_ci)}
                </td>
                <td className="num text-right">
                  {fmt.pct(g.pad_rate_mean)}
                  {ci(g.pad_rate_ci, 0, true)}
                </td>
                <td className="num text-right">
                  {n === stats.reference ? (
                    <span className="text-ink-3">reference</span>
                  ) : poi?.p != null ? (
                    <>
                      <span className={clsx(poi.ci && poi.ci[0] > 0.5 ? 'text-good' : poi.ci && poi.ci[1] < 0.5 ? 'text-crit' : 'text-ink')}>{fmt.num(poi.p, 2)}</span>
                      {ci(poi.ci, 2)}
                    </>
                  ) : (
                    '—'
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </Table>
      <p className="mt-2 text-xs text-ink-3">
        P(improvement) is P(X &gt; Y) + ½·P(X = Y) over every pair of policies (the Mann–Whitney statistic); its interval resamples the training runs of both groups. It
        is green when its whole interval is above 0.5 and red when it is below; otherwise the data cannot tell the groups apart. An interval containing 0.5 does not
        establish that the groups are equally good.
        {few && ' With fewer than 5 policies per group, intervals are wide: that is the honest result.'}
      </p>
      {names.some((n) => {
        const p = stats.probability_of_improvement[n]
        return n !== stats.reference && p?.p != null && (p.p === 0 || p.p === 1)
      }) && (
        <p className="mt-2 text-xs text-warn">
          A value of 0.00 [0.00, 0.00] (or 1.00 [1.00, 1.00]) means complete separation in this sample: every policy of one group scored below every policy of the other.
          The empirical bootstrap can then only resample that ordering, so the interval collapses. With so few training runs it is not evidence that a future run has
          literally no chance of doing better.
        </p>
      )}
      <h3 className="mb-2 mt-6 text-[13px] font-medium text-ink">Performance profiles</h3>
      <PerformanceProfiles stats={stats} styles={styles} />
    </Card>
  )
}

function PerformanceProfiles({ stats, styles }: { stats: RobustStats; styles: GroupStyle[] }) {
  const names = Object.keys(stats.groups).filter((n) => stats.groups[n].profile.fraction.length)
  if (!names.length) return null
  const tau = stats.groups[names[0]].profile.tau
  const rows = tau.map((t, i) => {
    const row: Record<string, number | [number, number]> = { tau: t }
    names.forEach((n, k) => {
      const p = stats.groups[n].profile
      row[`f${k}`] = p.fraction[i]
      row[`b${k}`] = [p.lo[i], p.hi[i]]
    })
    return row
  })
  return (
    <figure aria-label="Performance profiles: fraction of evaluation episodes with original return above each threshold">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <Legend items={names.map((n) => ({ label: n, color: styleFor(styles, n).color, dashed: !!styleFor(styles, n).dash }))} />
        <span className="text-[11px] text-ink-3">fraction of episodes with return &gt; τ · band: 95% bootstrap over policies</span>
      </div>
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 6, right: 12, bottom: 16, left: 4 }}>
            <CartesianGrid stroke="#1b2532" vertical={false} />
            <XAxis dataKey="tau" type="number" domain={['dataMin', 'dataMax']} tick={AXIS} stroke="#2d3e52" tickLine={false} label={{ value: 'original return threshold τ', position: 'insideBottom', offset: -10, fill: '#8494a8', fontSize: 11 }} />
            <YAxis domain={[0, 1]} tick={AXIS} stroke="#2d3e52" tickLine={false} width={44} tickFormatter={(v) => fmt.pct(v)} />
            <ReferenceLine x={200} stroke="#5b6f88" strokeDasharray="3 4" />
            <Tooltip
              isAnimationActive={false}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="rounded-md border border-line-strong bg-surface-2/95 px-3 py-2 text-xs shadow-xl">
                    <div className="num mb-1 text-ink-3">τ = {fmt.num(Number(label), 0)}</div>
                    {payload
                      .filter((p) => String(p.dataKey).startsWith('f'))
                      .map((p) => (
                        <div key={String(p.dataKey)} className="num flex justify-between gap-4">
                          <span className="text-ink-2">{p.name}</span>
                          <span className="text-ink">{fmt.pct(Number(p.value))}</span>
                        </div>
                      ))}
                  </div>
                ) : null
              }
            />
            {names.map((n, k) => {
              const st = styleFor(styles, n)
              return <Area key={`b${k}`} dataKey={`b${k}`} stroke="none" fill={st.color} fillOpacity={0.12} isAnimationActive={false} legendType="none" />
            })}
            {names.map((n, k) => {
              const st = styleFor(styles, n)
              return <Line key={`f${k}`} dataKey={`f${k}`} name={n} stroke={st.color} strokeDasharray={st.dash} strokeWidth={st.dqn ? 1.25 : 2} dot={false} isAnimationActive={false} />
            })}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

export function RobustnessCard({ table, experimentId }: { table: RobustnessTable; experimentId?: string }) {
  const conds = Object.keys(table.conditions)
  return (
    <Card title="Robustness: physics never seen in training" eyebrow="frozen checkpoints · same episode seeds · original reward">
      {table.rows.length === 0 ? (
        <div className="text-[13px] text-ink-2">
          <p>No robustness evaluations for these runs yet. They fly each run&apos;s frozen checkpoint under wind, turbulence and heavier gravity, on the first 50 final-test seeds:</p>
          <pre className="mt-2 overflow-x-auto rounded-md border border-line bg-bg p-3 font-mono text-xs text-ink">
            python -m lunarlab robustness {experimentId ? `--experiment-id ${experimentId}` : '--run-ids <id1,id2,...>'} --parallel 4
          </pre>
        </div>
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <th>Group</th>
                {conds.map((c) => (
                  <th key={c} className="text-right" title={table.conditions[c]}>
                    {c === 'calm' ? 'calm' : c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r) => (
                <tr key={r.reward_name}>
                  <td>
                    <span className="inline-flex items-center gap-1.5">
                      <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[r.reward_preset] }} />
                      {r.reward_name}
                    </span>
                  </td>
                  {conds.map((c) => {
                    const v = r.conditions[c]
                    return (
                      <td key={c} className="num text-right align-top">
                        {v ? (
                          <>
                            <div className={clsx(v.mean_original_return >= 200 ? 'text-good' : v.mean_original_return < 0 ? 'text-crit' : 'text-ink')}>{fmt.num(v.mean_original_return, 0)}</div>
                            <div className="text-[11px] text-ink-3">
                              pad {fmt.pct(v.pad_landing_rate)} · n={v.n_seeds}
                            </div>
                          </>
                        ) : (
                          <span className="text-ink-3">—</span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </Table>
          <ul className="mt-3 grid grid-cols-1 gap-x-6 gap-y-0.5 text-xs text-ink-3 md:grid-cols-2">
            {conds.map((c) => (
              <li key={c}>
                <span className="font-mono text-ink-2">{c}</span>: {table.conditions[c]}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-ink-3">Each cell: mean over training seeds of each policy&apos;s mean original return (n = policies). {table.note}</p>
        </>
      )}
    </Card>
  )
}

export interface PhysicsComparison {
  name: string
  algo: string
  reward_preset: Preset
  fixed_group: string
  randomized_group: string
  randomized_physics: string
  n_fixed: number
  n_randomized: number
  conditions: {
    condition: string
    fixed: { mean_original_return: number; pad_landing_rate: number; n_seeds: number } | null
    randomized: { mean_original_return: number; pad_landing_rate: number; n_seeds: number } | null
    difference: number | null
    ci?: CI
  }[]
}

function Cell({ v }: { v: { mean_original_return: number; pad_landing_rate: number; n_seeds: number } | null }) {
  if (!v) return <span className="text-ink-3">—</span>
  return (
    <>
      <div className="num text-ink">{fmt.num(v.mean_original_return, 0)}</div>
      <div className="text-[11px] text-ink-3">
        pad {fmt.pct(v.pad_landing_rate)} · n={v.n_seeds}
      </div>
    </>
  )
}

export function PhysicsComparisonCard({ rows, conditions }: { rows: PhysicsComparison[]; conditions: Record<string, string> }) {
  if (!rows.length) return null
  return (
    <Card title="Training physics: fixed vs randomized" eyebrow="same rewards and seeds · evaluated on calm and windy physics">
      <p className="mb-4 max-w-[110ch] text-[13px] text-ink-2">
        Runs trained with randomized wind, turbulence and gravity next to runs trained on default physics. Both are selected on calm validation episodes and then fly the same
        evaluation episodes: the calm final test and the robustness conditions. Differences are between means over policies, with 95% bootstrap intervals that resample each
        side’s policies; a difference is coloured only when its interval excludes zero. With few policies per side, read them with the per-seed dots of the robustness card.
      </p>
      <div className="space-y-6">
        {rows.map((r) => (
          <div key={r.name}>
            <h3 className="mb-1 flex flex-wrap items-center gap-2 text-[13px] font-medium text-ink">
              <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[r.reward_preset] }} />
              {r.name}
            </h3>
            <p className="mb-2 text-xs text-ink-3">
              Randomized side: {r.randomized_physics.replace(/^randomized:\s*/, '')} · {r.n_fixed} fixed and {r.n_randomized} randomized policies evaluated
            </p>
            <Table>
              <thead>
                <tr>
                  <th>Evaluation condition</th>
                  <th className="text-right">Fixed-physics training</th>
                  <th className="text-right">Randomized training</th>
                  <th className="text-right">Difference (randomized − fixed)</th>
                </tr>
              </thead>
              <tbody>
                {r.conditions.map((c) => (
                  <tr key={c.condition} className="align-top">
                    <td title={conditions[c.condition]}>
                      <span className="font-mono text-xs">{c.condition}</span>
                      <div className="text-[11px] text-ink-3">{conditions[c.condition]}</div>
                    </td>
                    <td className="text-right">
                      <Cell v={c.fixed} />
                    </td>
                    <td className="text-right">
                      <Cell v={c.randomized} />
                    </td>
                    <td className={clsx('num text-right', c.difference == null ? 'text-ink-3' : !c.ci ? 'text-ink' : c.ci[0] > 0 ? 'text-good' : c.ci[1] < 0 ? 'text-crit' : 'text-ink')}>
                      {c.difference == null ? '—' : fmt.signed(c.difference, 0)}
                      {c.ci && (
                        <div className="text-[11px] text-ink-3">
                          [{fmt.signed(c.ci[0], 0)}, {fmt.signed(c.ci[1], 0)}]
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-ink-3">Missing cells: that side has no evaluation for the condition yet (run the final test and `python -m lunarlab robustness`).</p>
    </Card>
  )
}

interface Effect {
  difference: number | null
  ci: CI
  p_improvement: number | null
  p_improvement_ci: CI
}

interface AblationCellData {
  algo: string
  gamma: number
  group: string
  reference: boolean
  n_seeds: number
  scores: number[]
  mean: number | null
  mean_ci: CI
  iqm: number | null
  pad_landing_rate: number | null
}

export interface GammaAblation {
  reward_name: string
  reward_preset: Preset
  physics_label: string
  cells: AblationCellData[]
  gamma_effects: (Effect & { algo: string; gamma: number; vs_gamma: number })[]
  algorithm_effects: (Effect & { gamma: number })[]
  reference_setups: (Effect & { ppo_gamma: number; dqn_gamma: number }) | null
  caveats: string[]
}

function AblationCell({ c }: { c: AblationCellData }) {
  return (
    <>
      <div className="num text-ink">
        {fmt.num(c.mean, 0)}
        {c.mean_ci && (
          <span className="text-ink-3">
            {' '}
            [{fmt.num(c.mean_ci[0], 0)}, {fmt.num(c.mean_ci[1], 0)}]
          </span>
        )}
      </div>
      <div className="text-[11px] text-ink-3">
        {c.n_seeds} seed{c.n_seeds === 1 ? '' : 's'} · pad {fmt.pct(c.pad_landing_rate)}
        {c.reference && ' · reference γ'}
      </div>
    </>
  )
}

/** Coloured only when the interval excludes zero; the sign alone is not evidence. */
function effectTone(e: Effect): string {
  if (!e.ci) return 'text-ink'
  return e.ci[0] > 0 ? 'text-good' : e.ci[1] < 0 ? 'text-crit' : 'text-ink'
}

function EffectRow({ label, note, e }: { label: string; note: string; e: Effect }) {
  return (
    <tr className="align-top">
      <td>
        {label}
        <div className="text-[11px] text-ink-3">{note}</div>
      </td>
      <td className={clsx('num text-right', effectTone(e))}>{fmt.signed(e.difference, 0)}</td>
      <td className="num text-right text-ink-2">{e.ci ? `[${fmt.signed(e.ci[0], 0)}, ${fmt.signed(e.ci[1], 0)}]` : '—'}</td>
      <td className="num text-right text-ink-2">
        {fmt.num(e.p_improvement, 2)}
        {e.p_improvement_ci && (
          <span className="text-ink-3">
            {' '}
            [{fmt.num(e.p_improvement_ci[0], 2)}, {fmt.num(e.p_improvement_ci[1], 2)}]
          </span>
        )}
      </td>
    </tr>
  )
}

export function GammaAblationCard({ blocks }: { blocks: GammaAblation[] }) {
  if (!blocks.length) return null
  return (
    <Card title="Discount factor: controlled ablation" eyebrow="algorithm × discount factor · same rewards, budget, seeds and evaluation">
      <p className="mb-4 max-w-[110ch] text-[13px] text-ink-2">
        PPO’s reference discount factor is 0.999 and DQN’s is 0.99, so PPO against DQN at their reference settings changes two things at once. Here the discount factor is varied on its
        own: its effect within each algorithm, and PPO against DQN at the same γ. Cells are means over training seeds of each policy’s mean original return on the final test, with 95%
        bootstrap intervals over seeds; differences resample each cell’s seeds. A difference is coloured only when its interval excludes zero.
      </p>
      <div className="space-y-6">
        {blocks.map((b) => {
          const algos = [...new Set(b.cells.map((c) => c.algo))]
          const gammas = [...new Set(b.cells.map((c) => c.gamma))].toSorted((x, y) => x - y)
          return (
            <div key={`${b.reward_name}|${b.physics_label}`}>
              <h3 className="mb-1 flex flex-wrap items-center gap-2 text-[13px] font-medium text-ink">
                <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[b.reward_preset] }} />
                {b.reward_name}
              </h3>
              <p className="mb-2 text-xs text-ink-3">Training physics: {b.physics_label}</p>
              <Table>
                <thead>
                  <tr>
                    <th>Algorithm</th>
                    {gammas.map((g) => (
                      <th key={g} className="text-right">
                        <span className="normal-case">γ</span> = {g}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {algos.map((a) => (
                    <tr key={a} className="align-top">
                      <td className="font-mono text-xs uppercase">{a}</td>
                      {gammas.map((g) => {
                        const c = b.cells.find((x) => x.algo === a && x.gamma === g)
                        return <td key={g} className="text-right">{c ? <AblationCell c={c} /> : <span className="text-ink-3">not trained</span>}</td>
                      })}
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Table className="mt-3">
                <thead>
                  <tr>
                    <th>Contrast</th>
                    <th className="text-right">Difference</th>
                    <th className="text-right">95% interval</th>
                    <th className="text-right" title="Probability that a policy from the first cell scores higher than one from the second">
                      P(first higher)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {b.gamma_effects.map((e) => (
                    <EffectRow key={`g-${e.algo}-${e.gamma}`} label={`${e.algo.toUpperCase()}: γ ${e.gamma} − γ ${e.vs_gamma}`} note="the discount factor alone" e={e} />
                  ))}
                  {b.algorithm_effects.map((e) => (
                    <EffectRow key={`a-${e.gamma}`} label={`PPO − DQN at γ ${e.gamma}`} note="the algorithm at a matched discount factor" e={e} />
                  ))}
                  {b.reference_setups && (
                    <EffectRow
                      label={`PPO (γ ${b.reference_setups.ppo_gamma}) − DQN (γ ${b.reference_setups.dqn_gamma})`}
                      note="reference settings: algorithm and discount factor both differ"
                      e={b.reference_setups}
                    />
                  )}
                </tbody>
              </Table>
              {b.caveats.length > 0 && (
                <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-warn">
                  {b.caveats.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              )}
            </div>
          )
        })}
      </div>
    </Card>
  )
}
