# Command-line reference

Generated from the parser in `lunarlab/cli.py`. Run any command with `--help` for the same text.

```text
usage: python -m lunarlab [-h] [--version]
                          {doctor,version,random-demo,heuristic-demo,train,resume,stop,evaluate,record,compare,report,suite,run-experiment,rlhf-dataset,reward-model,rlhf-active,rlhf-study,tune,tune-resume,tune-status,tune-cancel,tune-apply,record-showcase,results,showcase,warm-restart,test-status,freeze-migrate,reclassify-outcomes,export-demo,reproduce-smoke,export-artifact,reproduce-artifact,overhead-benchmark,robustness,robustness-run,train-run,sweep,runs,rescore,benchmark,reward,serve,processes,worker}
                          ...
```

## `benchmark`

measure throughput before changing worker counts

```text
usage: python -m lunarlab benchmark [-h] [--n-envs N_ENVS] [--seconds SECONDS] [--threads THREADS]
                                    [--no-ppo]
```

| Argument | Description |
|---|---|
| `--n-envs` |  (default: `1,2,4,8`) |
| `--seconds` |  (default: `3.0`) |
| `--threads` |  (default: `1`) |
| `--no-ppo` |  |

## `compare`

compare runs

```text
usage: python -m lunarlab compare [-h] [--experiment-id EXPERIMENT_ID] [--run-ids RUN_IDS]
                                  [--split {validation,test}] [--json]
```

| Argument | Description |
|---|---|
| `--experiment-id` |  |
| `--run-ids` | comma-separated run ids |
| `--split` |  Choices: validation, test. (default: `test`) |
| `--json` |  |

## `doctor`

check the installation

```text
usage: python -m lunarlab doctor [-h]
```

## `evaluate`

evaluate a checkpoint with the original reward

```text
usage: python -m lunarlab evaluate [-h] --run-id RUN_ID --split {validation,test}
                                   [--checkpoint CHECKPOINT]
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |
| `--split` | required.  Choices: validation, test. |
| `--checkpoint` | best | final | latest | <file name> (default: `best`) |

## `export-artifact`

copy a run's tested checkpoint, config and recorded final test into a reproduction package

```text
usage: python -m lunarlab export-artifact [-h] --run-id RUN_ID --out OUT
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |
| `--out` | required. new folder to create |

## `export-demo`

write a static, read-only snapshot of results for the hosted demo

```text
usage: python -m lunarlab export-demo [-h] --experiment-ids EXPERIMENT_IDS [--run-ids RUN_IDS]
                                      [--out OUT] [--draft]
```

| Argument | Description |
|---|---|
| `--experiment-ids` | required.  |
| `--run-ids` | additional runs to include |
| `--out` |  (default: `demo/api`) |
| `--draft` | allow uncommitted source changes; the snapshot is labelled a draft (a release export refuses them) |

## `freeze-migrate`

give legacy freeze records an immutable artifact (only if the bytes are intact)

```text
usage: python -m lunarlab freeze-migrate [-h] [--experiment-id EXPERIMENT_ID] [--run-ids RUN_IDS]
                                         [--all] [--dry-run]
```

| Argument | Description |
|---|---|
| `--experiment-id` |  |
| `--run-ids` |  |
| `--all` |  |
| `--dry-run` | report what would happen; change nothing |

## `heuristic-demo`

record one episode of Gymnasium's HEURISTIC controller

```text
usage: python -m lunarlab heuristic-demo [-h] [--episode-seed EPISODE_SEED]
```

| Argument | Description |
|---|---|
| `--episode-seed` |  (default: `20000`) |

## `overhead-benchmark`

measure LunarLab's instrumentation overhead against plain SB3 (time, memory, artifacts)

```text
usage: python -m lunarlab overhead-benchmark [-h] [--profile {smoke,standard,comprehensive}]
                                             [--transitions TRANSITIONS] [--repeats REPEATS]
                                             [--torch-threads TORCH_THREADS] [--out OUT] [--yes]
```

| Argument | Description |
|---|---|
| `--profile` |  Choices: smoke, standard, comprehensive. (default: `smoke`) |
| `--transitions` | override the profile's transitions per run |
| `--repeats` | override the profile's repetitions per configuration |
| `--torch-threads` |  (default: `1`) |
| `--out` | new output folder (default reports/jmlr/benchmarks/<profile>-<time>) |
| `--yes` | required for the comprehensive profile |

