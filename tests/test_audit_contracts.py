# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Contracts of the task-independent audit layer, checked against independent oracles.

Seeds are nonnegative integers, refused (never coerced) before any environment exists. Rewards, term
outputs, weights and the discount are finite. Accounting is checked against sums calculated by hand on a
tiny deterministic environment, never by calling the helper on both sides. Potential shaping is checked at
a true termination, a time-limit truncation and a step that reports both. The reward provenance record
states what each digest covers, and reports code it cannot locate as incomplete.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
import sys
import textwrap

import gymnasium as gym
import numpy as np
import pytest
from gymnasium import spaces
from gymnasium.wrappers import TimeLimit

from lunarlab.audit import (
    SEED_CONTRACT,
    AuditInputError,
    NonFiniteValueError,
    RewardAccountingWrapper,
    RewardTerm,
    TaskAdapter,
    Transition,
    audit_policy,
    definition_sha256,
    get_adapter,
    normalize_seeds,
    per_step,
    potential_shaping,
    rescore_transitions,
    reward_provenance,
    seed_split_problems,
    terms_hash,
)
from lunarlab.audit import provenance as prov
from lunarlab.audit.contracts import finite_mean
from lunarlab.audit.core import EpisodeAudit

# --------------------------------------------------------------------------- #
# A tiny deterministic environment with hand-calculable rewards
# --------------------------------------------------------------------------- #

REWARDS = (1.0, -2.0, 3.0)
XS = (4.0, 2.0, 1.0, 0.5)  # observation[1] at s_0 .. s_3


class Chain(gym.Env):
    """Three steps with original rewards 1, -2, 3; observation = (t, x_t). ``end`` sets the final flags."""

    def __init__(self, end: str = "terminate", nan_at: int | None = None):
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(2,), dtype=np.float64)
        self.action_space = spaces.Discrete(2)
        self.end, self.nan_at, self.t = end, nan_at, 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.t = 0
        return np.array([0.0, XS[0]]), {"reset_seed": seed}

    def step(self, action):
        reward = math.nan if self.nan_at == self.t else REWARDS[self.t]
        self.t += 1
        last = self.t == 3
        terminated = last and self.end in ("terminate", "both")
        truncated = last and self.end in ("truncate", "both")
        return np.array([float(self.t), XS[self.t]]), reward, terminated, truncated, {"step": self.t}


def chain_adapter(counter: dict | None = None, **env_kw) -> TaskAdapter:
    def factory(**kw):
        if counter is not None:
            counter["envs"] = counter.get("envs", 0) + 1
        return Chain(**{**env_kw, **kw})

    return TaskAdapter(
        name="chain",
        version="1",
        env_id="Chain-test",
        env_kwargs={},
        observation_labels=("t", "x"),
        action_labels=("a0", "a1"),
        outcome_categories=("ended",),
        classify=lambda end: {"outcome": "ended"},
        factory=factory,
    )


def run_episode(env, actions=(0, 0, 0)):
    out = [env.reset(seed=0)]
    for a in actions:
        out.append(env.step(a))
        if out[-1][2] or out[-1][3]:
            break
    return out


def phi(o) -> float:
    return -float(o[1])


# --------------------------------------------------------------------------- #
# Seeds
# --------------------------------------------------------------------------- #

INVALID_SEEDS = {
    "booleans": [True, False],
    "fractional floats": [1.5, 2.7],
    "integral floats": [3.0, 4.0],
    "numeric strings": ["7", "8"],
    "negative after a valid seed": [5, -1],
    "empty": [],
    "distinct values that collapse after int()": [1, 1.5],
    "a string and an int that collapse": ["9", 9],
    "numpy bool": [np.bool_(True)],
    "a set": {1, 2},
    "a string": "12",
    "two-dimensional array": np.array([[1, 2]]),
}


@pytest.mark.parametrize("label", sorted(INVALID_SEEDS))
def test_invalid_seeds_are_refused_before_any_environment_exists(label):
    counter: dict = {}
    with pytest.raises(AuditInputError) as err:
        audit_policy(chain_adapter(counter), lambda o: 0, INVALID_SEEDS[label], gamma=0.9)
    assert counter.get("envs", 0) == 0, "an environment was created before the seeds were checked"
    assert "Contract:" in str(err.value)


