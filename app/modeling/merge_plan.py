from dataclasses import dataclass


@dataclass
class MergePlan:
    merge_sql: str
    close_old_sql: str
    insert_new_sql: str
