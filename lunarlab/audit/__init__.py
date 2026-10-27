# SPDX-FileCopyrightText: 2026 Shayan Abrar
# SPDX-License-Identifier: MIT
"""Task-independent auditing layer: reward accounting, task adapters and policy audits.

The main LunarLab pipeline (``lunarlab.training``, ``lunarlab.evaluation``) is specific to
``LunarLander-v3``. This package holds the parts that do not depend on the task, behind a small adapter
interface, so the same accounting can be applied to another Gymnasium environment::

    from lunarlab.audit import RewardAccountingWrapper, audit_policy, get_adapter

    cartpole = get_adapter("cartpole")
    shaping = cartpole.term("upright_potential", gamma=0.99)
    report = audit_policy(cartpole, policy, seeds=range(100, 110), gamma=0.99, terms={shaping.name: shaping})

See docs/jmlr/EXTENDING_LUNARLAB.md for the contract and what remains LunarLander-specific.
"""

from lunarlab.audit.adapters import (
    EpisodeEnd,
    TaskAdapter,
    adapter_names,
    cartpole_adapter,
    get_adapter,
    lunar_lander_adapter,
    register_adapter,
)
from lunarlab.audit.contracts import (
    SEED_CONTRACT,
    AuditInputError,
    NonFiniteValueError,
    canonical_json,
    normalize_seeds,
    seed_problems,
)
from lunarlab.audit.core import (
    EpisodeAudit,
    RewardAccountingWrapper,
    RewardTerm,
    Transition,
    per_step,
    potential_shaping,
    rescore_transitions,
    state_bonus,
    terms_hash,
)
from lunarlab.audit.evaluate import audit_policy, seed_split_problems
from lunarlab.audit.provenance import PROVENANCE_SCHEMA, definition_sha256, reward_provenance

__all__ = [
    "PROVENANCE_SCHEMA",
    "SEED_CONTRACT",
    "AuditInputError",
    "EpisodeAudit",
    "EpisodeEnd",
    "NonFiniteValueError",
    "RewardAccountingWrapper",
    "RewardTerm",
    "TaskAdapter",
    "Transition",
    "adapter_names",
    "audit_policy",
    "canonical_json",
    "cartpole_adapter",
    "definition_sha256",
    "get_adapter",
    "lunar_lander_adapter",
    "normalize_seeds",
    "per_step",
    "potential_shaping",
    "register_adapter",
    "rescore_transitions",
    "reward_provenance",
    "seed_problems",
    "seed_split_problems",
    "state_bonus",
    "terms_hash",
]
