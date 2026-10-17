# `lunarlab.env`

Source: [`lunarlab/env.py`](../../lunarlab/env.py)

Environment construction and a small read-only adapter for LunarLander internals.

Everything in LunarLab that needs to look *inside* the Gymnasium LunarLander
implementation (pad geometry, whether the lander body touched the ground,
whether Box2D put the lander to sleep) goes through :func:`probe`. That keeps the
dependency on private attributes in one tested place. The adapter only reads; it
never mutates the simulator.

Verified against gymnasium 1.4.0 (``gymnasium/envs/box2d/lunar_lander.py``).

### class `ActionInfo`

ActionInfo(index: 'int', key: 'str', label: 'str')

`ActionInfo(index: 'int', key: 'str', label: 'str') -> None`


### class `AdapterError`(RuntimeError)

Raised when the installed LunarLander no longer exposes what we read.

`AdapterError(...)`


### class `Geometry`

Constants of the installed implementation, read from the module.

`Geometry(viewport_w: 'float', viewport_h: 'float', scale: 'float', fps: 'float', leg_down: 'float') -> None`

- property `world_h`: World height in Box2D units.
- property `world_w`: World width in Box2D units.
- method `world_x_to_obs(self, x_world: 'float') -> 'float'`: Convert a world x coordinate to the normalised observation x.

### class `LanderProbe`

Snapshot of internal flags after a step (read-only).

`LanderProbe(body_contact: 'bool', awake: 'bool', helipad_x1_world: 'float', helipad_x2_world: 'float', helipad_y_world: 'float', pad_x1_obs: 'float', pad_x2_obs: 'float', leg_x_world: 'tuple[float, float]', leg_contact: 'tuple[bool, bool]') -> None`

- method `to_dict(self) -> 'dict[str, Any]'`: JSON-ready dict.

### class `ObservationField`

ObservationField(index: 'int', key: 'str', label: 'str', units: 'str', description: 'str')

`ObservationField(index: 'int', key: 'str', label: 'str', units: 'str', description: 'str') -> None`


### `builtin_shaping(obs: 'np.ndarray') -> 'float'`

The environment's internal shaping potential, recomputed from an observation.

Mirrors the installed implementation::

    -100*sqrt(x^2+y^2) - 100*sqrt(vx^2+vy^2) - 100*|angle| + 10*left + 10*right

The environment evaluates this on float64 values *before* casting the
observation to float32, so a reconstruction from the float32 observation
differs by a tiny rounding residual, which LunarLab reports explicitly.

### `check_adapter() -> 'dict[str, Any]'`

Exercise the adapter on a real reset/step. Used by tests and ``doctor``.

### `decompose_builtin_reward(prev_obs: 'np.ndarray', next_obs: 'np.ndarray', action: 'int', reward: 'float', terminated: 'bool') -> 'dict[str, float]'`

Explain one original reward in terms of its built-in pieces.

On non-terminal steps the original reward is::

    [shaping(s') - shaping(s)] - 0.30*[main fired] - 0.03*[side fired]

On a terminal step the environment *replaces* the whole reward with -100
(crash / out of bounds) or +100 (lander at rest), so no other component is
reported for that step. ``residual`` is reward minus the sum of the reported
components and should be tiny (float32 rounding) on ordinary steps.

### `environment_record() -> 'dict[str, Any]'`

Everything we store about the environment with each run.

### `geometry() -> 'Geometry'`

Viewport, scale and helipad constants of the installed LunarLander (fails clearly if they changed).

### `instantiated_environment(env: 'gym.Env', overrides: 'dict[str, Any] | None' = None) -> 'dict[str, Any]'`

What an evaluation actually ran: id, keyword arguments and the effective physics of ``env``.

### `make_env(render_mode: 'str | None' = None, overrides: 'dict[str, Any] | None' = None) -> 'gym.Env'`

Create the standard environment.

``render_mode=None`` for training/evaluation, ``"rgb_array"`` for recording.
The returned env includes the registered ``TimeLimit`` wrapper.

``overrides`` (wind, turbulence, gravity) exist only for the separately labelled robustness
evaluations; training and every primary evaluation use the default physics.

### `probe(env: 'gym.Env') -> 'LanderProbe'`

Read outcome-relevant internals from any wrapped LunarLander env.

### `scene_for_seed(seed: 'int') -> 'dict[str, Any]'`

Re-derive an episode's scene from its seed (terrain depends only on the reset seed).

### `scene_geometry(env: 'gym.Env') -> 'dict[str, Any]'`

Terrain, helipad and lander dimensions of the current episode, in world units.

The terrain profile is the environment's own ``sky_polys`` (one segment per
terrain chunk), so a 3-D replay can show the exact ground the episode used.
``obs_to_world`` converts observation x/y back to world coordinates.

## Constants

- `ACTIONS` = `(ActionInfo(index=0, key='noop', label='Do nothing'), ActionInfo(index=1, key='left', label='Fire left orientation engin…`
- `ACTION_KEYS` = `('noop', 'left', 'main', 'right')`
- `BUILTIN_MAIN_ENGINE_COST` = `0.3`
- `BUILTIN_SIDE_ENGINE_COST` = `0.03`
- `BUILTIN_TERMINAL_CRASH` = `-100.0`
- `BUILTIN_TERMINAL_REST` = `100.0`
- `ENV_ID` = `'LunarLander-v3'`
- `ENV_KWARGS` = `{'continuous': False}`
- `OBSERVATION_FIELDS` = `(ObservationField(index=0, key='x', label='Horizontal position', units='normalized', description='(x - W/2) / (W/2) with…`
- `OBS_KEYS` = `('x', 'y', 'vx', 'vy', 'angle', 'angular_velocity', 'left_contact', 'right_contact')`
- `ROBUSTNESS_KEYS` = `frozenset({'enable_wind', 'gravity', 'turbulence_power', 'wind_power'})`
- `TESTED_GYMNASIUM_VERSIONS` = `('1.4.0',)`