def test_valid_seed_types_are_normalised_without_changing_values():
    counter: dict = {}
    seeds = [np.int64(5), np.int32(6), 7, range(8, 9)[0]]
    report = audit_policy(chain_adapter(counter), lambda o: 0, seeds, gamma=0.9)
    assert report["seeds"] == [5, 6, 7, 8] and all(type(s) is int for s in report["seeds"])
    assert [e["seed"] for e in report["episodes"]] == [5, 6, 7, 8]
    assert counter["envs"] == 1 and report["seed_contract"] == SEED_CONTRACT
    assert normalize_seeds(np.arange(3)) == [0, 1, 2]


def test_seed_messages_are_deterministic_and_name_every_offending_entry():
    msg = str(pytest.raises(AuditInputError, normalize_seeds, [0, True, 2.5, "3", -4]).value)
    assert msg == str(pytest.raises(AuditInputError, normalize_seeds, [0, True, 2.5, "3", -4]).value)
    for fragment in (
        "seeds[1] = True (bool): booleans are not seeds",
        "seeds[2] = 2.5 (float): not an integer",
        "seeds[3] = '3' (str): not an integer; numeric strings are not converted",
        "seeds[4] = -4 (int): negative",
    ):
        assert fragment in msg


def test_seed_split_problems():
    assert seed_split_problems([1, 2], [3, 4]) == []
    assert seed_split_problems([np.int64(1)], [np.int32(2)]) == []
    assert any("overlap" in p for p in seed_split_problems([1, 2], [2, 3]))
    assert any("overlap" in p for p in seed_split_problems([np.int64(5)], [5]))
    assert any("duplicates" in p for p in seed_split_problems([1, 1], [3]))
    assert any("integers" in p for p in seed_split_problems([True], [3]))
    assert any("must not be empty" in p for p in seed_split_problems([], [3]))
    assert any("must not be empty" in p for p in seed_split_problems([1], []))
    assert any("negative" in p for p in seed_split_problems([-1, 2], [3]))
    assert any("not an integer" in p for p in seed_split_problems([[1]], [2]))  # unhashable: no TypeError
    assert any("not an integer" in p for p in seed_split_problems([1.0], [2]))


def test_historical_valid_protocols_remain_accepted():
    from lunarlab.config import TEST_SEEDS, VALIDATION_SEEDS, EvalProtocol

    assert seed_split_problems(VALIDATION_SEEDS, TEST_SEEDS) == []
    assert EvalProtocol().problems() == []
    assert seed_split_problems(list(range(10_000, 10_010)), list(range(20_000, 20_050))) == []  # example


# --------------------------------------------------------------------------- #
# Finite values and the error boundary
# --------------------------------------------------------------------------- #


def nan_term(name="nan_term", when=lambda t: True) -> RewardTerm:
    return RewardTerm(name, lambda t: math.nan if when(t) else 0.0, {"type": "custom", "id": name})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_a_non_finite_term_output_is_refused_and_named(value):
    term = RewardTerm("bad_term", lambda t: value, {"type": "custom"})
    w = RewardAccountingWrapper(Chain(), {"bad_term": term}, gamma=0.9)
    w.reset(seed=0)
    with pytest.raises(NonFiniteValueError, match="reward term 'bad_term' output"):
        w.step(0)
    with pytest.raises(RuntimeError, match="before reset"):  # the broken episode cannot be continued
        w.step(0)
    w.reset(seed=0)  # a reset starts a new, valid episode


def test_a_non_finite_original_reward_is_refused_and_named():
    w = RewardAccountingWrapper(Chain(nan_at=1), gamma=0.9)
    w.reset(seed=0)
    w.step(0)
    with pytest.raises(NonFiniteValueError, match="original reward at step 1"):
        w.step(0)


