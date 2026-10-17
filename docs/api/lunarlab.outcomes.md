# `lunarlab.outcomes`

Source: [`lunarlab/outcomes.py`](../../lunarlab/outcomes.py)

Episode outcome classification.

Definitions (documented in docs/EVALUATION.md):

``env_outcome`` — what the *environment* decided at the final step:

* ``at_rest``        terminated because Box2D put the lander to sleep. The env pays
                     +100. This is the environment's own notion of success, and it
                     does **not** check where the lander came to rest.
* ``crash``          terminated because the lander *body* touched the ground
                     (``game_over``) and the lander was still awake. Env pays -100.
* ``out_of_bounds``  terminated because |x| >= 1 without body contact. Env pays -100.
* ``timeout``        truncated by the 1000-step ``TimeLimit``.
* ``unknown``        terminated for no reason we can identify (should not happen;
                     reported rather than guessed).

Note the env's own order: if the body touched the ground *and* the lander fell
asleep on the same step, the env pays +100 (sleep wins). We report ``at_rest``
with ``body_contact=True``; such an episode never counts as a strict pad landing.

``pad_landing`` (strict) requires all of:

1. ``env_outcome == "at_rest"`` (Box2D put the lander to sleep: it is not moving);
2. no body contact at any point (``game_over`` is sticky within an episode);
3. leg ground contact was reported at least once during the episode;
4. both leg bodies horizontally between the helipad flags (x read from the env);
5. final |angle| <= ``max_final_abs_angle_rad``.

Why not "both legs in contact in the final observation"? In gymnasium 1.4.0 the
contact detector keeps one boolean per leg: ``BeginContact`` sets it, ``EndContact``
clears it. When a leg slides across the joint between two terrain edge fixtures,
the new contact begins before the old one ends, so the flag reads 0 although the
leg is still on the ground. Landers asleep on the pad with both flags at 0 are
common (e.g. the heuristic controller on episode seed 20011). A sleeping lander
without body contact must be resting on its legs, so condition 3 only asks that
leg contact was seen at some point. ``both_legs_contact`` (final frame) is still
reported for transparency.

A score of >= 200 is reported separately: score and outcome measure different things.

Classifier version 2 (``OUTCOME_CLASSIFIER_VERSION``) keeps *where* the lander came to rest apart from
*how well* it landed. ``pad_geography`` is ``within`` (both leg bodies between the flags),
``straddling`` (one leg between them, one beyond), ``outside`` (neither) or ``unknown`` (leg or pad
coordinates missing or not finite: never guessed). ``landing_category`` is exactly one of:

* ``strict_pad_landing``          all five conditions above hold;
* ``on_pad_not_strict``           at rest without body contact, both legs between the flags, but
                                  another condition failed (final angle, or no leg contact seen);
* ``landed_not_within_pad``       at rest without body contact, not wholly within the pad
                                  (``straddling`` or ``outside``);
* ``at_rest_after_body_contact``  the environment's ``at_rest`` after the body touched the ground;
* ``at_rest_geometry_unknown``    at rest without body contact, but the geometry is unknown;
* ``crash`` / ``out_of_bounds`` / ``timeout`` / ``unknown``  the environment outcome.

``strict_failures`` lists every strict condition an episode failed. The definition of
``pad_landing`` itself is unchanged from version 1. ``landed_off_pad`` now means
``landed_not_within_pad``; version 1 set it for *every* clean at-rest episode that was not a strict
pad landing, including tilted landings on the pad. Version-1 records are never relabelled in place:
:func:`reclassify_legacy_episode` derives version-2 categories from the fields they stored, and
derived values are always labelled as derived.

### class `OutcomeRecord`

