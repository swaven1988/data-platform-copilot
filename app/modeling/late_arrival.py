def late_arrival_strategy(scd_type: str):
    if scd_type == "type2":
        return {
            "strategy": "recompute_effective_window",
            "note": "Will close and reopen historical records"
        }
    return {
        "strategy": "overwrite"
    }
