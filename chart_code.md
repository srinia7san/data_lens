# Chart Plotting — All Code Files

Copy each section exactly into the corresponding file.

---

## 1. `nodes/chart_node.py` *(NEW FILE — create this)*

```python
import os
import traceback
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend — safe for terminal use
import matplotlib.pyplot as plt

from utils.console import node_start, node_detail, node_end


# ─────────────────────────────────────────────
# CHART TYPE DETECTION
# ─────────────────────────────────────────────

def detect_chart_type(df: pd.DataFrame) -> str:
    """
    Automatically pick the best chart type based on the shape of the data.

    Rules:
    - 1 categorical col + 1 numeric col + ≤ 8 rows  → pie
    - 1 categorical col + 1 numeric col              → bar
    - any col that looks like a date/time            → line
    - 2+ numeric cols                                → line
    - anything else                                  → table (no chart)
    """
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols     = df.select_dtypes(exclude="number").columns.tolist()

    # Check for date/time columns
    has_time = any(
        pd.api.types.is_datetime64_any_dtype(df[c]) or
        "date" in c.lower() or "time" in c.lower() or "year" in c.lower() or "month" in c.lower()
        for c in df.columns
    )

    if has_time and numeric_cols:
        return "line"

    if len(cat_cols) >= 1 and len(numeric_cols) == 1 and len(df) <= 8:
        return "pie"

    if len(cat_cols) >= 1 and len(numeric_cols) >= 1:
        return "bar"

    if len(numeric_cols) >= 2:
        return "line"

    return "table"  # fallback — no chart drawn


# ─────────────────────────────────────────────
# CHART DRAWING
# ─────────────────────────────────────────────

def draw_chart(df: pd.DataFrame, chart_type: str, question: str, output_dir: str = "charts") -> str:
    """
    Draw and save the chart. Returns the file path of the saved image.
    """
    os.makedirs(output_dir, exist_ok=True)

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols     = df.select_dtypes(exclude="number").columns.tolist()

    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor("#1e1e2e")
    ax.set_facecolor("#1e1e2e")

    title = question[:80] + ("…" if len(question) > 80 else "")

    # ── BAR CHART ──────────────────────────────
    if chart_type == "bar":
        x_col = cat_cols[0]
        y_col = numeric_cols[0]
        labels = df[x_col].astype(str).tolist()
        values = df[y_col].tolist()

        bars = ax.bar(labels, values, color="#7c3aed", edgecolor="#a78bfa", linewidth=0.8)

        # value labels on top of bars
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.01,
                f"{val:,.0f}" if isinstance(val, (int, float)) else str(val),
                ha="center", va="bottom", fontsize=8, color="white"
            )

        ax.set_xlabel(x_col, color="white")
        ax.set_ylabel(y_col, color="white")
        plt.xticks(rotation=30, ha="right", color="white", fontsize=8)
        plt.yticks(color="white")

    # ── PIE CHART ──────────────────────────────
    elif chart_type == "pie":
        x_col = cat_cols[0]
        y_col = numeric_cols[0]
        labels = df[x_col].astype(str).tolist()
        values = df[y_col].tolist()
        colors = ["#7c3aed", "#2563eb", "#059669", "#d97706", "#dc2626",
                  "#7c3aed", "#8b5cf6", "#6366f1"]

        ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            colors=colors[:len(values)],
            textprops={"color": "white"},
            startangle=140,
            wedgeprops={"edgecolor": "#1e1e2e", "linewidth": 1.5}
        )

    # ── LINE CHART ─────────────────────────────
    elif chart_type == "line":
        x_col = df.columns[0]
        line_colors = ["#7c3aed", "#2563eb", "#059669", "#d97706"]
        x_labels = df[x_col].astype(str).tolist()

        for i, col in enumerate(numeric_cols):
            ax.plot(
                x_labels,
                df[col].tolist(),
                marker="o",
                label=col,
                color=line_colors[i % len(line_colors)],
                linewidth=2,
                markersize=5
            )

        ax.legend(facecolor="#2d2d3f", labelcolor="white")
        ax.set_xlabel(x_col, color="white")
        plt.xticks(rotation=30, ha="right", color="white", fontsize=8)
        plt.yticks(color="white")

    # ── TITLE & STYLE ──────────────────────────
    ax.set_title(title, color="white", fontsize=11, pad=12)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#3d3d5c")

    plt.tight_layout()

    path = os.path.join(output_dir, "latest_chart.png")
    plt.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    return os.path.abspath(path)


# ─────────────────────────────────────────────
# LANGGRAPH NODE
# ─────────────────────────────────────────────

def chart_node(state: dict) -> dict:
    """
    LangGraph node — generates a chart from query result rows.
    Never raises — pipeline continues even if charting fails.
    """
    node_start("chart_node", "Generating chart from query results")

    try:
        rows = state.get("result", {}).get("rows", [])

        if not rows:
            node_detail("chart_node", "Skip", "No rows returned — skipping chart")
            state["chart_path"] = ""
            state["chart_type"] = "none"
            node_end("chart_node", "No chart generated (empty result)")
            return state

        df = pd.DataFrame(rows)

        if df.empty or len(df.columns) < 2:
            node_detail("chart_node", "Skip", "DataFrame has fewer than 2 columns — skipping chart")
            state["chart_path"] = ""
            state["chart_type"] = "table"
            node_end("chart_node", "No chart generated (not enough columns)")
            return state

        chart_type = detect_chart_type(df)
        node_detail("chart_node", "Detected chart type", chart_type)

        if chart_type == "table":
            node_detail("chart_node", "Skip", "Data is tabular — no chart drawn")
            state["chart_path"] = ""
            state["chart_type"] = "table"
            node_end("chart_node", "No chart generated (table data)")
            return state

        path = draw_chart(df, chart_type, state.get("question", ""))
        state["chart_path"] = path
        state["chart_type"] = chart_type

        node_detail("chart_node", "Chart saved", path)
        node_end("chart_node", f"{chart_type.upper()} chart saved ✓")

    except Exception:
        # NEVER crash the pipeline
        node_detail("chart_node", "ERROR", traceback.format_exc())
        state["chart_path"] = ""
        state["chart_type"] = "error"
        node_end("chart_node", "Chart generation failed — pipeline continues")

    return state
```

