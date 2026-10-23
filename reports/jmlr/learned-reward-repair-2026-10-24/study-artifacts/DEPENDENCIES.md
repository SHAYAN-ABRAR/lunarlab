# Learned-reward dependency inventory (repaired bundle, 24 October 2026)

Each learned-reward package now carries its original reward model under `reward_model/`, listed in `artifact.json` with its SHA-256. The bytes are identical to `data/reward_models/<id>/` in the original data home and to the historical integrity manifest. Checkpoint, configuration and recorded-evaluation bytes of all 38 packages are unchanged from the 19 October export.

| Policy (run ID) | Group | Reward model | model.npz SHA-256 | meta.json SHA-256 | Payload unchanged |
|---|---|---|---|---|---|
| `20261015-235939-custom-s0-standard-0274` | Learned reward 300 pairs | `rm-20261015-235825-rm-300-4877` | `ed282e43800420d9…` | `96841ecd5e3fd909…` | True |
| `20261015-235939-custom-s1-standard-b692` | Learned reward 300 pairs | `rm-20261015-235825-rm-300-4877` | `ed282e43800420d9…` | `96841ecd5e3fd909…` | True |
| `20261015-235940-custom-s2-standard-a299` | Learned reward 300 pairs | `rm-20261015-235825-rm-300-4877` | `ed282e43800420d9…` | `96841ecd5e3fd909…` | True |
| `20261015-235940-custom-s0-standard-d28b` | Learned reward 3000 pairs | `rm-20261015-235939-rm-3000-cfd0` | `4426daaae4d24804…` | `b7911c64f3f388f6…` | True |
| `20261015-235940-custom-s1-standard-ce26` | Learned reward 3000 pairs | `rm-20261015-235939-rm-3000-cfd0` | `4426daaae4d24804…` | `b7911c64f3f388f6…` | True |
| `20261015-235940-custom-s2-standard-dbc1` | Learned reward 3000 pairs | `rm-20261015-235939-rm-3000-cfd0` | `4426daaae4d24804…` | `b7911c64f3f388f6…` | True |

Other 32 packages: no reward-model dependency, no new files. Problems: none.
