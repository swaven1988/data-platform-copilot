from .scd_engine import build_scd2_merge_sql
from .partition_advisor import recommend_partitioning


def generate_spark_job(spec):
    merge_sql = build_scd2_merge_sql(spec)
    partition = recommend_partitioning(spec)

    return {
        "spark_job_template": f"""
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("{spec.target_table}").getOrCreate()

spark.sql(\"\"\"{merge_sql}\"\"\")
""",
        "partition_strategy": partition,
    }
