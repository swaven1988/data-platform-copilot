from typing import Literal

ProfileType = Literal["dev", "staging", "prod", "regulated"]


PROFILE_CONFIG = {
    "dev": {"strict_policy": False, "enable_cost_estimation": False},
    "staging": {"strict_policy": True, "enable_cost_estimation": True},
    "prod": {"strict_policy": True, "enable_cost_estimation": True},
    "regulated": {"strict_policy": True, "enable_cost_estimation": True},
}


def get_profile(profile: ProfileType) -> dict:
    return PROFILE_CONFIG.get(profile, PROFILE_CONFIG["dev"])