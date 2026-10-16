import { Clapperboard, Play, Rocket } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router'
import { api, idempotencyKey } from '../lib/api'
import { fmt } from '../lib/format'
import { useApi } from '../lib/hooks'
import { PRESET_COLOR, PRESET_LABEL } from '../lib/reward'
import type { Job, Meta, Preset, RewardConfigRow, RunSummary, SystemInfo } from '../lib/types'
import { useJobWatch } from './Jobs'
import { DEFAULT_PHYSICS, PhysicsFields, type PhysicsRanges, physicsError, physicsPayload } from './Physics'
import { Button, Dialog, ErrorBanner, Field, Notice, NumberInput, Segmented } from './ui'

type Profile = 'smoke' | 'standard' | 'extended'

const PROFILE_TEXT: Record<Profile, string> = {
  smoke: 'Technical pipeline test, ~8k transitions (about 15 s). Verifies training, checkpoints and evaluation. Not a trained agent.',
  standard: '~1M transitions per run (rounded up to whole 4,096-transition rollouts). Several minutes on a recent laptop CPU.',
  extended: '~3M transitions. Long; available only with explicit confirmation.',
}

function roundUp(n: number, k: number) {
  return Math.ceil(n / k) * k
}

export function ProfileInfo({ profile, meta, sys }: { profile: Profile; meta?: Meta; sys?: SystemInfo }) {
  const total = meta?.profiles[profile]?.total_transitions
  const planned = total && meta ? roundUp(total, meta.rollout_size) : undefined
  const tps = sys?.benchmark?.default_config?.ppo_tps
  return (
    <div className="mt-2 space-y-1 text-xs text-ink-3">
      <p>{PROFILE_TEXT[profile]}</p>
      {planned !== undefined && (
        <p className="num">
          budget {fmt.int(total)} requested → {fmt.int(planned)} actual transitions
          {tps ? ` · ≈ ${fmt.duration(planned / tps)} at the measured ${fmt.int(tps)} transitions/s (plus validation)` : ' · run the throughput benchmark for a time estimate'}
        </p>
      )}
    </div>
  )
}