## `processes`

list (or terminate) this project's backend/worker processes

```text
usage: python -m lunarlab processes [-h] [--terminate]
```

| Argument | Description |
|---|---|
| `--terminate` | terminate them (no stop checkpoint is written) |

## `random-demo`

record one RANDOM-policy episode

```text
usage: python -m lunarlab random-demo [-h] [--episode-seed EPISODE_SEED]
                                      [--action-seed ACTION_SEED]
```

| Argument | Description |
|---|---|
| `--episode-seed` |  (default: `20000`) |
| `--action-seed` |  |

## `reclassify-outcomes`

derived outcome-classifier-v2 report for version-1 evaluations (files are never modified)

```text
usage: python -m lunarlab reclassify-outcomes [-h] [--experiment-ids EXPERIMENT_IDS]
                                              [--experiment-id EXPERIMENT_ID] [--run-ids RUN_IDS]
                                              [--out OUT]
```

| Argument | Description |
|---|---|
| `--experiment-ids` |  |
| `--experiment-id` |  |
| `--run-ids` |  |
| `--out` | directory for the derived report; without it nothing is written |

## `record`

record one episode of a run's checkpoint

```text
usage: python -m lunarlab record [-h] --run-id RUN_ID --episode-seed EPISODE_SEED
                                 [--checkpoint CHECKPOINT]
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |
| `--episode-seed` | required.  |
| `--checkpoint` |  (default: `best`) |

## `record-showcase`

record every reward group's policy on the same episode seeds

```text
usage: python -m lunarlab record-showcase [-h] --experiment-id EXPERIMENT_ID [--seeds SEEDS]
                                          [--training-seed TRAINING_SEED] [--references]
```

| Argument | Description |
|---|---|
| `--experiment-id` | required.  |
| `--seeds` | episode seeds (final-test seeds start at 20000) (default: `20000,20001`) |
| `--training-seed` | which training seed's policy to record per group |
| `--references` | also record the heuristic and random policies |

## `report`

write a Markdown/HTML report

```text
usage: python -m lunarlab report [-h] [--experiment-id EXPERIMENT_ID] [--run-ids RUN_IDS]
                                 [--split {validation,test}] [--title TITLE]
```

| Argument | Description |
|---|---|
| `--experiment-id` |  |
| `--run-ids` | comma-separated run ids |
| `--split` |  Choices: validation, test. (default: `test`) |
| `--title` |  |

## `reproduce-artifact`

verify a reproduction package and re-evaluate its checkpoint on the recorded test seeds

```text
usage: python -m lunarlab reproduce-artifact [-h] --artifact ARTIFACT [--episodes EPISODES]
                                             [--tolerance TOLERANCE] [--report REPORT]
```

| Argument | Description |
|---|---|
| `--artifact` | required. folder written by export-artifact |
| `--episodes` | only the first N recorded seeds (default: all) |
| `--tolerance` | absolute tolerance on returns (default 0: bit-identical) |
| `--report` | write the JSON report to this file |

## `reproduce-smoke`

bounded end-to-end reproducibility check in an isolated temporary home (no web UI needed)

```text
usage: python -m lunarlab reproduce-smoke [-h] [--transitions TRANSITIONS] [--seed SEED]
                                          [--preset {baseline,time-penalty,hover-bonus,potential}]
                                          [--algo {ppo,dqn}] [--training-determinism]
                                          [--workdir WORKDIR] [--keep] [--report REPORT]
```

| Argument | Description |
|---|---|
| `--transitions` |  (default: `4096`) |
| `--seed` |  |
| `--preset` |  Choices: baseline, time-penalty, hover-bonus, potential. (default: `potential`) |
| `--algo` |  Choices: ppo, dqn. (default: `ppo`) |
| `--training-determinism` | train the same configuration twice and compare weights and episodes |
| `--workdir` | use this (new) folder instead of a temporary one |
| `--keep` | keep the working folder for inspection |
| `--report` | write the JSON report to this file |

## `rescore`

Reward Stress Test: re-score a recorded trajectory

```text
usage: python -m lunarlab rescore [-h] --recording-id RECORDING_ID [--presets PRESETS]
                                  [--gamma GAMMA]
