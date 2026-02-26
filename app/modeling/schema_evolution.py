def detect_schema_changes(current_schema: dict, new_schema: dict):
    added = []
    changed = []

    for col, dtype in new_schema.items():
        if col not in current_schema:
            added.append(col)
        elif current_schema[col] != dtype:
            changed.append(col)

    return {
        "added_columns": added,
        "changed_columns": changed,
        "breaking_change": len(changed) > 0,
    }
