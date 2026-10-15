"""Reward configuration schema and the four named presets.

A reward configuration is pure data validated by a fixed schema. There is no
expression language and nothing from the editor is ever evaluated as code.

    training_reward = original_weight * original_reward + sum(enabled additional terms)

``original_weight`` is 1 for every preset: the original environment reward is
included unchanged. Only the learned-reward (RLHF) experiments set it to 0, so
the agent optimises a reward model and never sees the environment's reward.
The additional terms are:

* ``time_penalty``      -cost on every transition
* ``hover_bonus``       +bonus when the *resulting* state satisfies the eligibility predicate
* ``potential_shaping`` alpha * (gamma * Phi(s') - Phi(s)), with Phi(terminal) = 0
* ``learned_reward``    scale * r_model(s, a, s') from a reward model trained on preferences

``gamma`` for potential shaping is *not* part of the reward config: it is
always the PPO discount of the run that uses the config, so the two cannot
drift apart.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lunarlab.hover import DEFAULT_BONUS_ELIGIBILITY, HoverThresholds

TERM_KEYS: tuple[str, ...] = ("time_penalty", "hover_bonus", "potential_shaping", "learned_reward")
PresetName = Literal["baseline", "time-penalty", "hover-bonus", "potential", "custom"]
PRESET_NAMES: tuple[str, ...] = ("baseline", "time-penalty", "hover-bonus", "potential")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TimePenaltyConfig(_Strict):
    enabled: bool = False
    cost_per_step: float = Field(0.01, ge=0.0, le=1.0, description="Subtracted on every transition.")


class HoverBonusConfig(_Strict):
    enabled: bool = False
    bonus_per_step: float = Field(
        1.0, ge=0.0, le=10.0, description="Added when the resulting state is eligible."
    )
    eligibility: HoverThresholds = Field(default_factory=lambda: DEFAULT_BONUS_ELIGIBILITY.model_copy())


class PotentialWeights(_Strict):
    x: float = Field(1.0, ge=0.0, le=10.0, description="Weight on tanh(|x|).")
    y: float = Field(0.5, ge=0.0, le=10.0, description="Weight on tanh(|y|).")
    speed: float = Field(1.0, ge=0.0, le=10.0, description="Weight on tanh(hypot(vx, vy)).")
    angle: float = Field(0.5, ge=0.0, le=10.0, description="Weight on tanh(|angle|).")
    angular_velocity: float = Field(0.25, ge=0.0, le=10.0, description="Weight on tanh(|angular velocity|).")


class PotentialConfig(_Strict):
    enabled: bool = False
    alpha: float = Field(10.0, ge=0.0, le=100.0, description="Scale of the shaping term.")
    weights: PotentialWeights = Field(default_factory=PotentialWeights)


class LearnedRewardConfig(_Strict):
    enabled: bool = False
    model_id: str | None = Field(None, max_length=96, pattern=r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")
    scale: float = Field(1.0, gt=0.0, le=100.0, description="Multiplies the normalised model output.")


class RewardConfig(_Strict):
    schema_version: Literal[1] = 1
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.\-]*$")
    preset: PresetName = "custom"
    description: str = Field("", max_length=2000)
    time_penalty: TimePenaltyConfig = Field(default_factory=TimePenaltyConfig)
    hover_bonus: HoverBonusConfig = Field(default_factory=HoverBonusConfig)
    potential: PotentialConfig = Field(default_factory=PotentialConfig)
    original_weight: float = Field(
        1.0, ge=0.0, le=1.0, description="Weight of the original environment reward."
    )
    learned: LearnedRewardConfig = Field(default_factory=LearnedRewardConfig)

    @model_validator(mode="after")
    def _learned_needs_model(self) -> RewardConfig:
        if self.learned.enabled and not self.learned.model_id:
            raise ValueError("learned reward enabled without a model_id")
        return self

    def active_terms(self) -> list[str]:
        out = []
        if self.time_penalty.enabled:
            out.append("time_penalty")
        if self.hover_bonus.enabled:
            out.append("hover_bonus")
        if self.potential.enabled:
            out.append("potential_shaping")
        if self.learned.enabled:
            out.append("learned_reward")
        return out

    def reward_payload(self) -> dict:
        """Only the fields that change the reward function (not name/description).

        Fields added after the first release are included only when they differ from their
        defaults, so every earlier configuration keeps exactly the same content hash.
        """
        d = self.model_dump(mode="json")
        out = {k: d[k] for k in ("schema_version", "time_penalty", "hover_bonus", "potential")}
        if self.original_weight != 1.0:
            out["original_weight"] = self.original_weight
        if self.learned.enabled:
            out["learned"] = d["learned"]
        return out

    def content_hash(self) -> str:
        """Hash of the reward function itself. Two configs with equal hashes are the same reward."""
        canonical = json.dumps(self.reward_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def is_original(self) -> bool:
        return not self.active_terms() and self.original_weight == 1.0

    def warnings(self) -> list[str]:
        """Design warnings shown in the Reward Studio (not validation errors)."""
        w: list[str] = []
        terms = self.active_terms()
        if self.potential.enabled and len(terms) > 1:
            w.append(
                "Potential-based shaping is combined with other terms. The policy-invariance argument "
                "covers only the potential term; the other terms change the optimal policy."
            )
        if (
            self.potential.enabled
            and self.potential.alpha > 0
            and sum(self.potential.weights.model_dump().values()) == 0
        ):
            w.append("Potential shaping is enabled but every weight is zero, so it adds nothing.")
        if self.hover_bonus.enabled and self.hover_bonus.bonus_per_step >= 0.3:
            w.append(
                "A per-step bonus for an intermediate state competes with finishing the task: an episode "
                "that keeps collecting the bonus may be worth more than one that lands and ends."
            )
        if self.time_penalty.enabled and self.time_penalty.cost_per_step >= 0.1:
            w.append(
                "A large per-step cost can make ending the episode early (including crashing) more "
                "attractive than a careful landing."
            )
        if self.potential.enabled and self.potential.alpha >= 50:
            w.append("Large alpha: the shaping term may dominate the original reward early in training.")
        if self.original_weight == 0 and not self.active_terms():
            w.append(
                "The original reward has weight 0 and no other term is enabled: there is nothing to learn from."
            )
        if self.original_weight == 0 and self.learned.enabled:
            w.append(
                "The agent never sees the environment reward and optimises the learned reward model only "
                "(the RLHF setting). Where the model is wrong, the agent may exploit it."
            )
        return w


def preset(name: str) -> RewardConfig:
    """Return a fresh copy of a named preset."""
    if name == "baseline":
        return RewardConfig(
            name="Original baseline",
            preset="baseline",
            description="training_reward = original_reward. No additional terms.",
        )
    if name == "time-penalty":
        return RewardConfig(
            name="Time-penalty ablation",
            preset="time-penalty",
            description=(
                "training_reward = original_reward - time_cost. An ablation, not a guaranteed improvement: "
                "a per-step cost changes the objective and can favour ending episodes early."
            ),
            time_penalty=TimePenaltyConfig(enabled=True, cost_per_step=0.01),
        )
    if name == "hover-bonus":
        return RewardConfig(
            name="Flawed hover bonus",
            preset="hover-bonus",
            description=(
                "training_reward = original_reward + bonus * eligible(s'). Intentionally flawed: it pays for "
                "remaining in a desirable intermediate state, which can compete with finishing the landing."
            ),
            hover_bonus=HoverBonusConfig(enabled=True, bonus_per_step=1.0),
        )
    if name == "potential":
        return RewardConfig(
            name="Potential-based shaping",
            preset="potential",
            description=(
                "training_reward = original_reward + alpha * (gamma * Phi(s') - Phi(s)), Phi(terminal) = 0, "
                "gamma = PPO gamma. Bounded state-only potential."
            ),
            potential=PotentialConfig(enabled=True),
        )
    raise KeyError(f"unknown preset {name!r}; choose from {', '.join(PRESET_NAMES)}")


def all_presets() -> list[RewardConfig]:
    return [preset(n) for n in PRESET_NAMES]
