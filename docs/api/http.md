# HTTP API (local)

The web interface talks to this API. It binds to 127.0.0.1 only, has no authentication (single local user), and every state-changing request must carry the `X-LunarLab: 1` header (a CSRF guard). The machine-readable schema is [openapi.json](openapi.json).

| Method | Path | Summary |
|---|---|---|
| POST | `/api/benchmark` | Benchmark |
| POST | `/api/compare` | Compare |
| POST | `/api/demos` | Demo |
| GET | `/api/experiments` | Experiments |
| POST | `/api/experiments` | Experiment Create |
| POST | `/api/experiments/plan` | Experiment Plan |
| GET | `/api/experiments/{experiment_id}` | Experiment |
| POST | `/api/flights` | Flight Start |
| DELETE | `/api/flights/{session_id}` | Flight Abandon |
| POST | `/api/flights/{session_id}/step` | Flight Step |
| GET | `/api/health` | Health |
| GET | `/api/jobs` | List Jobs |
| GET | `/api/jobs/{job_id}` | Get Job |
| GET | `/api/jobs/{job_id}/log` | Job Log |
| POST | `/api/jobs/{job_id}/stop` | Stop Job |
| POST | `/api/jobs/{job_id}/terminate` | Terminate Job |
| GET | `/api/meta` | Meta |
| GET | `/api/overview` | Overview |
| GET | `/api/preferences` | Preference Datasets |
| GET | `/api/preferences/{dataset_id}/active-studies` | Preference Active Studies |
| POST | `/api/preferences/{dataset_id}/ensemble` | Preference Ensemble |
| POST | `/api/preferences/{dataset_id}/labels` | Preference Label |
| GET | `/api/preferences/{dataset_id}/pair` | Preference Pair |
| GET | `/api/preferences/{dataset_id}/progress` | Preference Progress |
| POST | `/api/queue` | Set Queue |
| GET | `/api/recordings` | Recordings |
| GET | `/api/recordings/{recording_id}` | Recording |
| GET | `/api/recordings/{recording_id}/frames/{index}` | Recording Frame |
| POST | `/api/recordings/{recording_id}/rescore` | Recording Rescore |
| GET | `/api/recordings/{recording_id}/scene` | Recording Scene |
| GET | `/api/recordings/{recording_id}/video` | Recording Video |
| GET | `/api/reports` | Reports |
| POST | `/api/reports` | Report |
| GET | `/api/reports/{report_id}/{name}` | Report File |
| POST | `/api/reward-analysis/hover` | Analysis Hover |
| GET | `/api/reward-analysis/time-penalty` | Analysis Time |
| GET | `/api/reward-configs` | Reward Configs |
| POST | `/api/reward-configs` | Create Reward |
| POST | `/api/reward-configs/import` | Import Reward |
| POST | `/api/reward-configs/validate` | Validate Reward |
| GET | `/api/reward-configs/{config_id}` | Reward Config |
| GET | `/api/reward-configs/{config_id}/export` | Export Reward |
| GET | `/api/reward-models` | Reward Models |
| GET | `/api/runs` | Runs |
| POST | `/api/runs` | Create Run Endpoint |
| GET | `/api/runs/{run_id}` | Run Detail |
| GET | `/api/runs/{run_id}/config.yaml` | Run Config File |
| GET | `/api/runs/{run_id}/curve` | Run Curve |
| GET | `/api/runs/{run_id}/estimate` | Run Estimate |
| POST | `/api/runs/{run_id}/evaluate` | Run Evaluate |
| GET | `/api/runs/{run_id}/evaluations/{name}` | Run Evaluation |
| GET | `/api/runs/{run_id}/events` | Run Events |
| GET | `/api/runs/{run_id}/files/{kind}/{name}` | Run File |
| GET | `/api/runs/{run_id}/metrics` | Run Metrics |
| POST | `/api/runs/{run_id}/record` | Run Record |
| POST | `/api/runs/{run_id}/resume` | Run Resume |
| POST | `/api/runs/{run_id}/stop` | Run Stop |
| POST | `/api/runs/{run_id}/train` | Run Train |
| GET | `/api/runs/{run_id}/validation` | Run Validation |
| POST | `/api/runs/{run_id}/warm-restart` | Run Warm Restart |
| POST | `/api/shutdown` | Shutdown |
| GET | `/api/system` | System |
| GET | `/api/tuning` | Tuning Studies |
| POST | `/api/tuning` | Tuning Create |
| GET | `/api/tuning/space` | Tuning Space |
| GET | `/api/tuning/{study_id}` | Tuning Study |
| POST | `/api/tuning/{study_id}/apply` | Tuning Apply |
| POST | `/api/tuning/{study_id}/cancel` | Tuning Cancel |
| POST | `/api/tuning/{study_id}/resume` | Tuning Resume |
