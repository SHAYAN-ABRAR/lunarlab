# Reproducing LunarLab's results independently

A short path for someone who did not write LunarLab: install it from a release archive, check the installation,
re-evaluate a published policy, read the result, and send a report. About 15 minutes on a laptop; no GPU, no
account and no web interface needed. The full tutorial is [TUTORIAL.md](TUTORIAL.md); what each check means is in
[jmlr/REPRODUCIBILITY.md](jmlr/REPRODUCIBILITY.md).

## 1. Install from a release archive

A release is published as `lunarlab-<version>-src.tar.gz` with a `SHA256SUMS` file. Check the digest, extract,
and install the locked dependencies (Python 3.12; on Windows also 3.13):

```bash
sha256sum -c SHA256SUMS                       # Windows: Get-FileHash lunarlab-<version>-src.tar.gz
tar xzf lunarlab-<version>-src.tar.gz && cd lunarlab-<version>
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-ci.lock --torch-backend cpu    # Windows: -r requirements.lock
uv pip install --python .venv/bin/python --no-deps .
```

Until a release exists, a clone of the repository at a known commit works the same way (`git checkout <commit>`),
and `python tools/build_source_archive.py --rev <commit>` builds the archive a release would contain.

## 2. Check the installation

```bash
.venv/bin/python -m lunarlab --version
.venv/bin/python -m lunarlab doctor
.venv/bin/python -m lunarlab reproduce-smoke --training-determinism --report smoke.json
```

`--version` names the source revision and the numerical libraries; keep it for your report. `reproduce-smoke`
trains, checkpoints, reloads, validates, freezes, tests and exports a tiny run in a temporary folder and verifies
every link (exit status 0 = all checks passed).

## 3. Re-evaluate a published policy

The three published final tests ship in `examples/artifacts/`:

```bash
.venv/bin/python -m lunarlab reproduce-artifact --artifact examples/artifacts/ppo-hover-bonus-s0 --report hover.json
```

It verifies the files and the recorded evaluation, re-flies the 100 recorded test episodes and compares them
with the record.

## 4. Read the result

The first line of the output and the report's `status` say what kind of agreement you obtained:

| Status | Exit | Meaning |
|---|---:|---|
| `exact` | 0 | all five compared episode-summary fields match exactly (not full-trajectory identity) |
| `numerical-difference` | 3 | another platform: episodes differ numerically, no aggregate differs significantly from the record (expected on Linux; not a failure) |
| `unexpected-difference` | 1 | episodes differ on the recording platform and libraries — please report |
| `aggregate-disagreement` | 1 | a mean return or outcome rate differs significantly from the record — please report |
| `integrity-failure` | 1 | files, configuration, seeds, protocol or weights do not match the record — the artifact is not the published one |

Bit-identical results are expected only on the platform that recorded them; across operating systems the
report shows how far each episode moved and whether the published conclusions still hold. To see where your
platform's trajectories part from the recording platform's:

```bash
.venv/bin/python -m lunarlab trace-artifact --artifact examples/artifacts/ppo-hover-bonus-s0 --compare reports/jmlr/reproducibility/traces/ppo-hover-bonus-s0-windows.npz --report trace.json
```

## 5. Replay a learned-reward policy

The study's six learned-reward policies are in `examples/learned-reward-artifacts/`. Each carries the original
reward model it was trained with:

```bash
LUNARLAB_HOME="$(mktemp -d)" .venv/bin/python -m lunarlab reproduce-artifact --artifact examples/learned-reward-artifacts/20261015-235939-custom-s0-standard-0274 --report lr.json
```

- **Expected result:** `exact` on Windows with the locked libraries (about 25 seconds on a laptop CPU), and
  `numerical-difference` on Linux. The Linux results of continuous integration are in
  `reports/neurocomputing-2026-10-27/linux-replay/`.
- **Missing or corrupt model:** a missing or corrupt `reward_model/` file gives `integrity-failure` (exit 1)
  before any episode runs.
- **Data home:** the empty data home stays empty; the package needs nothing from your machine.

## 6. Reproduce a recorded figure

