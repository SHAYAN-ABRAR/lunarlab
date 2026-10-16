// Shapes returned by the LunarLab API (lunarlab/server/api.py). Kept deliberately loose
// where the backend passes through stored JSON.

export type JobState =
  | 'queued' | 'starting' | 'running' | 'stop_requested'
  | 'stopped' | 'completed' | 'failed' | 'interrupted'

export type RunState = 'created' | 'running' | 'stopped' | 'completed' | 'failed' | 'interrupted'

export type Preset = 'baseline' | 'time-penalty' | 'hover-bonus' | 'potential' | 'custom'

export interface EvalSummary {
  file?: string
  split?: 'validation' | 'test'
  created_at?: string
  checkpoint?: string
  checkpoint_transitions?: number
  repeat_index?: number
  n_episodes: number
  mean_original_return: number
  std_original_return: number
  median_original_return: number
  ci: [number, number] | null
  pad_landing_rate: number
  env_success_rate: number
  score_rate: number
  crash_rate: number
  out_of_bounds_rate: number
  timeout_rate: number
  hover_fraction_mean: number
  sustained_hover_rate: number
  mean_length: number
  main_engine_fraction: number
  training_return_rescored_mean: number
}

export interface CheckpointEntry {
  name: string
  kind: 'periodic' | 'final' | 'stop' | 'best_validation'
  transitions: number
  updates: number
  segment: number
  created_at: string
  sha256: string
  size_bytes: number
  validation_mean_original_return?: number
  validation_pad_landing_rate?: number
}

export interface RunSummary {
  run_id: string
  experiment_id: string | null
  label: string
  created_at: string
  reward_name: string
  reward_preset: Preset
  reward_hash: string
  reward_revision: number | null
  active_terms: string[]
  seed: number
  profile: 'smoke' | 'standard' | 'extended' | 'custom'
  requested_transitions: number
  planned_transitions: number
  checkpoint_transitions: number
  state: RunState
  completed: boolean
  evidence: string
  best_validation: CheckpointEntry | null
  latest_validation: EvalSummary | null
  latest_test: EvalSummary | null
  frozen_for_test: { checkpoint: string; frozen_at: string } | null
  protocol_hash: string
  algo?: 'ppo' | 'dqn'
  gamma?: number
  variant?: string
  physics_label?: string
  validation_history?: ValidationPoint[]
}

export interface ValidationPoint extends EvalSummary {
  time: string
  segment: number
  transitions: number
  is_best: boolean
}

export interface Job {
  id: string
  kind: 'train' | 'resume' | 'evaluate' | 'record' | 'record_demo' | 'report' | 'benchmark' | 'reward_ensemble' | 'tune'
  lane: string
  run_id: string | null
  params: Record<string, unknown> | null
  state: JobState
  created_at: string
  started_at: string | null
  finished_at: string | null
  heartbeat_at: string | null
  pid: number | null
  exit_code: number | null
  error: string | null
  progress: Record<string, unknown> | null
  result: Record<string, unknown> | null
}

export interface RunStatus {
  state?: string
  phase?: string
  transitions?: number
  target_transitions?: number
  requested_transitions?: number
  progress?: number
  elapsed_s?: number
  throughput_tps?: number | null
  episodes?: number
  updated_at?: string
  started_at?: string
  pid?: number
  segment?: number
  best_validation_mean_original_return?: number | null
  recent_original_return_mean?: number | null
  recent_training_return_mean?: number | null
  recent_pad_landing_rate?: number | null
  recent_timeout_rate?: number | null
  recent_mean_length?: number | null
  recent_window?: number
  process?: { cpu_percent: number; rss_mb: number }
  error?: string | null
}

export interface CurvePoint {
  episode: number
  transitions: number
  elapsed_s?: number | null
  original_return: number
  training_return: number
  length: number
  pad_landing_rate: number
  timeout_rate: number
  hover_fraction: number
}

export interface MetricRow {
  update: number
  transitions: number
  approx_kl?: number
  clip_fraction?: number
  entropy_loss?: number
  policy_gradient_loss?: number
  value_loss?: number
  explained_variance?: number
  learning_rate?: number
  throughput_tps?: number | null
  original_return_mean?: number
  training_return_mean?: number
}

export interface RecordingMeta {
  recording_id: string
  created_at: string
  run_id: string | null
  source: Record<string, unknown> & { type: string; kind?: string; run_id?: string; reward_name?: string; training_seed?: number; checkpoint?: string; profile?: string }
  policy: { kind: 'random' | 'heuristic' | 'ppo' | 'dqn' | 'human'; label: string }
  episode_seed: number
  seed_split: 'validation' | 'test' | 'other'
  n_frames: number
  fps: number
  video: { format: 'mp4-h264' | 'jpeg-frames'; file: string; verified: boolean; frames: number; bytes: number }
  original_return: number
  training_return: number
  env_outcome: string
  pad_landing: boolean
  length: number
  hover_fraction: number
  reward_preset: Preset | null
}

