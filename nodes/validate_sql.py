import re
from utils.console import node_start, node_detail, node_end

FORBIDDEN_SQL = {
    "alter",
    "create",
    "delete",
    "drop",
    "insert",
    "merge",
    "truncate",
    "update",
}


def _strip_identifier(identifier: str) -> str:
    identifier = identifier.strip().strip('"`[]')
    return identifier.split(".")[-1].strip('"`[]')


def _referenced_tables(sql: str) -> set[str]:
    matches = re.findall(r"\b(?:from|join)\s+([\"`\[\]\w.]+)", sql, flags=re.IGNORECASE)
    return {_strip_identifier(match) for match in matches}


def _strip_markdown(sql: str) -> str:
    # Remove markdown code fences
    sql = re.sub(r"```sql|```", "", sql, flags=re.IGNORECASE).strip()
    # Remove SQL single-line comments
    sql = re.sub(r"--[^\n]*\n?", "", sql).strip()
    # Remove SQL block comments
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL).strip()
    return sql


def _extract_sql(raw: str) -> str:
    """Try to pull a SQL query out of the LLM response."""
    cleaned = _strip_markdown(raw)
    lowered = cleaned.lower()

    # If it already starts with a valid keyword, return as-is
    if lowered.startswith(("select", "with", "(")):
        return cleaned

    # Try to find a SELECT or WITH statement buried in prose
    match = re.search(r"\b(SELECT\b.+)", cleaned, re.IGNORECASE | re.DOTALL)
    if not match:
        match = re.search(r"\b(WITH\b.+)", cleaned, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    return cleaned


def validate_sql_node(state: dict) -> dict:
    node_start("validate_sql", "Validating generated SQL for safety & correctness")

    raw_sql = state["generated_query"]
    sql = _extract_sql(raw_sql)
    lowered = sql.lower()

    node_detail("validate_sql", "Cleaned SQL", sql)

    if not lowered.startswith(("select", "with", "(")):
        node_detail("validate_sql", "Raw LLM output", raw_sql)
        node_end("validate_sql", "❌ FAILED — SQL does not start with SELECT/WITH")
        raise ValueError("Generated SQL must start with SELECT, WITH, or a subquery")

    statements = [part.strip() for part in sql.split(";") if part.strip()]
    if len(statements) != 1:
        node_end("validate_sql", "❌ FAILED — multiple statements detected")
        raise ValueError("Generated SQL must contain exactly one statement")

    tokens = set(re.findall(r"\b[a-z_]+\b", lowered))
    forbidden = FORBIDDEN_SQL.intersection(tokens)
    if forbidden:
        node_end("validate_sql", f"❌ FAILED — forbidden operations: {', '.join(sorted(forbidden))}")
        raise ValueError(f"Forbidden SQL operation: {', '.join(sorted(forbidden))}")

    schema = state.get("schema") or {}
    known_tables = set(schema.keys())
    unknown_tables = _referenced_tables(sql) - known_tables
    if unknown_tables:
        node_end("validate_sql", f"FAILED - unknown tables: {', '.join(sorted(unknown_tables))}")
        raise ValueError(
            "Generated SQL referenced table(s) outside the discovered schema: "
            + ", ".join(sorted(unknown_tables))
        )

    node_detail("validate_sql", "Checks passed", "single SELECT statement, no forbidden operations")
    node_end("validate_sql", "SQL is safe to execute")
    return {**state, "generated_query": statements[0]}
