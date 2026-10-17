# Evidence for each statement in main.tex

Every factual statement in the manuscript, and where it is established. "Test" means an automated test in
`tests/`; "measured" means a stored measurement in `reports/jmlr/`.

| Statement (section) | Evidence |
|---|---|
| Records the original reward, every added term and the training reward on each transition (abstract, §2) | `lunarlab/rewards/wrapper.py`, `lunarlab/rewards/terms.py`; tests `test_rewards.py`, `test_properties.py::test_accounting_identity_holds_for_any_reward_configuration` |
| Evaluates policies on the original reward only (abstract, §2) | `evaluation.make_eval_env` (`apply=False`), the cross-check in `evaluation.run_episode`; smoke check "validation evaluation uses the original reward" |
| Potential-based shaping telescopes; absorbing terminal and truncation handled (§2) | `rewards/terms.py::potential_shaping`; `test_properties.py::test_potential_shaping_telescopes_on_lander_states` |
| Seeds strict, distinct, disjoint; environment checked against the declaration (§2) | `config.EvalProtocol.problems`, `evaluation.evaluate_policy`; `test_protocol.py` |
| Selected checkpoint frozen as an immutable, read-only, digest-checked artifact; never trained again; retries on the same bytes; exposure registry (§2) | `lunarlab/freeze.py`, `lunarlab/lineage.py`; `test_freeze.py`; smoke checks on the frozen copy |
| Hover detector independent of the reward; strict landing classifier (§2) | `lunarlab/hover.py`, `lunarlab/outcomes.py`; `test_diagnostics.py`, `test_outcomes_v2.py` |
| Hashes, seeds, budgets in transitions, versions and source revision per segment and evaluation (§2) | `runs.create_run`, `training._train_locked`, `evaluation._save_result`; smoke checks |
| Crash-safe checkpoints with a SHA-256 manifest; exact PPO/DQN resume incl. replay buffer, never unpickled (§2) | `training.save_model_atomic`, `lunarlab/continuation.py`; `test_dqn_continuation.py`, `test_continuation_validation.py`, `test_windows.py` |
| CLI, Python API, local web interface, no network service or account (§2) | `lunarlab/cli.py`, `docs/api/`, `frontend/`; `docs/TUTORIAL.md` |
| Adapter layer: LunarLander adapter reproduces the pipeline exactly; CartPole demonstrates the contract (§2) | `lunarlab/audit/`; `test_audit_core.py::test_generic_accounting_reproduces_lunarlabs_wrapper_on_lunarlander`, `test_audit_policy_on_cartpole_is_deterministic_and_records_provenance`; `examples/cartpole_audit.py` |
| N tests, B browser flows, C % coverage; CI on Linux and Windows (abstract, §3) | `reports/jmlr/coverage/SUMMARY.md` (final figures); `.github/workflows/ci.yml` |
| Tutorial executed command by command; API reference generated; deterministic archive test-installed (§3) | `test_tutorial.py`; `tools/gen_api_docs.py --check`; `tools/build_source_archive.py --verify`, `test_source_archive.py`, `reports/jmlr/artifacts/source_archive_verification.txt` |
| `reproduce-smoke` verifies 14 provenance checks; training twice gave identical weights (§3) | `lunarlab/reproduce.py`; measured `reports/jmlr/artifacts/reproduce-smoke-ppo-windows.json`, `…-dqn-windows.json` |
| 300 of 300 published final-test episodes re-evaluated bit-identically (abstract, §3) | `examples/artifacts/`; measured `reports/jmlr/artifacts/reproduce-{ppo-baseline,ppo-hover-bonus,dqn-baseline}-s0-windows.json` |
| Cross-platform bit-identity not claimed (§3, §4) | `docs/jmlr/REPRODUCIBILITY.md`; SB3's own statement cited there |
| Table 1 values; "about 4 %" (abstract, §3) | measured `reports/jmlr/benchmarks/standard-2026-10-17T154705+0000/summary.json` and `raw.jsonl`; protocol `docs/jmlr/BENCHMARK_PROTOCOL.md` |
| Study design: PPO, 1 M transitions, 5 seeds, four reward designs; DQN and learned rewards included (§3) | `docs/RESULTS.md`; experiment definitions in `data/experiments/` (local) |
| Hover bonus: training return 746 vs original −50 at the end of training (§3, Fig. 2) | measured `reports/jmlr/figures/reward_accounting.csv` (last row of each series; median over five seeds) |
| Hover-bonus policies: 0 of 500 test landings, 80 % at the time limit (§3) | `docs/RESULTS.md`, `docs/results/results.json` |
| Time penalty and potential shaping: every P(improvement) interval contains 0.5 (§3) | `docs/results/tables.md`: 0.32 [0.00, 0.72] and 0.36 [0.00, 0.76] |
| MIT License; Windows and Linux; Python 3.12; CPU only, no proprietary dependency (§4) | `LICENSE`, SPDX headers (`tools/spdx_headers.py`); `requirements-ci.lock`; `THIRD_PARTY_NOTICES.md` |
| Main pipeline specific to LunarLander-v3 (§4) | `config.EvalProtocol.problems`; `docs/jmlr/EXTENDING_LUNARLAB.md` |
