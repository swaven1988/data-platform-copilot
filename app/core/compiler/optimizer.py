def suggest_optimizations(shuffle_stages: int, executor_memory_gb: int):
    suggestions = []

    if shuffle_stages > 2:
        suggestions.append("Increase shuffle partitions")
        suggestions.append("Enable Adaptive Query Execution")

    if executor_memory_gb < 8:
        suggestions.append("Increase executor memory to at least 8GB")

    return suggestions