def test_an_overflowing_training_reward_is_refused():
    w = RewardAccountingWrapper(Chain(), gamma=0.9, original_weight=1e308)
    w.reset(seed=0)
    w.step(0)  # 1e308 * 1.0 is finite
    with pytest.raises(NonFiniteValueError, match="training reward at step 1"):
        w.step(0)  # 1e308 * -2.0 overflows to -inf


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"original_weight": math.nan}, "original_weight must be finite"),
        ({"original_weight": math.inf}, "original_weight must be finite"),
        ({"gamma": math.nan}, "gamma must be finite"),
        ({"gamma": math.inf}, "gamma must be finite"),
        ({"gamma": 1.5}, "gamma must be in"),
    ],
)
def test_invalid_weights_and_discounts_are_refused_before_any_environment_exists(kwargs, match):
    counter: dict = {}
    args = {"gamma": 0.9, **kwargs}
    with pytest.raises(ValueError, match=match):
        audit_policy(chain_adapter(counter), lambda o: 0, [1], **args)
    assert counter.get("envs", 0) == 0


@pytest.mark.parametrize(
    "describe, match",
    [
        ({"type": "custom", "scale": math.nan}, r"reward term 'b' description\.scale = nan"),
        ({"type": "custom", "nested": {"w": [1.0, math.inf]}}, r"description\.nested\.w\[1\] = inf"),
        ({"type": "custom", "f": object()}, "reward term 'b' description is not JSON-serialisable"),
    ],
)
def test_invalid_term_descriptions_are_refused_with_the_field_named(describe, match):
    term = RewardTerm("b", lambda t: 0.0, describe)
    with pytest.raises(AuditInputError, match=match):
        terms_hash({"b": term}, 1.0)
    counter: dict = {}
    with pytest.raises(AuditInputError, match=match):
        audit_policy(chain_adapter(counter), lambda o: 0, [1], gamma=0.9, terms={"b": term})
    assert counter.get("envs", 0) == 0


def test_a_failure_in_a_later_episode_returns_no_partial_report():
    def nan_in_third_episode():
        state = {"episodes": 0}

        def fn(t):
            if t.obs[0] == 0.0:  # first transition of an episode
                state["episodes"] += 1
            return math.nan if state["episodes"] == 3 else 0.0

        return RewardTerm("late_nan", fn, {"type": "custom", "id": "late_nan"})

    control = audit_policy(
        chain_adapter(), lambda o: 0, [1, 2], gamma=0.9, terms={"late_nan": nan_in_third_episode()}
    )
    assert control["aggregate"]["n_episodes"] == 2  # the term is finite in the first two episodes
    result = None
    with pytest.raises(NonFiniteValueError, match="reward term 'late_nan' output"):
        result = audit_policy(
            chain_adapter(), lambda o: 0, [1, 2, 3], gamma=0.9, terms={"late_nan": nan_in_third_episode()}
        )
    assert result is None  # two completed episodes are not returned as a report


def test_built_in_term_parameters_must_be_finite():
    with pytest.raises(NonFiniteValueError, match="per_step term 'p' value"):
        per_step("p", math.nan)
    with pytest.raises(NonFiniteValueError, match="potential_shaping term 'f' alpha"):
        potential_shaping("f", phi, alpha=math.inf, gamma=0.9, potential_id="-x")


class Scripted(gym.Env):
    """Episode k (from 0) pays ``episodes[k]`` step by step and terminates after its last reward."""

    observation_space = spaces.Box(-1.0, 1.0, (1,), np.float64)
    action_space = spaces.Discrete(1)

    def __init__(self, *episodes: tuple[float, ...]):
        self.episodes, self.k, self.t = episodes, -1, 0

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.k, self.t = self.k + 1, 0
        return np.zeros(1), {}

    def step(self, action):
        rewards = self.episodes[self.k]
        self.t += 1
        return np.zeros(1), rewards[self.t - 1], self.t == len(rewards), False, {}


LARGEST_DOUBLE = sys.float_info.max  # about 1.798e308, so 1e308 + 1e308 is not representable


