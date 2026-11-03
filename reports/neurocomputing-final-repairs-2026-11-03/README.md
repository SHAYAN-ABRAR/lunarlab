# Repairs after the Linux audit, 3 November 2026

An assistant-executed Linux audit (ChatGPT, in its own sandbox; 2 to 3 November 2026) validated the archive
candidate of 1 November (`a38d07f`). It confirmed the repairs of 1 November and found four things to fix or
disclose:

- the validator's two install commands wrote the same log, so the first was overwritten;
- one DQN policy's Linux replay disagrees significantly with its record, and stays blocking;
- the manuscript's "every named file is present" claim was too broad, as were its byte-identity and licence
  wording, and its "not merged" statement was stale;
- the third-party notice wrongly said that no third-party source is copied, and the archive drafts had faults.

This folder holds the repairs, their verification and the updated submission plan. **Historical evidence is
unchanged**, nothing was trained, and nothing was deposited, published or submitted. The branch is
`research/neurocomputing-final-repairs`, made from `main` at `05ca17f`.

| Path | What it holds |
|---|---|
| [PROGRESS_LOG.md](PROGRESS_LOG.md) | The dated log (UTC): starting state, every step and command |
| [received/](received/linux-audit-2026-11-03/RECEIVED.md) | The labelled subset of the Linux audit, checked against its own digests |
| [dqn-diagnostic/](dqn-diagnostic/README.md) | The policy that disagrees on Linux: the received reports summarized; its exact replays and trace on Windows; the pending Linux comparison |
| [archive/](archive/CANDIDATE.md) | The new archive candidate (`c0d9e5d`): its record, its own documents and `SHA256SUMS`, its licence map, and the build logs. Nothing was deposited |
| [validation/](validation/README.md) | The candidate's fresh-extraction validation on Windows, in both environment modes (every step passed; 38 of 38 replays exact), and three negative checks |
| [manuscript/](manuscript/VISUAL_REVIEW.md) | The two CI builds of the manuscript (logs, digests, the page-by-page review) and a local Tectonic build |
| [ci/](ci/run-41667323177-c0d9e5d/README.md) | CI of `c0d9e5d`: all six jobs passed; the Linux source archive is byte-identical to the Windows one |
| [integrity/](integrity/README.md) | The historical evidence compared with the inventory of 27 October: 2,359 of 2,359 unchanged |
| [tests/](tests/) | The local full suite (708 passed, on the base interpreter and in the project `.venv`) and the targeted tests, lint and checks |
| [package/](package/build_review_zip.py) | `build_review_zip.py`, which assembles and seals the review ZIP |
| [READINESS.md](READINESS.md) | What was repaired and verified, what is pending, the author's decisions |

The validator is [`tools/validate_review_package.py`](../../tools/validate_review_package.py); its regression tests
are in [`tests/test_validator_failures.py`](../../tests/test_validator_failures.py), and those of the manuscript
check in [`tests/test_manuscript_check.py`](../../tests/test_manuscript_check.py).
