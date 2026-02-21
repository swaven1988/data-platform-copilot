def generate_hash_expression(columns: list[str]) -> str:
    """
    Returns SQL expression for deterministic hash.
    Example:
      md5(col1 || '|' || col2 || '|' || col3)
    """
    if not columns:
        raise ValueError("Change detection columns cannot be empty")

    concat_expr = " || '|' || ".join(columns)
    return f"md5({concat_expr})"
