# Hybrid AI-Driven Plotly Visualization Engine - Implementation Code

This document contains all the necessary code updates across your data analysis project (`da_project`) to implement the Hybrid AI-Driven Plotly Visualization Engine.

## 1. `app/state.py`
Update your state to handle the new AI visualization configuration fields, the single source-of-truth DataFrame, and the final HTML report path.

```python
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
    
    # -------------------------------------
    # NEW: AI Visualization metadata
    # -------------------------------------
    generated_query: str
    ai_chart_type: str
    ai_x_axis: str
    ai_y_axis: str
    ai_title: str
    ai_x_label: str
    ai_y_label: str
    
    query_results: Any
    df_path: str  # Path to parquet file containing query results
    
    # -------------------------------------
    # NEW: Validation & Rendering results
    # -------------------------------------
    final_visualization: dict
    html_report_path: str
    
    result: Any
    insights: str
    answer: str
    session_id: str
    pinecone_namespace: str
    tenant_id: str
    force_reembed: bool
```

## 2. `nodes/generate_sql.py`
Implement `pydantic` models to extract structured outputs from the LLM. 

```python
from app.llm import llm
from memory import append_turn, load_memory, new_session_id
from utils.console import node_start, node_detail, node_end
from utils.pinecone_schema_query import retrieve_top_schema
from nodes.schema import _format_table_schema 
from pydantic import BaseModel, Field

_MAX_TURNS = 10

# Pydantic schemas for structured output
class VisualizationConfig(BaseModel):
    chart_type: str = Field(description="The recommended chart type: line, bar, scatter, pie, histogram, etc.")
    x_axis: str = Field(description="The column name to use for the X-axis")
    y_axis: str = Field(description="The column name to use for the Y-axis")
    title: str = Field(description="A descriptive title for the chart")
    x_label: str = Field(description="A readable label for the X-axis")
    y_label: str = Field(description="A readable label for the Y-axis")

class SQLAndVisualizationOutput(BaseModel):
    sql_query: str = Field(description="The generated SQL query to answer the user's question")
    visualization: VisualizationConfig = Field(description="The recommended visualization configuration")

def _build_prompt(state: dict, session_id: str) -> str:
    history = load_memory(session_id)
    recent = history[-_MAX_TURNS:]
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
        -You must strictly follow Foreign Key relationships when joining tables. Never join columns that are not explicitly linked in the schema.
        - generate exactly one SELECT statement
        - use {dialect}-compatible syntax only
        - do not use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, or other write operations
        - use table and column names from the schema
        """
    return f"{convo}\n\n{instruction}" if convo else instruction


def generate_sql_node(state: dict, session_id: str | None = None) -> dict:
    node_start("generate_sql", "Generating SQL and Visualization Config")

    if session_id is None:
        session_id = state.get("session_id") or new_session_id()
        state["session_id"] = session_id

    question = state.get("question") or state.get("user_question", "")
    node_detail("generate_sql", "Question", question)
    append_turn(session_id, "user", f"question: {question}")

    # RAG Graph Traversal (Kept intact)
    pinecone_namespace = state.get("pinecone_namespace", "")
    top_schema_matches = retrieve_top_schema(question, top_k=5, namespace=pinecone_namespace)
    seed_table_names = [match[2]["table_name"] for match in top_schema_matches]
    
    full_schema = state.get("schema", {})
    selected_tables = set(seed_table_names)
    
    for table_name in seed_table_names:
        table_obj = full_schema.get(table_name)
        if not table_obj: continue
        for fk in table_obj.foreign_keys:
            selected_tables.add(fk.ref_table)
            
    for table_name, table_obj in full_schema.items():
        for fk in table_obj.foreign_keys:
            if fk.ref_table in seed_table_names:
                selected_tables.add(table_name)

    relevant_schemas = []
    for t_name in selected_tables:
        t_obj = full_schema.get(t_name)
        if t_obj:
             relevant_schemas.append(_format_table_schema(t_obj))

    schema_context = "\n\n".join(relevant_schemas)
    state["schema_context"] = schema_context
    state["relevant_tables"] = list(selected_tables)

    # ---------------------------------------------------------
    # GENERATE SQL USING STRUCTURED OUTPUT
    # ---------------------------------------------------------
    prompt = _build_prompt(state, session_id)
    structured_llm = llm.with_structured_output(SQLAndVisualizationOutput)
    response = structured_llm.invoke(prompt)
    
    generated_query = response.sql_query.strip()
    vis_config = response.visualization

    append_turn(session_id, "assistant", generated_query)
    
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
```

