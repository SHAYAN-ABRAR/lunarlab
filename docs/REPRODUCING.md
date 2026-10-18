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
| `exact` | 0 | every episode bit-identical to the record (expected on Windows with the locked libraries) |
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

## 5. Send a report

Open a [reproducibility report](https://github.com/SHAYAN-ABRAR/lunarlab/issues/new?template=reproducibility_report.yml)
on GitHub, or fill in [jmlr/REPRODUCTION_REPORT_TEMPLATE.md](jmlr/REPRODUCTION_REPORT_TEMPLATE.md) and send it by
any means. Attach the JSON files written by `--report` and the output of `--version`. Reports that match exactly
are as useful as reports of differences; the template asks whether your report may be cited.
