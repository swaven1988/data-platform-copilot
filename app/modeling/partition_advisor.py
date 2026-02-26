class PartitionAdvisor:

    @staticmethod
    def recommend(columns: list[str]) -> dict:
        """
        Simple deterministic partition advisory.
        Future: enhance with cardinality analysis.
        """
        if "event_date" in columns:
            return {"strategy": "date", "columns": ["event_date"]}

        if "ingestion_date" in columns:
            return {"strategy": "date", "columns": ["ingestion_date"]}

        if "created_at" in columns:
            return {"strategy": "date", "columns": ["created_at"]}

        return {"strategy": "none", "columns": []}
