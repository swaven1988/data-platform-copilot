from typing import Dict, List


class HintMapper:

    @staticmethod
    def map_to_advisor_tags(hints: Dict) -> List[str]:
        tags = []

        if hints.get("affects_policy"):
            tags.append("policy")

        if hints.get("affects_dag"):
            tags.append("dag")

        if hints.get("affects_spark"):
            tags.append("spark")

        if hints.get("affects_api"):
            tags.append("api")

        return tags
