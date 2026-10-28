# Readiness assessment: Neurocomputing research-strengthening revision

Written 28 October 2026, as evidence for the brief's reassessment. It is not a rating, and it does not
estimate acceptance. The manuscript is **not submission-ready**; the blockers are listed below.

| | |
|---|---|
| Branch | `research/neurocomputing-audit-evidence`, pushed. Not merged into `main` |
| Base | `932cf1c` (`main`, equal to `origin/main` on 27 October); the reviewed implementation `444a4c5` is its parent |
| Software revision the paper describes | `30bd3f6`, the last commit that changed library code. CI run 40694880778 passed all six jobs on it |
| Final commit and its CI | See the end of this file |

## 1. Did the generic contract defects actually reproduce, and were they fixed?

**They reproduced at runtime on the unmodified `932cf1c`.** See `contracts/candidates-before-932cf1c.json` and
`PROGRESS_LOG.md`, 15:40. `audit_policy`:

- ran booleans, fractional and integral floats, and numeric strings as seeds;
- ran duplicate episodes;
- returned a zero-episode report for an empty seed list;
- played a valid seed before Gymnasium refused a negative one.

The other reproduced defects:

- `seed_split_problems` accepted empty and negative lists and crashed on an unhashable entry.
- `PPO(seed=…)` silently replaced the CartPole example's environment seed roots, and later resets were
  unseeded.
- NaN or infinite terms and weights produced "complete" reports that were not valid JSON.
- Two terms with equal descriptions and payments of 1 and 1,000 had the same reward hash.

**Fixed in `3b96048`:** the seed, finite-value and seeding defects.

- **Old-API probe:** it fails 16 of 17 checks on `932cf1c`; the one that passes is a valid-input control. It
  passes 17 of 17 on the fixed code (`contracts/probe-*.txt`).
- **Tests:** `tests/test_audit_contracts.py` checks the contracts against sums calculated by hand on a tiny
  deterministic environment. It covers potential shaping at a termination, at a truncation and with both
  flags.
- **Seeding:** the example now seeds its environments after building PPO. The study workflow records the
  effective first-reset seeds and refuses to finish if they differ from the protocol.

**Reward identity: fixed in two steps, the second on 28 October.**

- **By design:** the legacy 16-hex hash keeps its meaning, so it still collides for that pair.
- **Schema 1 (`3b96048`):** the versioned provenance record added a full definition digest and each defining
  file's digest and git status. While the claims were checked on 28 October, `contracts/provenance_identity_check.py`
  showed that this record still could not tell the reproduced pair apart: two lambdas in one class body share
  a description, a file and a qualified name. Two closures of one factory could not be told apart either.
- **Schema 2 (`30bd3f6`):** it records each callable's first line, a digest of its own source text and its
  captured values, and tells all three tested pairs apart (`contracts/provenance-identity-*.txt`).
- **Still not identified:** two lambdas on one source line with equal captured values; changes in modules a
  term imports; module-level names it reads from other files; library versions. A captured value without a
  JSON form is reported as `incomplete`.

## 2. Can equivalent workflows reconstruct and check the same audit?

**On the designed cases, yes.** The protocol, specification, fault inventory, fixtures and the three programs
were hashed before the main run (`workflow-comparison/protocol/HASHES.sha256`).

- **W2 matches W3:** W2 is an independent implementation on SB3, Gymnasium and NumPy that does not import
  LunarLab. It reached the same S1–S10 status vector as W3 (LunarLab) on all 14 cases:
  - the clean control, accepted with an exact replay;
  - the cross-platform control, accepted as a permitted numerical difference;
  - all 12 faults, rejected through the targeted check before any episode ran.
- **W1 checks nothing:** W1, the conventional SB3 evaluation, attempted none of these checks. It evaluated
  100 episodes in every case and reported 500.0 ± 0 for the swapped checkpoint, as for the clean one.
- **Where LunarLab differs:** a competent SB3 user can write the same checks; W2 needed 277 counted lines.
  LunarLab supplies them as tested functions (W3 needed 152 lines for this neutral format) and as one command
  for its own artifacts.
- **Cost:** no cost difference can be claimed. The wall times were bimodal across runs, and the medians
  differ by less than the run-to-run variation.
- **Limits:**
  - one task, one policy and one recorded trajectory;
  - the faults were designed, and say nothing about how often faults occur;
  - the specification, W2, W3 and LunarLab were written by the same developer, assisted by AI tools;
  - researcher time and usability were not measured.

## 3. Did the second task run through the reusable API?

**Yes.** The CartPole study ran entirely through `lunarlab.audit`:

- an adapter;
- a protocol, hashed before training;
- PPO training with original-reward validation;
- the prespecified selection rule;
- freezing through the main pipeline's `freeze.immutable_copy`;
- digest-checked final tests;
- exported artifacts that `lunarlab audit-artifact` verifies before replaying them.

It covered 15 main runs and a labelled pilot, with 1,562,880 new training transitions. The analysis
reproduces byte for byte from the committed records (`cartpole-study/analyze.py records/main`). On Linux
CI, the generic example trains, exports and reproduces exactly.

