from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PartitionSpec:
    strategy: str  # none | date | ingestion | custom
    columns: List[str] = field(default_factory=list)


@dataclass
class ChangeDetectionSpec:
    strategy: str  # hash | column_compare
    columns: List[str]


@dataclass
class SCDSpec:
    type: str  # scd1 | scd2
    natural_keys: List[str]
    surrogate_key: Optional[str]
    change_detection: ChangeDetectionSpec
    effective_from_col: str = "effective_dt"
    effective_to_col: str = "end_dt"
    current_flag_col: str = "is_current"
    late_arrival_strategy: str = "close_and_reopen"


@dataclass
class IncrementalSpec:
    watermark_column: Optional[str]
    deduplicate: bool = True


@dataclass
class ModelSpec:
    table_name: str
    model_type: str  # full | incremental | scd1 | scd2
    columns: List[str]
    partition: PartitionSpec
    incremental: Optional[IncrementalSpec] = None
    scd: Optional[SCDSpec] = None