def test_finite_rewards_whose_totals_overflow_end_the_episode_without_a_summary():
    assert math.isfinite(1e308) and LARGEST_DOUBLE < 1e308 + 1e308  # the premise, checked independently
    w = RewardAccountingWrapper(Scripted((1e308, 1e308), (1.0, 2.0)), gamma=0.99)
    w.reset(seed=0)
    _, reward, terminated, _, info = w.step(0)
    assert reward == 1e308 and not terminated and "audit_episode" not in info
    with pytest.raises(NonFiniteValueError) as err:
        w.step(0)  # every value is finite; the four totals are not
    message = str(err.value)
    for total in (
        "original_return",
        "training_return",
        "discounted_original_return",
        "discounted_training_return",
    ):
        assert total in message
    assert "at step 1" in message and "floating-point range" in message
    assert w.last_episode is None  # nothing that looks like a completed audit
    with pytest.raises(RuntimeError, match="before reset"):
        w.step(0)  # the failed episode cannot be continued
    w.reset(seed=0)  # a reset starts a new audit, which completes normally
    w.step(0)
    *_, info = w.step(0)
    assert info["audit_episode"]["original_return"] == 3.0 and w.last_episode["original_return"] == 3.0


def test_totals_near_the_largest_double_stay_exact_when_they_fit():
    big = 2.0**1020  # powers of two: every expected total below is exact
    w = RewardAccountingWrapper(Scripted((big, big)), gamma=0.5)
    w.reset(seed=0)
    w.step(0)
    *_, info = w.step(0)
    ep = info["audit_episode"]
    assert ep["original_return"] == ep["training_return"] == 2.0**1021
    assert (
        ep["discounted_original_return"] == ep["discounted_training_return"] == 3 * 2.0**1019
    )  # big + big / 2


def test_finite_term_outputs_whose_sum_overflows_raise_the_audit_error_not_overflow_error():
    terms = {n: RewardTerm(n, lambda t: 1e308, {"type": "custom", "id": n}) for n in ("a", "b")}
    w = RewardAccountingWrapper(Scripted((0.0,)), terms, gamma=0.9)
    w.reset(seed=0)
    with pytest.raises(NonFiniteValueError, match="reward-term outputs at step 0 are each finite"):
        w.step(0)
    assert w.last_episode is None


def test_a_refused_transition_leaves_the_episode_audit_unchanged():
    audit = EpisodeAudit(0.5)
    audit.add(1e308, {"t": 1e308}, 1e308)
    before = audit.summary()
    with pytest.raises(NonFiniteValueError, match=r"term_returns\['t'\]"):
        audit.add(1e308, {"t": 1e308}, 0.0)
    assert audit.summary() == before and audit.length == 1


def test_rescoring_refuses_totals_that_overflow():
    zero = np.zeros(1)
    transitions = [Transition(zero, 0, 1e308, zero, i == 1, False) for i in range(2)]
    with pytest.raises(NonFiniteValueError, match="episode totals overflow at step 1"):
        rescore_transitions(transitions, {}, gamma=0.99)


def test_the_audit_mean_is_exact_when_only_the_plain_sum_would_overflow():
    adapter = TaskAdapter(
        name="large",
        version="1",
        env_id="Large-test",
        env_kwargs={},
        observation_labels=("x",),
        action_labels=("a",),
        outcome_categories=("ended",),
        classify=lambda end: {"outcome": "ended"},
        factory=lambda **kw: Scripted((1.5e308,), (1.5e308,)),
    )
    report = audit_policy(adapter, lambda o: 0, [1, 2], gamma=0.9)
    assert [e["original_return"] for e in report["episodes"]] == [1.5e308, 1.5e308]
    assert report["aggregate"]["mean_original_return"] == 1.5e308  # x/2 + x/2 is exact for this x
    assert finite_mean([0.1, 0.2, 0.7], "m") == statistics.fmean([0.1, 0.2, 0.7])  # ordinary values unchanged


# --------------------------------------------------------------------------- #
# Accounting against hand-calculated values
# --------------------------------------------------------------------------- #


