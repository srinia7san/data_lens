import re
from app.llm import get_llm
from utils.console import node_start, node_detail, node_end
from utils.pinecone_schema_query import retrieve_top_schema
from nodes.schema import _format_table_schema
from pydantic import BaseModel, Field

_MAX_HISTORY_TURNS = 10

from typing import Literal

class VisualizationConfig(BaseModel):
    chart_type: Literal["line", "bar", "scatter", "pie", "histogram", "violin", "box", "area", "treemap", "sunburst", "funnel"] = Field(description="The exact chart type to render.")
    x_axis: str = Field(description="The column name to use for the X-axis")
    y_axis: str = Field(description="The column name to use for the Y-axis")
    title: str = Field(description="A descriptive title for the chart")
    x_label: str = Field(description="A readable label for the X-axis")
    y_label: str = Field(description="A readable label for the Y-axis")

class SQLAndVisualizationOutput(BaseModel):
    can_answer: bool = Field(description="Whether the question can be answered exactly using only the provided database schema.")
    refusal_reason: str = Field(description="Plain-text reason when can_answer is false, otherwise empty.")
    sql_query: str = Field(description="The generated SQL query to answer the user's question")
    visualization: VisualizationConfig = Field(description="The recommended visualization configuration")


def _normalize_token(token: str) -> str:
    token = token.lower().strip("_")
    return token[:-1] if len(token) > 3 and token.endswith("s") else token


def _schema_token_overlap(question: str, schema: dict) -> set[str]:
    question_tokens = {_normalize_token(t) for t in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", question)}
    schema_tokens = set()
    for table_name, table in schema.items():
        schema_tokens.update(_normalize_token(part) for part in table_name.split("_"))
        for column in table.columns:
            schema_tokens.update(_normalize_token(part) for part in column.name.split("_"))
    stopwords = {"show", "give", "tell", "what", "which", "total", "count", "average", "avg", "top", "bottom", "by", "for", "the", "and", "or"}
    return (question_tokens - stopwords) & schema_tokens


def _build_prompt(state: dict) -> str:
    # Build conversation context from chat history stored in SQLite
    history = state.get("chat_history") or []
    recent = history[-_MAX_HISTORY_TURNS:]
    convo = "\n".join(f"{t['role']}: {t['content']}" for t in recent)

    question = state.get("question") or state.get("user_question", "")
    schema_context = state.get("schema_context", "")
    dialect = state.get("db_dialect", "SQL")

    instruction = f"""
        you are an expert {dialect} data analyst

        database: {dialect}
        database schema:
        {schema_context}

        question:
        {question}

        Rules Strict:
        - If the question is not related to this database schema, set can_answer=false and do not invent SQL.
        - If the exact answer cannot be produced from the listed tables/columns, set can_answer=false.
        -You must strictly follow Foreign Key relationships when joining tables. Never join columns that are not explicitly linked in the schema.
        - Generate SQL only when can_answer=true.
        - generate exactly one SELECT statement
        - use {dialect}-compatible syntax only
        - do not use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, or other write operations
        - use table and column names from the schema
        - Do not guess table names, column names, categories, dates, or business definitions.

        """
    return f"{convo}\n\n{instruction}" if convo else instruction


def generate_sql_node(state: dict) -> dict:
    node_start("generate_sql", "Generating SQL from natural language question")

    question = state.get("question") or state.get("user_question", "")
    node_detail("generate_sql", "Question", question)

    # =========================================================================
    # PRODUCTION RAG: VECTOR SEARCH + GRAPH TRAVERSAL
    # =========================================================================
    
    # 1. Semantic Search: Get seed tables from Pinecone
    pinecone_namespace = state.get("pinecone_namespace", "")
    top_schema_matches = retrieve_top_schema(
        question,
        top_k=5,
        namespace=pinecone_namespace,
        gemini_api_key=state.get("gemini_api_key"),
        pinecone_api_key=state.get("pinecone_api_key"),
    )
    seed_table_names = [match[2]["table_name"] for match in top_schema_matches]
    
    # 2. Graph Traversal: Find connected tables via Foreign Keys
    full_schema = state.get("schema", {})
    if not full_schema:
        raise ValueError("No database schema was discovered, so I cannot answer this exactly.")

    max_score = max((match[1] or 0 for match in top_schema_matches), default=0)
    token_overlap = _schema_token_overlap(question, full_schema)
    if not seed_table_names or (max_score < 0.25 and not token_overlap):
        raise ValueError("This question does not appear to be related to the connected database schema.")

    selected_tables = set(seed_table_names)
    
    for table_name in seed_table_names:
        table_obj = full_schema.get(table_name)
        if not table_obj:
            continue
            
        # Add tables that this seed table points TO
        for fk in table_obj.foreign_keys:
            selected_tables.add(fk.ref_table)
            
    # Add tables that point TO our seed tables (reverse relationships)
    for table_name, table_obj in full_schema.items():
        for fk in table_obj.foreign_keys:
            if fk.ref_table in seed_table_names:
                selected_tables.add(table_name)

    node_detail("generate_sql", "Graph Traversal", f"Expanded {len(seed_table_names)} seed tables to {len(selected_tables)} total tables")

    # 3. Context Assembly
    relevant_schemas = []
    for t_name in selected_tables:
        t_obj = full_schema.get(t_name)
        if t_obj:
             relevant_schemas.append(_format_table_schema(t_obj))

    # Save exactly what the LLM is looking at into state
    schema_context = "\n\n".join(relevant_schemas)
    state["schema_context"] = schema_context
    state["relevant_tables"] = list(selected_tables)
    node_detail("generate_sql", "Final Tables Sent to LLM", ", ".join(state["relevant_tables"]))

    # =========================================================================

    # Generate the SQL
    prompt = _build_prompt(state)
    structured_llm = get_llm(state.get("gemini_api_key")).with_structured_output(SQLAndVisualizationOutput)
    response = structured_llm.invoke(prompt)

    if not response.can_answer:
        reason = response.refusal_reason or "This question cannot be answered exactly from the connected database."
        raise ValueError(reason)

    generated_query = response.sql_query.strip()
    vis_config = response.visualization


    # Store all outputs in State
    state["generated_query"] = generated_query
    state["ai_chart_type"] = vis_config.chart_type
    state["ai_x_axis"] = vis_config.x_axis
    state["ai_y_axis"] = vis_config.y_axis
    state["ai_title"] = vis_config.title
    state["ai_x_label"] = vis_config.x_label
    state["ai_y_label"] = vis_config.y_label

    node_detail("generate_sql", "Generated SQL", generated_query)
    node_detail("generate_sql", "AI Chart Type", vis_config.chart_type)
    node_end("generate_sql", "SQL & Visualization config generated")
    
    return state