---

## 2. `app/state.py` *(ADD 2 lines)*

Add `chart_path` and `chart_type` to the existing `AnalystState` class:

```python
from typing import Any, Literal, TypedDict


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
    query_results: Any
    result: Any
    insights: str
    answer: str
    session_id: str
    pinecone_namespace: str
    tenant_id: str
    force_reembed: bool
    # ── NEW ───────────────────────────────────
    chart_path: str        # absolute path to saved chart image (empty if none)
    chart_type: str        # "bar" | "line" | "pie" | "table" | "none" | "error"
```

---

## 3. `app/graph.py` *(ADD chart_node between exec_sql and answer_node)*

```python
from langgraph.graph import StateGraph, END
from app.state import AnalystState

from nodes.schema import schema_node
from nodes.generate_sql import generate_sql_node
from nodes.validate_sql import validate_sql_node
from nodes.answer_node import answer_node
from nodes.sql_node import sql_node
from nodes.chart_node import chart_node          # ← NEW


def route_after_schema(state: AnalystState) -> str:
    return state["source_type"]


builder = StateGraph(AnalystState)
builder.add_node("schema",       schema_node)
builder.add_node("generate_sql", generate_sql_node)
builder.add_node("validate_sql", validate_sql_node)
builder.add_node("exec_sql",     sql_node)
builder.add_node("chart_node",   chart_node)     # ← NEW
builder.add_node("answer_node",  answer_node)

builder.set_entry_point("schema")

builder.add_edge("schema",       "generate_sql")
builder.add_edge("generate_sql", "validate_sql")
builder.add_edge("validate_sql", "exec_sql")
builder.add_edge("exec_sql",     "chart_node")   # ← CHANGED (was answer_node)
builder.add_edge("chart_node",   "answer_node")  # ← NEW
builder.add_edge("answer_node",  END)

graph = builder.compile()
```

---

## 4. `app/chat.py` *(ADD chart display after pipeline runs)*

```python
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.graph import graph
from utils.console import pipeline_start, pipeline_end

def run_chat():
    print("=" * 80)
    print("🧠 DATA ANALYST INTERACTIVE TERMINAL")
    print("Type 'exit' or 'quit' to close.")
    print("=" * 80)

    session_id = None

    while True:
        try:
            question = input("\n📝 Ask a question: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if question.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if not question:
            continue

        pipeline_start(question)

        state_input = {
            "question":          question,
            "connection_string": os.getenv("DATABASE_URL"),
            "db_dialect":        "PostgreSQL",
        }

        if session_id:
            state_input["session_id"] = session_id

        try:
            result     = graph.invoke(state_input)
            session_id = result.get("session_id")
            pipeline_end(result)

            # ── Print answer ───────────────────────────────────────────────
            final_answer = result.get("answer")
            if final_answer:
                print("\n" + "=" * 40)
                print("🤖 ANSWER:")
                print(final_answer)
                print("=" * 40)

            # ── Show chart ─────────────────────────────────────────────────  ← NEW
            chart_path = result.get("chart_path", "")
            chart_type = result.get("chart_type", "none")

            if chart_path and os.path.exists(chart_path):
                print(f"\n📊 Chart ({chart_type}): {chart_path}")
                try:
                    # Windows: open the image in the default viewer
                    subprocess.Popen(["start", "", chart_path], shell=True)
                except Exception:
                    pass  # viewer launch is optional — never crash
            elif chart_type in ("table", "none"):
                print("\n📋 Result is tabular — no chart generated.")
            elif chart_type == "error":
                print("\n⚠️  Chart generation failed (see logs above).")

        except Exception as e:
            print(f"\n❌ Pipeline failed: {e}")

if __name__ == "__main__":
    run_chat()
```

---

## 5. Install dependency

Run once in your activated venv:

```bash
pip install matplotlib
```

---

## Quick Reference — What changed where

| File | Change |
|---|---|
| `nodes/chart_node.py` | **NEW** — entire file |
| `app/state.py` | +2 lines (`chart_path`, `chart_type`) |
| `app/graph.py` | +2 imports, +1 node, +1 edge changed, +1 edge added |
| `app/chat.py` | +`import subprocess`, +chart display block after answer |
