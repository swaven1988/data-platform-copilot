# Data Platform Copilot – Stage 3 Contract (Plugin System + Resolver)

## Execution Flow (Authoritative)

resolve_active_plugins (via resolve_advisors)
→ PluginRegistry.run(context, cfg)
→ PluginRegistry._invoke(plugin, context, options)
→ PluginRegistry._normalize_result(result, context)
→ merge into context["plan"]
→ aggregate advisor_findings
→ return advisor_findings

## Plugin Invocation (Supported)

A plugin may implement ONE of:

- advise(plan, options?) -> list[AdvisorFinding] OR (plan, list[AdvisorFinding])
- run(*, context, options) -> list[AdvisorFinding] OR (plan, list[AdvisorFinding])
- __call__(context, options) -> list[AdvisorFinding] OR (plan, list[AdvisorFinding])

## Result Normalization

_normalize_result() must support:

- None -> []
- list[AdvisorFinding] -> list
- (plan, list) -> updates context["plan"], returns list
- (list, plan) -> tolerated, updates context["plan"], returns list
- unknown -> []

## Context Invariants

- context["plan"] always exists and is a list
- context["spec"] is present (dict or None) and consistent across entrypoints

## Deterministic Resolver

resolve_advisors(registry, intent, paths, cfg) returns (selected, skipped):

Selection rules:
- Start from registry.get_active_plugins(cfg)
- If plugin.applies_to exists and intent not in applies_to -> skipped (reason: not_applicable)
- If plugin disabled by cfg -> skipped (reason: disabled)

Ordering rules:
- phase rank: preflight(10), build(20), advise(30), post(40), unknown(999)
- then priority (ascending)
- then name (ascending)

## API

GET /plugins
- Lists all plugins and runtime enabled state

GET /plugins/resolve?intent=...&enabled=...&disabled=...
- Returns:
  - selected: ordered plugin names
  - skipped: [{name, reason}]
  - order: ordered plugin names

## Tests (Must Stay Green)

- return-shape normalization tests
- resolver applies_to test
- resolver priority ordering test
- resolver phase ordering test
