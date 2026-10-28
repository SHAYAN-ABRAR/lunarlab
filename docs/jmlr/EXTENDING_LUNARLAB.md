# Extending LunarLab: reward terms, diagnostics and other environments

LunarLab's main pipeline (training jobs, final-test freezing, the web interface, the published study) is built
for Gymnasium's `LunarLander-v3`. The parts of it that do not depend on the task are also available, behind a
small adapter interface, in `lunarlab.audit`. This page says which parts are which, how to add a reward term or a
diagnostic, how to add an environment, and what would still be needed to run the *whole* pipeline on another task.

## What is generic and what is LunarLander-specific

| Capability | Where | Task-independent? |
|---|---|---|
| Training reward `= w · original + Σ terms`, checked per transition | `lunarlab.audit.core.RewardAccountingWrapper`; `lunarlab.rewards.wrapper` (LunarLander) | **yes** (`audit.core`) |
| Original and training returns kept apart, undiscounted and discounted, per term | `audit.core.EpisodeAudit`; `rewards.accounting` | **yes** (`audit.core`) |
| Potential-based shaping with absorbing terminal and correct truncation | `audit.core.potential_shaping`; `rewards.terms.potential_shaping` | **yes** (any potential function) |
| Per-step and state-predicate terms (the shape of the flawed hover bonus) | `audit.core.per_step`, `audit.core.state_bonus` | **yes** |
| Reward-definition identity | `audit.core.terms_hash` (schema 0: 16-hex digest of the declared descriptions); `audit.provenance.reward_provenance` (versioned record, schema 2: full definition digest; for each term's callables, the digest and git status of the source file, a digest of the callable's own source and the values it captures; `incomplete` when the code cannot be located or a captured value has no JSON form); `RewardConfig.content_hash` | **yes** |
| Seed contract: non-empty, nonnegative integers, nothing coerced, no duplicates, disjoint splits; checked before any environment exists | `audit.contracts`, `audit.evaluate.seed_split_problems`; `EvalProtocol.problems` | **yes** (`audit`); `EvalProtocol` accepts only `LunarLander-v3` by design |
| Finite rewards, term outputs, weights, descriptions and episode totals (NaN, infinity and totals that overflow refused, naming the source; recorded values must be numbers, never null, booleans or text) | `audit.contracts`, `audit.core.RewardAccountingWrapper` | **yes** |
| Policy audit on fixed seeds with the original reward | `audit.evaluate.audit_policy`; `evaluation.evaluate_policy` | **yes** (`audit`) |
| A prespecified PPO study: training with scheduled original-reward validation, selection rule, freezing (`freeze.immutable_copy`), digest-checked final test, artifacts verified before replay | `audit.study`, `examples/cartpole_study.py`, `lunarlab audit-artifact` | **yes** (PPO only) |
| Statistics across training seeds (IQM, bootstrap CIs, P(improvement), profiles) | `lunarlab.rl_stats`, `lunarlab.stats` | **yes** (plain arrays) |
| Checkpoint digests, configuration hashes, segments, provenance | `runs`, `storage`, `freeze`, `continuation` | the mechanisms are generic; `RunConfig` is LunarLander's |
| Outcome classification (strict pad landing, pad geography, body contact) | `lunarlab.outcomes` | **no**: lander geometry |
| Hover detector and hover bonus eligibility | `lunarlab.hover` | **no**: lander state |
| Action labels (no-op, left, main, right), observation fields | `lunarlab.env` | **no** |
| Built-in reward decomposition, scene geometry, 3-D replay, Fly It Yourself | `lunarlab.env`, `lunarlab.play`, frontend | **no** |
| Episode accumulator's action counts and leg-contact statistics | `lunarlab.rewards.accounting` | **no** (the generic `EpisodeAudit` omits them) |

None of the lander-specific metrics is applied to another environment: an adapter declares its own outcome
categories and metrics, and the wrapper refuses an outcome that is not one of them.

## The adapter contract

```python
from lunarlab.audit import TaskAdapter, register_adapter, per_step, potential_shaping

def my_adapter() -> TaskAdapter:
    return TaskAdapter(
        name="mytask",                     # registry key
        version="1",                       # bump when outcome definitions change (recorded with every audit)
        env_id="MyEnv-v0",
        env_kwargs={},
        observation_labels=("x", "v"),
        action_labels=("left", "right"),
        outcome_categories=("success", "failure", "time_limit"),
        classify=lambda end: {"outcome": "time_limit" if end.truncated else ("success" if end.observations[-1][0] > 1 else "failure")},
        term_factories={
            "progress": lambda gamma, alpha=1.0: potential_shaping(
                "progress", lambda o: float(o[0]), alpha=alpha, gamma=gamma, potential_id="x"),
            "step_cost": lambda cost=0.01: per_step("step_cost", -cost),
        },
        diagnostics={"max_x": lambda obs: float(obs[:, 0].max())},          # per episode, from s_0..s_T
        metrics={"success_rate": lambda eps: sum(e["outcome"] == "success" for e in eps) / len(eps)},
    )

register_adapter("mytask", my_adapter)
```

