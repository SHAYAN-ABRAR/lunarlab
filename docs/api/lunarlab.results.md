# `lunarlab.results`

Source: [`lunarlab/results.py`](../../lunarlab/results.py)

Figures and tables for the results write-up (docs/RESULTS.md), generated only from stored data.

    python -m lunarlab results --experiment-ids <main>,<dqn>,<rlhf> --out docs/results

Everything is computed from the final-test evaluations (100 held-out episode seeds per
policy, frozen validation-selected checkpoints, original reward) via ``compare_runs``:
the same numbers the Compare page shows. Nothing is typed in by hand.

### `algorithm_rows(data: 'dict') -> 'list[list[dict]]'`

Reward designs trained with more than one algorithm at one shared budget (matched-budget
comparisons), each as its list of groups (algorithm x discount factor x training physics).

### `build_results(experiment_ids: 'list[str]', out_dir: 'Path', echo=<built-in function print>) -> 'dict'`

### `fig_algorithms(data: 'dict', out: 'Path') -> 'bool'`

Matched-budget algorithm comparison: learning curves against transitions and wall-clock time.

### `fig_curves(data: 'dict', out: 'Path') -> 'bool'`

### `fig_headline(data: 'dict', out: 'Path') -> 'bool'`

### `fig_learned(data: 'dict', out: 'Path') -> 'bool'`

### `fig_profiles(data: 'dict', out: 'Path') -> 'bool'`

### `fig_robustness(data: 'dict', out: 'Path') -> 'bool'`

### `make_showcase(recording_ids: 'list[str]', labels: 'list[str]', out: 'Path', *, frames_dir: 'Path | None' = None, cols: 'int' = 2, tile: 'tuple[int, int]' = (360, 240), step: 'int' = 3, max_steps: 'int' = 750, frame_ms: 'int' = 60, colors: 'int' = 96, quality: 'int' = 70) -> 'dict'`

Compose several recorded flights side by side into one looping animation.

The format follows ``out``'s extension: ``.gif`` (palette of ``colors``) or ``.webp`` (lossy,
``quality``; far smaller for the shaded 3-D frames).

Frames come from the real simulator footage (each recording's MP4; every ``step``-th frame is kept,
50 fps → ~16.7 fps), or, with ``frames_dir``, from the 3-D reconstruction captured by
``frontend/tools/capture3d.mjs`` (``<frames_dir>/<recording id>/*.jpg`` + ``meta.json``). When a
flight's episode ends, its tile shows the outcome and the episode's original return.

### `tables_markdown(data: 'dict') -> 'str'`

## Constants

- `ALGO_COLORS` = `{'ppo': '#3987e5', 'dqn': '#d95926'}`
- `CONDITIONS` = `{'wind-5': {'label': 'Light wind (5, turbulence 0.5)', 'env': {'enable_wind': True, 'wind_power': 5.0, 'turbulence_power…`
- `LEARNED_COLORS` = `['#8a63d2', '#4d4d4d', '#b07aa1']`
- `PRESET_COLORS` = `{'baseline': '#3987e5', 'time-penalty': '#c98500', 'hover-bonus': '#d55181', 'potential': '#008300', 'custom': '#8494a8'…`
- `PRESET_LINESTYLES` = `{'baseline': '-', 'time-penalty': (0, (6, 3)), 'hover-bonus': (0, (2, 3)), 'potential': (0, (10, 4)), 'custom': (0, (1, …`
- `PRESET_MARKERS` = `{'baseline': 'o', 'time-penalty': 's', 'hover-bonus': '^', 'potential': 'D', 'custom': 'x'}`
- `VARIANT_LINESTYLES` = `['-', (0, (6, 3)), (0, (2, 2)), (0, (8, 3, 2, 3))]`