## 3. `nodes/sql_node.py`
Modify the execution node to generate the Pandas DataFrame and save it into the state.

```python
from app.sql_helper import get_engine, run_query
from utils.console import node_start, node_detail, node_end
import pandas as pd
import tempfile
import os

def sql_node(state):
    node_start("exec_sql", "Executing SQL against the database")

    sql = state.get("generated_query")
    connection_string = state.get("connection_string")

    if not sql:
        raise ValueError("generated_query is missing or empty")
    if not connection_string:
        raise ValueError("connection_string is missing or empty")

    node_detail("exec_sql", "Query", sql)

    engine = get_engine(connection_string)
    try:
        query_results = run_query(engine, sql)
    finally:
        engine.dispose()

          # Convert to DataFrame and save to disk
    df = pd.DataFrame(query_results)
    
    if not df.empty:
        fd, path = tempfile.mkstemp(suffix=".parquet", prefix="da_data_")
        os.close(fd)
        df.to_parquet(path)
        state["df_path"] = path
    else:
        state["df_path"] = None
    
    row_count = len(df)
    node_detail("exec_sql", "Rows returned", str(row_count))

    if not df.empty:
        node_detail("exec_sql", "Preview", str(df.head(3)))

    state["query_results"] = query_results
    state["result"] = {"rows": query_results}

    node_end("exec_sql", f"Query executed — {row_count} row(s)")
    return state
```

## 4. `nodes/validate_visualization.py`
Create this new file to act as the Rule-Based Fallback Engine to correct hallucinations.

```python
import pandas as pd
import os
from utils.console import node_start, node_detail, node_end

def validate_visualization_node(state):
    node_start("validate_viz", "Validating AI visualization recommendation")

    df_path = state.get("df_path")
    df = pd.read_parquet(df_path) if df_path and os.path.exists(df_path) else None

    ai_chart = state.get("ai_chart_type", "").lower()
    x_axis = state.get("ai_x_axis")
    y_axis = state.get("ai_y_axis")
    title = state.get("ai_title", "Data Visualization")
    
    if df is None or df.empty:
        node_detail("validate_viz", "Warning", "DataFrame is empty or missing. Cannot visualize.")
        state["final_visualization"] = None
        node_end("validate_viz", "Validation complete - empty data")
        return state
        
    columns = list(df.columns)
    valid_x = x_axis in columns
    valid_y = y_axis in columns
    
    # Simple Rule-Based Engine
    final_chart = ai_chart
    final_x = x_axis if valid_x else None
    final_y = y_axis if valid_y else None
    
    # 1. Column existence validation (Fallback to first two columns)
    if not valid_x or not valid_y:
        node_detail("validate_viz", "Issue", "AI suggested columns not in dataframe. Engaging fallback.")
        if len(columns) >= 2:
            final_x = columns[0]
            final_y = columns[1]
        elif len(columns) == 1:
            final_x = columns[0]
            final_chart = "histogram"
            
    # 2. Data size validation (e.g., Pie chart with too many categories)
    if final_chart == "pie" and final_x:
        unique_categories = df[final_x].nunique()
        if unique_categories > 15:
            node_detail("validate_viz", "Issue", "Too many categories for Pie chart. Switching to Bar chart.")
            final_chart = "bar"
            
    # Build final validated config
    config = {
        "chart_type": final_chart,
        "x_axis": final_x,
        "y_axis": final_y,
        "title": title,
        "x_label": state.get("ai_x_label", final_x),
        "y_label": state.get("ai_y_label", final_y)
    }
    
    state["final_visualization"] = config
    node_detail("validate_viz", "Final Config", str(config))
    node_end("validate_viz", "Validation complete")
    
    return state
```

