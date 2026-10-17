// SPDX-FileCopyrightText: 2026 Shayan Abrar
// SPDX-License-Identifier: MIT
import clsx from 'clsx'
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  Clock,
  Loader2,
  OctagonX,
  PauseCircle,
  PlayCircle,
  XCircle,
} from 'lucide-react'
import { type ButtonHTMLAttributes, type ReactNode, useEffect, useId, useRef } from 'react'

// --------------------------------------------------------------------------- //
// Buttons
// --------------------------------------------------------------------------- //

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

export function Button({
  variant = 'secondary',
  size = 'md',
  pending,
  icon,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: 'sm' | 'md'
  pending?: boolean
  icon?: ReactNode
}) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors whitespace-nowrap',
        'disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-8 px-3 text-[13px]' : 'h-9 px-4 text-sm',
        variant === 'primary' && 'bg-accent text-accent-ink hover:bg-accent-strong',
        variant === 'secondary' && 'bg-surface-3 text-ink border border-line-strong hover:border-[#3a4e66] hover:bg-[#213043]',
        variant === 'ghost' && 'text-ink-2 hover:text-ink hover:bg-surface-3',
        variant === 'danger' && 'border border-crit/60 text-crit hover:bg-crit/10',
        className,
      )}
    >
      {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  )
}

// --------------------------------------------------------------------------- //
// Layout primitives
// --------------------------------------------------------------------------- //