```

| Argument | Description |
|---|---|
| `--recording-id` | required.  |
| `--presets` |  (default: `baseline,time-penalty,hover-bonus,potential`) |
| `--gamma` |  (default: `0.999`) |

## `results`

figures and tables for the results write-up (final-test data only)

```text
usage: python -m lunarlab results [-h] --experiment-ids EXPERIMENT_IDS [--out OUT]
```

| Argument | Description |
|---|---|
| `--experiment-ids` | required.  |
| `--out` |  (default: `docs/results`) |

## `resume`

continue a stopped/interrupted run from a checkpoint

```text
usage: python -m lunarlab resume [-h] --run-id RUN_ID [--checkpoint CHECKPOINT]
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |
| `--checkpoint` |  (default: `latest`) |

## `reward`

export a preset or validate a reward configuration file

```text
usage: python -m lunarlab reward [-h] [--preset {baseline,time-penalty,hover-bonus,potential}]
                                 [--file FILE] [--output OUTPUT]
                                 {export,validate}
```

| Argument | Description |
|---|---|
| `action` | required.  Choices: export, validate. |
| `--preset` |  Choices: baseline, time-penalty, hover-bonus, potential. (default: `baseline`) |
| `--file` |  |
| `--output, -o` |  |

## `reward-model`

fit a reward model to a dataset's preferences

```text
usage: python -m lunarlab reward-model [-h] --dataset-id DATASET_ID [--pairs PAIRS]
                                       [--include-human] [--seed SEED] [--members MEMBERS]
```

| Argument | Description |
|---|---|
| `--dataset-id` | required.  |
| `--pairs` | simulated-human comparisons (default: `3000`) |
| `--include-human` | also use the labels given in the UI |
| `--seed` |  |
| `--members` | ensemble size (bootstrap resamples; 1 = one network) (default: `1`) |

## `rlhf-active`

active vs random preference selection (simulated labeller)

```text
usage: python -m lunarlab rlhf-active [-h] --dataset-id DATASET_ID [--strategies STRATEGIES]
                                      [--seeds SEEDS] [--budget BUDGET] [--initial INITIAL]
                                      [--batch BATCH] [--members MEMBERS]
                                      [--candidates CANDIDATES] [--register]
```

| Argument | Description |
|---|---|
| `--dataset-id` | required.  |
| `--strategies` |  (default: `random,disagreement`) |
| `--seeds` |  (default: `0,1,2`) |
| `--budget` | labels per run (default: `1000`) |
| `--initial` | random labels before the first selection (default: `100`) |
| `--batch` | labels selected per round (default: `100`) |
| `--members` | ensemble size (default: `5`) |
| `--candidates` | random candidate pairs scored per round (default: `2000`) |
| `--register` | register each final ensemble as a reward model |

## `rlhf-dataset`

collect flight segments for preference labelling

```text
usage: python -m lunarlab rlhf-dataset [-h] [--from-experiment FROM_EXPERIMENT]
                                       [--source-seeds SOURCE_SEEDS] [--episodes EPISODES]
```

| Argument | Description |
|---|---|
| `--from-experiment` | also use checkpoints of this experiment's baseline/hover-bonus runs |
| `--source-seeds` |  (default: `0,1`) |
| `--episodes` | episodes per source policy (default: `20`) |

## `rlhf-study`

preferences -> reward models -> PPO on the learned reward

```text
usage: python -m lunarlab rlhf-study [-h] [--dataset-id DATASET_ID]
                                     [--from-experiment FROM_EXPERIMENT]
                                     [--source-seeds SOURCE_SEEDS] [--episodes EPISODES]
                                     [--pairs PAIRS] [--include-human] [--rm-seed RM_SEED]
                                     [--members MEMBERS] [--reward-models REWARD_MODELS]
                                     [--seeds SEEDS] [--profile {smoke,standard,extended}]
                                     [--name NAME] [--parallel PARALLEL] [--create-only]
```

