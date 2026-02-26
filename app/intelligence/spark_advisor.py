class SparkAdvisor:
    """
    Deterministic Spark heuristics.
    No runtime dependencies.
    """

    @staticmethod
    def analyze(model_spec):
        columns = model_spec.columns

        result = {
            "join_strategy": "sort_merge",
            "broadcast_recommended": False,
            "shuffle_partition_recommendation": 200,
            "skew_risk": "low",
        }

        if len(columns) > 20:
            result["shuffle_partition_recommendation"] = 400

        if "id" in columns or "customer_id" in columns:
            result["skew_risk"] = "medium"

        if len(columns) < 10:
            result["broadcast_recommended"] = True
            result["join_strategy"] = "broadcast"

        return result