/** Inline training launcher: reward source, profile, seed, advanced options. */
export function LaunchForm({ initialPreset = 'baseline', initialConfigId, compact = false }: { initialPreset?: Preset; initialConfigId?: string; compact?: boolean }) {
  const navigate = useNavigate()
  const meta = useApi<Meta>('/api/meta')
  const sys = useApi<SystemInfo>('/api/system')
  const configs = useApi<RewardConfigRow[]>('/api/reward-configs')
  const [source, setSource] = useState<string>(initialConfigId ? `config:${initialConfigId}` : `preset:${initialPreset}`)
  const [profile, setProfile] = useState<Profile>('smoke')
  const [seed, setSeed] = useState(0)
  const [advanced, setAdvanced] = useState(false)
  const [nEnvs, setNEnvs] = useState(4)
  const [vecEnv, setVecEnv] = useState<'dummy' | 'subproc'>('dummy')
  const [algo, setAlgo] = useState<'ppo' | 'dqn'>('ppo')
  const [gammaText, setGammaText] = useState('')
  const [physicsMode, setPhysicsMode] = useState<'fixed' | 'randomized'>('fixed')
  const [physics, setPhysics] = useState<PhysicsRanges>(DEFAULT_PHYSICS)
  const [confirmExtended, setConfirmExtended] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [key] = useState(idempotencyKey)

  const custom = useMemo(() => (configs.data ?? []).filter((c) => !c.builtin), [configs.data])
  const seedInvalid = !Number.isInteger(seed) || seed < 0 || seed > 999
  const gamma = gammaText.trim() === '' ? null : Number(gammaText)
  const gammaInvalid = gamma !== null && !(gamma > 0.9 && gamma < 1)
  const physicsInvalid = physicsMode === 'randomized' && physicsError(physics) !== null

  const submit = async (confirmed = false) => {
    if (profile === 'extended' && !confirmed) {
      setConfirmExtended(true)
      return
    }
    setPending(true)
    setError(null)
    try {
      const body: Record<string, unknown> = { profile, seed, start: true, idempotency_key: key, confirm_extended: confirmed }
      if (source.startsWith('preset:')) body.preset = source.slice(7)
      else body.reward_config_id = source.slice(7)
      if (advanced) {
        body.n_envs = nEnvs
        body.vec_env = vecEnv
        body.algo = algo
        if (gamma !== null) body.gamma = gamma
      }
      if (physicsMode === 'randomized') body.physics = physicsPayload(physics)
      const res = await api.post<{ run: RunSummary; job: Job }>('/api/runs', body)
      navigate(`/runs/${res.run.run_id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setPending(false)
      setConfirmExtended(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className={compact ? 'grid gap-4' : 'grid gap-4 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_120px]'}>
        <Field label="Reward configuration" htmlFor="launch-reward">
          <select id="launch-reward" className="field" value={source} onChange={(e) => setSource(e.target.value)}>
            <optgroup label="Presets">
              {(['baseline', 'time-penalty', 'hover-bonus', 'potential'] as Preset[]).map((p) => (
                <option key={p} value={`preset:${p}`}>
                  {PRESET_LABEL[p]}
                </option>
              ))}
            </optgroup>
            {custom.length > 0 && (
              <optgroup label="Saved revisions (Reward Studio)">
                {custom.map((c) => (
                  <option key={c.id} value={`config:${c.id}`}>
                    {c.name} · rev {c.revision}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </Field>
        <Field label="Budget profile">
          <Segmented<Profile>
            label="Budget profile"
            value={profile}
            onChange={setProfile}
            options={[
              { value: 'smoke', label: 'Smoke' },
              { value: 'standard', label: 'Standard' },
              { value: 'extended', label: 'Extended' },
            ]}
          />
        </Field>
        <Field label="Training seed" htmlFor="launch-seed" error={seedInvalid ? '0–999' : null}>
          <NumberInput id="launch-seed" value={seed} onChange={setSeed} min={0} max={999} step={1} invalid={seedInvalid} />
        </Field>
      </div>
      <ProfileInfo profile={profile} meta={meta.data} sys={sys.data} />
      <Field label="Training physics">
        <Segmented
          label="Training physics"
          value={physicsMode}
          onChange={setPhysicsMode}
          options={[
            { value: 'fixed', label: 'Fixed (default)' },
            { value: 'randomized', label: 'Randomized wind & gravity' },
          ]}
        />
      </Field>
      {physicsMode === 'randomized' && <PhysicsFields value={physics} onChange={setPhysics} idPrefix="launch-physics" />}
      <details open={advanced} onToggle={(e) => setAdvanced((e.target as HTMLDetailsElement).open)} className="rounded-md border border-line px-3 py-2">
        <summary className="cursor-pointer text-[13px] text-ink-2">Advanced: algorithm, discount, vectorization</summary>
        <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Algorithm" hint="DQN uses RL Baselines3 Zoo's LunarLander settings.">
            <Segmented
              label="Algorithm"
              value={algo}
              onChange={setAlgo}
              options={[
                { value: 'ppo', label: 'PPO' },
                { value: 'dqn', label: 'DQN' },
              ]}
            />
          </Field>
          <Field label="Discount factor γ" htmlFor="launch-gamma" hint={`Empty: the algorithm's reference value (${algo === 'ppo' ? '0.999' : '0.99'}).`} error={gammaInvalid ? 'Between 0.9 and 1 (exclusive).' : null}>
            <input id="launch-gamma" className="field num" inputMode="decimal" placeholder={algo === 'ppo' ? '0.999' : '0.99'} value={gammaText} onChange={(e) => setGammaText(e.target.value)} aria-invalid={gammaInvalid || undefined} />
          </Field>
          <Field label="Parallel environments (n_envs)" htmlFor="launch-nenvs" hint="Changes the rollout size (n_envs × 1024). Keep 4 for comparable experiments.">
            <NumberInput id="launch-nenvs" value={nEnvs} onChange={setNEnvs} min={1} max={16} step={1} />
          </Field>
          <Field label="Vector environment" hint="Subprocess workers use Windows-safe spawn; benchmark first — they are often slower for this small env.">
            <Segmented
              label="Vector environment"
              value={vecEnv}
              onChange={setVecEnv}
              options={[
                { value: 'dummy', label: 'In-process' },
                { value: 'subproc', label: 'Subprocess' },
              ]}
            />
          </Field>
        </div>
      </details>
      <ErrorBanner error={error} />
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" icon={<Play className="size-4" />} pending={pending} disabled={seedInvalid || gammaInvalid || physicsInvalid} onClick={() => submit()}>
          Start training run
        </Button>
        <span className="text-xs text-ink-3">Runs in a separate worker process; one training job at a time, others queue.</span>
      </div>
      <Dialog
        open={confirmExtended}
        title="Start an EXTENDED run?"
        onClose={() => setConfirmExtended(false)}
        actions={
          <Button variant="primary" pending={pending} onClick={() => submit(true)}>
            Start extended run
          </Button>
        }
      >
        <p>
          Extended runs train for about 3 million transitions and can take hours on a laptop CPU. The laptop must stay awake;
          training pauses during sleep. You can stop at any time and resume from the last checkpoint.
        </p>
      </Dialog>
    </div>
  )
}

/** Quick "Train baseline" action: preset fixed, choose profile and seed in a dialog. */
export function TrainPresetButton({ preset, label, variant = 'secondary' }: { preset: Preset; label: string; variant?: 'primary' | 'secondary' }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant={variant} icon={<Rocket className="size-4" />} onClick={() => setOpen(true)}>
        {label}
      </Button>
      {open && (
        <Dialog open={open} title={`Train · ${PRESET_LABEL[preset]}`} onClose={() => setOpen(false)}>
          <div className="mb-3 flex items-center gap-2 text-xs text-ink-3">
            <span className="inline-block size-2.5 rounded-full" style={{ background: PRESET_COLOR[preset] }} />
            Reward: {PRESET_LABEL[preset]}
          </div>
          <LaunchForm initialPreset={preset} compact />
        </Dialog>
      )}
    </>
  )
}

/** Record a RANDOM or HEURISTIC demonstration and open it in Flight Replay. */
export function DemoButton({ policy = 'random', label, seed = 20_000, variant = 'primary' }: { policy?: 'random' | 'heuristic'; label: string; seed?: number; variant?: 'primary' | 'secondary' }) {
  const navigate = useNavigate()
  const [jobId, setJobId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const job = useJobWatch(jobId, (j) => {
    setJobId(null)
    const rid = (j.result as { recording_id?: string } | null)?.recording_id
    if (j.state === 'completed' && rid) navigate(`/replay/${rid}`)
    else setError(j.error ?? `Recording ${j.state}`)
  })
  const start = async () => {
    setError(null)
    try {
      const j = await api.post<Job>('/api/demos', { policy, episode_seed: seed, action_seed: Math.floor(Math.random() * 1_000_000), idempotency_key: idempotencyKey() })
      setJobId(j.id)
    } catch (e) {
      setError((e as Error).message)
    }
  }
  const busy = !!jobId
  return (
    <div className="inline-flex flex-col gap-1">
      <Button variant={variant} icon={<Clapperboard className="size-4" />} pending={busy} onClick={start}>
        {busy ? (job?.state === 'queued' ? 'Queued…' : 'Recording…') : label}
      </Button>
      {error && <span className="max-w-xs text-xs text-crit">{error}</span>}
    </div>
  )
}

export function ComparabilityNote() {
  return (
    <Notice tone="info" title="Same physics, same evaluation">
      Every run uses LunarLander-v3 with default physics and identical PPO settings. All policies are evaluated on the original
      reward with the same fixed episode seeds.
    </Notice>
  )
}