- `classify(end)` receives an `EpisodeEnd` (the environment below the accounting wrapper, all observations
  `s_0 … s_T`, `terminated`, `truncated`, the last `info`) and returns a dict with `"outcome"` set to one of
  `outcome_categories`; any other keys are copied into the episode record. Use `end.env.unwrapped` for read-only
  task internals (the CartPole adapter reads its failure thresholds there instead of hard-coding them).
- Reward terms are pure functions of one `Transition(obs, action, original_reward, next_obs, terminated,
  truncated)`. Keep them pure: the same function must give the same value when a recorded trajectory is
  re-scored.
- `describe` (built by the term helpers) must identify the term completely; it enters the reward hash.

Two adapters ship with LunarLab: `lunarlander` (LunarLab's own outcome classifier, hover detector and preset
terms, so it reproduces the main pipeline exactly; see `tests/test_audit_core.py`) and `cartpole`
(`CartPole-v1`: the pole fell, the cart left the track, or it balanced until the time limit).

## Auditing a policy on another task

```python
from lunarlab.audit import audit_policy, get_adapter

cartpole = get_adapter("cartpole")
shaping = cartpole.term("upright_potential", gamma=0.99)
report = audit_policy(cartpole, policy, seeds=list(range(20_000, 20_050)), gamma=0.99,
                      terms={shaping.name: shaping})
report["aggregate"]   # mean original return, mean shaped return, outcome counts, adapter metrics
```

`examples/cartpole_audit.py` trains PPO on CartPole twice (original reward; original plus the upright potential)
through `RewardAccountingWrapper`, then audits both policies with the original reward on the same held-out seeds.
It demonstrates the contract; it is not a research result about CartPole. `PPO(seed=...)` re-seeds the
environments, so the example sets their seeds after building the model.

For a controlled study, write a protocol (`lunarlab.audit.study`; examples in `examples/protocols/` and
`reports/neurocomputing-2026-10-27/cartpole-study/protocol/`) and run `examples/cartpole_study.py`. The protocol
fixes the reward designs, the learner, the budget, the training and environment seeds, the validation and test
seeds and the selection rule; it is validated before training. Each run:

- records the effective first-reset seeds and refuses to finish if they differ from the protocol;
- selects a checkpoint on original-reward validation only, then freezes it and the final checkpoint;
- tests only after every frozen digest is verified, and exports an artifact.

`lunarlab audit-artifact verify|reproduce` checks the artifact's files, protocol, reward definition and records
before any episode runs. The 27 October 2026 CartPole study and its analysis are in
`reports/neurocomputing-2026-10-27/cartpole-study/`.

## Adding a reward term to the main LunarLander pipeline

1. Add a configuration block to `lunarlab/rewards/config.py` (a strict pydantic model with bounds; it becomes
   part of `RewardConfig` and of its content hash) and its key to `TERM_KEYS`.
2. Add a pure function to `lunarlab/rewards/terms.py` and call it from `compute_terms`. The wrapper, evaluation
   and the trajectory re-scorer all call `compute_terms`, so there is one implementation.
3. Add the corresponding factory to the `lunarlander` adapter if it should be available to `lunarlab.audit`.
4. Tests: an exact value test on a scripted transition (`tests/conftest.py` provides `ScriptedEnv`), the
   accounting identity, and re-scoring of a recorded trajectory.

## Adding a diagnostic

Per-episode diagnostics of the main pipeline live in `rewards/accounting.py` (the episode accumulator) and are
aggregated in `evaluation.aggregate`. For another task, pass a function of the observation array to the
adapter's `diagnostics`; its value is stored in every episode record.

## What running the full pipeline on another task would still need

The adapter layer covers accounting, audits, statistics and, with `audit.study`, a prespecified PPO study with
selection, freezing, final tests and verified artifacts. Running the main application on another environment
would additionally need the following. That application covers resumable training jobs, DQN, the run registry,
robustness and tuning studies, preference learning and the web interface.

- `RunConfig`/`EvalProtocol` to carry an adapter name instead of the fixed `LunarLander-v3` declaration (and
  `EvalProtocol.problems` to validate against the adapter), with a configuration-hash rule that keeps every
  existing LunarLander run's hash unchanged;
- `training._build_training_env` and `evaluation.make_eval_env` to build the environment through the adapter;
- the episode CSV schema (`training.EPISODE_FIELDS`) to take its outcome and action columns from the adapter;
- the frontend to treat landing categories, the 3-D replay and Fly It Yourself as LunarLander-only features.

These changes touch the code that produced the published results, so they were not made without a study that
needs them; the adapter layer was added beside the existing pipeline instead, and its LunarLander adapter is
tested to give identical rewards, returns and outcomes.