```bash
.venv/bin/python paper/neurocomputing/figures/build_figures.py    # "figures written: final_test_audit, ..."
.venv/bin/python paper/neurocomputing/check_manuscript.py --final # "OK"
```

- **What it builds:** the manuscript's figures, from the recorded results in a few seconds.
- **Figure 2:** every plotted value is re-derived from `docs/results/results.json`. The build stops if any
  differs.
- **Other figures:** compare `paper/neurocomputing/figures/*.values.json` with the evidence they cite. PDF bytes
  can differ under another Matplotlib or font version; the plotted values cannot.

## 7. Run the task-independent audit on CartPole

The generic layer runs a prespecified study on any registered Gymnasium task. The smoke protocol trains three
tiny CartPole policies in about a minute:

```bash
.venv/bin/python examples/cartpole_study.py --protocol examples/protocols/cartpole-smoke.json --out smoke-study --workers 2
.venv/bin/python -m lunarlab audit-artifact verify --artifact smoke-study/artifacts/failure-bonus-s7     # VERIFIED: ...
.venv/bin/python -m lunarlab audit-artifact reproduce --artifact smoke-study/artifacts/failure-bonus-s7  # EXACT: ...
```

The full study of 27 October 2026 uses
`reports/neurocomputing-2026-10-27/cartpole-study/protocol/protocol.json`. It has 15 policies of 100,096
transitions each, and took about 7 minutes with `--workers 5` on a 10-core laptop CPU (Intel i7-13620H). The
`cartpole-study/analyze.py` script there recomputes its results.

## 8. Add a custom reward term

A reward term is a pure function of one transition, wrapped in a `RewardTerm` with a JSON description:

```python
from lunarlab.audit import RewardTerm, audit_policy, get_adapter

def centred(t):  # pays for keeping the cart near the centre; t is a lunarlab.audit.Transition
    return 0.1 * max(0.0, 1.0 - abs(float(t.next_obs[0])) / 2.4)

term = RewardTerm("centred", centred, {"type": "custom", "scale": 0.1}, term_id="mylab.centred", version="1")
report = audit_policy(get_adapter("cartpole"), lambda o: int(o[2] > 0), [210000, 210001], gamma=0.98, terms={"centred": term})
print(report["aggregate"]["mean_training_return"], report["reward"]["provenance"]["implementation_identity"])
```

- **Rules for a term:** its output must be finite.
- **Provenance:** the report records the term's description digest and, separately, the digest and git status
  of the file defining `centred`. A function typed into an interactive session is reported as `incomplete`.
- **Using it in a study:** register a term factory on a task adapter (`lunarlab/audit/adapters.py`). Training on
  LunarLander with the full application is described in [TUTORIAL.md](TUTORIAL.md).

## Common errors

| Message | Cause | What to do |
|---|---|---|
| `AuditInputError: invalid seeds: ... booleans are not seeds` | A seed list holds `True`, `3.0` or `"7"`, or is empty, negative or duplicated | Pass plain nonnegative integers; nothing is converted |
| `NonFiniteValueError: reward term 'x' output must be finite` | A term returned NaN or infinity | Fix the term; the episode is not counted |
| `INTEGRITY-FAILURE (blocking)`, exit 1 | A packaged file, reward model or record no longer matches its digest | Use the original package; nothing was evaluated |
| `NUMERICAL-DIFFERENCE`, exit 3 | Another operating system or library build | Expected; read the per-episode differences in the report |
| `error: ... no manifest.json`, exit 2 | `audit-artifact` was pointed at a folder that is not an audit artifact | Pass the folder written by the study's export phase |

## 9. Send a report

Open a [reproducibility report](https://github.com/SHAYAN-ABRAR/lunarlab/issues/new?template=reproducibility_report.yml)
on GitHub, or fill in [jmlr/REPRODUCTION_REPORT_TEMPLATE.md](jmlr/REPRODUCTION_REPORT_TEMPLATE.md) and send it by
any means. Attach the JSON files written by `--report` and the output of `--version`. Reports that match exactly
are as useful as reports of differences; the template asks whether your report may be cited. A structured
exercise for an independent researcher is in [jmlr/COMMUNITY_EVIDENCE.md](jmlr/COMMUNITY_EVIDENCE.md).
