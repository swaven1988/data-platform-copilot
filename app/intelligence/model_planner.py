from app.modeling.scd_engine import SCDEngine
from app.modeling.partition_advisor import PartitionAdvisor
from app.intelligence.spark_advisor import SparkAdvisor
from app.intelligence.dq_profiler import DQProfiler
from app.intelligence.cost_estimator import CostEstimator


class ModelPlanner:

    @staticmethod
    def plan(model_spec):
        result = {}

        if model_spec.model_type == "scd2" and model_spec.scd:
            merge_plan = SCDEngine.generate_scd2_merge(model_spec)
            result["scd_merge_sql"] = merge_plan.merge_sql

        result["partition_recommendation"] = PartitionAdvisor.recommend(
            model_spec.columns
        )

        result["spark_analysis"] = SparkAdvisor.analyze(model_spec)
        result["dq_recommendations"] = DQProfiler.suggest(model_spec)
        result["cost_estimation"] = CostEstimator.estimate(model_spec)

        return result
