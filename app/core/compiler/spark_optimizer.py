def recommend_spark_config(data_gb: float, joins: int, sla_minutes: int) -> dict:
    executors = max(2, int(data_gb / 5))
    cores = 4 if joins < 3 else 6

    config = {
        "spark.executor.instances": executors,
        "spark.executor.cores": cores,
        "spark.executor.memory": "8g" if data_gb < 50 else "14g",
        "spark.sql.shuffle.partitions": max(200, int(data_gb * 4)),
    }

    if sla_minutes and sla_minutes < 30:
        config["spark.speculation"] = "true"

    return config