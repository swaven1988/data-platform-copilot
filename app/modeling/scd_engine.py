from .model_spec import ModelSpec
from .change_detection import generate_hash_expression
from .merge_plan import MergePlan


class SCDEngine:

    @staticmethod
    def generate_scd2_merge(model: ModelSpec) -> MergePlan:
        if not model.scd or model.scd.type != "scd2":
            raise ValueError("ModelSpec must contain SCD2 configuration")

        scd = model.scd

        hash_expr = generate_hash_expression(scd.change_detection.columns)

        natural_key_cond = " AND ".join(
            [f"t.{k} = s.{k}" for k in scd.natural_keys]
        )

        close_sql = f"""
        UPDATE {model.table_name} t
        SET {scd.effective_to_col} = current_timestamp,
            {scd.current_flag_col} = false
        FROM staging s
        WHERE {natural_key_cond}
          AND t.{scd.current_flag_col} = true
          AND {hash_expr} <> s.hash_value
        """

        insert_sql = f"""
        INSERT INTO {model.table_name}
        SELECT *,
               current_timestamp as {scd.effective_from_col},
               '9999-12-31' as {scd.effective_to_col},
               true as {scd.current_flag_col}
        FROM staging s
        """

        merge_sql = close_sql.strip() + ";\n" + insert_sql.strip()

        return MergePlan(
            merge_sql=merge_sql,
            close_old_sql=close_sql.strip(),
            insert_new_sql=insert_sql.strip(),
        )
