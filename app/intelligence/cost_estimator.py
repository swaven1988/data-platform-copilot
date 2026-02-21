class CostEstimator:
    """
    Lightweight cost heuristics.
    """

    @staticmethod
    def estimate(model_spec):
        column_count = len(model_spec.columns)

        estimated_scan_gb = column_count * 0.5
        estimated_runtime_minutes = max(5, column_count // 2)

        return {
            "estimated_scan_gb": estimated_scan_gb,
            "estimated_runtime_minutes": estimated_runtime_minutes,
            "estimated_emr_cost_usd": round(estimated_runtime_minutes * 0.25, 2),
        }
