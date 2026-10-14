import clsx from 'clsx'
import { Calculator, Download, FileUp, Lock, Rocket, Save } from 'lucide-react'
import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { LaunchForm } from '../components/Launch'
import { Badge, Button, Card, Dialog, ErrorBanner, Field, Notice, NumberInput, PageHeader, Spinner, Toggle } from '../components/ui'
import { api } from '../lib/api'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import { PRESET_COLOR, TERM_LABEL, formulaLines } from '../lib/reward'
import type { RewardConfig, RewardConfigRow } from '../lib/types'

interface Validation {
  valid: boolean
  errors: { loc: (string | number)[]; msg: string }[]
  warnings?: string[]
  hash?: string
  active_terms?: string[]
}

interface HoverAnalysis {
  net_per_hover_step: number
  naive_undiscounted_bonus: number
  discounted_hover_value_until_limit: number
  discounted_hover_value_with_timeout_bootstrap: number
  effective_horizon_steps: number | null
  landing_value_range: [number, number]
  explanation: string
}

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))

function Num({ label, value, onChange, min, max, step, hint, disabled, id }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; step: number; hint?: ReactNode; disabled?: boolean; id: string }) {
  const invalid = !Number.isFinite(value) || value < min || value > max
  return (
    <Field label={label} htmlFor={id} hint={hint} error={invalid ? `Allowed range ${min} – ${max}` : null}>
      <NumberInput id={id} value={value} onChange={onChange} min={min} max={max} step={step} disabled={disabled} invalid={invalid} />
    </Field>
  )
}

function TermSection({ title, enabled, onToggle, children, explain, pitfall, disabled }: { title: string; enabled: boolean; onToggle: (v: boolean) => void; children: ReactNode; explain: ReactNode; pitfall: ReactNode; disabled?: boolean }) {
  return (
    <section className={clsx('rounded-lg border p-4', enabled ? 'border-line-strong bg-surface-2/40' : 'border-line')} aria-label={title}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-[14px] font-semibold">{title}</h3>
        <Toggle checked={enabled} onChange={onToggle} label={`Enable ${title}`} disabled={disabled} />
      </div>
      <div className="prose-lab mt-1 text-[13px]">{explain}</div>
      {enabled && <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">{children}</div>}
      <div className="mt-3 rounded-md border border-warn/25 bg-warn/[0.05] px-3 py-2 text-xs text-ink-2">
        <span className="font-medium text-warn">Pitfall · </span>
        {pitfall}
      </div>
    </section>
  )
}

function HoverCalculator({ bonus, gamma }: { bonus: number; gamma: number }) {
  const [hoverStart, setHoverStart] = useState(100)
  const [duty, setDuty] = useState(0.5)
  const [landStep, setLandStep] = useState(300)
  const [landReturn, setLandReturn] = useState(220)
  const [res, setRes] = useState<HoverAnalysis | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    const t = window.setTimeout(async () => {
      try {
        setRes(await api.post<HoverAnalysis>('/api/reward-analysis/hover', { bonus, gamma, hover_start: hoverStart, main_engine_duty: duty, landing_step: landStep, landing_original_return: landReturn }))
        setErr(null)
      } catch (e) {
        setErr((e as Error).message)
      }
    }, 250)
    return () => window.clearTimeout(t)
  }, [bonus, gamma, hoverStart, duty, landStep, landReturn])
  return (
    <div className="space-y-4">
      <p className="text-[13px] text-ink-2">
        What does the hover bonus <em>offer</em>, compared with landing? A calculator with explicit assumptions. It does not predict what PPO learns: exploration, the critic and the budget decide that.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <Num id="calc-start" label="Hover starts at step" value={hoverStart} onChange={setHoverStart} min={0} max={999} step={10} />
        <Num id="calc-duty" label="Main-engine duty to hold altitude" value={duty} onChange={setDuty} min={0} max={1} step={0.05} hint="fraction of steps × 0.30 fuel cost" />
        <Num id="calc-land" label="Landing finishes at step" value={landStep} onChange={setLandStep} min={1} max={1000} step={10} />
        <Num id="calc-ret" label="Original return of a landing" value={landReturn} onChange={setLandReturn} min={-500} max={500} step={10} />
      </div>
      <ErrorBanner error={err} />
      {res && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ['Naive: bonus × steps', res.naive_undiscounted_bonus, 'undiscounted; ignores γ and fuel'],
            ['Discounted, until the 1000-step limit', res.discounted_hover_value_until_limit, `net ${fmt.num(res.net_per_hover_step, 2)}/step after fuel`],
            ['Discounted, critic bootstraps at timeout', res.discounted_hover_value_with_timeout_bootstrap, 'SB3 adds γ·V(s_T) on truncation'],
            ['Landing (discounted range)', null, `${fmt.num(res.landing_value_range[0], 0)} … ${fmt.num(res.landing_value_range[1], 0)}`],
          ].map(([label, v, sub]) => (
            <div key={String(label)} className="rounded-md border border-line bg-bg/50 p-3">
              <div className="text-xs text-ink-3">{label}</div>
              <div className="num mt-1 text-lg text-ink">{v === null ? `${fmt.num(res.landing_value_range[1], 0)}` : fmt.num(Number(v), 0)}</div>
              <div className="text-[11px] text-ink-3">{sub}</div>
            </div>
          ))}
        </div>
      )}
      {res && <p className="text-xs text-ink-3">{res.explanation}</p>}
    </div>
  )
}

