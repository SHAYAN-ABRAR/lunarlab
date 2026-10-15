"""Request bodies. Strict schemas: unknown fields are rejected, numbers are bounded."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from lunarlab.rewards.config import RewardConfig

ProfileName = Literal["smoke", "standard", "extended"]
PresetName = Literal["baseline", "time-penalty", "hover-bonus", "potential"]
IdemKey = Field(None, max_length=80, pattern=r"^[A-Za-z0-9_\-]+$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RewardConfigCreate(_Strict):
    config: RewardConfig
    parent_id: str | None = Field(None, max_length=120)


class RewardConfigValidate(_Strict):
    config: dict


class RewardImport(_Strict):
    yaml: str = Field(..., max_length=100_000)
    parent_id: str | None = Field(None, max_length=120)


class HoverAnalysisRequest(_Strict):
    bonus: float = Field(1.0, ge=0.0, le=10.0)
    gamma: float = Field(0.999, gt=0.0, lt=1.0)
    horizon: int = Field(1000, ge=1, le=100_000)
    hover_start: int = Field(100, ge=0, le=100_000)
    main_engine_duty: float = Field(0.5, ge=0.0, le=1.0)
    landing_step: int = Field(300, ge=1, le=100_000)
    landing_original_return: float = Field(220.0, ge=-1000, le=1000)


class RunCreate(_Strict):
    reward_config_id: str | None = Field(None, max_length=120)
    preset: PresetName | None = None
    profile: ProfileName = "smoke"
    seed: int = Field(0, ge=0, le=999)
    total_transitions: int | None = Field(None, ge=4096, le=20_000_000)
    n_envs: int | None = Field(None, ge=1, le=16)
    vec_env: Literal["dummy", "subproc"] | None = None
    label: str = Field("", max_length=120)
    experiment_id: str | None = Field(None, max_length=120)
    start: bool = True
    confirm_extended: bool = False
    idempotency_key: str | None = IdemKey


class ResumeRequest(_Strict):
    checkpoint: str = Field("latest", max_length=80, pattern=r"^[A-Za-z0-9_.\-]+$")
    idempotency_key: str | None = IdemKey


class EvaluateRequest(_Strict):
    split: Literal["validation", "test"]
    checkpoint: str = Field("best", max_length=80, pattern=r"^[A-Za-z0-9_.\-]+$")
    confirm_test: bool = False
    idempotency_key: str | None = IdemKey


class RecordRequest(_Strict):
    episode_seed: int = Field(20_000, ge=0, le=2**31 - 1)
    checkpoint: str = Field("best", max_length=80, pattern=r"^[A-Za-z0-9_.\-]+$")
    idempotency_key: str | None = IdemKey


class DemoRequest(_Strict):
    policy: Literal["random", "heuristic"] = "random"
    episode_seed: int = Field(20_000, ge=0, le=2**31 - 1)
    action_seed: int = Field(0, ge=0, le=2**31 - 1)
    idempotency_key: str | None = IdemKey


class RescoreRequest(_Strict):
    config_ids: list[str] = Field(default_factory=list, max_length=12)
    presets: list[PresetName] = Field(default_factory=list, max_length=4)
    gamma: float = Field(0.999, gt=0.0, le=1.0)


class SuitePlan(_Strict):
    presets: list[PresetName] = Field(default_factory=list, max_length=4)
    config_ids: list[str] = Field(default_factory=list, max_length=12)
    seeds: list[int] = Field(..., min_length=1, max_length=10)
    profile: ProfileName = "standard"


class SuiteCreate(SuitePlan):
    name: str = Field(
        "reward-shaping-suite", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.\-]*$"
    )
    description: str = Field("", max_length=1000)
    start: bool = True
    confirm_large: bool = False
    idempotency_key: str | None = IdemKey


class CompareRequest(_Strict):
    run_ids: list[str] = Field(..., min_length=1, max_length=40)
    split: Literal["validation", "test"] = "test"


class ReportRequest(_Strict):
    run_ids: list[str] = Field(default_factory=list, max_length=40)
    experiment_id: str | None = Field(None, max_length=120)
    split: Literal["validation", "test"] = "test"
    title: str = Field("LunarLab experiment report", max_length=120)
    idempotency_key: str | None = IdemKey


class QueueRequest(_Strict):
    paused: bool


class BenchmarkRequest(_Strict):
    n_envs: list[int] = Field(default_factory=lambda: [1, 2, 4, 8], min_length=1, max_length=5)
    ppo: bool = True
    idempotency_key: str | None = IdemKey


class FlightStart(_Strict):
    seed: int | None = Field(None, ge=0, le=2**31 - 1)
    opponent: str | None = Field(None, max_length=120, pattern=r"^[A-Za-z0-9_\-]+$")


class FlightStep(_Strict):
    actions: list[Annotated[int, Field(ge=0, le=3)]] = Field(..., min_length=1, max_length=50)


class PreferenceLabel(_Strict):
    i: int = Field(..., ge=0, le=10_000_000)
    j: int = Field(..., ge=0, le=10_000_000)
    choice: Literal["a", "b", "tie"]
