# Manuscript figures: sources, inputs and conventions

Every figure is built by one command:

```bash
python paper/neurocomputing/figures/build_figures.py
```

- **Hashes:** `MANIFEST.json` holds the SHA-256 of every input and output, together with the Python,
  Matplotlib and NumPy versions.
- **Plotted values:** each `<figure>.values.json` holds exactly what was plotted.
- **Captions:** the captions are in `../main.tex`, under the label given below.
- **Checks:** `python paper/neurocomputing/check_manuscript.py --final` compares the included files with the
  manifest.
- **What a rebuild may change:** another Matplotlib or font version can change the PDF bytes, but not the
  plotted values.

| Figure | Files | Inputs | What is plotted, and how |
|---|---|---|---|
| 1 (`fig:architecture`) | `architecture.{pdf,svg,png}`, `architecture.values.json` | None: a node list in `build_figures.py` | The stages of the reusable core, the checks between them and the LunarLander application. Every function the figure names is checked to exist (`importlib`) before drawing. Solid arrows are data flow, diamonds are checks, dashed arrows are the application's connections |
| 2 (`fig:audit`) | `final_test_audit.{pdf,svg}`, `final_test_audit.source.json`, `final_test_audit.verification.json` | `docs/results/results.json` | The historical figure, copied byte for byte from `paper/jmlr-mloss/figures` (drawn there by `build_audit_figure.py`). The build re-derives all 20 policy values and the four IQMs from the input and stops on any difference. Vertical displacement only separates overlapping markers |
| 3 (`fig:comparison`) | `workflow_comparison.*` | `E/workflow-comparison/results/summary.json`, `E/workflow-comparison/protocol/fault_inventory.json` | One row per designed case (2 controls, 12 faults) and one column per program. Outcomes are shown by symbol and text as well as colour: ✓ accepted, ✗ with the rejecting check, — not attempted. No warned or missed outcome occurred in W2 or W3 |
| 4 (`fig:cartpole`) | `cartpole_study.*` | `E/cartpole-study/results/results.json` | Five policies per design, each the mean over the same 100 test seeds, offset vertically in seed order. Each design's mean and its 95% percentile bootstrap interval over policies (10,000 resamples, seed 0) are shown; every interval is narrower than its marker (at most 0.172 units). Panel (c) is each design's own training reward |
| A.1 (`fig:linux`) | `linux_replay.*` | The six `E/linux-replay/run-40545198707-dea292c/reproduce-*-linux.json` reports | (a) Every one of the 600 paired per-episode differences, zeros included, on a symmetric log axis that is linear within ±10⁻³. Jitter is vertical only, and bars mark the medians. (b) The recorded and Linux pad-landing rates |

`E/` is `reports/neurocomputing-2026-10-27/`.

## Conventions

- **Width:** Figures 1, 3, 4 and A.1 are drawn 5.39 inches wide, the manuscript's text width of 390 pt.
- **Text size:** these figures' text is at least 9 pt, and they are included at full width, so they print at
  their drawn size. Figure 2 was drawn 6.0 inches wide with text of at least 10 pt; its smallest text prints at
  9.03 pt.
- **Colours:** the Okabe–Ito palette. Meaning never depends on colour alone.
- **Formats:** PDF with embedded TrueType fonts, and SVG with text as paths. SVG line endings are normalized to
  LF, so the bytes do not depend on the platform.
