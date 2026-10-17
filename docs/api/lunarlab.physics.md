# `lunarlab.physics`

Source: [`lunarlab/physics.py`](../../lunarlab/physics.py)

Training under varied physics: per-episode wind, turbulence and gravity.

``PhysicsRandomizer`` sits directly on the LunarLander environment (below the reward wrapper).
Before each reset it draws the next episode's physics from ``PhysicsRandomization`` and sets them on
the unwrapped environment; Gymnasium reads gravity when the episode's world is created and wind /
turbulence at every step, and draws the terrain and initial push before the wind phase, so the
episode seed still fixes the terrain. The draw is reported in ``info["lunarlab_physics"]`` at reset
and on the final step, and the reward wrapper copies it into the episode summary.

Its generator is seeded from the episode seed of the worker's first reset (the run's recorded
worker seed), then continues across the auto-resets of the vector environment, so a run's sequence
of physics is reproducible.

### class `PhysicsRandomizer`(Wrapper)

Per-episode physics randomisation for training, below the reward wrapper; seeded from the worker's
episode seed so a run's sequence of physics is reproducible.

`PhysicsRandomizer(env: 'gym.Env', config: 'PhysicsRandomization') -> 'None'`

- method `reset(self, *, seed: 'int | None' = None, options: 'dict | None' = None)`: Draw and apply the next episode's physics, then reset; the draw is in ``info["lunarlab_physics"]``.
- method `step(self, action)`: Step; the episode's physics are repeated in the last step's info.

### `apply_physics(env: 'gym.Env', physics: 'dict[str, Any]') -> 'None'`

Set drawn physics on the unwrapped LunarLander before its next reset.

### `sample_physics(config: 'PhysicsRandomization', rng: 'np.random.Generator') -> 'dict[str, Any]'`

Draw one episode's physics: wind (with ``wind_probability``), wind and turbulence power, gravity.

## Constants

- `PHYSICS_FIELDS` = `('wind', 'wind_power', 'turbulence_power', 'gravity')`