def test_accounting_matches_hand_calculated_sums_and_leaves_the_environment_unchanged():
    gamma, weight = 0.9, 2.0
    plain = run_episode(Chain())
    w = RewardAccountingWrapper(
        Chain(), {"step_cost": per_step("step_cost", -0.5)}, gamma=gamma, original_weight=weight, apply=True
    )
    wrapped = run_episode(w)
    assert np.array_equal(plain[0][0], wrapped[0][0]) and plain[0][1] == wrapped[0][1]
    for (o1, r1, t1, u1, i1), (o2, r2, t2, u2, i2) in zip(plain[1:], wrapped[1:], strict=True):
        assert np.array_equal(o1, o2) and (t1, u1) == (t2, u2)
        assert {k: v for k, v in i2.items() if k != "audit_episode"} == i1
        assert r2 == pytest.approx(weight * r1 - 0.5, abs=1e-12)  # apply=True: the training reward
    ep = wrapped[-1][4]["audit_episode"]
    # Hand calculation: rewards 1, -2, 3; discounts 1, 0.9, 0.81.
    assert ep["length"] == 3
    assert ep["original_return"] == pytest.approx(2.0, abs=1e-12)
    assert ep["discounted_original_return"] == pytest.approx(1.63, abs=1e-12)  # 1 - 1.8 + 2.43
    assert ep["term_returns"]["step_cost"] == pytest.approx(-1.5, abs=1e-12)
    assert ep["term_discounted_returns"]["step_cost"] == pytest.approx(-1.355, abs=1e-12)  # -0.5 * 2.71
    assert ep["training_return"] == pytest.approx(2.5, abs=1e-12)  # 2 * 2 - 1.5
    assert ep["discounted_training_return"] == pytest.approx(1.905, abs=1e-12)  # 2 * 1.63 - 1.355
    evaluation = run_episode(RewardAccountingWrapper(Chain(), {}, gamma=gamma, apply=False))
    assert [s[1] for s in evaluation[1:]] == list(REWARDS)  # apply=False: the original reward unchanged


# Hand-calculated F_t = gamma * Phi(s_{t+1}) - Phi(s_t) with Phi(s) = -x, gamma = 0.9 and x = 4, 2, 1, 0.5:
# F_0 = 0.9 * -2 + 4 = 2.2 and F_1 = 0.9 * -1 + 2 = 1.1. The last step depends on how the episode ended:
# absorbing (Phi(s_3) = 0): F_2 = 1.0, discounted sum 2.2 + 0.99 + 0.81 = 4.0
# truncated (Phi(s_3) = -0.5): F_2 = -0.45 + 1 = 0.55, discounted sum 2.2 + 0.99 + 0.4455 = 3.6355
POTENTIAL_EXPECTED = {
    "terminate": ((2.2, 1.1, 1.0), 4.0),
    "truncate": ((2.2, 1.1, 0.55), 3.6355),
    "both": ((2.2, 1.1, 1.0), 4.0),  # a true termination is absorbing even when truncation coincides
}


@pytest.mark.parametrize("end", sorted(POTENTIAL_EXPECTED))
def test_potential_shaping_at_termination_truncation_and_both(end):
    gamma = 0.9
    steps, discounted = POTENTIAL_EXPECTED[end]
    f = potential_shaping("f", phi, alpha=1.0, gamma=gamma, potential_id="-x")
    w = RewardAccountingWrapper(Chain(end=end), {"f": f}, gamma=gamma, original_weight=0.0, apply=True)
    episode = run_episode(w)
    assert [s[1] for s in episode[1:]] == pytest.approx(list(steps), abs=1e-12)
    summary = episode[-1][4]["audit_episode"]
    assert (summary["terminated"], summary["truncated"]) == (end != "truncate", end != "terminate")
    assert summary["term_discounted_returns"]["f"] == pytest.approx(discounted, abs=1e-12)
    # The telescoping identity, from the hand-written endpoint values (not from the term itself):
    phi_end = 0.0 if end != "truncate" else -XS[3]
    assert discounted == pytest.approx(gamma**3 * phi_end - (-XS[0]), abs=1e-12)


