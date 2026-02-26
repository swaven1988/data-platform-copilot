class DQProfiler:
    """
    Baseline deterministic DQ suggestion engine.
    """

    @staticmethod
    def suggest(model_spec):
        suggestions = []

        suggestions.append("freshness_check")

        if model_spec.model_type in ["scd2", "incremental"]:
            suggestions.append("duplicate_check")

        if len(model_spec.columns) > 0:
            suggestions.append("null_threshold_check")

        return {
            "recommended_checks": suggestions
        }