export interface PolicyInfo {
  probs?: number[]
  entropy?: number
  value?: number
  q?: number[]
}

export interface TelemetryRow {
  t: number
  action: number | null
  policy?: PolicyInfo
  obs: number[]
  original_reward: number
  terms: Record<string, number>
  training_reward: number
  cum_original: number
  cum_training: number
  builtin: Record<string, number> | null
  hover: boolean
  terminated: boolean
  truncated: boolean
}

export interface Telemetry extends Omit<RecordingMeta, 'original_return' | 'training_return' | 'env_outcome' | 'pad_landing' | 'length' | 'hover_fraction' | 'run_id'> {
  indexing: string
  pad: { x1_obs: number; x2_obs: number }
  reward_config: RewardConfig | null
  terms_note: string
  gamma: number
  policy_diagnostics?: { fields: Record<string, string>; indexing: string }
  episode: Record<string, unknown> & {
    original_return: number
    training_return: number
    length: number
    env_outcome: string
    pad_landing: boolean
    hover_fraction: number
    longest_hover_streak: number
    body_contact: boolean
    legs_within_pad: boolean
    terminated: boolean
    truncated: boolean
    actions: Record<string, number>
  }
  rows: TelemetryRow[]
}

export interface HoverThresholds {
  min_height: number
  max_height: number
  max_abs_angle_rad: number
  max_abs_vx: number
  max_abs_vy: number
  max_abs_angular_velocity: number | null
}

export interface RewardConfig {
  schema_version: 1
  name: string
  preset: Preset
  description: string
  time_penalty: { enabled: boolean; cost_per_step: number }
  hover_bonus: { enabled: boolean; bonus_per_step: number; eligibility: HoverThresholds }
  potential: {
    enabled: boolean
    alpha: number
    weights: { x: number; y: number; speed: number; angle: number; angular_velocity: number }
  }
}

export interface RewardConfigRow {
  id: string
  family: string
  revision: number
  parent_id: string | null
  name: string
  preset: Preset
  builtin: boolean
  content_hash: string
  created_at: string
  config: RewardConfig
  warnings: string[]
  active_terms: string[]
}

export interface Meta {
  observation_fields: { index: number; key: string; label: string; units: string; description: string }[]
  actions: { index: number; key: string; label: string }[]
  presets: (RewardConfig & { hash: string })[]
  profiles: Record<string, { total_transitions: number; checkpoint_every: number; validation_every: number; label: string }>
  ppo_defaults: Record<string, number | number[] | string>
  rollout_size: number
  eval_protocol: Record<string, unknown> & { validation_seeds: number[]; test_seeds: number[]; hash: string; hover_detector: HoverThresholds; sustained_hover_min_steps: number; pad_landing: { max_final_abs_angle_rad: number } }
}

export interface SystemInfo {
  cpu_percent: number
  cpu_count: number
  ram: { used_gb: number; total_gb: number; percent: number }
  disk: { free_gb: number; total_gb: number; percent: number }
  jobs: Record<string, number>
  queue_paused: boolean
  readiness: Record<string, { ok: boolean; detail: string } | boolean>
  environment: Record<string, unknown>
  benchmark: { rows: { vec_env: string; n_envs: number; env_tps: number; ppo_tps?: number }[]; default_config: { ppo_tps?: number } | null; created_at: string } | null
}

export interface Experiment {
  experiment_id: string
  name: string
  description: string
  created_at: string
  profile: string
  seeds: number[]
  rewards: { name: string; preset: Preset; hash: string }[]
  run_ids: string[]
}

// --------------------------------------------------------------------------- //
// Keyboard flights
// --------------------------------------------------------------------------- //

export interface FlightEpisode {
  original_return: number
  env_outcome: string
  pad_landing: boolean
  length: number
  actions: Record<string, number>
}

export interface GhostFlight {
  opponent: string
  label: string
  source: { type: 'heuristic' } | { type: 'run'; run_id: string; checkpoint: string; checkpoint_transitions: number; reward_name: string; algo: string; training_seed: number }
  rows: { obs: number[]; action: number | null }[]
  episode: FlightEpisode
}

export interface FlightStepResult {
  rows: TelemetryRow[]
  done: boolean
  recording?: RecordingMeta
  episode?: FlightEpisode
}

