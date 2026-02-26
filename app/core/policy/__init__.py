from .engine import PolicyEngine
from .builtin import policy_require_owner_email, policy_require_source_target

DEFAULT_POLICY_ENGINE = PolicyEngine(
    policies=[
        policy_require_source_target,
        policy_require_owner_email,
    ]
)