## 5. `nodes/render_plotly.py`
Create this new file to generate and display the interactive HTML report using Plotly.

```python
import pandas as pd
import plotly.express as px
import tempfile
import webbrowser
import os
from utils.console import node_start, node_detail, node_end

def render_plotly_node(state):
    node_start("render_plotly", "Rendering Plotly Visualization")
    
    df_path = state.get("df_path")
    df = pd.read_parquet(df_path) if df_path and os.path.exists(df_path) else None
    config = state.get("final_visualization")
    
    if df is None or df.empty or not config:
        node_detail("render_plotly", "Skip", "No data or config to render.")
        node_end("render_plotly", "Skipped rendering")
        return state
        
    chart_type = config.get("chart_type")
    x = config.get("x_axis")
    y = config.get("y_axis")
    title = config.get("title")
    labels = {
        x: config.get("x_label", x),
        y: config.get("y_label", y)
    }
    
    fig = None
    try:
        # Match Chart Type
        if chart_type in ["bar", "column"]:
            fig = px.bar(df, x=x, y=y, title=title, labels=labels)
        elif chart_type == "line":
            fig = px.line(df, x=x, y=y, title=title, labels=labels)
        elif chart_type == "scatter":
            fig = px.scatter(df, x=x, y=y, title=title, labels=labels)
        elif chart_type == "pie":
            fig = px.pie(df, names=x, values=y, title=title)
        elif chart_type == "histogram":
            fig = px.histogram(df, x=x, title=title, labels=labels)
        else:
            # Ultimate Fallback
            fig = px.bar(df, x=x, y=y, title=title, labels=labels)
            
        fig.update_layout(template="plotly_dark") # Beautiful dark theme
        
        # Save to temporary HTML file
        fd, path = tempfile.mkstemp(suffix=".html", prefix="da_report_")
        os.close(fd)
        
        fig.write_html(path)
        state["html_report_path"] = path
        
        node_detail("render_plotly", "Report Path", path)
        
        # Auto-open in browser
        webbrowser.open_new_tab(f"file://{path}")
        
    except Exception as e:
        node_detail("render_plotly", "Error", f"Failed to render chart: {e}")
        
    node_end("render_plotly", "Rendering complete")
    return state
```

## 6. `app/graph.py`
Update your LangGraph definition to include the new nodes in the pipeline.

```python
from langgraph.graph import StateGraph, END
from app.state import AnalystState

from nodes.schema import schema_node
from nodes.generate_sql import generate_sql_node
from nodes.validate_sql import validate_sql_node
from nodes.answer_node import answer_node
from nodes.sql_node import sql_node

# Import the new nodes
from nodes.validate_visualization import validate_visualization_node
from nodes.render_plotly import render_plotly_node

def route_after_schema(state: AnalystState) -> str:
    return state["source_type"]


builder = StateGraph(AnalystState)
builder.add_node("schema", schema_node)
builder.add_node("generate_sql", generate_sql_node)
builder.add_node("validate_sql", validate_sql_node)
builder.add_node("exec_sql", sql_node)

# Add the new nodes to the graph
builder.add_node("validate_visualization", validate_visualization_node)
builder.add_node("render_plotly", render_plotly_node)

builder.add_node("answer_node", answer_node)

builder.set_entry_point("schema")

builder.add_edge("schema", "generate_sql")
builder.add_edge("generate_sql", "validate_sql")
builder.add_edge("validate_sql", "exec_sql")

# Route SQL results through the visualization engine
builder.add_edge("exec_sql", "validate_visualization")
builder.add_edge("validate_visualization", "render_plotly")
builder.add_edge("render_plotly", "answer_node")

builder.add_edge("answer_node", END)

graph = builder.compile()
```
