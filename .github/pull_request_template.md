## What and why

<!-- What does this change do, and which research or usability problem does it address? -->

## Checklist

- [ ] Tests added or updated for every behaviour change (`python -m pytest`)
- [ ] `ruff check lunarlab tests tools` and `ruff format --check lunarlab tests tools` are clean
- [ ] Frontend changes: `npm run typecheck`, `npm run lint`, `npm run build` (and `npx playwright test` for UI flows)
- [ ] Documentation updated; every documented command still parses (`tests/test_docs.py`)
- [ ] New source files carry the SPDX license header
- [ ] No existing experiment evidence (runs, evaluations, checkpoints, recordings) is modified; tests use temporary homes
- [ ] Reward terms remain pure functions of the transition, and `training = w * original + sum(terms)` still holds