export function Card({
  title,
  eyebrow,
  actions,
  children,
  className,
  bodyClassName,
  id,
}: {
  title?: ReactNode
  eyebrow?: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
  bodyClassName?: string
  id?: string
}) {
  return (
    <section id={id} className={clsx('rounded-[10px] border border-line bg-surface', className)} aria-label={typeof title === 'string' ? title : undefined}>
      {(title || actions || eyebrow) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            {eyebrow && <div className="eyebrow mb-0.5">{eyebrow}</div>}
            {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={clsx('p-5', bodyClassName)}>{children}</div>
    </section>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 max-w-[90ch] text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Stat({
  label,
  value,
  sub,
  className,
  testId,
}: {
  label: ReactNode
  value: ReactNode
  sub?: ReactNode
  className?: string
  testId?: string
}) {
  return (
    <div className={clsx('min-w-0', className)} data-testid={testId}>
      <div className="eyebrow">{label}</div>
      <div className="num mt-1 truncate text-xl font-medium text-ink">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-3">{sub}</div>}
    </div>
  )
}

export function KV({ k, v, mono = true }: { k: ReactNode; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line/60 py-1.5 text-[13px] last:border-0">
      <span className="text-ink-3">{k}</span>
      <span className={clsx('min-w-0 break-words text-right text-ink', mono && 'num')}>{v}</span>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Status
// --------------------------------------------------------------------------- //

type Tone = 'good' | 'warn' | 'crit' | 'info' | 'neutral' | 'active'

const TONE: Record<Tone, string> = {
  good: 'bg-good/10 text-good border-good/30',
  warn: 'bg-warn/10 text-warn border-warn/30',
  crit: 'bg-crit/10 text-crit border-crit/30',
  info: 'bg-accent/10 text-accent border-accent/30',
  active: 'bg-accent/10 text-accent border-accent/40',
  neutral: 'bg-surface-3 text-ink-2 border-line-strong',
}

export function Badge({ tone = 'neutral', icon, children, className }: { tone?: Tone; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <span className={clsx('inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap', TONE[tone], className)}>
      {icon}
      {children}
    </span>
  )
}

const STATE_META: Record<string, { tone: Tone; label: string; Icon: typeof CheckCircle2; spin?: boolean }> = {
  created: { tone: 'neutral', label: 'not trained', Icon: CircleDashed },
  queued: { tone: 'neutral', label: 'queued', Icon: Clock },
  starting: { tone: 'active', label: 'starting', Icon: Loader2, spin: true },
  running: { tone: 'active', label: 'training', Icon: PlayCircle },
  stop_requested: { tone: 'warn', label: 'stopping…', Icon: PauseCircle },
  stopped: { tone: 'warn', label: 'stopped', Icon: PauseCircle },
  interrupted: { tone: 'warn', label: 'interrupted', Icon: AlertTriangle },
  completed: { tone: 'good', label: 'completed', Icon: CheckCircle2 },
  failed: { tone: 'crit', label: 'failed', Icon: XCircle },
}

export function StateBadge({ state, labelOverride }: { state: string; labelOverride?: string }) {
  const m = STATE_META[state] ?? { tone: 'neutral' as Tone, label: state, Icon: CircleSlash }
  return (
    <Badge tone={m.tone} icon={<m.Icon className={clsx('size-3.5', m.spin && 'animate-spin')} aria-hidden />}>
      {labelOverride ?? m.label}
    </Badge>
  )
}

export function EvidenceBadge({ evidence }: { evidence: string }) {
  const map: Record<string, Tone> = {
    'technical test only': 'warn',
    'not trained': 'neutral',
    'training incomplete': 'warn',
    'awaiting final test': 'info',
    evaluated: 'good',
  }
  return <Badge tone={map[evidence] ?? 'neutral'}>{evidence}</Badge>
}

const LANDING_LABELS: Record<string, [Tone, string, string]> = {
  on_pad_not_strict: ['info', 'on pad, not strict', 'Came to rest with both legs between the flags, but failed another strict criterion (final angle, or no leg contact seen).'],
  landed_not_within_pad: ['info', 'landed off pad', 'Came to rest cleanly, not wholly between the flags (beside the pad or straddling its edge).'],
  at_rest_after_body_contact: ['warn', 'at rest after body contact', 'The environment reports at rest, but the body touched the ground first: never a pad landing.'],
  at_rest_geometry_unknown: ['neutral', 'at rest, position unknown', 'Leg or pad coordinates were not available: where it landed is not guessed.'],
}

/** Episode outcome. ``category`` (outcome classifier v2) keeps where it landed apart from how well;
 *  without it (older records) a non-strict landing is only "at rest, not strict pad", never "off pad". */
export function OutcomeBadge({ outcome, pad, category }: { outcome: string; pad?: boolean; category?: string }) {
  if (pad) return <Badge tone="good" icon={<CheckCircle2 className="size-3.5" aria-hidden />}>pad landing</Badge>
  const landing = category ? LANDING_LABELS[category] : undefined
  if (landing) {
    return (
      <span title={landing[2]}>
        <Badge tone={landing[0]} icon={<CircleDashed className="size-3.5" aria-hidden />}>{landing[1]}</Badge>
      </span>
    )
  }
  const m: Record<string, [Tone, string]> = {
    at_rest: ['info', 'at rest, not strict pad'],
    crash: ['crit', 'crash'],
    out_of_bounds: ['crit', 'out of bounds'],
    timeout: ['warn', 'time limit'],
    unknown: ['neutral', 'unknown'],
  }
  const [tone, label] = m[outcome] ?? ['neutral', outcome]
  const Icon = tone === 'crit' ? OctagonX : tone === 'warn' ? Clock : CircleDashed
  return <Badge tone={tone} icon={<Icon className="size-3.5" aria-hidden />}>{label}</Badge>
}

export function PolicyBadge({ kind }: { kind: string }) {
  const tone: Tone = kind === 'ppo' || kind === 'dqn' ? 'info' : kind === 'heuristic' ? 'warn' : kind === 'human' ? 'good' : 'neutral'
  return <Badge tone={tone} className="font-mono uppercase tracking-wide">{kind === 'human' ? 'you' : kind}</Badge>
}

// --------------------------------------------------------------------------- //
// Feedback states
// --------------------------------------------------------------------------- //

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-ink-3">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      <span>{label}…</span>
    </div>
  )
}

export function ErrorBanner({ error, onRetry }: { error: string | null | undefined; onRetry?: () => void }) {
  if (!error) return null
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md border border-crit/40 bg-crit/10 px-4 py-3 text-sm text-ink">
      <XCircle className="mt-0.5 size-4 shrink-0 text-crit" aria-hidden />
      <div className="min-w-0 flex-1 whitespace-pre-wrap break-words">{error}</div>
      {onRetry && (
        <Button size="sm" variant="ghost" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}

export function Notice({ tone = 'info', title, children }: { tone?: 'info' | 'warn' | 'good'; title?: ReactNode; children: ReactNode }) {
  const Icon = tone === 'warn' ? AlertTriangle : tone === 'good' ? CheckCircle2 : CircleDashed
  const color = tone === 'warn' ? 'border-warn/35 bg-warn/[0.07]' : tone === 'good' ? 'border-good/35 bg-good/[0.07]' : 'border-accent/30 bg-accent/[0.06]'
  const ic = tone === 'warn' ? 'text-warn' : tone === 'good' ? 'text-good' : 'text-accent'
  return (
    <div className={clsx('flex gap-3 rounded-md border px-4 py-3 text-[13px] text-ink-2', color)}>
      <Icon className={clsx('mt-0.5 size-4 shrink-0', ic)} aria-hidden />
      <div className="min-w-0">
        {title && <div className="mb-0.5 font-medium text-ink">{title}</div>}
        {children}
      </div>
    </div>
  )
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-[10px] border border-dashed border-line-strong px-6 py-10 text-center">
      {icon && <div className="mb-3 text-ink-3">{icon}</div>}
      <div className="font-medium text-ink">{title}</div>
      {children && <div className="mt-1 max-w-[60ch] text-[13px] text-ink-2">{children}</div>}
      {action && <div className="mt-4 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  )
}

export function ProgressBar({ value, label }: { value: number | null | undefined; label: string }) {
  const v = Math.max(0, Math.min(1, value ?? 0))
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v * 100)} className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
      <div className="h-full rounded-full bg-accent transition-[width] duration-500" style={{ width: `${v * 100}%` }} />
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Form controls
// --------------------------------------------------------------------------- //

export function Field({ label, hint, error, children, htmlFor }: { label: ReactNode; hint?: ReactNode; error?: string | null; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="min-w-0">
      <label htmlFor={htmlFor} className="mb-1 block text-[13px] font-medium text-ink-2">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-ink-3">{hint}</p>}
      {error && <p className="mt-1 text-xs text-crit">{error}</p>}
    </div>
  )
}

export function NumberInput({
  value,
  onChange,
  min,
  max,
  step,
  disabled,
  id,
  label,
  invalid,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  id?: string
  label?: string
  invalid?: boolean
}) {
  return (
    <input
      id={id}
      aria-label={label}
      type="number"
      className="field num"
      value={Number.isFinite(value) ? value : ''}
      min={min}
      max={max}
      step={step ?? 'any'}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      onChange={(e) => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value))}
    />
  )
}

export function Toggle({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={clsx(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors disabled:opacity-50',
        checked ? 'border-accent bg-accent/80' : 'border-line-strong bg-surface-3',
      )}
    >
      <span className={clsx('inline-block size-3.5 rounded-full bg-ink transition-transform', checked ? 'translate-x-[18px]' : 'translate-x-[2px]')} />
    </button>
  )
}

export function Segmented<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; disabled?: boolean }[]; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex max-w-full flex-wrap rounded-md border border-line-strong bg-bg p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          disabled={o.disabled}
          onClick={() => onChange(o.value)}
          className={clsx(
            'rounded px-3 py-1 text-[13px] transition-colors disabled:cursor-not-allowed disabled:opacity-40',
            value === o.value ? 'bg-surface-3 text-ink shadow-[inset_0_0_0_1px_var(--color-line-strong)]' : 'text-ink-3 hover:text-ink',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Tabs<T extends string>({ value, onChange, tabs }: { value: T; onChange: (v: T) => void; tabs: { value: T; label: ReactNode }[] }) {
  return (
    <div role="tablist" className="flex gap-1 border-b border-line">
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          type="button"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={clsx(
            '-mb-px border-b-2 px-3 py-2 text-[13px] font-medium transition-colors',
            value === t.value ? 'border-accent text-ink' : 'border-transparent text-ink-3 hover:text-ink',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Dialog
// --------------------------------------------------------------------------- //

export function Dialog({
  open,
  title,
  children,
  onClose,
  actions,
}: {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
  actions?: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onCancel={onClose}
      className="m-auto w-[min(560px,calc(100vw-2rem))] rounded-xl border border-line-strong bg-surface p-0 text-ink backdrop:bg-black/60"
    >
      <div className="border-b border-line px-5 py-4">
        <h2 id={titleId} className="text-base font-semibold">
          {title}
        </h2>
      </div>
      <div className="px-5 py-4 text-sm text-ink-2">{children}</div>
      <div className="flex justify-end gap-2 border-t border-line px-5 py-3">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        {actions}
      </div>
    </dialog>
  )
}

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={clsx('overflow-x-auto', className)}>
      <table className="w-full border-collapse text-[13px] [&_td]:border-b [&_td]:border-line/70 [&_td]:px-3 [&_td]:py-2 [&_th]:border-b [&_th]:border-line [&_th]:px-3 [&_th]:py-2 [:where(&_th)]:text-left [&_th]:text-[11px] [&_th]:font-medium [&_th]:uppercase [&_th]:tracking-wider [&_th]:text-ink-3 [&_tr:last-child_td]:border-0">
        {children}
      </table>
    </div>
  )
}
