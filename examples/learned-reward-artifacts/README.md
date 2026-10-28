# The six learned-reward policies of the 38-policy study

These are byte-exact copies of the six learned-reward exports in the repaired study bundle of 24 October 2026
(`reports/jmlr/learned-reward-repair-2026-10-24/`). `SHA256SUMS` lists their 60 files, and every digest
equals the bundle's own `SHA256SUMS` entry.

| Run ID | Group | Reward model |
|---|---|---|
| `20261015-235939-custom-s0-standard-0274` | learned reward, 300 preference pairs | `rm-20261015-235825-rm-300-4877` |
| `20261015-235939-custom-s1-standard-b692` | learned reward, 300 preference pairs | `rm-20261015-235825-rm-300-4877` |
| `20261015-235940-custom-s2-standard-a299` | learned reward, 300 preference pairs | `rm-20261015-235825-rm-300-4877` |
| `20261015-235940-custom-s0-standard-d28b` | learned reward, 3000 preference pairs | `rm-20261015-235939-rm-3000-cfd0` |
| `20261015-235940-custom-s1-standard-ce26` | learned reward, 3000 preference pairs | `rm-20261015-235939-rm-3000-cfd0` |
| `20261015-235940-custom-s2-standard-dbc1` | learned reward, 3000 preference pairs | `rm-20261015-235939-rm-3000-cfd0` |

They are in the repository, at 2.3 MB, so that continuous integration can replay them on Linux
(`.github/workflows/learned-reward-linux.yml`). The original data home is on a Windows machine, and no
Linux machine was available locally. They are not an archive of the study. The complete 38-policy bundle
is prepared for a separate public deposit, which is still pending.

Replay one from an empty data home:

```sh
LUNARLAB_HOME="$(mktemp -d)" python -m lunarlab reproduce-artifact --artifact examples/learned-reward-artifacts/20261015-235939-custom-s0-standard-0274
```

Each package carries its original reward model under `reward_model/`. Integrity checks refuse a missing or
corrupt model before any episode runs.
