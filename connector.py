#!/usr/bin/env python3
"""Local Database Connector for Data Analysis Application.

Run this script on your local machine to securely connect your local database
(e.g., PostgreSQL running on localhost:5432) to your hosted application.

Usage
-----
    python connector.py --token YOUR_AUTH_TOKEN --db postgresql://postgres:root@localhost:5432/pagila

Optionally specify --server if the app is hosted on Render or another domain:
    python connector.py --server wss://your-app.onrender.com --token YOUR_TOKEN --db postgresql://...
"""

import argparse
import asyncio
import json
import sys
import time
from typing import Any

# Check dependencies
try:
    import websockets
except ImportError:
    print("[ERROR] 'websockets' package is required. Install it using:")
    print("        pip install websockets")
    sys.exit(1)

try:
    from sqlalchemy import create_engine, inspect, text
except ImportError:
    print("[ERROR] 'sqlalchemy' package is required. Install it using:")
    print("        pip install sqlalchemy")
    sys.exit(1)


def discover_schema_dict(connection_string: str) -> dict[str, Any]:
    """Inspect local database schema and return it as a plain dictionary."""
    engine = create_engine(connection_string)
    try:
        inspector = inspect(engine)
        discovered = {}
        for table_name in inspector.get_table_names():
            columns = [
                {"name": col["name"], "datatype": str(col["type"])}
                for col in inspector.get_columns(table_name)
            ]
            pk_info = inspector.get_pk_constraint(table_name)
            primary_keys = pk_info.get("constrained_columns", []) if pk_info else []

            foreign_keys = []
            for fk in inspector.get_foreign_keys(table_name):
                for col, ref_col in zip(fk.get("constrained_columns", []), fk.get("referred_columns", [])):
                    foreign_keys.append({
                        "column": col,
                        "ref_table": fk.get("referred_table", ""),
                        "ref_column": ref_col,
                    })

            discovered[table_name] = {
                "name": table_name,
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
            }
        return discovered
    finally:
        engine.dispose()


def execute_sql_dict(connection_string: str, sql: str) -> list[dict[str, Any]]:
    """Execute SQL query against local database and return rows as dictionaries."""
    engine = create_engine(connection_string)
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = []
            for row in result:
                row_dict = {}
                for key, val in row._mapping.items():
                    # Handle non-serializable objects (datetime, Decimal, UUID, bytes)
                    if hasattr(val, "isoformat"):
                        row_dict[key] = val.isoformat()
                    elif hasattr(val, "__float__"):
                        row_dict[key] = float(val) if isinstance(val, (float, int)) else str(val)
                    elif isinstance(val, (bytes, bytearray)):
                        row_dict[key] = "<binary>"
                    else:
                        row_dict[key] = val
                rows.append(row_dict)
            return rows
    finally:
        engine.dispose()


async def run_connector(server_url: str, token: str, default_db_url: str):
    """Main connector loop with automatic reconnection."""
    # Ensure scheme is ws:// or wss://
    if server_url.startswith("http://"):
        ws_url = "ws://" + server_url[7:].rstrip("/")
    elif server_url.startswith("https://"):
        ws_url = "wss://" + server_url[8:].rstrip("/")
    elif not (server_url.startswith("ws://") or server_url.startswith("wss://")):
        ws_url = "ws://" + server_url.rstrip("/")
    else:
        ws_url = server_url.rstrip("/")

    full_ws_url = f"{ws_url}/api/v1/ws/connector?token={token}"

    print("=" * 60)
    print("  Local Database Connector for Data Analysis Application")
    print("=" * 60)
    print(f"  Server URL   : {ws_url}")
    print(f"  Target DB    : {default_db_url.split('@')[-1] if '@' in default_db_url else default_db_url}")
    print("=" * 60)

    reconnect_delay = 2

    while True:
        try:
            print(f"\n[Connecting] Establishing connection to {ws_url}...")
            async with websockets.connect(full_ws_url) as ws:
                print("[Connected] Successfully connected to server! Waiting for requests...")
                reconnect_delay = 2  # Reset delay on successful connection

                while True:
                    raw_msg = await ws.recv()
                    msg = json.loads(raw_msg)
                    request_id = msg.get("request_id")
                    action = msg.get("action")
                    payload = msg.get("payload", {})

                    print(f"\n[Request Received] Action: '{action}' (ID: {request_id[:8]})")

                    try:
                        if action == "discover_schema":
                            db_url = payload.get("connection_string") or default_db_url
                            print("  -> Inspecting local database schema...")
                            schema_result = discover_schema_dict(db_url)
                            print(f"  -> Discovered {len(schema_result)} tables successfully.")
                            response = {"request_id": request_id, "payload": schema_result}

                        elif action == "execute_sql":
                            db_url = payload.get("connection_string") or default_db_url
                            sql = payload.get("sql", "")
                            print(f"  -> Executing SQL: {sql[:100]}...")
                            rows = execute_sql_dict(db_url, sql)
                            print(f"  -> Returned {len(rows)} rows successfully.")
                            response = {"request_id": request_id, "payload": rows}

                        else:
                            response = {"request_id": request_id, "error": f"Unknown action '{action}'"}

                    except Exception as err:
                        print(f"  [ERROR] Execution failed: {err}")
                        response = {"request_id": request_id, "error": str(err)}

                    await ws.send(json.dumps(response))

        except websockets.exceptions.ConnectionClosed as e:
            print(f"[Disconnected] Connection closed: {e}")
        except Exception as e:
            print(f"[Connection Error] {e}")

        print(f"[Reconnecting] Retrying in {reconnect_delay} seconds... (Press Ctrl+C to stop)")
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 1.5, 30)


def main():
    parser = argparse.ArgumentParser(description="Data Analysis Local Database Connector")
    parser.add_argument(
        "--token",
        required=True,
        help="Your authentication token from the web application",
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Local database connection string (e.g. postgresql://user:pass@localhost:5432/dbname)",
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="Server base URL (e.g. http://localhost:8000 or https://your-app.onrender.com)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(run_connector(args.server, args.token, args.db))
    except KeyboardInterrupt:
        print("\n[Stopped] Connector shut down by user.")


if __name__ == "__main__":
    main()
