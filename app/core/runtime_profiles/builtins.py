from __future__ import annotations

from .models import RuntimeProfile, ClusterDefaults, PricingHints


def builtin_profiles() -> list[RuntimeProfile]:
    # Deterministic defaults (no external pricing). Users can override pricing via API.
    return [
        RuntimeProfile(
            name="aws_emr_yarn_default",
            cloud="aws",
            cluster_mode="yarn",
            spark_version="3.5.0",
            description="AWS EMR on YARN (default profile)",
            spark_conf={
                "spark.sql.adaptive.enabled": "true",
                "spark.sql.adaptive.coalescePartitions.enabled": "true",
                "spark.sql.adaptive.skewJoin.enabled": "true",
                "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
            },
            cluster_defaults=ClusterDefaults(executor_instances=8, executor_cores=4, executor_memory_gb=16),
            pricing=PricingHints(instance_type="m5.2xlarge", instance_hourly_rate=0.384),
        ),
        RuntimeProfile(
            name="gcp_dataproc_yarn_default",
            cloud="gcp",
            cluster_mode="yarn",
            spark_version="3.5.0",
            description="GCP Dataproc on YARN (default profile)",
            spark_conf={
                "spark.sql.adaptive.enabled": "true",
                "spark.sql.adaptive.coalescePartitions.enabled": "true",
                "spark.sql.adaptive.skewJoin.enabled": "true",
                "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
            },
            cluster_defaults=ClusterDefaults(executor_instances=8, executor_cores=4, executor_memory_gb=16),
            pricing=PricingHints(instance_type="n2-standard-8", instance_hourly_rate=0.379),
        ),
        RuntimeProfile(
            name="azure_synapse_yarn_default",
            cloud="azure",
            cluster_mode="yarn",
            spark_version="3.5.0",
            description="Azure Synapse Spark (default profile)",
            spark_conf={
                "spark.sql.adaptive.enabled": "true",
                "spark.sql.adaptive.coalescePartitions.enabled": "true",
                "spark.sql.adaptive.skewJoin.enabled": "true",
                "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
            },
            cluster_defaults=ClusterDefaults(executor_instances=8, executor_cores=4, executor_memory_gb=16),
            pricing=PricingHints(instance_type="Standard_D8_v5", instance_hourly_rate=0.376),
        ),
        RuntimeProfile(
            name="k8s_spark_default",
            cloud="onprem",
            cluster_mode="k8s",
            spark_version="3.5.0",
            description="Spark on Kubernetes (default profile)",
            spark_conf={
                "spark.kubernetes.container.image.pullPolicy": "IfNotPresent",
                "spark.sql.adaptive.enabled": "true",
                "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
            },
            cluster_defaults=ClusterDefaults(executor_instances=6, executor_cores=2, executor_memory_gb=8),
            pricing=PricingHints(instance_type=None, instance_hourly_rate=0.0),
        ),
    ]