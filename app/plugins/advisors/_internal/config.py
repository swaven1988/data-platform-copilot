from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AdvisorsRunConfig:
    # IMPORTANT: keep these names; tests and API use them
    enabled: Optional[list[str]] = None   # None => not explicitly set (use enabled_by_default)
    disabled: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    force: bool = False

    @classmethod
    def from_payload(cls, payload: Any) -> "AdvisorsRunConfig":
        """
        Accepts:
          - None
          - ["basic_checks", ...]
          - {"enabled":[...], "disabled":[...], "options":{...}, "force":true}
        Also tolerates accidental {"advisors":["..."], "force":true}.
        """
        if payload is None:
            return cls()

        # list -> enabled advisors
        if isinstance(payload, list):
            return cls(enabled=[x for x in payload if isinstance(x, str)])

        # dict -> structured config
        if isinstance(payload, dict):
            enabled = payload.get("enabled", payload.get("advisors", None))
            disabled = payload.get("disabled", [])
            options = payload.get("options", {})

            # tolerate enabled="basic_checks"
            if isinstance(enabled, str):
                enabled = [enabled]

            force = payload.get("force", False)

            # hard-guard: never treat "force" as an advisor name
            if isinstance(enabled, list):
                enabled = [x for x in enabled if isinstance(x, str) and x != "force"]
            else:
                enabled = None

            return cls(
                enabled=[x for x in enabled if isinstance(x, str)] if isinstance(enabled, list) else None,
                disabled=[x for x in disabled if isinstance(x, str)] if isinstance(disabled, list) else [],
                options=options if isinstance(options, dict) else {},
                force=bool(force),
            )

        return cls()

    def plugin_options(self, plugin_name: str) -> dict[str, Any]:
        opts = self.options or {}
        v = opts.get(plugin_name, {})
        return v if isinstance(v, dict) else {}

    def is_enabled_with_default(self, name: str, *, enabled_by_default: bool = True) -> bool:
        if name in (self.disabled or []):
            return False

        # enabled explicitly set => allowlist semantics
        if self.enabled is not None:
            return name in self.enabled

        # enabled not set => default behavior based on plugin metadata
        return bool(enabled_by_default)
