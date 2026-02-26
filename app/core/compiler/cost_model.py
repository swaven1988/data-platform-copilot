def estimate_cost_usd(
    runtime_minutes: float,
    executor_instances: int,
    instance_hourly_rate: float
) -> float:
    hours = runtime_minutes / 60.0
    return round(hours * executor_instances * instance_hourly_rate, 2)