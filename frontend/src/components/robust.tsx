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
        P(improvement) is green when its whole interval is above 0.5 and red when it is below; otherwise the data cannot tell the groups apart.
        {few && ' With fewer than 5 policies per group, intervals are wide: that is the honest result.'}
      </p>
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
