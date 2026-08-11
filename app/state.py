from typing import Any, Literal, TypedDict
import pandas as pd

class AnalystState(TypedDict, total=False):
    source_type: Literal["csv", "sql"]
    csv_path: str
    connection_string: str
    question: str
    db_dialect: str
    user_question: str
    schema: Any
    schema_graph: dict
    relevant_tables: list[str]
    schema_context: str
    code: str
    generated_query: str
    ai_chart_type: str
    ai_x_axis: str
    ai_y_axis: str
    ai_title: str
    ai_x_label: str
    ai_y_label: str
    df_path: str
    final_visualization: dict
    html_report_path: str
    query_results: Any
    result: Any
    insights: str
    answer: str
    session_id: str
    pinecone_namespace: str
    tenant_id: str
    force_reembed: bool
    response_mode: str
    gemini_api_key: str
    pinecone_api_key: str
    # Conversation memory — list of {"role": "user"|"assistant", "content": "..."}
    chat_history: list[dict[str, str]]
    # User identifier — used to look up WebSocket connector in ws_hub
    user_id: str

