// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
/**
 * Training-physics controls: per-episode randomization of wind, turbulence and gravity while training.
 * Mirrors lunarlab.config.PhysicsRandomization (same defaults and limits).
 */
import { Field, NumberInput } from './ui'

export interface PhysicsRanges {
  wind_probability: number
  wind_power: [number, number]
  turbulence_power: [number, number]
  gravity: [number, number]
}

export const DEFAULT_PHYSICS: PhysicsRanges = {
  wind_probability: 0.8,
  wind_power: [0, 10],
  turbulence_power: [0, 1],
  gravity: [-11, -9],
}

function rangeOk(lo: number, hi: number, a: number, b: number, strict = false) {
  return Number.isFinite(lo) && Number.isFinite(hi) && lo <= hi && (strict ? lo > a && hi < b : lo >= a && hi <= b)
}

/** A validation message, or null when the ranges are acceptable to the backend. */
export function physicsError(p: PhysicsRanges): string | null {
  const ok = rangeOk
  if (!(p.wind_probability >= 0 && p.wind_probability <= 1)) return 'Wind probability must be between 0 and 1.'
  if (!ok(p.wind_power[0], p.wind_power[1], 0, 20)) return 'Wind power: 0 ≤ low ≤ high ≤ 20.'
  if (!ok(p.turbulence_power[0], p.turbulence_power[1], 0, 2)) return 'Turbulence: 0 ≤ low ≤ high ≤ 2.'
  if (!ok(p.gravity[0], p.gravity[1], -12, 0, true)) return 'Gravity: −12 < low ≤ high < 0.'
  return null
}

export function physicsPayload(p: PhysicsRanges) {
  return { enabled: true, ...p }
}

function Range({ id, label, value, onChange, min, max, step, hint }: { id: string; label: string; value: [number, number]; onChange: (v: [number, number]) => void; min: number; max: number; step: number; hint?: string }) {
  return (
    <Field label={label} hint={hint}>
      <div className="flex items-center gap-2">
        <NumberInput id={`${id}-lo`} label={`${label}: low`} value={value[0]} onChange={(v) => onChange([v, value[1]])} min={min} max={max} step={step} />
        <span className="text-ink-3">to</span>
        <NumberInput id={`${id}-hi`} label={`${label}: high`} value={value[1]} onChange={(v) => onChange([value[0], v])} min={min} max={max} step={step} />
      </div>
    </Field>
  )
}

export function PhysicsFields({ value, onChange, idPrefix = 'physics' }: { value: PhysicsRanges; onChange: (v: PhysicsRanges) => void; idPrefix?: string }) {
  const err = physicsError(value)
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Episodes with wind" hint="Share of training episodes that have wind and turbulence at all.">
          <NumberInput id={`${idPrefix}-wp`} label="Episodes with wind" value={value.wind_probability} onChange={(v) => onChange({ ...value, wind_probability: v })} min={0} max={1} step={0.05} />
        </Field>
        <Range id={`${idPrefix}-wind`} label="Wind power" value={value.wind_power} onChange={(v) => onChange({ ...value, wind_power: v })} min={0} max={20} step={0.5} hint="Gymnasium's scale: 0–20 (default when wind is on: 15)." />
        <Range id={`${idPrefix}-turb`} label="Turbulence" value={value.turbulence_power} onChange={(v) => onChange({ ...value, turbulence_power: v })} min={0} max={2} step={0.1} hint="Rotational gusts: 0–2." />
        <Range id={`${idPrefix}-grav`} label="Gravity" value={value.gravity} onChange={(v) => onChange({ ...value, gravity: v })} min={-11.9} max={-0.1} step={0.1} hint="Default −10; Gymnasium allows −12 to 0." />
      </div>
      {err && <p className="text-xs text-crit">{err}</p>}
      <p className="text-xs text-ink-3">
        Each training episode draws its physics from these ranges, reproducibly from the run&apos;s seeds. Validation and the final test always fly default physics, so checkpoint
        selection is the same for every run; the robustness evaluations then test wind and heavier gravity, partly outside these ranges.
      </p>
    </div>
  )
}