| Argument | Description |
|---|---|
| `--dataset-id` | reuse an existing dataset instead of collecting a new one |
| `--from-experiment` | use checkpoints of this experiment's baseline/hover-bonus runs as data sources |
| `--source-seeds` |  (default: `0,1`) |
| `--episodes` | episodes per source policy (default: `20`) |
| `--pairs` | comparison counts, one reward model each (default: `300,3000`) |
| `--include-human` | also use the labels given in the UI |
| `--rm-seed` |  |
| `--members` | reward-model ensemble size (default: `1`) |
| `--reward-models` | train on these existing reward models instead (comma-separated ids) |
| `--seeds` | PPO training seeds per reward model (default: `0,1,2`) |
| `--profile` |  Choices: smoke, standard, extended. (default: `standard`) |
| `--name` |  (default: `rlhf-study`) |
| `--parallel` |  (default: `1`) |
| `--create-only` |  |

## `robustness`

evaluate frozen checkpoints under wind/gravity they never trained on

```text
usage: python -m lunarlab robustness [-h] [--experiment-id EXPERIMENT_ID] [--run-ids RUN_IDS]
                                     [--conditions CONDITIONS] [--episodes EPISODES]
                                     [--parallel PARALLEL]
```

| Argument | Description |
|---|---|
| `--experiment-id` |  |
| `--run-ids` |  |
| `--conditions` | comma-separated; default: all |
| `--episodes` |  (default: `50`) |
| `--parallel` |  (default: `1`) |

## `robustness-run`

==SUPPRESS==

```text
usage: python -m lunarlab robustness-run [-h] --run-id RUN_ID --conditions CONDITIONS
                                         [--episodes EPISODES]
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |
| `--conditions` | required.  |
| `--episodes` |  (default: `50`) |

## `run-experiment`

train/resume the unfinished runs of an experiment, then final-test them

```text
usage: python -m lunarlab run-experiment [-h] --experiment-id EXPERIMENT_ID [--parallel PARALLEL]
                                         [--no-test]
```

| Argument | Description |
|---|---|
| `--experiment-id` | required.  |
| `--parallel` |  (default: `1`) |
| `--no-test` |  |

## `runs`

list runs

```text
usage: python -m lunarlab runs [-h]
```

## `serve`

run the web application (loopback only by default)

```text
usage: python -m lunarlab serve [-h] [--host HOST] [--port PORT]
```

| Argument | Description |
|---|---|
| `--host` |  (default: `127.0.0.1`) |
| `--port` |  (default: `8765`) |

## `showcase`

compose recorded flights side by side (GIF or animated WebP)

```text
usage: python -m lunarlab showcase [-h] --recordings RECORDINGS --labels LABELS
                                   [--frames-dir FRAMES_DIR] --out OUT [--tile-width TILE_WIDTH]
                                   [--max-steps MAX_STEPS] [--colors COLORS] [--quality QUALITY]
```

| Argument | Description |
|---|---|
| `--recordings` | required. comma-separated recording ids |
| `--labels` | required. one label per recording, separated by '|' |
| `--frames-dir` | 3-D frames from frontend/tools/capture3d.mjs (default: simulator footage) |
| `--out` | required. .gif or .webp |
| `--tile-width` |  (default: `360`) |
| `--max-steps` | footage only: cut long episodes here (default: `600`) |
| `--colors` | GIF palette size (default: `96`) |
| `--quality` | WebP quality (0-100) (default: `70`) |

## `stop`

ask a running training to stop at the next safe boundary

```text
usage: python -m lunarlab stop [-h] --run-id RUN_ID
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |

## `suite`

multi-seed suite: presets × seeds, then final test evaluation

```text
usage: python -m lunarlab suite [-h] [--presets PRESETS] [--seeds SEEDS]
                                [--profile {smoke,standard,extended}] [--name NAME] [--yes]
                                [--create-only] [--no-test] [--parallel PARALLEL]
                                [--algo {ppo,dqn}] [--algos ALGOS] [--gammas GAMMAS]
                                [--holdout-seeds HOLDOUT_SEEDS]
                                [--physics {fixed,randomized,both}]
                                [--wind-probability WIND_PROBABILITY] [--wind-power WIND_POWER]
                                [--turbulence TURBULENCE] [--gravity GRAVITY]
                                [--total-transitions TOTAL_TRANSITIONS]
                                [--checkpoint-every CHECKPOINT_EVERY]
                                [--validation-every VALIDATION_EVERY]
```

