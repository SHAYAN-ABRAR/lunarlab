# `lunarlab.divergence`

Source: [`lunarlab/divergence.py`](../../lunarlab/divergence.py)

Where two platforms' evaluations of the same policy part: per-step traces and their comparison.

A recorded evaluation stores per-episode summaries, not trajectories, so the first step at which a reproduction
departs from the record cannot be read from it. :func:`record_traces` therefore flies chosen seeds of an
artifact and stores, per step, the observation, the network's raw outputs (PPO action logits or DQN Q-values,
float32), the action and the reward. :func:`diagnose` repeats those episodes on another machine against the
stored trace and separates the two possible sources of a difference:

* **policy inference**: the network is evaluated on the *reference* observations; any difference in its
  outputs (bit for bit) or in the chosen action is an inference difference;
* **simulator dynamics**: the environment is stepped open-loop with the *reference* actions; any difference in
  the observations is a dynamics difference (Box2D and the environment code), independent of the policy.

It also reports the closed-loop trajectory: the first step whose observation or action differs, and how far
the episode's return moved. Traces are uncompressed ``.npz`` files of numeric arrays, read with
``allow_pickle=False``.

### `compare_trace(reference: 'dict[str, np.ndarray]', env, policy, seed: 'int', *, reference_return: 'float | None' = None) -> 'dict[str, Any]'`

Compare one reference episode with this machine: inference, open-loop dynamics and closed loop.

### `diagnose(artifact_dir: 'Path', reference: 'Path') -> 'dict[str, Any]'`

Compare every traced episode of ``reference`` with this machine (see the module docstring).

### `load_traces(path: 'Path') -> 'tuple[dict, dict[int, dict[str, np.ndarray]]]'`

Read a trace pair (``.npz`` + ``.json``); the arrays must match the digest in the JSON.

### `policy_outputs(policy, obs: 'np.ndarray') -> 'np.ndarray'`

The raw outputs the greedy action is the arg-max of: PPO action logits or DQN Q-values (float32).

### `record_traces(artifact_dir: 'Path', seeds: 'list[int]', out: 'Path') -> 'dict[str, Any]'`

Trace ``seeds`` of an artifact on this machine; write ``out`` (``.npz``) and ``out`` with ``.json``.

### `replay_actions(env, seed: 'int', actions: 'np.ndarray') -> 'np.ndarray'`

Step the environment open-loop with given actions; the observations reached (up to len(actions)+1).

### `trace_episode(env, policy, seed: 'int') -> 'dict[str, Any]'`

Fly one greedy episode and keep every step: observations (T+1), outputs, actions and rewards (T).

## Constants

- `ARRAYS` = `('observations', 'outputs', 'actions', 'rewards')`
- `TRACE_FORMAT` = `'lunarlab.trace'`
- `TRACE_VERSION` = `1`