def test_a_time_limit_wrapper_that_coincides_with_termination_reports_both_flags():
    gamma = 0.9
    f = potential_shaping("f", phi, alpha=1.0, gamma=gamma, potential_id="-x")
    env = TimeLimit(Chain(end="terminate"), max_episode_steps=3)
    w = RewardAccountingWrapper(env, {"f": f}, gamma=gamma, original_weight=0.0)
    episode = run_episode(w)
    _, last_reward, terminated, truncated, info = episode[-1]
    assert terminated and truncated
    assert last_reward == pytest.approx(1.0, abs=1e-12)  # absorbing, as POTENTIAL_EXPECTED["both"]
    assert info["audit_episode"]["term_discounted_returns"]["f"] == pytest.approx(4.0, abs=1e-12)


def test_rescoring_a_recorded_trajectory_matches_the_hand_calculation():
    obs = [np.array([float(t), x]) for t, x in enumerate(XS)]
    transitions = [Transition(obs[t], 0, REWARDS[t], obs[t + 1], t == 2, False) for t in range(3)]
    f = potential_shaping("f", phi, alpha=1.0, gamma=0.9, potential_id="-x")
    out = rescore_transitions(transitions, {"f": f}, gamma=0.9, original_weight=1.0)
    assert [s["terms"]["f"] for s in out["steps"]] == pytest.approx([2.2, 1.1, 1.0], abs=1e-12)
    assert out["summary"]["term_discounted_returns"]["f"] == pytest.approx(4.0, abs=1e-12)
    assert out["summary"]["training_return"] == pytest.approx(2.0 + 4.3, abs=1e-12)
    bad = [Transition(obs[0], 0, math.nan, obs[1], False, False)]
    with pytest.raises(NonFiniteValueError, match="original reward of transition 0"):
        rescore_transitions(bad, {}, gamma=0.9)


# --------------------------------------------------------------------------- #
# Reward-definition identity and provenance
# --------------------------------------------------------------------------- #


def test_equal_descriptions_give_equal_definition_digests_whatever_the_code_does():
    pays_1 = RewardTerm("bonus", lambda t: 1.0, {"type": "custom", "id": "bonus"})
    pays_1000 = RewardTerm("bonus", lambda t: 1000.0, {"type": "custom", "id": "bonus"})
    assert terms_hash({"bonus": pays_1}, 1.0) == terms_hash({"bonus": pays_1000}, 1.0)
    assert definition_sha256({"bonus": pays_1}, 1.0) == definition_sha256({"bonus": pays_1000}, 1.0)
    assert len(definition_sha256({"bonus": pays_1}, 1.0)) == 64
    record = reward_provenance({"bonus": pays_1}, 1.0)
    assert "not what the term callables compute" in record["scopes"]["definition_sha256"]


def test_historical_terms_hash_values_are_unchanged():
    # Values computed by the unmodified 932cf1c implementation for these definitions.
    bonus = RewardTerm("bonus", lambda t: 1.0, {"type": "custom", "id": "bonus"})
    assert terms_hash({"bonus": bonus}, 1.0) == "7c35d7d90b6715e4"
    shaping = get_adapter("cartpole").term("upright_potential", gamma=0.99)
    old_formula = {"original_weight": 1.0, "terms": {"upright_potential": dict(shaping.describe)}}
    expected = hashlib.sha256(json.dumps(old_formula, sort_keys=True).encode()).hexdigest()[:16]
    assert terms_hash({"upright_potential": shaping}, 1.0) == expected


def _module_term(tmp_path, name: str, body: str):
    path = tmp_path / f"{name}.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    namespace: dict = {}
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    exec(code, namespace)  # noqa: S102 - test module written above
    return namespace["TERM"], path