OutcomeRecord(env_outcome: 'str', terminated: 'bool', truncated: 'bool', body_contact: 'bool', both_legs_contact: 'bool', leg_contact_seen: 'bool', legs_within_pad: 'bool', pad_landing: 'bool', landed_off_pad: 'bool', final_abs_angle_rad: 'float', pad_x1_obs: 'float', pad_x2_obs: 'float', landing_category: 'str' = 'unknown', pad_geography: 'str' = 'unknown', strict_failures: 'tuple[str, ...]' = (), on_pad_not_strict: 'bool' = False, leg_x_world: 'tuple[float, ...] | None' = None, helipad_x_world: 'tuple[float, float] | None' = None, outcome_classifier_version: 'int' = 2)

`OutcomeRecord(env_outcome: 'str', terminated: 'bool', truncated: 'bool', body_contact: 'bool', both_legs_contact: 'bool', leg_contact_seen: 'bool', legs_within_pad: 'bool', pad_landing: 'bool', landed_off_pad: 'bool', final_abs_angle_rad: 'float', pad_x1_obs: 'float', pad_x2_obs: 'float', landing_category: 'str' = 'unknown', pad_geography: 'str' = 'unknown', strict_failures: 'tuple[str, ...]' = (), on_pad_not_strict: 'bool' = False, leg_x_world: 'tuple[float, ...] | None' = None, helipad_x_world: 'tuple[float, float] | None' = None, outcome_classifier_version: 'int' = 2) -> None`

- method `to_dict(self) -> 'dict'`: JSON-ready dict (non-finite coordinates become None).

### class `PadLandingCriteria`(BaseModel)

What a strict pad landing requires beyond coming to rest without body contact: leg contact seen,
both leg bodies between the flags, and a final tilt of at most ``max_final_abs_angle_rad``.

| Field | Type | Default | Description |
|---|---|---|---|
| `require_leg_contact_seen` | `bool` | `True` |  |
| `require_legs_within_pad` | `bool` | `True` |  |
| `max_final_abs_angle_rad` | `float` | `0.35` |  |


### `classify_env_outcome(terminated: 'bool', truncated: 'bool', final_obs: 'np.ndarray', p: 'LanderProbe') -> 'str'`

The environment's own ending: ``at_rest``, ``crash``, ``out_of_bounds``, ``timeout`` (time-limit
truncation) or ``unknown``.

### `classify_outcome(terminated: 'bool', truncated: 'bool', final_obs: 'np.ndarray', p: 'LanderProbe', criteria: 'PadLandingCriteria | None' = None, *, leg_contact_seen: 'bool') -> 'OutcomeRecord'`

Classify an episode's end (outcome classifier version 2).

Returns the environment outcome, whether it was a strict pad landing, the pad geography (within, straddling,
outside, unknown), exactly one landing category, and every strict condition that failed.

### `derived_v2_rates(episodes: 'list[dict]', *, max_final_abs_angle_rad: 'float') -> 'dict | None'`

Version-2 category rates derived from version-1 episode records (None if they lack the fields).

### `pad_geography(leg_xs, pad_x1: 'float', pad_x2: 'float') -> 'str'`

``within`` / ``straddling`` / ``outside``, or ``unknown`` when any coordinate is unusable.

### `reclassify_legacy_episode(ep: 'dict', *, max_final_abs_angle_rad: 'float') -> 'dict'`

Version-2 category of a version-1 episode record, derived only from what it stored.

Version 1 stored whether both legs were between the flags, not the leg positions, so a landing
that was not within the pad is ``not_within`` (straddling and outside cannot be told apart).

## Constants

- `ENV_OUTCOMES` = `('at_rest', 'crash', 'out_of_bounds', 'timeout', 'unknown')`
- `LANDING_CATEGORIES` = `('strict_pad_landing', 'on_pad_not_strict', 'landed_not_within_pad', 'at_rest_after_body_contact', 'at_rest_geometry_unk…`
- `LEGACY_FIELDS` = `('env_outcome', 'body_contact', 'leg_contact_seen', 'legs_within_pad', 'final_abs_angle_rad', 'pad_landing')`
- `OUTCOME_CLASSIFIER_VERSION` = `2`
