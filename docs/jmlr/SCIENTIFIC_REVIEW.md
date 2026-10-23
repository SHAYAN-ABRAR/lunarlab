# Independent scientific and software review

Review date: 19 October 2026. Base revision: `67440c664f658ccd589f7198ee2182d5820ca7c1`.

## Recommended positioning

Choose **B: a scientific evaluation and provenance framework for reward-shaped reinforcement learning**, expressed in the title “LunarLab: Auditable Reward-Design Experiments in Reinforcement Learning.” A reproducible reward-auditing platform is a useful secondary description if reproducibility is qualified. The visualization toolkit framing is too broad and places emphasis on interface polish rather than the research contribution.

One coherent argument: changing a reward creates several linked obligations—account for the changed objective, select on validation observations, protect the tested policy, and inspect discrepancies against task outcomes. LunarLab implements that process and exposes its evidence. It does not introduce an RL algorithm, a new statistical estimator, a universal reward-hacking detector, or a general-purpose multi-environment training platform.

## Strengths

- Shared reward-term functions and an explicit accounting identity reduce ambiguity between original and optimized reward. Episode totals remain accessible even when transitions are not stored.
- Frozen final-test copies, digest checks, explicit test exposure, and DQN replay restoration address concrete experimental failure modes.
- A supplied failure example is informative: all five hover-bonus PPO policies fail strict landing despite positive shaped returns, while the baseline has high task success.
- CLI, Python API, tutorial tests, source installation tests, cross-platform CI and three real example artifacts are stronger than a demonstration-only application.
- Numerical disagreements are now inspectable rather than silently ignored. This is useful even when exact reproduction fails.

## Likely reviewer objections and substantive responses

| Objection | Assessment | Most effective response |
|---|---|---|
| “This is a wrapper around SB3.” | Individual components are established; integration may still be useful software work | Show an independent researcher completing a reward-audit task and identify the resulting artifact chain. Give a minimal equivalent SB3 recipe and explain what bookkeeping remains manual |
| “Why is a LunarLander dashboard important to ML?” | The main workflow is narrow; UI polish alone is insufficient | Emphasize reward-design methodology; demonstrate one external extension through the generic API and disclose where portability ends |
| “There are no users.” | Currently supported by the absence of documented external evidence | Obtain genuine use/reproduction reports and documented maintenance responses; do not invent uptake |
| “Can I reproduce the plotted experiment?” | Per-policy summary calculations are reproducible, but most full run artifacts are missing | Export the existing selected models/evaluations with manifest digests; do not retrain to replace inconvenient results |
| “The reproduction gate proves equivalence.” | False: failure to reject a difference does not establish equivalence | Report effect sizes, paired intervals, outcome changes and trace scope. Use prespecified practical margins only in a future validation protocol |
| “Only five seeds?” | A reasonable demonstration, weak evidence for small performance gains | State uncertainty and avoid superiority claims. More seeds are optional unless claiming a subtle benefit |
| “PPO beats DQN.” | Existing reference budgets differ by approximately tenfold | Remove controlled-superiority interpretations. Matched-budget runs are optional and only needed for an algorithm-comparison claim |
| “Preference rewards do not use the task reward.” | False for these experiments | State that simulated labels and validation use original reward; no human study was established |
| “Memory/runtime overhead is universally tiny.” | Unsupported upper bound; historical memory scopes differ | Report measured ratios and conditions; rerun the patched benchmark before comparing training-only memory |

## Statistical audit

The IQM implementation trims `floor(n/4)` scores at either tail, as in SciPy's trimmed mean. With five policies it averages the middle three; with three it equals the mean. Each score is a mean across 100 fixed test seeds. Bootstrap intervals resample training runs, not 500 independent policies and not an arbitrary population of environments. Five training seeds provide limited interval resolution. A bootstrap interval `[0, 0]` after complete empirical separation is not proof that future improvement probability is zero. The episode-pooled performance profile is not identical to a multi-task rliable benchmark profile.