export default function RewardStudio() {
  const list = useApi<RewardConfigRow[]>('/api/reward-configs')
  const meta = useApi<{ ppo_defaults: { gamma: number } }>('/api/meta')
  const gamma = Number(meta.data?.ppo_defaults.gamma ?? 0.999)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState<RewardConfig | null>(null)
  const [validation, setValidation] = useState<Validation | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [savedNote, setSavedNote] = useState<string | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  const [importText, setImportText] = useState('')
  const [importError, setImportError] = useState<string | null>(null)
  const [trainOpen, setTrainOpen] = useState(false)

  const rows = useMemo(() => list.data ?? [], [list.data])
  const selected = rows.find((r) => r.id === selectedId) ?? null

  useEffect(() => {
    if (!selectedId && rows.length) {
      const hover = rows.find((r) => r.preset === 'hover-bonus') ?? rows[0]
      setSelectedId(hover.id)
      setDraft(clone(hover.config))
    }
  }, [rows, selectedId])

  const dirty = !!selected && !!draft && JSON.stringify(selected.config) !== JSON.stringify(draft)

  useEffect(() => {
    if (!draft) return
    const t = window.setTimeout(async () => {
      try {
        setValidation(await api.post<Validation>('/api/reward-configs/validate', { config: draft }))
      } catch (e) {
        setValidation({ valid: false, errors: [{ loc: [], msg: (e as Error).message }] })
      }
    }, 300)
    return () => window.clearTimeout(t)
  }, [draft])

  const families = useMemo(() => {
    const m = new Map<string, RewardConfigRow[]>()
    rows.filter((r) => !r.builtin).forEach((r) => m.set(r.family, [...(m.get(r.family) ?? []), r]))
    return [...m.values()].map((revs) => revs.toSorted((a, b) => b.revision - a.revision))
  }, [rows])

  const pick = (r: RewardConfigRow) => {
    setSelectedId(r.id)
    setDraft(clone(r.config))
    setSavedNote(null)
    setSaveError(null)
  }
  const set = (fn: (d: RewardConfig) => void) =>
    setDraft((cur) => {
      if (!cur) return cur
      const next = clone(cur)
      fn(next)
      return next
    })

  const save = async () => {
    if (!draft) return
    setSaving(true)
    setSaveError(null)
    try {
      const body = { config: { ...draft, preset: selected?.builtin && !dirty ? draft.preset : 'custom' }, parent_id: selectedId }
      const row = await api.post<RewardConfigRow>('/api/reward-configs', body)
      await list.reload()
      setSelectedId(row.id)
      setDraft(clone(row.config))
      setSavedNote(`Saved as “${row.name}” revision ${row.revision}. Earlier revisions and any runs using them are unchanged.`)
    } catch (e) {
      setSaveError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const doImport = async () => {
    setImportError(null)
    try {
      const row = await api.post<RewardConfigRow>('/api/reward-configs/import', { yaml: importText })
      await list.reload()
      pick(row)
      setImportOpen(false)
      setImportText('')
    } catch (e) {
      setImportError((e as Error).message)
    }
  }

  if (list.error && !list.data) return <ErrorBanner error={list.error.message} onRetry={list.reload} />
  if (!draft) return <Spinner label="Loading reward configurations" />
  const e = draft.hover_bonus.eligibility
  const w = draft.potential.weights
  const canSave = !!validation?.valid && (dirty || !!selected?.builtin)

  return (
    <>
      <PageHeader
        title="Reward Studio"
        subtitle="Design reward configurations from a fixed schema. Saving always creates a new immutable revision, so a running or finished experiment can never have its reward changed underneath it."
        actions={
          <Button icon={<FileUp className="size-4" />} onClick={() => setImportOpen(true)}>
            Import YAML
          </Button>
        }
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[260px_minmax(0,1fr)_400px]">
        <nav aria-label="Reward configurations" className="space-y-5">
          <div>
            <div className="eyebrow mb-2">Presets (read-only)</div>
            <ul className="space-y-1">
              {rows.filter((r) => r.builtin).map((r) => (
                <li key={r.id}>
                  <button type="button" onClick={() => pick(r)} aria-current={r.id === selectedId} className={clsx('flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-[13px]', r.id === selectedId ? 'bg-surface-2 text-ink' : 'text-ink-2 hover:bg-surface')}>
                    <span className="inline-block size-2 rounded-full" style={{ background: PRESET_COLOR[r.preset] }} />
                    <span className="flex-1 truncate">{r.name}</span>
                    <Lock className="size-3.5 text-ink-3" aria-label="built-in" />
                  </button>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="eyebrow mb-2">Your configurations</div>
            {families.length === 0 ? (
              <p className="px-1 text-xs text-ink-3">None yet. Edit a preset and save to create one.</p>
            ) : (
              <ul className="space-y-2">
                {families.map((revs) => (
                  <li key={revs[0].family} className="rounded-md border border-line p-1.5">
                    <div className="px-1.5 py-1 text-[13px] font-medium text-ink">{revs[0].name}</div>
                    <ul>
                      {revs.map((r) => (
                        <li key={r.id}>
                          <button type="button" onClick={() => pick(r)} aria-current={r.id === selectedId} className={clsx('flex w-full items-center justify-between rounded px-2 py-1 text-left text-xs', r.id === selectedId ? 'bg-surface-2 text-ink' : 'text-ink-3 hover:bg-surface')}>
                            <span>rev {r.revision}</span>
                            <span className="num">{r.content_hash.slice(0, 8)}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </nav>

        <div className="min-w-0 space-y-4">
          <Card bodyClassName="p-5 space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              {selected?.builtin ? <Badge tone="neutral" icon={<Lock className="size-3" />}>preset · editing creates a new configuration</Badge> : <Badge tone="info">revision {selected?.revision}</Badge>}
              {dirty && <Badge tone="warn">unsaved changes</Badge>}
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Name" htmlFor="rc-name" error={validation?.errors.find((x) => x.loc[0] === 'name')?.msg}>
                <input id="rc-name" className="field" value={draft.name} maxLength={64} onChange={(ev) => set((d) => void (d.name = ev.target.value))} />
              </Field>
              <Field label="Description" htmlFor="rc-desc">
                <input id="rc-desc" className="field" value={draft.description} maxLength={2000} onChange={(ev) => set((d) => void (d.description = ev.target.value))} />
              </Field>
            </div>
          </Card>

          <Notice title="Always included: the original environment reward">
            The unmodified LunarLander reward: change in the built-in shaping (distance, speed, tilt, leg contact), −0.30 per main-engine step, −0.03 per side-engine step, and on the final step a <strong>replacement</strong> reward of −100 (crash or out of bounds) or +100 (lander at rest). Additional terms below are added on top; they never replace it.
          </Notice>

          <TermSection
            title={TERM_LABEL.time_penalty}
            enabled={draft.time_penalty.enabled}
            onToggle={(v) => set((d) => void (d.time_penalty.enabled = v))}
            explain={<p>Subtracts a fixed cost on every transition, terminal steps included. An <strong>ablation</strong>, not a guaranteed improvement: it changes the objective toward shorter episodes.</p>}
            pitfall="If staying alive costs more than crashing (−100), ending the episode early becomes optimal. At 0.01/step a full 1000-step episode costs only 10."
          >
            <Num id="tp-cost" label="Cost per transition" value={draft.time_penalty.cost_per_step} onChange={(v) => set((d) => void (d.time_penalty.cost_per_step = v))} min={0} max={1} step={0.005} />
          </TermSection>

          <TermSection
            title={TERM_LABEL.hover_bonus}
            enabled={draft.hover_bonus.enabled}
            onToggle={(v) => set((d) => void (d.hover_bonus.enabled = v))}
            explain={<p>Pays a bonus whenever the state <em>reached</em> by a step is eligible: airborne (no leg contact), inside a height band, nearly level and slow. These thresholds are design choices, not validated optimal values. Units are the environment’s normalized observation units.</p>}
            pitfall="Paying for remaining in a desirable intermediate state competes with finishing the task: a policy that collects the bonus until the time limit may be worth more than one that lands. Whether PPO actually learns to hover is an empirical question — run it and look."
          >
            <Num id="hb-bonus" label="Bonus per eligible step" value={draft.hover_bonus.bonus_per_step} onChange={(v) => set((d) => void (d.hover_bonus.bonus_per_step = v))} min={0} max={10} step={0.05} />
            <Num id="hb-ymin" label="Min height y" value={e.min_height} onChange={(v) => set((d) => void (d.hover_bonus.eligibility.min_height = v))} min={-0.5} max={2.5} step={0.05} hint="0 ≈ legs on pad, ~1.4 at spawn" />
            <Num id="hb-ymax" label="Max height y" value={e.max_height} onChange={(v) => set((d) => void (d.hover_bonus.eligibility.max_height = v))} min={-0.5} max={2.5} step={0.05} />
            <Num id="hb-ang" label="Max |angle| (rad)" value={e.max_abs_angle_rad} onChange={(v) => set((d) => void (d.hover_bonus.eligibility.max_abs_angle_rad = v))} min={0.01} max={3.14} step={0.01} hint={`= ${fmt.deg(e.max_abs_angle_rad)}`} />
            <Num id="hb-vx" label="Max |vx| (scaled)" value={e.max_abs_vx} onChange={(v) => set((d) => void (d.hover_bonus.eligibility.max_abs_vx = v))} min={0.01} max={5} step={0.01} />
            <Num id="hb-vy" label="Max |vy| (scaled)" value={e.max_abs_vy} onChange={(v) => set((d) => void (d.hover_bonus.eligibility.max_abs_vy = v))} min={0.01} max={5} step={0.01} />
            <div className="sm:col-span-2 lg:col-span-3">
              <div className="flex items-center gap-3">
                <Toggle checked={e.max_abs_angular_velocity !== null} onChange={(v) => set((d) => void (d.hover_bonus.eligibility.max_abs_angular_velocity = v ? 0.2 : null))} label="Limit angular velocity" />
                <span className="text-[13px] text-ink-2">Limit angular velocity</span>
              </div>
              {e.max_abs_angular_velocity !== null && (
                <div className="mt-3 max-w-xs">
                  <Num id="hb-w" label="Max |angular velocity| (scaled)" value={e.max_abs_angular_velocity} onChange={(v) => set((d) => void (d.hover_bonus.eligibility.max_abs_angular_velocity = v))} min={0.01} max={5} step={0.01} />
                </div>
              )}
            </div>
          </TermSection>

          <TermSection
            title={TERM_LABEL.potential_shaping}
            enabled={draft.potential.enabled}
            onToggle={(v) => set((d) => void (d.potential.enabled = v))}
            explain={
              <p>
                Adds α·(γ·Φ(s′) − Φ(s)) with a bounded state-only potential Φ ≤ 0 and γ equal to the PPO discount ({gamma}). Φ(terminal) = 0 on a true termination; on a time-limit truncation the real final observation is used, matching SB3’s bootstrap. Over a terminated episode the discounted shaping sum is exactly −α·Φ(s₀), independent of the policy (Ng, Harada &amp; Russell, 1999).
              </p>
            }
            pitfall="Policy invariance is a statement about optimal policies, not about how fast or how well finite-budget PPO learns. Clipping the term, dropping γ, or adding terminal bonuses would void the theorem. Expect a positive shaping step at crashes: it cancels potential gathered earlier."
          >
            <Num id="ps-alpha" label="α (scale)" value={draft.potential.alpha} onChange={(v) => set((d) => void (d.potential.alpha = v))} min={0} max={100} step={0.5} hint={`max |total| ≈ ${fmt.num(draft.potential.alpha * (w.x + w.y + w.speed + w.angle + w.angular_velocity), 1)}`} />
            <Num id="ps-wx" label="w · tanh|x|" value={w.x} onChange={(v) => set((d) => void (d.potential.weights.x = v))} min={0} max={10} step={0.05} />
            <Num id="ps-wy" label="w · tanh|y|" value={w.y} onChange={(v) => set((d) => void (d.potential.weights.y = v))} min={0} max={10} step={0.05} />
            <Num id="ps-wv" label="w · tanh‖v‖" value={w.speed} onChange={(v) => set((d) => void (d.potential.weights.speed = v))} min={0} max={10} step={0.05} />
            <Num id="ps-wa" label="w · tanh|angle|" value={w.angle} onChange={(v) => set((d) => void (d.potential.weights.angle = v))} min={0} max={10} step={0.05} />
            <Num id="ps-ww" label="w · tanh|ω|" value={w.angular_velocity} onChange={(v) => set((d) => void (d.potential.weights.angular_velocity = v))} min={0} max={10} step={0.05} />
          </TermSection>

          <Card title="Discounted-return reasoning" eyebrow="hover bonus vs landing" actions={<Calculator className="size-4 text-ink-3" aria-hidden />}>
            <HoverCalculator bonus={draft.hover_bonus.enabled ? draft.hover_bonus.bonus_per_step : 1} gamma={gamma} />
          </Card>
        </div>

        <aside className="min-w-0 space-y-4 xl:sticky xl:top-6 xl:self-start">
          <Card title="Formula preview">
            <pre className="num overflow-x-auto whitespace-pre-wrap rounded-md border border-line bg-bg p-3 text-[12px] leading-relaxed text-ink">{formulaLines(draft, gamma).join('\n')}</pre>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-ink-3">
              <span>reward hash</span>
              <span className="num text-ink-2">{validation?.hash ?? '—'}</span>
            </div>
            <p className="mt-2 text-xs text-ink-3">Identical hashes mean identical reward functions (names and descriptions are ignored).</p>
          </Card>
          <Card title="Validation and design warnings">
            {!validation ? (
              <p className="text-xs text-ink-3">Checking…</p>
            ) : (
              <div className="space-y-2">
                {validation.errors.map((x, i) => (
                  <ErrorBanner key={i} error={`${x.loc.join('.')}: ${x.msg}`} />
                ))}
                {validation.valid && !validation.warnings?.length && <Notice tone="good">Schema valid. No design warnings.</Notice>}
                {validation.warnings?.map((x) => (
                  <Notice key={x} tone="warn">
                    {x}
                  </Notice>
                ))}
              </div>
            )}
          </Card>
          <Card>
            <div className="space-y-3">
              <Button variant="primary" className="w-full" icon={<Save className="size-4" />} pending={saving} disabled={!canSave} onClick={save} title={!validation?.valid ? 'Fix validation errors first' : !dirty && !selected?.builtin ? 'No changes to save' : undefined}>
                {selected?.builtin ? 'Save as new configuration' : 'Save as new revision'}
              </Button>
              {savedNote && <Notice tone="good">{savedNote}</Notice>}
              <ErrorBanner error={saveError} />
              <Button className="w-full" icon={<Rocket className="size-4" />} disabled={dirty || !selected} title={dirty ? 'Save first: runs reference saved revisions only' : undefined} onClick={() => setTrainOpen(true)}>
                Train with this revision…
              </Button>
              {selected && (
                <a href={`/api/reward-configs/${selected.id}/export`} className="flex items-center justify-center gap-2 rounded-md py-2 text-[13px] text-ink-2 hover:bg-surface-3 hover:text-ink">
                  <Download className="size-4" aria-hidden /> Export YAML
                </a>
              )}
            </div>
          </Card>
        </aside>
      </div>

      <Dialog open={importOpen} title="Import a reward configuration (YAML)" onClose={() => setImportOpen(false)} actions={<Button variant="primary" disabled={!importText.trim()} onClick={doImport}>Validate and import</Button>}>
        <p className="mb-2">The file is parsed with a safe YAML loader and validated against the fixed schema. Unknown fields are rejected; nothing is executed.</p>
        <textarea aria-label="YAML" className="field num h-56" value={importText} onChange={(ev) => setImportText(ev.target.value)} placeholder="name: My reward&#10;hover_bonus:&#10;  enabled: true&#10;  bonus_per_step: 0.5" />
        <div className="mt-2">
          <ErrorBanner error={importError} />
        </div>
      </Dialog>
      {trainOpen && selected && (
        <Dialog open title={`Train · ${selected.name}${selected.builtin ? '' : ` rev ${selected.revision}`}`} onClose={() => setTrainOpen(false)}>
          <LaunchForm compact initialPreset={selected.builtin && selected.preset !== 'custom' ? selected.preset : 'baseline'} initialConfigId={selected.builtin ? undefined : selected.id} />
        </Dialog>
      )}
    </>
  )
}
