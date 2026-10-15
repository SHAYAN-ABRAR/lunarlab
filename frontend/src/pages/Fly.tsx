import clsx from 'clsx'
import { ArrowBigLeft, ArrowBigRight, ArrowBigUp, Ghost, Keyboard, Pause, Play, RotateCcw, Shuffle, Trophy, X } from 'lucide-react'
import { type ReactNode, Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router'
import type { FlightHandle } from '../components/FlightScene'
import type { SceneData } from '../components/Scene3D'
import { Button, Card, EmptyState, ErrorBanner, Field, Notice, OutcomeBadge, PageHeader, Segmented, Table } from '../components/ui'
import { api } from '../lib/api'
import { DEMO } from '../lib/demo'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import type { FlightEpisode, FlightStepResult, GhostFlight, RecordingMeta, RunSummary, TelemetryRow } from '../lib/types'

// three.js loads only when a flight starts.
const FlightScene = lazy(() => import('../components/FlightScene'))

interface FlightStart {
  session_id: string
  seed: number
  fps: number
  scene: SceneData
  row: TelemetryRow
  max_actions_per_request: number
  ghost: GhostFlight | null
}

type Phase = 'setup' | 'starting' | 'countdown' | 'flying' | 'landed'
type Speed = '1' | '0.75' | '0.5'

/** Keys → discrete actions. ← fires the +x-side jet (action 1), which pushes the lander towards −x. */
function keyAction(key: string): number | null {
  if (key === 'ArrowUp' || key === 'w' || key === 'W' || key === ' ') return 2
  if (key === 'ArrowLeft' || key === 'a' || key === 'A') return 1
  if (key === 'ArrowRight' || key === 'd' || key === 'D') return 3
  return null
}

/** One action per step: with several keys held, alternate them step by step. */
function chooseAction(held: Set<number>, step: number): number {
  if (held.size === 0) return 0
  const list = [2, 1, 3].filter((a) => held.has(a))
  return list[step % list.length]
}

function ghostName(g: GhostFlight): string {
  if (g.source.type === 'heuristic') return 'Heuristic'
  return `${g.source.algo.toUpperCase()} · ${g.source.reward_name} · seed ${g.source.training_seed}`
}

function engineUse(ep: FlightEpisode) {
  return { main: ep.actions.main ?? 0, side: (ep.actions.left ?? 0) + (ep.actions.right ?? 0) }
}

export default function Fly() {
  const runs = useApi<RunSummary[]>('/api/runs')
  const recordings = useApi<RecordingMeta[]>('/api/recordings')
  const [opponent, setOpponent] = useState('heuristic')
  const [terrain, setTerrain] = useState<'random' | 'seed'>('random')
  const [seedText, setSeedText] = useState('')
  const [speed, setSpeed] = useState<Speed>('1')
  const [phase, setPhase] = useState<Phase>('setup')
  const [flight, setFlight] = useState<FlightStart | null>(null)
  const [countdown, setCountdown] = useState(3)
  const [paused, setPaused] = useState(false)
  const [heldView, setHeldView] = useState<number[]>([])
  const [result, setResult] = useState<{ episode: FlightEpisode; recording: RecordingMeta } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const handleRef = useRef<FlightHandle | null>(null)
  const held = useRef(new Set<number>())
  const pausedRef = useRef(false)
  pausedRef.current = paused
  // Leaving the page mid-flight abandons the server session (it would otherwise expire after 10 min).
  const liveRef = useRef<string | null>(null)
  liveRef.current = flight && phase !== 'landed' ? flight.session_id : null
  useEffect(
    () => () => {
      if (liveRef.current) api.del(`/api/flights/${liveRef.current}`).catch(() => undefined)
    },
    [],
  )

  const opponents = useMemo(() => {
    const usable = (runs.data ?? []).filter((r) => r.frozen_for_test || r.best_validation)
    return usable
      .map((r) => ({
        value: r.run_id,
        score: r.latest_test?.mean_original_return ?? r.best_validation?.validation_mean_original_return ?? null,
        label: `${(r.algo ?? 'ppo').toUpperCase()} · ${r.reward_name} · seed ${r.seed} · ${fmt.compact(r.checkpoint_transitions)} steps${
          r.latest_test ? ` · test mean ${fmt.num(r.latest_test.mean_original_return, 0)}` : ''
        }`,
      }))
      .toSorted((a, b) => (b.score ?? -1e9) - (a.score ?? -1e9))
  }, [runs.data])

  const seedValue = terrain === 'seed' ? Number(seedText) : null
  const seedInvalid = terrain === 'seed' && (seedText.trim() === '' || !Number.isInteger(seedValue) || (seedValue ?? -1) < 0 || (seedValue ?? 0) > 2 ** 31 - 1)

  const syncHeld = () => setHeldView([...held.current])

  const start = useCallback(
    async (seed: number | null) => {
      setError(null)
      setResult(null)
      setPaused(false)
      held.current.clear()
      setHeldView([])
      setPhase('starting')
      try {
        const f = await api.post<FlightStart>('/api/flights', { seed, opponent: opponent || null })
        ;(document.activeElement as HTMLElement | null)?.blur() // Space must not re-press a focused button
        setFlight(f)
        setCountdown(3)
        setPhase('countdown')
      } catch (e) {
        setError((e as Error).message)
        setPhase('setup')
      }
    },
    [opponent],
  )

  const abort = useCallback(() => {
    if (flight && phase !== 'landed') api.del(`/api/flights/${flight.session_id}`).catch(() => undefined)
    setFlight(null)
    setPhase('setup')
  }, [flight, phase])

  // Countdown 3-2-1 with the scene already visible.
  useEffect(() => {
    if (phase !== 'countdown') return
    if (countdown <= 0) {
      setPhase('flying')
      return
    }
    const id = window.setTimeout(() => setCountdown((c) => c - 1), 700)
    return () => window.clearTimeout(id)
  }, [phase, countdown])

  // The step loop: real time (×speed). Actions due since the last request are sent together; the
  // server steps the real environment and returns the new rows.
  useEffect(() => {
    if (phase !== 'flying' || !flight) return
    let raf = 0
    let last = performance.now()
    let due = 0
    let step = 0
    let busy = false
    let stopped = false
    const stepMs = 1000 / (flight.fps * Number(speed))
    const tick = (now: number) => {
      if (stopped) return
      raf = requestAnimationFrame(tick)
      const dt = Math.max(0, now - last) // rAF timestamps can precede the start time slightly
      last = now
      if (pausedRef.current) return
      due = Math.min(due + dt / stepMs, flight.max_actions_per_request)
      if (busy || due < 1) return
      const n = Math.floor(due)
      due -= n
      const actions = Array.from({ length: n }, (_, i) => chooseAction(held.current, step + i))
      step += n
      busy = true
      api
        .post<FlightStepResult>(`/api/flights/${flight.session_id}/step`, { actions })
        .then((out) => {
          if (stopped) return
          handleRef.current?.push(out.rows)
          if (out.done && out.episode && out.recording) {
            stopped = true
            handleRef.current?.end(out.episode)
            setResult({ episode: out.episode, recording: out.recording })
          }
        })
        .catch((e) => {
          if (stopped) return
          stopped = true
          setError((e as Error).message)
          setFlight(null)
          setPhase('setup')
        })
        .finally(() => {
          busy = false
        })
    }
    raf = requestAnimationFrame(tick)
    return () => {
      stopped = true
      cancelAnimationFrame(raf)
    }
  }, [phase, flight, speed])

  // Keyboard (and pause when the tab is hidden).
  useEffect(() => {
    if (phase !== 'flying' && phase !== 'countdown') return
    const down = (e: KeyboardEvent) => {
      const a = keyAction(e.key)
      if (a !== null) {
        e.preventDefault()
        if (!held.current.has(a)) {
          held.current.add(a)
          syncHeld()
        }
      } else if (e.key === 'p' || e.key === 'P') {
        setPaused((p) => !p)
      } else if (e.key === 'Escape') {
        abort()
      }
    }
    const up = (e: KeyboardEvent) => {
      const a = keyAction(e.key)
      if (a !== null) {
        e.preventDefault()
        held.current.delete(a)
        syncHeld()
      }
    }
    const blur = () => {
      held.current.clear()
      syncHeld()
    }
    const vis = () => {
      if (document.hidden) setPaused(true)
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    window.addEventListener('blur', blur)
    document.addEventListener('visibilitychange', vis)
    return () => {
      window.removeEventListener('keydown', down)
      window.removeEventListener('keyup', up)
      window.removeEventListener('blur', blur)
      document.removeEventListener('visibilitychange', vis)
    }
  }, [phase, abort])

  useEffect(() => {
    handleRef.current?.setPaused(paused)
  }, [paused])

  const reloadRecordings = recordings.reload
  const onEnded = useCallback(() => {
    setPhase('landed')
    held.current.clear()
    setHeldView([])
    reloadRecordings()
  }, [reloadRecordings])

  const press = (a: number, on: boolean) => {
    if (on) held.current.add(a)
    else held.current.delete(a)
    syncHeld()
  }

  const myFlights = (recordings.data ?? []).filter((r) => r.policy.kind === 'human')
  const best = myFlights.reduce<RecordingMeta | null>((b, r) => (!b || r.original_return > b.original_return ? r : b), null)
  const active = phase === 'countdown' || phase === 'flying' || phase === 'landed'

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fly It Yourself"
        subtitle={
          <>
            You fly the same <span className="font-mono">LunarLander-v3</span> the agents learn: the backend steps the real physics 50 times a second with the keys you hold, scores the flight
            with the original reward and classifies the outcome exactly like an evaluation. Every flight is saved as a recording. Pick a ghost to race: it flies the same terrain and initial push.
          </>
        }
      />
      <ErrorBanner error={error} />
      {DEMO && (
        <Notice tone="warn" title="Needs the local app">
          Flying runs the real physics on the LunarLab backend, which the static demo does not have. The logbook below shows saved flights, and Flight Replay plays them back.
        </Notice>
      )}

      {!active && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <Card title="Pre-flight" eyebrow="Set up">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <Field label="Ghost opponent" htmlFor="fly-opponent" hint="Trained runs fly their frozen, validation-selected checkpoint (deterministic).">
                <select id="fly-opponent" className="field" value={opponent} onChange={(e) => setOpponent(e.target.value)}>
                  <option value="">No ghost</option>
                  <option value="heuristic">Gymnasium heuristic (hand-coded controller)</option>
                  {opponents.length > 0 && (
                    <optgroup label="Trained agents">
                      {opponents.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </Field>
              <Field label="Terrain" htmlFor="fly-seed" error={seedInvalid && seedText !== '' ? 'Use a whole number from 0 to 2147483647.' : null} hint="The episode seed fixes the terrain and the initial push.">
                <div className="flex flex-wrap items-center gap-2">
                  <Segmented
                    label="Terrain"
                    value={terrain}
                    onChange={setTerrain}
                    options={[
                      { value: 'random', label: 'Random' },
                      { value: 'seed', label: 'Seed' },
                    ]}
                  />
                  {terrain === 'seed' && (
                    <input id="fly-seed" className="field w-36" inputMode="numeric" placeholder="e.g. 20000" value={seedText} onChange={(e) => setSeedText(e.target.value.trim())} aria-invalid={seedInvalid || undefined} />
                  )}
                </div>
              </Field>
              <Field label="Game speed" hint="Practice slower; scores are the same physics either way.">
                <Segmented
                  label="Game speed"
                  value={speed}
                  onChange={setSpeed}
                  options={[
                    { value: '0.5', label: '0.5×' },
                    { value: '0.75', label: '0.75×' },
                    { value: '1', label: '1× real time' },
                  ]}
                />
              </Field>
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <Button variant="primary" icon={<Play className="size-4" aria-hidden />} pending={phase === 'starting'} disabled={seedInvalid || DEMO} onClick={() => start(seedValue)}>
                Start flight
              </Button>
              <span className="text-xs text-ink-3">A 3-second countdown follows. Esc aborts, P pauses.</span>
            </div>
          </Card>
          <Controls />
        </div>
      )}

      {active && flight && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="min-w-0 space-y-3">
            <Suspense fallback={<div className="flex aspect-[3/2] items-center justify-center rounded-lg border border-line bg-black text-ink-3">Loading 3-D view…</div>}>
              <FlightScene
                sessionId={flight.session_id}
                seed={flight.seed}
                fps={flight.fps}
                scene={flight.scene}
                row0={flight.row}
                ghost={flight.ghost ? { label: ghostName(flight.ghost), rows: flight.ghost.rows } : null}
                speed={Number(speed)}
                handleRef={handleRef}
                onEnded={onEnded}
                ended={phase === 'landed' && result ? result.episode : null}
              >
                {phase === 'countdown' && (
                  <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                    <div className="font-mono text-6xl font-medium text-accent drop-shadow-[0_0_18px_rgba(60,200,212,0.6)]" aria-live="assertive">
                      {countdown > 0 ? countdown : 'GO'}
                    </div>
                  </div>
                )}
                {paused && phase === 'flying' && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40">
                    <div className="rounded-md border border-white/15 bg-black/60 px-4 py-2 font-mono text-sm tracking-[0.2em] text-ink">PAUSED · press P</div>
                  </div>
                )}
              </FlightScene>
            </Suspense>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <TouchControls held={heldView} onPress={press} disabled={phase !== 'flying' && phase !== 'countdown'} />
              <div className="flex gap-2">
                {phase === 'flying' && (
                  <Button size="sm" icon={paused ? <Play className="size-4" aria-hidden /> : <Pause className="size-4" aria-hidden />} onClick={() => setPaused((p) => !p)}>
                    {paused ? 'Resume' : 'Pause'}
                  </Button>
                )}
                {phase !== 'landed' && (
                  <Button size="sm" variant="ghost" icon={<X className="size-4" aria-hidden />} onClick={abort}>
                    Abort
                  </Button>
                )}
              </div>
            </div>
          </div>
          <div className="space-y-6">
            {phase === 'landed' && result ? (
              <Results result={result} ghost={flight.ghost} seed={flight.seed} fps={flight.fps} onSame={() => start(flight.seed)} onNew={() => start(null)} onSetup={() => setPhase('setup')} />
            ) : (
              <Controls compact />
            )}
          </div>
        </div>
      )}

      <Card
        title="Your flights"
        eyebrow="Logbook"
        actions={best ? <span className="inline-flex items-center gap-1.5 text-[13px] text-ink-2"><Trophy className="size-4 text-warn" aria-hidden /> best {fmt.num(best.original_return, 1)}</span> : undefined}
      >
        {myFlights.length === 0 ? (
          <EmptyState icon={<Keyboard className="size-5" />} title="No flights yet">
            Finished flights appear here and in Flight Replay, with video and full telemetry.
          </EmptyState>
        ) : (
          <Table>
            <thead>
              <tr>
                <th>When</th>
                <th>Seed</th>
                <th className="text-right">Score</th>
                <th>Outcome</th>
                <th className="text-right">Time</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {myFlights.slice(0, 20).map((r) => (
                <tr key={r.recording_id}>
                  <td className="whitespace-nowrap text-ink-2">{fmt.time(r.created_at)}</td>
                  <td className="num">{r.episode_seed}</td>
                  <td className={clsx('num text-right', r.original_return >= 200 ? 'text-good' : r.original_return < 0 ? 'text-crit' : 'text-ink')}>{fmt.num(r.original_return, 1)}</td>
                  <td>
                    <OutcomeBadge outcome={r.env_outcome} pad={r.pad_landing} />
                  </td>
                  <td className="num text-right">{fmt.num(r.length / r.fps, 1)} s</td>
                  <td className="text-right">
                    <Link className="text-accent hover:underline" to={`/replay/${r.recording_id}`}>
                      Replay
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  )
}

function Key({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return <kbd className={clsx('inline-flex h-6 items-center justify-center rounded border border-line-strong bg-surface-3 px-1.5 font-mono text-[11px] text-ink', wide ? 'min-w-12' : 'min-w-6')}>{children}</kbd>
}

function Controls({ compact }: { compact?: boolean }) {
  return (
    <Card title="Controls" eyebrow="Keyboard">
      <ul className="space-y-2.5 text-[13px] text-ink-2">
        <li className="flex items-center justify-between gap-3">
          <span>Main engine (action 2)</span>
          <span className="flex gap-1">
            <Key>↑</Key>
            <Key>W</Key>
            <Key wide>Space</Key>
          </span>
        </li>
        <li className="flex items-center justify-between gap-3">
          <span>Push left: right-side jet (action 1)</span>
          <span className="flex gap-1">
            <Key>←</Key>
            <Key>A</Key>
          </span>
        </li>
        <li className="flex items-center justify-between gap-3">
          <span>Push right: left-side jet (action 3)</span>
          <span className="flex gap-1">
            <Key>→</Key>
            <Key>D</Key>
          </span>
        </li>
        <li className="flex items-center justify-between gap-3">
          <span>Pause · abort</span>
          <span className="flex gap-1">
            <Key>P</Key>
            <Key wide>Esc</Key>
          </span>
        </li>
      </ul>
      {!compact && (
        <div className="mt-4 space-y-2 text-xs text-ink-3">
          <p>The environment takes one action per step, so holding two keys alternates them step by step. Side jets also rotate the lander.</p>
          <p>Scoring is the original reward: get close to the pad, slow down, stay level, touch down on both legs (+10 each), and come to rest (+100). Crashing costs −100; the main engine costs 0.3 per step. 200 counts as solved.</p>
        </div>
      )}
    </Card>
  )
}

function TouchControls({ held, onPress, disabled }: { held: number[]; onPress: (a: number, on: boolean) => void; disabled: boolean }) {
  const buttons = [
    { a: 1, label: 'Push left', Icon: ArrowBigLeft },
    { a: 2, label: 'Main engine', Icon: ArrowBigUp },
    { a: 3, label: 'Push right', Icon: ArrowBigRight },
  ]
  return (
    <div className="flex gap-2" aria-label="Touch controls">
      {buttons.map(({ a, label, Icon }) => (
        <button
          key={a}
          type="button"
          aria-label={label}
          aria-pressed={held.includes(a)}
          disabled={disabled}
          onPointerDown={(e) => {
            e.currentTarget.setPointerCapture(e.pointerId)
            onPress(a, true)
          }}
          onPointerUp={() => onPress(a, false)}
          onPointerCancel={() => onPress(a, false)}
          onContextMenu={(e) => e.preventDefault()}
          className={clsx(
            'flex size-12 touch-none select-none items-center justify-center rounded-md border transition-colors disabled:opacity-40',
            held.includes(a) ? 'border-warn/70 bg-warn/20 text-warn' : 'border-line-strong bg-surface-3 text-ink-2',
          )}
        >
          <Icon className="size-6" aria-hidden />
        </button>
      ))}
    </div>
  )
}

function Results({
  result,
  ghost,
  seed,
  fps,
  onSame,
  onNew,
  onSetup,
}: {
  result: { episode: FlightEpisode; recording: RecordingMeta }
  ghost: GhostFlight | null
  seed: number
  fps: number
  onSame: () => void
  onNew: () => void
  onSetup: () => void
}) {
  const you = result.episode
  const diff = ghost ? you.original_return - ghost.episode.original_return : null
  const rows: { label: string; ep: FlightEpisode }[] = [{ label: 'You', ep: you }, ...(ghost ? [{ label: ghostName(ghost), ep: ghost.episode }] : [])]
  return (
    <Card title="Flight result" eyebrow={`Seed ${seed}`}>
      <div className="num text-4xl font-medium text-ink">{fmt.num(you.original_return, 1)}</div>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-[13px] text-ink-2">
        <OutcomeBadge outcome={you.env_outcome} pad={you.pad_landing} />
        <span>{you.original_return >= 200 ? 'solved (≥ 200)' : 'below the 200 "solved" line'}</span>
      </div>
      {ghost && diff !== null && (
        <Notice tone={diff >= 0 ? 'good' : 'info'} title={diff >= 0 ? 'You beat the ghost' : 'The ghost wins this one'}>
          {fmt.signed(diff, 1)} points vs {ghostName(ghost)} on the same terrain and initial push.
        </Notice>
      )}
      <ul className="mt-4 divide-y divide-line/70 border-y border-line/70">
        {rows.map(({ label, ep }) => (
          <li key={label} className="flex items-start justify-between gap-3 py-2.5 text-[13px]">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 text-ink">
                {label !== 'You' && <Ghost className="size-3.5 shrink-0 text-[#8fdcff]" aria-hidden />}
                <span className="truncate">{label}</span>
              </div>
              <div className="mt-0.5 text-xs text-ink-3">
                {fmt.num(ep.length / fps, 1)} s · main engine {engineUse(ep).main} steps · side jets {engineUse(ep).side}
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="num text-ink">{fmt.num(ep.original_return, 1)}</div>
              <div className="mt-0.5">
                <OutcomeBadge outcome={ep.env_outcome} pad={ep.pad_landing} />
              </div>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-5 flex flex-wrap gap-2">
        <Button variant="primary" size="sm" icon={<RotateCcw className="size-4" aria-hidden />} onClick={onSame}>
          Same terrain
        </Button>
        <Button size="sm" icon={<Shuffle className="size-4" aria-hidden />} onClick={onNew}>
          New terrain
        </Button>
        <Link to={`/replay/${result.recording.recording_id}`} className="inline-flex h-8 items-center rounded-md px-3 text-[13px] text-accent hover:bg-surface-3">
          Open in Flight Replay
        </Link>
        <Button size="sm" variant="ghost" onClick={onSetup}>
          Change setup
        </Button>
      </div>
    </Card>
  )
}
