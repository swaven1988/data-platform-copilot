def estimate_runtime_minutes(
    num_stages: int,
    shuffle_stages: int,
    base_parallelism: int
) -> float:
    base = num_stages * 2.5
    shuffle_penalty = shuffle_stages * 3.0
    parallelism_factor = max(1, base_parallelism / 200)
    return round((base + shuffle_penalty) / parallelism_factor, 2)