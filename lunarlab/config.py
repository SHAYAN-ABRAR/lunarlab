"""Run configuration: PPO settings, budget profiles, evaluation protocol.

Defaults for PPO follow RL Baselines3 Zoo's ``LunarLander-v3`` entry
(hyperparams/ppo.yml: n_steps 1024, batch 64, gae_lambda 0.98, gamma 0.999,
n_epochs 4, ent_coef 0.01, 1e6 steps) with one laptop adaptation:
``n_envs = 4`` instead of 16, so each update uses 4 096 transitions instead of
16 384. These are starting settings, not a promise of solving the task. They
are identical across the primary reward comparisons.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lunarlab.env import ENV_ID, ENV_KWARGS
from lunarlab.hover import DEFAULT_DETECTOR, HoverThresholds
from lunarlab.outcomes import PadLandingCriteria
from lunarlab.rewards.config import RewardConfig

CONFIG_SCHEMA_VERSION = 1

# Seed ranges are disjoint so training, validation and test never share episodes.
VALIDATION_SEEDS = tuple(range(10_000, 10_010))  # 10 fixed validation episodes
TEST_SEEDS = tuple(range(20_000, 20_100))  # 100 fixed final-test episodes
TRAIN_WORKER_SEED_BASE = 1_000_000  # worker seeds: base + 1000*seed + 100*segment + rank


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PPOConfig(_Strict):
    n_envs: int = Field(4, ge=1, le=32)
    n_steps: int = Field(1024, ge=16, le=16384)
    batch_size: int = Field(64, ge=8, le=65536)
    learning_rate: float = Field(3e-4, gt=0.0, le=0.1)
    gamma: float = Field(0.999, gt=0.0, le=1.0)
    gae_lambda: float = Field(0.98, ge=0.0, le=1.0)
    n_epochs: int = Field(4, ge=1, le=50)
    ent_coef: float = Field(0.01, ge=0.0, le=1.0)
    vf_coef: float = Field(0.5, ge=0.0, le=10.0)
    clip_range: float = Field(0.2, gt=0.0, le=1.0)
    max_grad_norm: float = Field(0.5, gt=0.0, le=100.0)
    net_arch_pi: list[int] = Field(default_factory=lambda: [64, 64], min_length=1, max_length=4)
    net_arch_vf: list[int] = Field(default_factory=lambda: [64, 64], min_length=1, max_length=4)
    activation: Literal["tanh", "relu"] = "tanh"

    @property
    def rollout_size(self) -> int:
        return self.n_envs * self.n_steps

    @model_validator(mode="after")
    def _check(self) -> PPOConfig:
        if any(not (4 <= h <= 1024) for h in self.net_arch_pi + self.net_arch_vf):
            raise ValueError("hidden layer sizes must be between 4 and 1024")
        if self.batch_size > self.rollout_size:
            raise ValueError(
                f"batch_size ({self.batch_size}) exceeds the rollout buffer n_envs*n_steps ({self.rollout_size})"
            )
        if self.rollout_size % self.batch_size != 0:
            raise ValueError(
                f"n_envs*n_steps ({self.rollout_size}) must be divisible by batch_size ({self.batch_size}) "
                "so every minibatch is full"
            )
        return self

    def compatibility_key(self) -> dict:
        """Settings that must match for a resume or a fair comparison."""
        return self.model_dump(mode="json")


class DQNConfig(_Strict):
    """DQN settings: RL Baselines3 Zoo's LunarLander-v3 entry (hyperparams/dqn.yml).

    Zoo tunes these for a 1e5-transition budget, and that is the budget the comparison study
    uses: DQN's update-per-4-steps schedule makes it about 20x slower per transition than PPO
    on CPU, so equal-experience runs (1e6) would take hours each. Budgets therefore differ
    between the algorithms; comparisons report it.
    """

    n_envs: int = Field(1, ge=1, le=16)
    learning_rate: float = Field(6.3e-4, gt=0.0, le=0.1)
    batch_size: int = Field(128, ge=8, le=4096)
    buffer_size: int = Field(50_000, ge=1_000, le=2_000_000)
    learning_starts: int = Field(0, ge=0)
    gamma: float = Field(0.99, gt=0.0, le=1.0)
    target_update_interval: int = Field(250, ge=1)
    train_freq: int = Field(4, ge=1, le=1000)
    gradient_steps: int = Field(-1, ge=-1, le=1000)
    exploration_fraction: float = Field(0.12, gt=0.0, le=1.0)
    exploration_final_eps: float = Field(0.1, ge=0.0, le=1.0)
    net_arch: list[int] = Field(default_factory=lambda: [256, 256], min_length=1, max_length=4)

    @property
    def rollout_size(self) -> int:
        return self.train_freq * self.n_envs

    def compatibility_key(self) -> dict:
        return self.model_dump(mode="json")


ProfileName = Literal["smoke", "standard", "extended", "custom"]


class TrainingConfig(_Strict):
    profile: ProfileName = "smoke"
    total_transitions: int = Field(8192, ge=256, le=50_000_000)
    checkpoint_every: int = Field(4096, ge=256)
    validation_every: int = Field(4096, ge=256)
    vec_env: Literal["dummy", "subproc"] = "dummy"
    device: Literal["cpu", "cuda", "auto"] = "cpu"
    torch_threads: int = Field(1, ge=1, le=64)


class PhysicsRandomization(_Strict):
    """Per-episode variation of wind, turbulence and gravity while TRAINING (off by default).

    Before every training episode, the physics are drawn from these ranges by a generator seeded
    from that worker's episode seed, so a run is reproducible. An episode has wind with probability
    ``wind_probability``; wind and turbulence strengths are then uniform in their ranges (both are 0
    without wind). Gravity is uniform in its range for every episode. Validation (checkpoint
    selection) and the final test always use default physics, for every run.
    """

    enabled: bool = False
    wind_probability: float = Field(0.8, ge=0.0, le=1.0)
    wind_power: tuple[float, float] = (0.0, 10.0)
    turbulence_power: tuple[float, float] = (0.0, 1.0)
    gravity: tuple[float, float] = (-11.0, -9.0)

    @model_validator(mode="after")
    def _ranges(self) -> PhysicsRandomization:
        bounds = {"wind_power": (0.0, 20.0), "turbulence_power": (0.0, 2.0)}
        for name, (lo_ok, hi_ok) in bounds.items():
            lo, hi = getattr(self, name)
            if not lo_ok <= lo <= hi <= hi_ok:
                raise ValueError(f"{name} range must satisfy {lo_ok} <= low <= high <= {hi_ok}")
        lo, hi = self.gravity
        if not -12.0 < lo <= hi < 0.0:
            raise ValueError("gravity range must satisfy -12 < low <= high < 0 (Gymnasium's limits)")
        return self

    def describe(self) -> str:
        if not self.enabled:
            return "fixed (default physics)"
        w, t, g = self.wind_power, self.turbulence_power, self.gravity
        return (
            f"randomized: wind on {self.wind_probability:.0%} of episodes, power {w[0]:g}–{w[1]:g}, "
            f"turbulence {t[0]:g}–{t[1]:g}; gravity {g[0]:g} to {g[1]:g}"
        )


PROFILES: dict[str, dict] = {
    "smoke": {
        "total_transitions": 8_192,
        "checkpoint_every": 4_096,
        "validation_every": 4_096,
        "label": "SMOKE — technical pipeline test (~8k transitions). Not a trained agent.",
    },
    "standard": {
        "total_transitions": 1_000_000,
        "checkpoint_every": 100_000,
        "validation_every": 50_000,
        "label": "STANDARD — ~1M transitions per training run.",
    },
    "extended": {
        "total_transitions": 3_000_000,
        "checkpoint_every": 250_000,
        "validation_every": 100_000,
        "label": "EXTENDED — larger budget; explicit launch only.",
    },
}


def training_for_profile(
    profile: str, *, total_transitions: int | None = None, **overrides
) -> TrainingConfig:
    """Build a TrainingConfig from a named profile. A changed budget is labelled ``custom``."""
    if profile not in PROFILES:
        raise KeyError(f"unknown profile {profile!r}; choose from {', '.join(PROFILES)}")
    base = {k: v for k, v in PROFILES[profile].items() if k != "label"}
    base["profile"] = profile
    if total_transitions is not None and total_transitions != base["total_transitions"]:
        base["total_transitions"] = total_transitions
        base["profile"] = "custom"
    base.update({k: v for k, v in overrides.items() if v is not None})
    return TrainingConfig(**base)


def actual_budget(requested: int, rollout_size: int) -> int:
    """PPO always completes whole rollouts, so it rounds the budget up."""
    return int(math.ceil(requested / rollout_size) * rollout_size)


class EvalProtocol(_Strict):
    """Everything that defines how a policy is measured. Persisted with every evaluation."""

    protocol_id: str = "lunarlab-eval-v1"
    env_id: str = ENV_ID
    env_kwargs: dict = Field(default_factory=lambda: dict(ENV_KWARGS))
    validation_seeds: list[int] = Field(
        default_factory=lambda: list(VALIDATION_SEEDS), min_length=1, max_length=1000
    )
    test_seeds: list[int] = Field(default_factory=lambda: list(TEST_SEEDS), min_length=1, max_length=5000)
    deterministic: bool = True
    score_threshold: float = 200.0
    hover_detector: HoverThresholds = Field(default_factory=lambda: DEFAULT_DETECTOR.model_copy())
    sustained_hover_min_steps: int = Field(100, ge=1, le=1000)
    pad_landing: PadLandingCriteria = Field(default_factory=PadLandingCriteria)
    ci_level: float = Field(0.95, gt=0.5, lt=1.0)
    bootstrap_resamples: int = Field(5000, ge=200, le=100_000)
    bootstrap_seed: int = 0

    def protocol_hash(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def seeds_for(self, split: str) -> list[int]:
        if split == "validation":
            return list(self.validation_seeds)
        if split == "test":
            return list(self.test_seeds)
        raise ValueError("split must be 'validation' or 'test'")


class RunConfig(_Strict):
    schema_version: Literal[1] = CONFIG_SCHEMA_VERSION
    run_id: str
    experiment_id: str | None = None
    label: str = Field("", max_length=120)
    created_at: str
    env_id: str = ENV_ID
    env_kwargs: dict = Field(default_factory=lambda: dict(ENV_KWARGS))
    reward: RewardConfig
    reward_config_id: str | None = None
    reward_revision: int | None = None
    ppo: PPOConfig = Field(default_factory=PPOConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    seed: int = Field(0, ge=0, le=999)
    eval_protocol: EvalProtocol = Field(default_factory=EvalProtocol)
    algo: Literal["ppo", "dqn"] = "ppo"
    dqn: DQNConfig | None = None
    physics: PhysicsRandomization = Field(default_factory=PhysicsRandomization)

    @model_validator(mode="after")
    def _env_fixed(self) -> RunConfig:
        if self.env_id != ENV_ID or self.env_kwargs != ENV_KWARGS:
            raise ValueError(f"LunarLab experiments use {ENV_ID} with {ENV_KWARGS} only (default physics)")
        if self.algo == "dqn" and self.dqn is None:
            self.dqn = DQNConfig()
        if self.algo == "ppo" and self.dqn is not None:
            raise ValueError("dqn settings given for a PPO run")
        return self

    def config_hash(self) -> str:
        """Hash of everything that defines the experiment (excluding identity and labels)."""
        d = self.model_dump(mode="json")
        for k in ("run_id", "experiment_id", "label", "created_at", "reward_config_id", "reward_revision"):
            d.pop(k, None)
        if self.algo == "ppo":  # added after the first release: PPO runs hash exactly as before
            d.pop("algo", None)
            d.pop("dqn", None)
        else:
            d.pop("ppo", None)  # unused by DQN runs
        if not self.physics.enabled:  # added later too: fixed-physics runs hash exactly as before
            d.pop("physics", None)
        d["reward"] = self.reward.reward_payload()
        canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    # Algorithm-neutral accessors -------------------------------------------------
    @property
    def gamma(self) -> float:
        return self.dqn.gamma if self.algo == "dqn" and self.dqn else self.ppo.gamma

    @property
    def n_envs(self) -> int:
        return self.dqn.n_envs if self.algo == "dqn" and self.dqn else self.ppo.n_envs

    @property
    def rollout_size(self) -> int:
        return self.dqn.rollout_size if self.algo == "dqn" and self.dqn else self.ppo.rollout_size

    def algo_settings(self) -> dict:
        return (
            self.dqn.compatibility_key() if self.algo == "dqn" and self.dqn else self.ppo.compatibility_key()
        )

    def worker_seeds(self, segment: int = 0) -> list[int]:
        base = TRAIN_WORKER_SEED_BASE + 1000 * self.seed + 100 * segment
        return [base + i for i in range(self.n_envs)]

    @property
    def requested_transitions(self) -> int:
        return self.training.total_transitions

    @property
    def planned_transitions(self) -> int:
        return actual_budget(self.training.total_transitions, self.rollout_size)


def resume_compatibility(saved: RunConfig, requested: RunConfig) -> list[str]:
    """Reasons a checkpoint of ``saved`` cannot continue as ``requested`` (empty = compatible)."""
    problems: list[str] = []
    if saved.env_id != requested.env_id or saved.env_kwargs != requested.env_kwargs:
        problems.append("environment differs")
    if saved.reward.content_hash() != requested.reward.content_hash():
        problems.append(
            "reward function differs — changing the reward is a new experiment, not a continuation"
        )
    if saved.algo != requested.algo:
        problems.append(f"algorithm differs ({saved.algo} vs {requested.algo})")
    elif saved.algo_settings() != requested.algo_settings():
        diffs = [k for k, v in saved.algo_settings().items() if requested.algo_settings().get(k) != v]
        problems.append(f"{saved.algo.upper()} settings differ ({', '.join(diffs)})")
    if saved.physics != requested.physics:
        problems.append("training physics differ (randomization is part of the experiment)")
    if saved.seed != requested.seed:
        problems.append("training seed differs")
    if saved.eval_protocol.protocol_hash() != requested.eval_protocol.protocol_hash():
        problems.append("evaluation protocol differs")
    return problems
