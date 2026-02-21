def build_cdc_merge_sql(target, staging, pk):
    return f"""
MERGE INTO {target} t
USING {staging} s
ON t.{pk} = s.{pk}
WHEN MATCHED AND s.op = 'D' THEN DELETE
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
"""
