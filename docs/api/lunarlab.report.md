# `lunarlab.report`

Source: [`lunarlab/report.py`](../../lunarlab/report.py)

Markdown + HTML experiment report generated only from stored data.

Figures (matplotlib, Agg backend):

* training curves: original vs training return per run (rolling mean);
* outcomes: stacked outcome rates per run (evaluation split);
* behaviour: hover fraction and main-engine fraction per run;
* seed variability: one dot per training seed, per reward configuration.

Missing data is reported as missing; nothing is filled in.

### `build_report(run_ids: 'list[str]', *, title: 'str', report_id: 'str', split: 'str' = 'test', out_root: 'Path | None' = None) -> 'dict[str, Any]'`

### `figure_behaviour(data: 'dict', out: 'Path') -> 'bool'`

### `figure_outcomes(data: 'dict', out: 'Path') -> 'bool'`

### `figure_seed_variability(data: 'dict', out: 'Path') -> 'bool'`

### `figure_training_curves(data: 'dict', out: 'Path') -> 'bool'`

### `render_html(md: 'str', title: 'str') -> 'str'`

Minimal Markdown → HTML for this report's own constructs (headings, tables, lists, images).

### `render_markdown(data: 'dict', *, title: 'str', figs: 'dict[str, str]') -> 'str'`

### `render_portfolio(data: 'dict') -> 'str'`

Portfolio summary template. Numbers appear only if real final-test evaluations exist.

SMOKE runs never count. Each figure states its evidence (number of training seeds,
episodes, split) so it cannot be quoted without context.

## Constants

- `NOT_MEASURED` = `'[not yet measured]'`
- `OUTCOME_COLORS` = `{'pad': '#3987e5', 'off_pad': '#199e70', 'crash': '#d95926', 'oob': '#9085e9', 'timeout': '#c98500'}`
- `PRESET_COLORS` = `{'baseline': '#3987e5', 'time-penalty': '#c98500', 'hover-bonus': '#d55181', 'potential': '#008300', 'custom': '#8494a8'…`
- `PRESET_LINESTYLES` = `{'baseline': '-', 'time-penalty': (0, (6, 3)), 'hover-bonus': (0, (2, 3)), 'potential': (0, (10, 4)), 'custom': (0, (1, …`
- `PRESET_MARKERS` = `{'baseline': 'o', 'time-penalty': 's', 'hover-bonus': '^', 'potential': 'D', 'custom': 'x'}`
