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
from lunarlab.audit.core import (
    EpisodeAudit,
    RewardAccountingWrapper,
    RewardTerm,
    Transition,
    per_step,
    potential_shaping,
    state_bonus,
    terms_hash,
)
from lunarlab.audit.evaluate import audit_policy, seed_split_problems

__all__ = [
    "EpisodeAudit",
    "EpisodeEnd",
    "RewardAccountingWrapper",
    "RewardTerm",
    "TaskAdapter",
    "Transition",
    "adapter_names",
    "audit_policy",
    "cartpole_adapter",
    "get_adapter",
    "lunar_lander_adapter",
    "per_step",
    "potential_shaping",
    "register_adapter",
    "seed_split_problems",
    "state_bonus",
    "terms_hash",
]