def test_provenance_records_the_defining_file_and_detects_a_code_change(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    body = """
        from lunarlab.audit import RewardTerm
        TERM = RewardTerm("bonus", lambda t: {value}, {{"type": "custom", "id": "bonus"}})
    """
    term_a, path = _module_term(repo, "terms_a", body.format(value=1.0))
    subprocess.run(["git", "add", "terms_a.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "terms"], cwd=repo, check=True)
    monkeypatch.setattr(prov, "_repo_root", lambda: repo.resolve())
    monkeypatch.setattr("lunarlab.sysinfo.project_root", lambda: repo)
    clean = reward_provenance({"bonus": term_a}, 1.0)
    impl = clean["terms"]["bonus"]["implementation"][0]
    assert impl["source_file"] == "terms_a.py" and impl["status"] == "tracked-unmodified"
    assert clean["implementation_identity"] == "recorded" and clean["source"]["available"]

    term_b, _ = _module_term(repo, "terms_a", body.format(value=1000.0))  # same description, new code
    changed = reward_provenance({"bonus": term_b}, 1.0)
    assert changed["definition_sha256"] == clean["definition_sha256"]  # the declaration did not change
    impl_b = changed["terms"]["bonus"]["implementation"][0]
    assert impl_b["source_file_sha256"] != impl["source_file_sha256"]  # the file digest did
    assert impl_b["status"] == "file-digest-only" and "uncommitted" in impl_b["reason"]
    assert changed["implementation_identity"] == "file-digests-only"


def test_code_without_a_recoverable_source_is_reported_as_incomplete():
    namespace: dict = {}
    exec(compile("f = lambda t: 2.0", "<stdin>", "exec"), namespace)  # noqa: S102 - simulated session
    interactive = RewardTerm("typed", namespace["f"], {"type": "custom"})
    builtin = RewardTerm("builtin", math.fabs, {"type": "custom"})
    for term in (interactive, builtin):
        record = reward_provenance({term.name: term}, 1.0)
        assert record["implementation_identity"] == "incomplete"
        assert record["terms"][term.name]["implementation"][0]["status"] == "unavailable"
        assert record["incomplete_reasons"]


def test_built_in_terms_name_their_implementation_and_components():
    f = potential_shaping("f", phi, alpha=1.0, gamma=0.9, potential_id="-x")
    record = reward_provenance({"f": f}, 1.0)
    entry = record["terms"]["f"]
    assert entry["term_id"] == "lunarlab.audit.potential_shaping" and entry["term_version"] == "1"
    files = [r["source_file"] for r in entry["implementation"]]
    assert files[0].endswith("lunarlab/audit/core.py") and files[1].endswith("tests/test_audit_contracts.py")
    assert record["schema"] == "lunarlab.reward-provenance/2" and record["legacy_terms_hash"] == terms_hash(
        {"f": f}, 1.0
    )
    fn_record = entry["implementation"][0]
    assert fn_record["captured"]["alpha"] == 1.0 and fn_record["captured"]["gamma"] == 0.9
    assert fn_record["captured"]["potential"]["callable"]["qualname"] == "phi"
    assert fn_record["captured_complete"] and record["implementation_identity"] != "incomplete"


class SameDescription:
    """The reproduced defect: two terms that declare the same description and pay 1 and 1,000."""

    a = RewardTerm("bonus", lambda t: 1.0, {"type": "custom", "id": "bonus"})
    b = RewardTerm("bonus", lambda t: 1000.0, {"type": "custom", "id": "bonus"})


def _paying(value: float):
    return lambda t: value


def _implementation(term: RewardTerm) -> dict:
    return reward_provenance({"bonus": term}, 1.0)["terms"]["bonus"]["implementation"][0]


def test_terms_with_equal_descriptions_are_told_apart_by_their_code_or_captured_values():
    # Two lambdas in one file: same description digest, same file digest, different source text and line.
    one, thousand = _implementation(SameDescription.a), _implementation(SameDescription.b)
    assert definition_sha256({"bonus": SameDescription.a}, 1.0) == definition_sha256(
        {"bonus": SameDescription.b}, 1.0
    )
    assert one["source_file_sha256"] == thousand["source_file_sha256"]
    assert one["function_source_sha256"] != thousand["function_source_sha256"]
    assert one["first_line"] + 1 == thousand["first_line"]
    # Two closures of one factory: same source, different captured value.
    desc = {"type": "custom", "id": "bonus"}
    c1, c1000 = (_implementation(RewardTerm("bonus", _paying(v), desc)) for v in (1.0, 1000.0))
    assert c1["function_source_sha256"] == c1000["function_source_sha256"]
    assert c1["captured"] == {"value": 1.0} and c1000["captured"] == {"value": 1000.0}
    # Arrays are recorded by digest.
    weights = np.array([0.5, -1.0])
    rec = _implementation(RewardTerm("bonus", lambda t: float(weights @ t.next_obs[:2]), desc))
    assert rec["captured"]["weights"]["array"]["shape"] == [2]


def test_a_captured_value_without_a_json_form_makes_the_identity_incomplete():
    class Opaque:
        pass

    thing = Opaque()
    term = RewardTerm("bonus", lambda t: 1.0 if thing else 0.0, {"type": "custom", "id": "bonus"})
    record = reward_provenance({"bonus": term}, 1.0)
    impl = record["terms"]["bonus"]["implementation"][0]
    assert impl["captured_complete"] is False and "Opaque" in impl["captured_reason"]
    assert record["implementation_identity"] == "incomplete"
    assert any("Opaque" in r for r in record["incomplete_reasons"])


def test_audit_reports_carry_the_versioned_provenance_record():
    cp = get_adapter("cartpole")
    shaping = cp.term("upright_potential", gamma=0.99)
    report = audit_policy(cp, lambda o: int(o[2] > 0), [100], gamma=0.99, terms={shaping.name: shaping})
    reward = report["reward"]
    assert reward["hash"] == terms_hash({shaping.name: shaping}, 1.0)
    assert reward["definition_sha256"] == reward["provenance"]["definition_sha256"]
    assert reward["provenance"]["adapter"] == {"name": "cartpole", "version": "1"}
    assert report["episodes"][0]["reward_definition_sha256"] == reward["definition_sha256"]


# --------------------------------------------------------------------------- #
# Effective seeding with Stable-Baselines3
# --------------------------------------------------------------------------- #


class ResetRecorder(gym.Wrapper):
    def __init__(self, env, log):
        super().__init__(env)
        self.log = log

    def reset(self, *, seed=None, options=None):
        self.log.append(seed)
        return self.env.reset(seed=seed, options=options)


def test_sb3_replaces_environment_seeds_set_before_the_model_is_built():
    """Documents the installed SB3 behaviour the CartPole example depends on."""
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv

    log: list = []
    venv = DummyVecEnv([lambda: ResetRecorder(gym.make("CartPole-v1"), log)] * 2)
    venv.seed(1_000_000)  # set too early ...
    model = PPO("MlpPolicy", venv, n_steps=64, batch_size=64, seed=3, device="cpu")
    model.env.reset()
    assert log == [3, 4]  # ... PPO(seed=3) replaced it with 3 + i
    log.clear()
    venv.seed(1_000_000)  # set after construction, as examples/cartpole_audit.py now does
    model.env.reset()
    assert log == [1_000_000, 1_000_001]
    log.clear()
    rng = np.random.default_rng(0)
    for _ in range(300):
        model.env.step(rng.integers(0, 2, size=2))
    assert log and all(s is None for s in log)  # later episodes are reset without a seed
    venv.close()


@pytest.mark.slow
def test_the_cartpole_example_trains_from_its_intended_environment_seeds(monkeypatch):
    sys.path.insert(0, str(prov._repo_root() / "examples"))
    try:
        import cartpole_audit
    finally:
        sys.path.pop(0)
    log: list = []
    cp = get_adapter("cartpole")
    recording = TaskAdapter(
        **{**cp.__dict__, "factory": lambda **kw: ResetRecorder(gym.make("CartPole-v1"), log)}
    )
    model = cartpole_audit.train(recording, {}, transitions=1024, seed=2)
    assert log[:4] == [1_002_000, 1_002_001, 1_002_002, 1_002_003]
    assert all(s is None for s in log[4:])
    assert model.num_timesteps == 1024
