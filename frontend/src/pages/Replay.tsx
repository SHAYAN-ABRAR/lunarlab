import clsx from 'clsx'
import { ArrowLeftRight, ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import { Suspense, lazy, memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Legend } from '../components/charts'
import { DemoButton } from '../components/Launch'
import { Badge, Card, EmptyState, ErrorBanner, KV, Notice, OutcomeBadge, PageHeader, PolicyBadge, Segmented, Spinner } from '../components/ui'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import { SERIES, TERM_COLOR, TERM_LABEL } from '../lib/reward'
import type { RecordingMeta, Telemetry, TelemetryRow } from '../lib/types'

// The 3-D view pulls in three.js, so it loads only when used.
const Scene3D = lazy(() => import('../components/Scene3D'))
type View = '3d' | 'footage'

const ACTIONS = [
  { key: 'noop', short: 'NOOP', label: 'Do nothing' },
  { key: 'left', short: 'LEFT', label: 'Fire left orientation engine' },
  { key: 'main', short: 'MAIN', label: 'Fire main engine' },
  { key: 'right', short: 'RIGHT', label: 'Fire right orientation engine' },
]
const SPEEDS = ['0.25', '0.5', '1', '2', '4'] as const
const BUILTIN_LABEL: Record<string, string> = {
  distance: 'Distance to pad (Δ)',
  speed: 'Speed (Δ)',
  tilt: 'Tilt (Δ)',
  leg_contact: 'Leg contact (Δ)',
  main_engine: 'Main engine fuel',
  side_engine: 'Side engine fuel',
  terminal: 'Terminal (replaces step reward)',
  residual: 'Rounding residual',
}

// --------------------------------------------------------------------------- //
// Frame surface: MP4 (native playback, frame derived from currentTime) or JPEG frames
// --------------------------------------------------------------------------- //

interface SurfaceProps {
  t: Telemetry
  frame: number
  playing: boolean
  speed: number
  onFrame: (f: number) => void
  onEnded: () => void
  label: string
}

function FrameSurface({ t, frame, playing, speed, onFrame, onEnded, label }: SurfaceProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const reported = useRef(0)
  const last = t.n_frames - 1
  const isMp4 = t.video.format === 'mp4-h264'

  // MP4: play natively and report the displayed frame index.
  useEffect(() => {
    const v = videoRef.current
    if (!isMp4 || !v) return
    v.playbackRate = speed
    if (!playing) {
      v.pause()
      return
    }
    let stop = false
    let handle = 0
    const report = () => {
      if (stop) return
      const f = Math.min(last, Math.floor(v.currentTime * t.fps + 1e-3))
      if (f !== reported.current) {
        reported.current = f
        onFrame(f)
      }
      if (v.ended) {
        onFrame(last)
        onEnded()
        return
      }
      handle = 'requestVideoFrameCallback' in v ? (v as HTMLVideoElement & { requestVideoFrameCallback: (cb: () => void) => number }).requestVideoFrameCallback(report) : requestAnimationFrame(report)
    }
    if (v.currentTime >= (last + 0.5) / t.fps) v.currentTime = 0
    v.play().then(report).catch(() => onEnded())
    return () => {
      stop = true
      if ('cancelVideoFrameCallback' in v) (v as HTMLVideoElement & { cancelVideoFrameCallback: (h: number) => void }).cancelVideoFrameCallback(handle)
      else cancelAnimationFrame(handle)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, speed, isMp4, t.recording_id])

  // MP4: external seeks (slider, keys, chart clicks) move the video to the middle of the frame.
  useEffect(() => {
    const v = videoRef.current
    if (!isMp4 || !v) return
    if (frame !== reported.current) {
      reported.current = frame
      v.currentTime = Math.min((frame + 0.5) / t.fps, v.duration || Infinity)
    }
  }, [frame, isMp4, t.fps])

  // JPEG frames: a timer advances the index.
  useEffect(() => {
    if (isMp4 || !playing) return
    const id = window.setInterval(() => {
      reported.current += 1
      if (reported.current >= last) {
        onFrame(last)
        onEnded()
        window.clearInterval(id)
      } else onFrame(reported.current)
    }, 1000 / (t.fps * speed))
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, speed, isMp4, last, t.fps])

  return (
    <div className="relative overflow-hidden rounded-lg border border-line bg-black" style={{ aspectRatio: '3 / 2' }}>
      {isMp4 ? (
        <video
          ref={videoRef}
          src={`/api/recordings/${t.recording_id}/video`}
          muted
          playsInline
          preload="auto"
          aria-label={label}
          className="h-full w-full object-contain"
          onLoadedMetadata={(e) => {
            ;(e.target as HTMLVideoElement).currentTime = (frame + 0.5) / t.fps
          }}
        />
      ) : (
        <img src={`/api/recordings/${t.recording_id}/frames/${frame}`} alt={label} className="h-full w-full object-contain" />
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Telemetry charts with an overlay cursor (no chart re-render per frame)
// --------------------------------------------------------------------------- //

const PLOT_LEFT = 56
const PLOT_RIGHT = 12

const TelemetryChart = memo(function TelemetryChart({
  data,
  series,
  title,
  yFormat = (v: number) => fmt.num(v, 2),
  refY,
  onSeek,
  height = 140,
}: {
  data: Record<string, number | null>[]
  series: { key: string; label: string; color: string; dashed?: boolean }[]
  title: string
  yFormat?: (v: number) => string
  refY?: number
  onSeek: (f: number) => void
  height?: number
}) {
  return (
    <figure className="min-w-0" aria-label={title}>
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <figcaption className="text-xs font-medium text-ink-2">{title}</figcaption>
        {series.length > 1 && <Legend items={series} />}
      </div>
      <div style={{ height }} className="relative cursor-crosshair" data-chart>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 4, right: PLOT_RIGHT, bottom: 0, left: 4 }}
            onClick={(s) => {
              const v = (s as { activeLabel?: number | string } | null)?.activeLabel
              if (v !== undefined) onSeek(Number(v))
            }}
          >
            <CartesianGrid stroke="#1b2532" vertical={false} />
            <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tick={{ fill: '#8494a8', fontSize: 10, fontFamily: 'IBM Plex Mono' }} stroke="#2d3e52" tickLine={false} height={18} />
            <YAxis tick={{ fill: '#8494a8', fontSize: 10, fontFamily: 'IBM Plex Mono' }} stroke="#2d3e52" tickLine={false} width={52} tickFormatter={yFormat} domain={['auto', 'auto']} />
            {refY !== undefined && <ReferenceLine y={refY} stroke="#5b6f88" strokeDasharray="3 4" />}
            <Tooltip
              isAnimationActive={false}
              cursor={{ stroke: '#5b6f88' }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="rounded-md border border-line-strong bg-surface-2/95 px-2.5 py-1.5 text-[11px] shadow-xl">
                    <div className="num text-ink-3">step {label}</div>
                    {payload.map((p) => (
                      <div key={String(p.dataKey)} className="num flex justify-between gap-3 text-ink">
                        <span className="text-ink-2">{series.find((s) => s.key === p.dataKey)?.label}</span>
                        {p.value === null || p.value === undefined ? '—' : yFormat(Number(p.value))}
                      </div>
                    ))}
                  </div>
                ) : null
              }
            />
            {series.map((s) => (
              <Line key={s.key} dataKey={s.key} type="linear" stroke={s.color} strokeWidth={1.75} strokeDasharray={s.dashed ? '5 4' : undefined} dot={false} isAnimationActive={false} connectNulls={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <div data-cursor className="pointer-events-none absolute top-1 w-px bg-ink/60" style={{ bottom: 18 }} />
      </div>
    </figure>
  )
})

/** Position every chart cursor in a container via CSS only. */
function useChartCursor(containerRef: React.RefObject<HTMLDivElement | null>, frame: number, last: number) {
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const frac = last > 0 ? frame / last : 0
    el.querySelectorAll<HTMLDivElement>('[data-cursor]').forEach((c) => {
      c.style.left = `calc(${PLOT_LEFT}px + (100% - ${PLOT_LEFT + PLOT_RIGHT}px) * ${frac})`
    })
  })
}

// --------------------------------------------------------------------------- //
// Panels
// --------------------------------------------------------------------------- //

function ActionIndicator({ action }: { action: number | null }) {
  return (
    <div>
      <div className="eyebrow mb-1.5">Action applied in this step</div>
      <div className="grid grid-cols-4 gap-1.5" role="list" aria-label="Actions">
        {ACTIONS.map((a, i) => (
          <div
            key={a.key}
            role="listitem"
            aria-current={action === i || undefined}
            title={a.label}
            className={clsx('rounded-md border px-1 py-1.5 text-center font-mono text-[11px] tracking-wide', action === i ? 'border-accent bg-accent/15 text-ink' : 'border-line text-ink-3')}
          >
            {a.short}
          </div>
        ))}
      </div>
      <p className="mt-1 text-[11px] text-ink-3">{action === null ? 'Frame 0 is the reset state: no action yet.' : ACTIONS[action].label}</p>
    </div>
  )
}

function ObsPanel({ row }: { row: TelemetryRow }) {
  const [x, y, vx, vy, ang, w, l, r] = row.obs
  return (
    <div>
      <div className="eyebrow mb-1">Observation (normalized environment units)</div>
      <KV k="x · horizontal position" v={fmt.num(x, 3)} />
      <KV k="y · height above pad" v={fmt.num(y, 3)} />
      <KV k="vx · horizontal velocity" v={fmt.num(vx, 3)} />
      <KV k="vy · vertical velocity" v={fmt.num(vy, 3)} />
      <KV k="angle" v={`${fmt.num(ang, 3)} rad · ${fmt.deg(ang)}`} />
      <KV k="angular velocity (0.4·ω)" v={fmt.num(w, 3)} />
      <div className="mt-2 flex items-center gap-4 text-[12px]">
        {[
          ['Left leg', l],
          ['Right leg', r],
        ].map(([name, v]) => (
          <span key={String(name)} className="inline-flex items-center gap-1.5 text-ink-2">
            <span className={clsx('inline-block size-2.5 rounded-full border', Number(v) > 0.5 ? 'border-good bg-good' : 'border-line-strong bg-transparent')} aria-hidden />
            {name}: {Number(v) > 0.5 ? 'contact' : 'airborne'}
          </span>
        ))}
      </div>
      <p className="mt-1 text-[11px] text-ink-3">Contact flags can read 0 while a resting leg slides across terrain-segment joints (an environment quirk; see Learn).</p>
    </div>
  )
}

function RewardPanel({ row, termKeys }: { row: TelemetryRow; termKeys: string[] }) {
  return (
    <div>
      <div className="eyebrow mb-1">Reward in this step</div>
      <KV k="Original reward" v={fmt.signed(row.original_reward, 3)} />
      {row.builtin && (
        <div className="my-1 rounded-md border border-line bg-bg/50 px-2.5 py-1">
          {Object.entries(row.builtin)
            .filter(([k, v]) => k === 'terminal' ? v !== 0 : k !== 'residual' || Math.abs(v) > 1e-4)
            .map(([k, v]) => (
              <div key={k} className="num flex justify-between gap-3 py-0.5 text-[11.5px]">
                <span className="text-ink-3">{BUILTIN_LABEL[k] ?? k}</span>
                <span className="text-ink-2">{fmt.signed(v, 3)}</span>
              </div>
            ))}
        </div>
      )}
      {termKeys.map((k) => (
        <KV key={k} k={`+ ${TERM_LABEL[k] ?? k}`} v={fmt.signed(row.terms[k] ?? 0, 3)} />
      ))}
      {termKeys.length > 0 && <KV k="= Training reward" v={fmt.signed(row.training_reward, 3)} />}
      <div className="mt-2 grid grid-cols-2 gap-3">
        <div>
          <div className="text-[11px] text-ink-3">Cumulative original</div>
          <div className="num text-[15px] text-ink">{fmt.num(row.cum_original, 2)}</div>
        </div>
        {termKeys.length > 0 && (
          <div>
            <div className="text-[11px] text-ink-3">Cumulative training</div>
            <div className="num text-[15px] text-ink">{fmt.num(row.cum_training, 2)}</div>
          </div>
        )}
      </div>
    </div>
  )
}

function OutcomeCard({ t }: { t: Telemetry }) {
  const e = t.episode
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <PolicyBadge kind={t.policy.kind} />
        <OutcomeBadge outcome={e.env_outcome} pad={e.pad_landing} />
        <Badge tone="neutral">
          seed {t.episode_seed} · {t.seed_split === 'other' ? 'not in a protocol split' : `${t.seed_split} seed`}
        </Badge>
      </div>
      <p className="text-xs text-ink-2">{t.policy.label}</p>
      <div>
        <KV k="Original return" v={fmt.num(e.original_return, 2)} />
        {t.reward_config && t.reward_config.preset !== 'baseline' && <KV k="Training return (rescored)" v={fmt.num(e.training_return, 2)} />}
        <KV k="Steps" v={`${e.length} (${fmt.num(e.length / t.fps, 2)} s sim)`} />
        <KV k="Terminated / truncated" v={`${e.terminated} / ${e.truncated}`} />
        <KV k="Body contact" v={String(e.body_contact)} />
        <KV k="Legs between flags" v={String(e.legs_within_pad)} />
        <KV k="Hover fraction · longest streak" v={`${fmt.pct(e.hover_fraction, 1)} · ${e.longest_hover_streak}`} />
        <KV k="Actions (noop/left/main/right)" v={`${e.actions.noop}/${e.actions.left}/${e.actions.main}/${e.actions.right}`} />
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------------- //

function usePlayback(n: number) {
  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>('1')
  const last = Math.max(0, n - 1)
  const seek = useCallback((f: number) => setFrame(Math.max(0, Math.min(last, Math.round(f)))), [last])
  return { frame, setFrame, seek, playing, setPlaying, speed, setSpeed, last }
}

function Controls({ pb }: { pb: ReturnType<typeof usePlayback> }) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-1">
        <button type="button" aria-label="First frame" className="rounded p-1.5 text-ink-2 hover:bg-surface-3" onClick={() => pb.seek(0)}><ChevronFirst className="size-4" /></button>
        <button type="button" aria-label="Previous frame" className="rounded p-1.5 text-ink-2 hover:bg-surface-3" onClick={() => { pb.setPlaying(false); pb.seek(pb.frame - 1) }}><ChevronLeft className="size-4" /></button>
        <button type="button" aria-label={pb.playing ? 'Pause' : 'Play'} className="rounded-md bg-accent p-2 text-accent-ink hover:bg-accent-strong" onClick={() => { if (!pb.playing && pb.frame >= pb.last) pb.seek(0); pb.setPlaying(!pb.playing) }}>
          {pb.playing ? <Pause className="size-4" /> : <Play className="size-4" />}
        </button>
        <button type="button" aria-label="Next frame" className="rounded p-1.5 text-ink-2 hover:bg-surface-3" onClick={() => { pb.setPlaying(false); pb.seek(pb.frame + 1) }}><ChevronRight className="size-4" /></button>
        <button type="button" aria-label="Last frame" className="rounded p-1.5 text-ink-2 hover:bg-surface-3" onClick={() => pb.seek(pb.last)}><ChevronLast className="size-4" /></button>
      </div>
      <input
        type="range"
        aria-label="Timeline (frame)"
        min={0}
        max={pb.last}
        value={pb.frame}
        onChange={(e) => pb.seek(Number(e.target.value))}
        className="h-1.5 min-w-[160px] flex-1 cursor-pointer accent-[#3cc8d4]"
      />
      <span className="num w-[150px] text-right text-xs text-ink-2">
        frame {pb.frame} / {pb.last}
      </span>
      <Segmented label="Playback speed" value={pb.speed} onChange={pb.setSpeed} options={SPEEDS.map((s) => ({ value: s, label: `${s}×` }))} />
    </div>
  )
}

function RecordingList({ items, current }: { items: RecordingMeta[]; current?: string }) {
  const [kind, setKind] = useState<'all' | 'random' | 'heuristic' | 'ppo'>('all')
  const shown = items.filter((r) => kind === 'all' || r.policy.kind === kind)
  return (
    <div className="space-y-3">
      <Segmented label="Filter recordings" value={kind} onChange={setKind} options={[{ value: 'all', label: 'All' }, { value: 'random', label: 'Random' }, { value: 'heuristic', label: 'Heuristic' }, { value: 'ppo', label: 'PPO' }]} />
      <ul className="max-h-[70vh] space-y-1 overflow-auto pr-1">
        {shown.map((r) => (
          <li key={r.recording_id}>
            <Link to={`/replay/${r.recording_id}`} aria-current={r.recording_id === current ? 'page' : undefined} className={clsx('block rounded-md border px-3 py-2', r.recording_id === current ? 'border-accent/50 bg-accent/[0.06]' : 'border-transparent hover:border-line hover:bg-surface')}>
              <div className="flex items-center justify-between gap-2">
                <PolicyBadge kind={r.policy.kind} />
                <span className="num text-xs text-ink-2">{fmt.num(r.original_return, 1)}</span>
              </div>
              <div className="mt-1 truncate text-[12.5px] text-ink">{r.policy.kind === 'ppo' ? `${r.source.reward_name ?? ''} · s${r.source.training_seed ?? ''}` : r.policy.kind === 'random' ? 'Random policy' : 'Heuristic controller'}</div>
              <div className="mt-0.5 flex items-center justify-between gap-2 text-[11px] text-ink-3">
                <span>seed {r.episode_seed} · {r.length} steps</span>
                <span>{r.pad_landing ? 'pad landing' : r.env_outcome.replaceAll('_', ' ')}</span>
              </div>
            </Link>
          </li>
        ))}
        {!shown.length && <li className="px-2 py-4 text-xs text-ink-3">No recordings of this kind.</li>}
      </ul>
    </div>
  )
}

function chartData(t: Telemetry) {
  const termKeys = Object.keys(t.rows[t.rows.length - 1]?.terms ?? {})
  return {
    termKeys,
    rows: t.rows.map((r, i) => {
      const last = i === t.rows.length - 1 && r.terminated
      const d: Record<string, number | null> = {
        t: r.t,
        y: r.obs[1],
        vx: r.obs[2],
        vy: r.obs[3],
        angle: (r.obs[4] * 180) / Math.PI,
        w: r.obs[5],
        cum_original: r.cum_original,
        cum_training: r.cum_training,
        step_original: i === 0 || last ? null : r.original_reward,
      }
      termKeys.forEach((k) => (d[`term_${k}`] = i === 0 ? null : r.terms[k] ?? 0))
      return d
    }),
  }
}

export default function Replay() {
  const { recordingId } = useParams()
  const navigate = useNavigate()
  const list = useApi<RecordingMeta[]>('/api/recordings', 10000)
  const items = useMemo(() => list.data ?? [], [list.data])
  useEffect(() => {
    if (!recordingId && items.length) navigate(`/replay/${items[0].recording_id}`, { replace: true })
  }, [recordingId, items, navigate])

  const telemetry = useApi<Telemetry>(recordingId ? `/api/recordings/${recordingId}` : null)
  const [view, setViewState] = useState<View>(() => {
    try {
      return localStorage.getItem('lunarlab.replayView') === 'footage' ? 'footage' : '3d'
    } catch {
      return '3d'
    }
  })
  const setView = (v: View) => {
    setViewState(v)
    try {
      localStorage.setItem('lunarlab.replayView', v)
    } catch {
      /* storage unavailable */
    }
  }
  const [compareId, setCompareId] = useState<string>('')
  const other = useApi<Telemetry>(compareId ? `/api/recordings/${compareId}` : null)
  useEffect(() => setCompareId(''), [recordingId])

  const t = telemetry.data
  const n = Math.max(t?.n_frames ?? 1, other.data?.n_frames ?? 1)
  const pb = usePlayback(n)
  useEffect(() => {
    pb.setFrame(0)
    pb.setPlaying(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordingId, compareId])

  const chartsRef = useRef<HTMLDivElement>(null)
  useChartCursor(chartsRef, Math.min(pb.frame, (t?.n_frames ?? 1) - 1), (t?.n_frames ?? 1) - 1)
  const cd = useMemo(() => (t ? chartData(t) : null), [t])

  // Keyboard: Space play/pause, ←/→ step (Shift = 10), Home/End.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName
      if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(tag) && e.key !== ' ') return
      if (['INPUT', 'SELECT', 'TEXTAREA'].includes(tag)) return
      if (e.key === ' ') {
        e.preventDefault()
        pb.setPlaying((p) => !p)
      } else if (e.key === 'ArrowRight') {
        pb.setPlaying(false)
        pb.seek(pb.frame + (e.shiftKey ? 10 : 1))
      } else if (e.key === 'ArrowLeft') {
        pb.setPlaying(false)
        pb.seek(pb.frame - (e.shiftKey ? 10 : 1))
      } else if (e.key === 'Home') pb.seek(0)
      else if (e.key === 'End') pb.seek(pb.last)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pb])

  const sameSeed = items.filter((r) => t && r.episode_seed === t.episode_seed && r.recording_id !== t.recording_id)

  if (list.error && !list.data) return <ErrorBanner error={list.error.message} onRetry={list.reload} />
  if (list.data && !items.length)
    return (
      <>
        <PageHeader title="Flight Replay" subtitle="Real simulator footage with synchronized telemetry." />
        <EmptyState title="No flights recorded yet" action={<><DemoButton policy="random" label="Watch Random Agent" /><DemoButton policy="heuristic" label="Record heuristic controller" variant="secondary" /></>}>
          Recordings are real Gymnasium episodes rendered frame by frame. Start with a random agent; trained policies can be recorded from their run page.
        </EmptyState>
      </>
    )

  // In side-by-side mode the longer flight drives the shared timeline.
  const otherIsMaster = !!(compareId && other.data && t && other.data.n_frames > t.n_frames)
  const row = t ? t.rows[Math.min(pb.frame, t.rows.length - 1)] : null
  const orow = other.data ? other.data.rows[Math.min(pb.frame, other.data.rows.length - 1)] : null

  return (
    <>
      <PageHeader
        title="Flight Replay"
        subtitle="Actual Gymnasium frames and the actions the policy really chose. Frame k shows the state after k steps; frame 0 is the reset state."
        actions={
          <>
            <DemoButton policy="random" label="Record random flight" variant="secondary" />
            <DemoButton policy="heuristic" label="Record heuristic flight" variant="secondary" />
          </>
        }
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[260px_minmax(0,1fr)]">
        <aside aria-label="Recordings">
          {list.data ? <RecordingList items={items} current={recordingId} /> : <Spinner />}
        </aside>
        <div className="min-w-0 space-y-6">
          <ErrorBanner error={telemetry.error?.message} onRetry={telemetry.reload} />
          {!t || !row || !cd ? (
            <Spinner label="Loading flight" />
          ) : (
            <>
              <div className={clsx('grid gap-6', compareId ? '2xl:grid-cols-2' : '2xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,1fr)]')}>
                <div className="min-w-0 space-y-3">
                  {!compareId && (
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Segmented
                        label="Replay view"
                        value={view}
                        onChange={setView}
                        options={[
                          { value: '3d', label: '3D view' },
                          { value: 'footage', label: 'Simulator footage' },
                        ]}
                      />
                      <span className="text-[11px] text-ink-3">
                        {view === '3d' ? 'Reconstructed from recorded telemetry and the episode’s real terrain' : 'Actual Gymnasium frames'}
                      </span>
                    </div>
                  )}
                  {view === '3d' && !compareId ? (
                    <Suspense fallback={<div className="flex items-center justify-center rounded-lg border border-line bg-black text-[13px] text-ink-3" style={{ aspectRatio: '3 / 2' }}>Loading 3-D view…</div>}>
                      <Scene3D t={t} frame={Math.min(pb.frame, t.n_frames - 1)} playing={pb.playing} speed={Number(pb.speed)} onFrame={pb.setFrame} onEnded={() => pb.setPlaying(false)} onUnavailable={() => setView('footage')} label={`Flight of ${t.policy.label}, episode seed ${t.episode_seed}`} />
                    </Suspense>
                  ) : (
                    <FrameSurface t={t} frame={Math.min(pb.frame, t.n_frames - 1)} playing={pb.playing} speed={Number(pb.speed)} onFrame={otherIsMaster ? () => undefined : pb.setFrame} onEnded={() => !otherIsMaster && pb.setPlaying(false)} label={`Flight of ${t.policy.label}, episode seed ${t.episode_seed}`} />
                  )}
                  {!compareId && <Controls pb={pb} />}
                  {view === '3d' && !compareId && (
                    <p className="text-[11px] leading-relaxed text-ink-3">
                      Position, tilt, engine firings, leg contacts, terrain profile, pad flags and outcome are the recorded data. LunarLander is a 2-D simulation: depth, lighting, particles and the lander model are illustrative. The faint cyan line marks the simulation plane.
                    </p>
                  )}
                </div>
                {compareId && other.data ? (
                  <div className="min-w-0 space-y-3">
                    <FrameSurface t={other.data} frame={Math.min(pb.frame, other.data.n_frames - 1)} playing={pb.playing} speed={Number(pb.speed)} onFrame={otherIsMaster ? pb.setFrame : () => undefined} onEnded={() => otherIsMaster && pb.setPlaying(false)} label={`Comparison flight, ${other.data.policy.label}`} />
                  </div>
                ) : (
                  <Card bodyClassName="p-4 space-y-4">
                    <div className="num flex items-baseline justify-between text-xs text-ink-3">
                      <span>step {row.t} of {t.n_frames - 1}</span>
                      <span>t = {fmt.num(row.t / t.fps, 2)} s (sim)</span>
                    </div>
                    <ActionIndicator action={row.action} />
                    {row.hover && <Badge tone="info">hover detector: hovering</Badge>}
                    {(row.terminated || row.truncated) && <Badge tone="warn">{row.terminated ? 'terminated' : 'truncated (time limit)'}</Badge>}
                    <ObsPanel row={row} />
                    <RewardPanel row={row} termKeys={cd.termKeys} />
                  </Card>
                )}
              </div>
              {compareId && <Controls pb={pb} />}

              <Card
                title="Side-by-side"
                eyebrow="same episode seed only"
                actions={
                  <select aria-label="Compare with recording" className="field w-[300px]" value={compareId} onChange={(e) => setCompareId(e.target.value)} disabled={!sameSeed.length}>
                    <option value="">{sameSeed.length ? 'Compare with another flight…' : 'No other flight with this seed'}</option>
                    {sameSeed.map((r) => (
                      <option key={r.recording_id} value={r.recording_id}>
                        {r.policy.kind.toUpperCase()} · {r.policy.kind === 'ppo' ? `${r.source.reward_name} s${r.source.training_seed}` : r.recording_id.slice(0, 15)} · {fmt.num(r.original_return, 0)}
                      </option>
                    ))}
                  </select>
                }
              >
                {compareId && other.data && orow ? (
                  <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    {[{ tt: t, r: row, name: 'Left' }, { tt: other.data, r: orow, name: 'Right' }].map(({ tt, r, name }) => (
                      <div key={name} className="space-y-3">
                        <div className="eyebrow">{name}</div>
                        <OutcomeCard t={tt} />
                        <ActionIndicator action={r.action} />
                        <KV k="Cumulative original return" v={fmt.num(r.cum_original, 2)} />
                        {pb.frame >= tt.n_frames && <p className="text-xs text-ink-3">This flight ended at step {tt.n_frames - 1}; holding its last frame.</p>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[13px] text-ink-3">
                    Matched demonstrations use the same episode seed (identical terrain and initial push), so differences come from the policies. Record other policies on seed {t.episode_seed} to compare.
                  </p>
                )}
              </Card>

              <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,1fr)]">
                <Card title="Telemetry" eyebrow="click a chart to seek" bodyClassName="p-4">
                  <div ref={chartsRef} className="grid grid-cols-1 gap-5 md:grid-cols-2">
                    <TelemetryChart data={cd.rows} title="Height y (0 ≈ legs on pad)" series={[{ key: 'y', label: 'y', color: SERIES.original }]} refY={0} onSeek={pb.seek} />
                    <TelemetryChart data={cd.rows} title="Velocity (scaled units)" series={[{ key: 'vx', label: 'vx', color: '#3987e5' }, { key: 'vy', label: 'vy', color: '#d95926' }]} refY={0} onSeek={pb.seek} />
                    <TelemetryChart data={cd.rows} title="Tilt (degrees)" series={[{ key: 'angle', label: 'angle', color: SERIES.original }]} yFormat={(v) => `${v.toFixed(0)}°`} refY={0} onSeek={pb.seek} />
                    <TelemetryChart data={cd.rows} title="Angular velocity (0.4·ω)" series={[{ key: 'w', label: 'angular velocity', color: SERIES.original }]} refY={0} onSeek={pb.seek} />
                    <TelemetryChart
                      data={cd.rows}
                      title="Cumulative return"
                      series={[{ key: 'cum_original', label: 'original', color: SERIES.original }, ...(cd.termKeys.length ? [{ key: 'cum_training', label: 'training (rescored)', color: SERIES.shaped, dashed: true }] : [])]}
                      yFormat={(v) => v.toFixed(0)}
                      onSeek={pb.seek}
                    />
                    <TelemetryChart
                      data={cd.rows}
                      title="Reward components per step (final step omitted)"
                      series={[{ key: 'step_original', label: 'original', color: SERIES.original }, ...cd.termKeys.map((k) => ({ key: `term_${k}`, label: TERM_LABEL[k] ?? k, color: TERM_COLOR[k] ?? '#8494a8', dashed: true }))]}
                      yFormat={(v) => v.toFixed(1)}
                      refY={0}
                      onSeek={pb.seek}
                    />
                  </div>
                </Card>
                <div className="space-y-6">
                  <Card title="Outcome">
                    <OutcomeCard t={t} />
                  </Card>
                  {cd.termKeys.length > 0 && (
                    <Notice title="Additional terms are rescored">
                      {t.terms_note}
                    </Notice>
                  )}
                  <Card title="Synchronisation" bodyClassName="p-4 text-xs text-ink-3 space-y-1">
                    <p className="num">{t.indexing}</p>
                    <p>
                      {t.video.format === 'mp4-h264' ? 'H.264 MP4' : 'JPEG frame sequence (MP4 encoder unavailable when recorded)'} · {t.video.frames} frames verified at {t.fps} fps · {fmt.compact(t.video.bytes)} bytes
                    </p>
                    <p>Keyboard: Space play/pause · ←/→ step · Shift+←/→ ten steps · Home/End.</p>
                    {t.policy.kind === 'heuristic' && <p className="text-warn">HEURISTIC is Gymnasium’s hand-coded controller, not a trained policy.</p>}
                  </Card>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      <p className="mt-6 flex items-center gap-1.5 text-xs text-ink-3">
        <ArrowLeftRight className="size-3.5" aria-hidden /> A single flight is one episode. Check outcome rates on the comparison page before treating any clip as typical.
      </p>
    </>
  )
}