| Argument | Description |
|---|---|
| `--presets` |  (default: `baseline,time-penalty,hover-bonus,potential`) |
| `--seeds` |  (default: `0,1,2`) |
| `--profile` |  Choices: smoke, standard, extended. (default: `standard`) |
| `--name` |  (default: `reward-shaping-suite`) |
| `--yes` |  |
| `--create-only` | create the runs; train them later (e.g. from the UI) |
| `--no-test` | skip the final test evaluation |
| `--parallel` | train up to N runs at once (one CPU core each) (default: `1`) |
| `--algo` |  Choices: ppo, dqn. (default: `ppo`) |
| `--algos` | several algorithms, e.g. ppo,dqn: one variant each, with exactly matched budgets |
| `--gammas` | discount-factor ablation, e.g. 0.99,0.999: one variant per value |
| `--holdout-seeds` | START:COUNT final-test seeds never used before (an untouched holdout for confirmatory claims) |
| `--physics` | training physics: fixed (default) or randomized wind/turbulence/gravity per episode Choices: fixed, randomized, both. (default: `fixed`) |
| `--wind-probability` | share of training episodes with wind (0-1) |
| `--wind-power` | uniform range low,high (0-20) |
| `--turbulence` | uniform range low,high (0-2) |
| `--gravity` | uniform range low,high in (-12, 0), e.g. --gravity=-11,-9 |
| `--total-transitions` | override the profile's budget (labelled 'custom') |
| `--checkpoint-every` |  |
| `--validation-every` |  |

## `sweep`

explicit development sweep over hover-bonus weights

```text
usage: python -m lunarlab sweep [-h] [--bonus BONUS] [--seeds SEEDS]
                                [--profile {smoke,standard,extended}] [--name NAME] [--yes]
                                [--create-only]
```

| Argument | Description |
|---|---|
| `--bonus` |  (default: `0.25,0.5,1,2`) |
| `--seeds` |  (default: `0`) |
| `--profile` |  Choices: smoke, standard, extended. (default: `standard`) |
| `--name` |  (default: `hover-bonus-sweep`) |
| `--yes` |  |
| `--create-only` |  |

## `test-status`

frozen checkpoint, final-test attempts and completion of a run

```text
usage: python -m lunarlab test-status [-h] --run-id RUN_ID
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |

## `train`

create a run and train it in this terminal

```text
usage: python -m lunarlab train [-h]
                                (--preset {baseline,time-penalty,hover-bonus,potential} | --reward-config REWARD_CONFIG)
                                [--profile {smoke,standard,extended}] [--seed SEED]
                                [--total-transitions TOTAL_TRANSITIONS] [--n-envs N_ENVS]
                                [--vec-env {dummy,subproc}] [--device {cpu,cuda,auto}]
                                [--threads THREADS] [--experiment-id EXPERIMENT_ID]
                                [--label LABEL] [--yes] [--algo {ppo,dqn}] [--gamma GAMMA]
                                [--physics {fixed,randomized}]
                                [--wind-probability WIND_PROBABILITY] [--wind-power WIND_POWER]
                                [--turbulence TURBULENCE] [--gravity GRAVITY]
```

| Argument | Description |
|---|---|
| `--preset` |  Choices: baseline, time-penalty, hover-bonus, potential. |
| `--reward-config` | YAML/JSON reward configuration file |
| `--profile` |  Choices: smoke, standard, extended. (default: `smoke`) |
| `--seed` |  |
| `--total-transitions` |  |
| `--n-envs` |  |
| `--vec-env` |  Choices: dummy, subproc. |
| `--device` |  Choices: cpu, cuda, auto. |
| `--threads` |  |
| `--experiment-id` |  |
| `--label` |  |
| `--yes` | skip confirmation for EXTENDED |
| `--algo` | PPO (default) or DQN (Zoo settings) Choices: ppo, dqn. (default: `ppo`) |
| `--gamma` | discount factor (default: the algorithm's reference value) |
| `--physics` | training physics: fixed (default) or randomized wind/turbulence/gravity per episode Choices: fixed, randomized. (default: `fixed`) |
| `--wind-probability` | share of training episodes with wind (0-1) |
| `--wind-power` | uniform range low,high (0-20) |
| `--turbulence` | uniform range low,high (0-2) |
| `--gravity` | uniform range low,high in (-12, 0), e.g. --gravity=-11,-9 |

## `train-run`

train an existing run that has not been started yet

```text
usage: python -m lunarlab train-run [-h] --run-id RUN_ID
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |

