from .spark_optimizer import recommend_spark_config


def simulate_execution(data_gb: float, joins: int, sla_minutes: int):
    spark_conf = recommend_spark_config(data_gb, joins, sla_minutes)

    estimated_runtime = max(5, int(data_gb / 2))

    return {
        "estimated_runtime_minutes": estimated_runtime,
        "recommended_spark_config": spark_conf,
    }