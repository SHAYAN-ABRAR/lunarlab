/**
 * Live 3-D view of a keyboard flight: the Scene3D engine in live mode (rows arrive from the server
 * as the real environment is stepped), with the opponent's flight on the same seed as a ghost.
 */
import { type ReactNode, type RefObject, useEffect, useRef, useState } from 'react'
import { usePrefersReducedMotion } from '../lib/hooks'
import type { Telemetry, TelemetryRow } from '../lib/types'
import { CameraSwitch, type GhostTrack, LanderScene, OutcomeBanner, type SceneData, TelemetryHud, useCameraMode } from './Scene3D'

export interface FlightHandle {
  push: (rows: TelemetryRow[]) => void
  end: (episode: { env_outcome: string; pad_landing: boolean }) => void
  setPaused: (paused: boolean) => void
}

interface Props {
  sessionId: string
  seed: number
  fps: number
  scene: SceneData
  row0: TelemetryRow
  ghost: GhostTrack | null
  speed: number
  handleRef: RefObject<FlightHandle | null>
  onEnded: () => void
  ended: { env_outcome: string; pad_landing: boolean } | null
  children?: ReactNode
}

export default function FlightScene({ sessionId, seed, fps, scene, row0, ghost, speed, handleRef, onEnded, ended, children }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const engineRef = useRef<LanderScene | null>(null)
  const rowsRef = useRef<TelemetryRow[]>([row0])
  const endedRef = useRef(onEnded)
  endedRef.current = onEnded
  const [frame, setFrame] = useState(0)
  const [mode, setMode] = useCameraMode()
  const [failed, setFailed] = useState<string | null>(null)
  const reduced = usePrefersReducedMotion()

  useEffect(() => {
    if (!canvasRef.current || !containerRef.current) return
    const rows: TelemetryRow[] = [row0]
    rowsRef.current = rows
    // A minimal telemetry object: the engine reads rows, fps, the seed (decor) and, at the end, the outcome.
    const t = { recording_id: sessionId, episode_seed: seed, fps, n_frames: 1, rows, episode: { env_outcome: 'unknown', pad_landing: false } } as unknown as Telemetry
    let engine: LanderScene
    try {
      engine = new LanderScene(canvasRef.current, containerRef.current, t, scene, { onFrame: setFrame, onEnded: () => endedRef.current() }, reduced, { live: true, ghost })
    } catch (e) {
      setFailed(`3-D view unavailable (${(e as Error).message}).`)
      return
    }
    engineRef.current = engine
    handleRef.current = {
      push: (r) => engine.pushRows(r),
      end: (ep) => engine.endLive(ep as Telemetry['episode']),
      setPaused: (p) => engine.setPaused(p),
    }
    return () => {
      engine.dispose()
      engineRef.current = null
      handleRef.current = null
    }
    // One engine per flight.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, reduced])

  useEffect(() => {
    engineRef.current?.setCameraMode(mode)
  }, [mode, sessionId])

  useEffect(() => {
    engineRef.current?.setSpeed(speed)
  }, [speed, sessionId])

  const rows = rowsRef.current
  const row = rows[Math.min(frame, rows.length - 1)] ?? row0

  return (
    <div ref={containerRef} className="relative overflow-hidden rounded-lg border border-line bg-black" style={{ aspectRatio: '3 / 2' }}>
      <canvas ref={canvasRef} role="img" aria-label="Live 3-D view of your flight" className="block h-full w-full" />
      {failed && <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/80 p-6 text-center text-[13px] text-ink-2">{failed}</div>}
      <div className="pointer-events-none absolute inset-0 select-none p-3 font-mono text-[11px] text-ink">
        <div className="flex items-start justify-between gap-3">
          <div className="rounded-md border border-white/10 bg-black/45 px-2.5 py-1.5 backdrop-blur-sm">
            <div className="tracking-[0.18em] text-accent">LIVE FLIGHT · SEED {seed}</div>
            <div className="text-[10px] text-ink-3">
              t = {(row.t / fps).toFixed(1)} s · step {row.t}
            </div>
            {ghost && (
              <div className="mt-1 flex items-center gap-1.5 text-[10px] text-[#8fdcff]">
                <span className="inline-block size-2 rounded-full bg-[#8fdcff]/70" aria-hidden />
                ghost: {ghost.label}
              </div>
            )}
          </div>
          <CameraSwitch mode={mode} onChange={setMode} />
        </div>
        {ended && <OutcomeBanner episode={ended} />}
        <TelemetryHud row={row} />
      </div>
      {children}
    </div>
  )
}
