class IncrementalEngine:

    @staticmethod
    def generate_filter_clause(watermark_column: str) -> str:
        if not watermark_column:
            raise ValueError("Watermark column must be provided")

        return (
            f"WHERE {watermark_column} > "
            f"(SELECT max({watermark_column}) FROM target)"
        )