**Limits:**

- **Ceiling effect:** the original and potential designs both reach the 500-step ceiling, so they cannot be
  ranked.
- **Expected by construction:** the flawed design (+1,000 for failing) is built to be exploited, so its failure
  demonstrates the audit records, not a discovery about CartPole.
- **Only the layer is generic:** resumable jobs, the registry, DQN, the web interface and the tuning and
  robustness studies remain LunarLander-specific.

## 4. What survives Linux replay?

The six learned-reward packages were replayed on Linux CI from an empty data home, with their bundled reward
models (run 40545198707).

- **Integrity:** every package passed its integrity checks.
- **Numerical differences:** every package shows them, as expected across operating systems.
  - signed median per-episode differences in original return are −0.00123 to +0.00021;
  - the largest single differences are 0.007, 0.013, 1.04, 10.0, 11.7 and 18.3;
  - outcome agreement is 99–100%.
- **Landing rates:** strict pad-landing rates are unchanged except one policy, at 35% versus 34% (one
  episode).
- **Aggregates:** no aggregate differs significantly in paired tests with Holm correction. This is not a
  test of equivalence.
- **Data home and refusals:** the data home stayed empty, and a missing model and a corrupt metadata file
  were refused before any episode.
- **Examples:** the three example packages also differ only numerically on Linux (CI run on `11145b3`), with
  unchanged landing rates.

**What does not survive:**

- **Bit identity:** there is none across platforms.
- **Coverage:** only 9 of the 38 policies have been replayed on Linux.
- **Platforms:** macOS was not tested.

## 5. Can an independent reader reproduce the figures?

**From the committed records, with one command** (`paper/neurocomputing/figures/build_figures.py`).

- **Manifests:** inputs and outputs are hashed in `MANIFEST.json`, and the plotted values are in
  `*.values.json`.
- **Figure 2:** its 20 policy values and four IQMs are re-derived from the unchanged historical summary; the
  build stops on any difference.
- **CartPole analysis:** it reproduces byte for byte from the committed records.
- **Not yet:** no one other than the author has done this.
- **Bytes:** PDF bytes depend on the Matplotlib and font versions; the plotted values do not.
- **Rerunning the experiments:** this needs the CartPole checkpoints and comparison fixtures, which are
  outside Git (digests recorded, all verified on 28 October). Retraining on another platform will not be
  bit-identical.

## 6. What remains unverified

- **Independent use:** no one outside the author has installed, run or reported on LunarLab. The exercise
  and report form in `docs/jmlr/COMMUNITY_EVIDENCE.md` have not yet been given to anyone.
- **Generality:** generality beyond LunarLander and one saturating classic-control task is unverified. So
  are faults outside the designed set.
- **Platforms:** cross-platform agreement is unverified for the 29 policies not replayed on Linux, and for
  macOS.
- **Precision:** five training seeds per design limit precision; rankings could change with more seeds,
  budgets or tasks.
- **Article type and fees:** whether Neurocomputing's OSP software article type is fee-free, and its format
  and length rules. Elsevier inquiry 261027-019124 has only an automatic acknowledgment, and no further
  inquiry was sent.
- **Local PDF build:** a local build was not possible, because the TeX binaries are blocked by Smart App
  Control, which was not bypassed. The PDF is built in CI with TeX Live 2023 (pdfLaTeX and BibTeX).

## 7. Practical blockers to submission

1. **Article type and fees:** fee-free OSP eligibility and the OSP format requirements are unresolved, so
   the article type is unconfirmed.
2. **Data deposit:** the research data (the 38-policy bundle, the CartPole checkpoints and the comparison
   fixtures) must be deposited with a persistent identifier, or the paper must state why it cannot be. The
   candidate and citation fields are in `ARCHIVE.md`; no deposit, DOI, tag or release exists.
3. **AI declaration:** the declaration of AI assistance is kept separately
   (`paper/neurocomputing/AI_Disclosure_For_Submission.tex`). Elsevier's policy requires it in the submitted
   manuscript.
4. **CRediT:** the guide requires a CRediT statement. It is missing, and the roles are the author's to state.
5. **Merge and release:** the evidence and code are on an unmerged review branch, so the availability
   statement can cite only that branch.

## 8. The smallest useful next step

The author should review the branch against `main` and decide whether to merge it. Then deposit the
`ARCHIVE.md` candidate to obtain an identifier, and replace the availability statement with that citation.
This removes blockers 2 and 5 without any new experiment.

For the evidence itself, the most informative next step is the independent-user exercise with one
researcher outside the project. It needs the author's decision to contact someone.

## Compute used

Details are in `PROGRESS_LOG.md`.

- **Research training:** 1,562,880 new transitions (pilot and main study) of the 2,000,000 allowed.
- **Including test fixtures:** about 1.89 million.
- **Local elapsed compute:** under one hour, against six allowed.
- **Other limits:** no paid services, and no retraining of the historical 38 policies.
