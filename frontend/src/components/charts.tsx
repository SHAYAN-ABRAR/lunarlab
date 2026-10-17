// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import { type ReactNode, useId } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import { fmt } from '../lib/format'

// Chart chrome: hairline solid grid one shade off the surface, muted mono ticks, 2px lines,
// no animation (respects reduced motion and keeps live charts calm).
const GRID = '#1b2532'
const AXIS = '#2d3e52'
const TICK = { fill: '#8494a8', fontSize: 11, fontFamily: 'IBM Plex Mono, monospace' }

export interface Series {
  key: string
  label: string
  color: string
  dashed?: boolean
}

export function Legend({ items }: { items: { label: string; color: string; dashed?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-2" aria-label="Legend">
      {items.map((i) => (
        <li key={i.label} className="inline-flex items-center gap-1.5">
          <svg width="18" height="8" aria-hidden>
            <line x1="1" y1="4" x2="17" y2="4" stroke={i.color} strokeWidth="2" strokeLinecap="round" strokeDasharray={i.dashed ? '4 3' : undefined} />
          </svg>
          {i.label}
        </li>
      ))}
    </ul>
  )
}

function TooltipCard({ title, rows }: { title: ReactNode; rows: { label: string; color: string; value: string }[] }) {
  return (
    <div className="rounded-md border border-line-strong bg-surface-2/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="num mb-1 text-ink-3">{title}</div>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4">
          <span className="inline-flex items-center gap-1.5 text-ink-2">
            <span className="inline-block size-2 rounded-full" style={{ background: r.color }} />
            {r.label}
          </span>
          <span className="num text-ink">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

type Row = Record<string, number | string | null | undefined>

export function LineChartPanel({
  data,
  x,
  series,
  height = 220,
  xLabel,
  yLabel,
  xFormat = (v: number) => fmt.compact(v),
  yFormat = (v: number) => fmt.num(v, 1),
  refY,
  refX,
  cursorX,
  yDomain,
  ariaLabel,
  showTable = true,
  emptyText = 'No data yet.',
  onPick,
}: {
  data: Row[]
  x: string
  series: Series[]
  height?: number
  xLabel?: string
  yLabel?: string
  xFormat?: (v: number) => string
  yFormat?: (v: number) => string
  refY?: { y: number; label: string }[]
  refX?: { x: number; label: string }[]
  cursorX?: number
  yDomain?: [number | 'auto' | 'dataMin' | 'dataMax', number | 'auto' | 'dataMin' | 'dataMax']
  ariaLabel: string
  showTable?: boolean
  emptyText?: string
  onPick?: (x: number) => void
}) {
  const id = useId()
  if (!data.length) {
    return (
      <div className="flex items-center justify-center rounded-md border border-dashed border-line text-[13px] text-ink-3" style={{ height }}>
        {emptyText}
      </div>
    )
  }
  return (
    <figure aria-labelledby={id} className="min-w-0">
      <figcaption id={id} className="sr-only">
        {ariaLabel}
      </figcaption>
      {series.length > 1 && (
        <div className="mb-2">
          <Legend items={series} />
        </div>
      )}
      <div style={{ height }} className="select-none">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 6, right: 12, bottom: xLabel ? 18 : 4, left: 4 }}
            onClick={(state) => {
              const v = (state as { activeLabel?: number | string } | null)?.activeLabel
              if (onPick && v !== undefined) onPick(Number(v))
            }}
          >
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey={x}
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={TICK}
              tickFormatter={xFormat}
              stroke={AXIS}
              tickLine={false}
              label={xLabel ? { value: xLabel, position: 'insideBottom', offset: -12, fill: '#8494a8', fontSize: 11 } : undefined}
            />
            <YAxis
              tick={TICK}
              tickFormatter={yFormat}
              stroke={AXIS}
              tickLine={false}
              width={52}
              domain={yDomain ?? ['auto', 'auto']}
              label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft', fill: '#8494a8', fontSize: 11, dx: 10, dy: 30 } : undefined}
            />
            <Tooltip
              isAnimationActive={false}
              cursor={{ stroke: '#5b6f88', strokeWidth: 1 }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TooltipCard
                    title={`${xLabel ?? x}: ${xFormat(Number(label))}`}
                    rows={payload.map((p) => {
                      const s = series.find((q) => q.key === p.dataKey)
                      return { label: s?.label ?? String(p.dataKey), color: s?.color ?? '#999', value: p.value === null || p.value === undefined ? '—' : yFormat(Number(p.value)) }
                    })}
                  />
                ) : null
              }
            />
            {refY?.map((r) => (
              <ReferenceLine key={`y${r.y}`} y={r.y} stroke="#5b6f88" strokeDasharray="3 4" label={{ value: r.label, position: 'insideTopRight', fill: '#8494a8', fontSize: 10 }} />
            ))}
            {refX?.map((r) => (
              <ReferenceLine key={`x${r.x}`} x={r.x} stroke="#5b6f88" strokeDasharray="3 4" label={{ value: r.label, position: 'insideTopLeft', fill: '#8494a8', fontSize: 10 }} />
            ))}
            {cursorX !== undefined && <ReferenceLine x={cursorX} stroke="#e7edf4" strokeOpacity={0.55} strokeWidth={1} />}
            {series.map((s) => (
              <Line
                key={s.key}
                type="linear"
                dataKey={s.key}
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray={s.dashed ? '5 4' : undefined}
                dot={false}
                activeDot={{ r: 4, stroke: '#111822', strokeWidth: 2 }}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      {showTable && <DataTable data={data} x={x} series={series} xFormat={xFormat} yFormat={yFormat} />}
    </figure>
  )
}

export function DataTable({ data, x, series, xFormat, yFormat }: { data: Row[]; x: string; series: Series[]; xFormat: (v: number) => string; yFormat: (v: number) => string }) {
  const step = Math.max(1, Math.ceil(data.length / 60))
  const rows = data.filter((_, i) => i % step === 0)
  return (
    <details className="mt-2 text-xs text-ink-3">
      <summary className="cursor-pointer select-none hover:text-ink-2">Table view{step > 1 ? ` (every ${step}th point)` : ''}</summary>
      <div className="mt-2 max-h-56 overflow-auto rounded border border-line">
        <table className="w-full text-left">
          <thead className="sticky top-0 bg-surface-2">
            <tr>
              <th className="px-2 py-1 font-medium">{x}</th>
              {series.map((s) => (
                <th key={s.key} className="px-2 py-1 font-medium">
                  {s.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="num text-ink-2">
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-line/60">
                <td className="px-2 py-0.5">{xFormat(Number(r[x]))}</td>
                {series.map((s) => (
                  <td key={s.key} className="px-2 py-0.5">
                    {r[s.key] === null || r[s.key] === undefined ? '—' : yFormat(Number(r[s.key]))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

/** Small single-series chart for PPO diagnostics (small multiples, one axis each). */
export function Sparkline({ data, x, y, label, color = '#3987e5', format = (v: number) => fmt.num(v, 3) }: { data: Row[]; x: string; y: string; label: string; color?: string; format?: (v: number) => string }) {
  const last = data.toReversed().find((d) => d[y] !== undefined && d[y] !== null)
  return (
    <div className="min-w-0 rounded-md border border-line bg-bg/40 p-3">
      <div className="truncate text-xs text-ink-3" title={label}>{label}</div>
      <div className="num text-[13px] text-ink">{last ? format(Number(last[y])) : '—'}</div>
      <div className="mt-1 h-14">
        {data.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 2, bottom: 0, left: 2 }}>
              <XAxis dataKey={x} type="number" domain={['dataMin', 'dataMax']} hide />
              <YAxis hide domain={['auto', 'auto']} />
              <Tooltip
                isAnimationActive={false}
                cursor={{ stroke: '#5b6f88' }}
                content={({ active, payload, label: lx }) =>
                  active && payload?.length ? (
                    <TooltipCard title={`transitions: ${fmt.compact(Number(lx))}`} rows={[{ label, color, value: format(Number(payload[0].value)) }]} />
                  ) : null
                }
              />
              <Line type="linear" dataKey={y} stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center text-xs text-ink-3">needs ≥ 2 updates</div>
        )}
      </div>
    </div>
  )
}

export interface StackPart {
  key: string
  label: string
  color: string
}

/** Horizontal 100%-stacked bars (e.g. outcome rates per run), with 2px surface gaps. */
export function StackedBars({ rows, parts, ariaLabel, valueFormat = (v: number) => fmt.pct(v) }: { rows: ({ name: string } & Record<string, number | string>)[]; parts: StackPart[]; ariaLabel: string; valueFormat?: (v: number) => string }) {
  if (!rows.length) return <div className="py-6 text-center text-[13px] text-ink-3">No evaluations to show.</div>
  return (
    <figure aria-label={ariaLabel}>
      <div className="mb-2">
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
          {parts.map((p) => (
            <li key={p.key} className="inline-flex items-center gap-1.5">
              <span className="inline-block size-2.5 rounded-sm" style={{ background: p.color }} />
              {p.label}
            </li>
          ))}
        </ul>
      </div>
      <div style={{ height: Math.max(80, rows.length * 34 + 30) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 12, bottom: 0, left: 4 }} barCategoryGap={8}>
            <CartesianGrid stroke={GRID} horizontal={false} />
            <XAxis type="number" domain={[0, 1]} tick={TICK} tickFormatter={(v) => fmt.pct(v)} stroke={AXIS} tickLine={false} />
            <YAxis type="category" dataKey="name" tick={{ ...TICK, fontFamily: 'IBM Plex Sans, sans-serif', fill: '#aab6c4' }} width={170} stroke={AXIS} tickLine={false} />
            <Tooltip
              isAnimationActive={false}
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <TooltipCard title={label} rows={parts.map((p) => ({ label: p.label, color: p.color, value: valueFormat(Number(payload[0].payload[p.key] ?? 0)) }))} />
                ) : null
              }
            />
            {parts.map((p) => (
              <Bar key={p.key} dataKey={p.key} stackId="s" fill={p.color} stroke="#111822" strokeWidth={2} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

/** One marker per training seed per group: variability across independently trained policies.
 *  Each group has its own colour AND marker shape (secondary encoding). */
export function SeedDotPlot({ groups, ariaLabel, refY = 200 }: { groups: { name: string; color: string; shape?: 'circle' | 'square' | 'triangle' | 'diamond' | 'cross'; points: { seed: number; value: number; runId: string }[] }[]; ariaLabel: string; refY?: number }) {
  const any = groups.some((g) => g.points.length)
  if (!any) return <div className="py-6 text-center text-[13px] text-ink-3">No evaluated seeds yet.</div>
  return (
    <figure aria-label={ariaLabel} style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            type="number"
            dataKey="gx"
            domain={[-0.5, groups.length - 0.5]}
            ticks={groups.map((_, i) => i)}
            tickFormatter={(i) => groups[i]?.name ?? ''}
            tick={{ ...TICK, fontFamily: 'IBM Plex Sans, sans-serif', fill: '#aab6c4' }}
            stroke={AXIS}
            tickLine={false}
          />
          <YAxis type="number" dataKey="value" tick={TICK} stroke={AXIS} tickLine={false} width={52} domain={['auto', 'auto']} tickFormatter={(v) => fmt.num(v, 0)} />
          <ZAxis range={[130, 130]} />
          <ReferenceLine y={refY} stroke="#5b6f88" strokeDasharray="3 4" label={{ value: `${refY}`, position: 'insideTopRight', fill: '#8494a8', fontSize: 10 }} />
          <Tooltip
            isAnimationActive={false}
            cursor={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as { group: string; seed: number; value: number; color: string }
              return <TooltipCard title={p.group} rows={[{ label: `seed ${p.seed}`, color: p.color, value: fmt.num(p.value, 1) }]} />
            }}
          />
          {groups.map((g, gi) => (
            <Scatter
              key={g.name}
              name={g.name}
              data={g.points.map((p) => ({ gx: gi, value: p.value, seed: p.seed, group: g.name, color: g.color }))}
              fill={g.color}
              stroke="#111822"
              strokeWidth={2}
              shape={g.shape ?? 'circle'}
              isAnimationActive={false}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </figure>
  )
}
