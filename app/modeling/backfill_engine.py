from datetime import datetime


def generate_backfill_plan(start_dt: str, end_dt: str, partition_column: str):
    return {
        "backfill_window": {
            "start": start_dt,
            "end": end_dt,
        },
        "strategy": "partition_reprocess",
        "partition_column": partition_column,
    }
