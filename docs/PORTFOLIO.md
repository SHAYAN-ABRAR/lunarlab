# Portfolio summary

Every report (`python -m lunarlab report --experiment-id <id>`, or *Generate report* on Compare & Diagnose)
also writes `reports/<id>/portfolio_summary.md`.

Its rules:

- Numbers are inserted **only** from stored final-test evaluations of non-SMOKE runs. Anything else shows
  `[not yet measured]`. Do not replace those markers by hand.
- Each figure carries its evidence (number of training seeds and test episodes) so it cannot be quoted
  without context.
- The reward-hacking line reports the outcome of the documented rule, including "no run met the rule",
  which is a valid result.
- It lists limitations to state alongside any number: few seeds, untuned PPO per reward, and that this is
  a 2-D simulation benchmark rather than evidence of real-world rocket-control capability.

Suggested workflow:

1. `python -m lunarlab benchmark`
2. `python -m lunarlab suite --seeds 0,1,2 --profile standard --yes`
3. `python -m lunarlab report --experiment-id <printed id>`
4. Use `portfolio_summary.md`, `report.html` and a side-by-side replay recorded on seed 20000. Pick the clip
   by seed, not by how dramatic it looks.
