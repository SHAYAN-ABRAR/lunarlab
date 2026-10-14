import type { Preset, RewardConfig } from './types'

// Fixed preset → colour mapping. Colour follows the entity, never its rank.
// Validated all-pairs on the chart surface (CVD ΔE ≥ 6.9, normal-vision ΔE ≥ 19.3, ≥ 3:1). The 6–8 CVD band
// requires secondary encoding, so every preset also has its own dash pattern and marker shape.
export const PRESET_COLOR: Record<Preset, string> = {
  baseline: '#3987e5',
  'time-penalty': '#c98500',
  'hover-bonus': '#d55181',
  potential: '#008300',
  custom: '#8494a8',
}

export const PRESET_DASH: Record<Preset, string | undefined> = {
  baseline: undefined,
  'time-penalty': '6 3',
  'hover-bonus': '2 3',
  potential: '10 4',
  custom: '1 3',
}

export const PRESET_SHAPE: Record<Preset, 'circle' | 'square' | 'triangle' | 'diamond' | 'cross'> = {
  baseline: 'circle',
  'time-penalty': 'square',
  'hover-bonus': 'triangle',
  potential: 'diamond',
  custom: 'cross',
}

/** Additional reward terms reuse the colour of the preset that introduces them. */
export const TERM_COLOR: Record<string, string> = {
  time_penalty: '#c98500',
  hover_bonus: '#d55181',
  potential_shaping: '#008300',
}

export const PRESET_LABEL: Record<Preset, string> = {
  baseline: 'Original baseline',
  'time-penalty': 'Time-penalty ablation',
  'hover-bonus': 'Flawed hover bonus',
  potential: 'Potential-based shaping',
  custom: 'Custom',
}

export const SERIES = { original: '#3987e5', shaped: '#d95926' }

export const TERM_LABEL: Record<string, string> = {
  time_penalty: 'Time penalty',
  hover_bonus: 'Hover bonus',
  potential_shaping: 'Potential shaping',
}

const n = (v: number) => (Number.isInteger(v) ? String(v) : String(Number(v.toFixed(4))))

/** Human-readable formula lines for a reward configuration (mirrors lunarlab/rewards/terms.py). */
export function formulaLines(cfg: RewardConfig, gamma = 0.999): string[] {
  const lines = ['training_reward = original_reward']
  if (cfg.time_penalty.enabled) lines.push(`  − ${n(cfg.time_penalty.cost_per_step)}            (every transition)`)
  if (cfg.hover_bonus.enabled) {
    const e = cfg.hover_bonus.eligibility
    const parts = [
      'airborne',
      `${n(e.min_height)} ≤ y ≤ ${n(e.max_height)}`,
      `|angle| ≤ ${n(e.max_abs_angle_rad)}`,
      `|vx| ≤ ${n(e.max_abs_vx)}`,
      `|vy| ≤ ${n(e.max_abs_vy)}`,
    ]
    if (e.max_abs_angular_velocity !== null) parts.push(`|ω| ≤ ${n(e.max_abs_angular_velocity)}`)
    lines.push(`  + ${n(cfg.hover_bonus.bonus_per_step)} · 1[ ${parts.join(' ∧ ')} ](s′)`)
  }
  if (cfg.potential.enabled) {
    const w = cfg.potential.weights
    lines.push(`  + ${n(cfg.potential.alpha)} · ( γ·Φ(s′) − Φ(s) ),   γ = ${gamma} (PPO γ),  Φ(terminal) = 0`)
    lines.push(
      `    Φ(s) = −( ${n(w.x)}·tanh|x| + ${n(w.y)}·tanh|y| + ${n(w.speed)}·tanh‖v‖ + ${n(w.angle)}·tanh|θ| + ${n(w.angular_velocity)}·tanh|ω| )`,
    )
  }
  if (lines.length === 1) lines.push('  (no additional terms)')
  return lines
}

export function activeTerms(cfg: RewardConfig): string[] {
  const t: string[] = []
  if (cfg.time_penalty.enabled) t.push('time_penalty')
  if (cfg.hover_bonus.enabled) t.push('hover_bonus')
  if (cfg.potential.enabled) t.push('potential_shaping')
  return t
}