The primary four PPO groups have equal actual training budgets of 1,003,520 transitions. Selected checkpoints may be earlier. Baseline IQM is 268.5609 (stored 95% interval 255.3679–272.0027); time penalty 265.3267 (246.5342–268.7959); potential shaping 262.2668 (238.2673–274.1742); hover bonus −33.1273 (−53.9050–15.6145). Strict landings total 488/500, 468/500, 470/500 and 0/500, respectively. Hover timeouts total 400/500. These counts are reconstructed from per-policy summary rates and episode counts, not from all missing raw episode records.

Potential-based shaping preserves optimal policies under the relevant assumptions; it need not improve finite-budget PPO optimization. The hover result demonstrates a deliberately engineered reward failure in this configuration. It does not estimate detector sensitivity, generalization to unseen failure mechanisms, or real-world safety.

## Code and protocol audit

The accounting wrapper computes terms at every step but writes episode totals by default; step-level `info` and trace storage are opt-in. Terminal and truncated transitions are handled separately. Freeze verification protects the tested checkpoint against alias changes; it does not prevent a human from learning from previous test outcomes. DQN continuation restores replay and learning state, but neither algorithm restores complete simulator/RNG state. Cross-platform trace comparison supports a numerical dynamics discrepancy on the sampled traces; the mechanism is not uniquely identified.

Coverage is useful evidence, not a substitute for meaningful tests. Published coverage is about 86%; the CLI remains among the least-covered important surfaces. Prioritize failure paths involving missing IDs, corrupt artifacts, malformed protocols, interruption and source-install behavior before adding tests whose only purpose is a percentage target. MLOSS describes near-complete coverage as a review expectation, not a numeric eligibility cutoff.

## Proportionate next experiments

| Priority | Work | Compute and decision value |
|---|---|---|
| 1 | Export missing existing final-test artifacts; verify hashes and regenerate group summaries | No new training; closes the central evidence gap |
| 1 | Independent installation, supplied-policy evaluation, custom reward and generic API task | Small CPU jobs; directly tests usefulness and onboarding |
| 2 | Rerun the fixed 3×3 overhead benchmark on the final source revision, same documented machine | Nine 102,400-transition PPO runs; isolates reporting change without a large study |
| 2 | Trace a few prespecified additional test seeds, reporting first divergence and action agreement | Small inference jobs; refines the limited portability evidence |
| 3 | Demonstrate one additional task adapter through a real user use case | Modest task-dependent compute; do this only if it supports a credible generality claim |
| Optional | Matched-budget PPO/DQN or additional training seeds | Needed only for stronger algorithm/performance claims, not to decorate an MLOSS paper |

## Professionalism audit

| Existing wording or presentation | Problem | Revision |
|---|---|---|
| “honest statistics/experiments” | Self-congratulatory; not evidence | “separate reward accounting and uncertainty estimates” |
| “leak-proof evaluation” / protocol that “cannot leak” | An absolute guarantee the software cannot provide | “validated seed separation and recorded test exposure” |
| “all episodes bit-identical” | Broader than the five fields compared | “selected episode-summary fields match exactly” |
| “traces locate the cause” | Overstates identification of a numerical mechanism | “trace comparisons support a simulator-numerics explanation” |
| “at most 4% overhead” | Treats a measured value as an upper bound and mixes benchmark runs | Identify the run and report 1.056 loop / 1.228 workflow ratios |
| “every claim backed,” broad green checkmarks | Hides partial availability and unresolved human inputs | Claim-specific evidence and explicit limits |
| Stale “uncommitted” correction-branch statement beside later commits | Contradictory project status | One current source identity; old reports retained only as historical evidence |
| Local path inside a manuscript `\url{...}` | Non-resolving scholarly link | Project URL and repository-relative evidence mapping outside the paper |
| Author/editor TODOs and funding placeholders | Acceptable draft markers; unacceptable as completed submission details | Keep visible until supplied; never invent them |
| “AI ghost” / mission-control language | Fine for a demonstration, weak in the scientific abstract | Keep playful labels out of scholarly claims; no frontend redesign required |

The revised paper is precise rather than promotional. That editorial improvement cannot manufacture community adoption or missing raw evidence.
