from typing import List
from .contracts import DQRule


def infer_basic_rules(schema: dict) -> List[DQRule]:
    rules = []

    for col, dtype in schema.items():
        if dtype in ("int", "float"):
            rules.append(DQRule(rule_type="non_negative", column=col))
        rules.append(DQRule(rule_type="not_null", column=col))

    return rules


def validate_rules(rules: List[DQRule]) -> dict:
    results = []

    for r in rules:
        if r.rule_type == "not_null" and not r.column:
            results.append({"status": "invalid", "reason": "missing column"})
        else:
            results.append({"status": "valid"})

    return {"results": results}