## `tune`

Optuna study: tune algorithm settings and reward weights on validation

```text
usage: python -m lunarlab tune [-h] [--name NAME] [--algo {ppo,dqn}]
                               [--preset {baseline,time-penalty,hover-bonus,potential}]
                               [--params PARAMS] [--trials TRIALS] [--transitions TRANSITIONS]
                               [--validation-every VALIDATION_EVERY] [--warmup WARMUP]
                               [--startup-trials STARTUP_TRIALS] [--seed SEED] [--timeout TIMEOUT]
                               [--create-only]
```

| Argument | Description |
|---|---|
| `--name` |  (default: `study`) |
| `--algo` |  Choices: ppo, dqn. (default: `ppo`) |
| `--preset` |  Choices: baseline, time-penalty, hover-bonus, potential. (default: `baseline`) |
| `--params` | comma-separated, e.g. ppo.learning_rate,reward.potential.alpha (default: a small set) |
| `--trials` |  (default: `20`) |
| `--transitions` | training budget of each trial (default: `200000`) |
| `--validation-every` |  (default: `25000`) |
| `--warmup` | no pruning before this many transitions (default: 2 validations) |
| `--startup-trials` | trials before the sampler and pruner kick in (default: `4`) |
| `--seed` | sampler seed |
| `--timeout` | start no new trial after N seconds (resumable) |
| `--create-only` |  |

## `tune-apply`

create normal runs from a study's best settings (then train + test)

```text
usage: python -m lunarlab tune-apply [-h] --study-id STUDY_ID [--seeds SEEDS]
                                     [--profile {smoke,standard,extended}] [--name NAME]
                                     [--parallel PARALLEL] [--create-only]
                                     [--holdout-seeds HOLDOUT_SEEDS]
```

| Argument | Description |
|---|---|
| `--study-id` | required.  |
| `--seeds` |  (default: `0,1,2`) |
| `--profile` |  Choices: smoke, standard, extended. (default: `standard`) |
| `--name` |  |
| `--parallel` |  (default: `1`) |
| `--create-only` |  |
| `--holdout-seeds` | START:COUNT final-test seeds never used before (keeps the new runs confirmatory) |

## `tune-cancel`

stop a running tuning study at the next safe boundary

```text
usage: python -m lunarlab tune-cancel [-h] --study-id STUDY_ID
```

| Argument | Description |
|---|---|
| `--study-id` | required.  |

## `tune-resume`

continue a tuning study (after a cancel, timeout or crash)

```text
usage: python -m lunarlab tune-resume [-h] --study-id STUDY_ID [--trials TRIALS]
                                      [--timeout TIMEOUT]
```

| Argument | Description |
|---|---|
| `--study-id` | required.  |
| `--trials` | at most this many more trials in this session |
| `--timeout` |  |

## `tune-status`

list tuning studies, or show one study's trials

```text
usage: python -m lunarlab tune-status [-h] [--study-id STUDY_ID]
```

| Argument | Description |
|---|---|
| `--study-id` |  |

## `version`

software identity: version, source revision, Python, dependencies

```text
usage: python -m lunarlab version [-h] [--json]
```

| Argument | Description |
|---|---|
| `--json` | machine-readable output |

## `warm-restart`

create a NEW run initialised from a checkpoint's weights (not a resume; lineage recorded)

```text
usage: python -m lunarlab warm-restart [-h] --run-id RUN_ID [--checkpoint CHECKPOINT] [--confirm]
                                       [--label LABEL] [--train]
```

| Argument | Description |
|---|---|
| `--run-id` | required.  |
| `--checkpoint` | manifest name, latest, final, best or frozen (default: `latest`) |
| `--confirm` | required: confirms this is a new run |
| `--label` |  |
| `--train` | start training the new run right away |

## `worker`

==SUPPRESS==

```text
usage: python -m lunarlab worker [-h] --job-id JOB_ID
```

| Argument | Description |
|---|---|
| `--job-id` | required.  |
