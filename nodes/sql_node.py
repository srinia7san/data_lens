import asyncio

from app.sql_helper import get_engine, run_query
from app import ws_hub
from utils.console import node_start, node_detail, node_end
import pandas as pd
import tempfile
import os


def sql_node(state):
    node_start("exec_sql", "Executing SQL against the database")

    sql = state.get("generated_query")
    connection_string = state.get("connection_string")
    user_id = state.get("user_id")

    if not sql:
        raise ValueError("generated_query is missing or empty")

    if not connection_string:
        raise ValueError("connection_string is missing or empty")

    node_detail("exec_sql", "Query", sql)

    # Route through WebSocket connector if available, otherwise use direct connection
    if user_id and ws_hub.has_connection(user_id):
        node_detail("exec_sql", "Mode", "WebSocket connector (remote)")
        try:
            query_results = asyncio.get_event_loop().run_until_complete(
                ws_hub.execute_remote(user_id, "execute_sql", {"sql": sql})
            )
        except RuntimeError:
            # If we're already in an async context (called via asyncio.to_thread),
            # we need a new event loop
            loop = asyncio.new_event_loop()
            try:
                query_results = loop.run_until_complete(
                    ws_hub.execute_remote(user_id, "execute_sql", {"sql": sql})
                )
            finally:
                loop.close()
    else:
        node_detail("exec_sql", "Mode", "Direct SQLAlchemy connection")
        engine = get_engine(connection_string)
        try:
            query_results = run_query(engine, sql)
        finally:
            engine.dispose()

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
