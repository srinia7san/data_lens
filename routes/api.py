import uuid
import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from fastapi import APIRouter, Depends, Header, HTTPException, status, WebSocket, WebSocketDisconnect, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from app import storage, ws_hub
from schema.models import (
    ChatRequest,
    AddConnectionRequest,
    LoginRequest,
    SwitchConnectionRequest,
    RemoveConnectionRequest,
    SignupRequest,
    UpdateKeysRequest,
)

router = APIRouter()
REPORTS_DIR = Path(tempfile.gettempdir()).resolve()

def _auth_response(user: dict, token: str) -> dict:
    return {"status": "success", "token": token, "user": storage.public_user(user)}


async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
        )

    token = authorization.split(" ", 1)[1].strip()
    user = storage.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    return user


# ─────────────────────────────────────────────────────────────────────────────
# CONNECTION MANAGEMENT ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Lightweight health check that does not touch LLM or database services."""
    return {"status": "healthy"}


@router.post("/auth/signup")
async def signup(request: SignupRequest):
    name = request.name.strip()
    email = request.email.strip().lower()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email is required.")
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    try:
        user = storage.create_user(
            name=name,
            email=email,
            password=request.password,
            gemini_api_key=(request.gemini_api_key or "").strip() or None,
            pinecone_api_key=(request.pinecone_api_key or "").strip() or None,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    return _auth_response(user, storage.create_auth_token(user["id"]))


@router.post("/auth/login")
async def login(request: LoginRequest):
    user = storage.authenticate_user(request.email, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return _auth_response(user, storage.create_auth_token(user["id"]))


@router.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {"status": "success", "user": storage.public_user(current_user)}


@router.put("/auth/keys")
async def update_keys(
    request: UpdateKeysRequest,
    current_user: dict = Depends(get_current_user),
):
    user = storage.update_user_keys(
        current_user["id"],
        gemini_api_key=(request.gemini_api_key or "").strip() or None,
        pinecone_api_key=(request.pinecone_api_key or "").strip() or None,
    )
    return {"status": "success", "user": storage.public_user(user)}


@router.post("/connections")
async def add_connection(
    request: AddConnectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Add a new named database connection. If this is the first connection
    in the session, it is automatically set as active."""
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Connection name cannot be empty.")

    storage.add_connection(
        user_id=current_user["id"],
        name=name,
        connection_string=request.connection_string.strip(),
        db_dialect=request.db_dialect,
    )
    active_conn = storage.get_active_connection(current_user["id"])
    connections = storage.list_connections(current_user["id"])

    return {
        "status": "success",
        "message": f"Connection '{name}' added.",
        "active_connection": active_conn["name"] if active_conn else None,
        "total_connections": len(connections),
    }


@router.get("/connections")
async def list_connections(current_user: dict = Depends(get_current_user)):
    """List all saved connections and which one is active."""
    connections = []
    active_connection = None
    for info in storage.list_connections(current_user["id"]):
        name = info["name"]
        if info["is_active"]:
            active_connection = name
        connections.append({
            "name": name,
            "db_dialect": info["db_dialect"],
            "added_at": info["added_at"],
            "is_active": bool(info["is_active"]),
            # Mask the connection string for security (show host + db only)
            "connection_hint": _mask_connection_string(info["connection_string"]),
        })

    return {
        "status": "success",
        "active_connection": active_connection,
        "connections": connections,
    }


@router.put("/connections/switch")
async def switch_connection(
    request: SwitchConnectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Switch the active database connection for a session."""
    name = request.name.strip()

    if not storage.switch_connection(current_user["id"], name):
        available = [conn["name"] for conn in storage.list_connections(current_user["id"])]
        raise HTTPException(
            status_code=404,
            detail=f"Connection '{name}' not found. Available: {available}",
        )

    return {
        "status": "success",
        "message": f"Switched active connection to '{name}'.",
        "active_connection": name,
    }


@router.delete("/connections")
async def remove_connection(
    request: RemoveConnectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Remove a saved connection. If it was the active one, auto-switch
    to the next available connection (or None if empty)."""
    name = request.name.strip()

    if not storage.remove_connection(current_user["id"], name):
        raise HTTPException(status_code=404, detail=f"Connection '{name}' not found.")

    active_conn = storage.get_active_connection(current_user["id"])
    connections = storage.list_connections(current_user["id"])

    return {
        "status": "success",
        "message": f"Connection '{name}' removed.",
        "active_connection": active_conn["name"] if active_conn else None,
        "total_connections": len(connections),
    }


# ─────────────────────────────────────────────────────────────────────────────
# WEBSOCKET CONNECTOR ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/connector")
async def connector_ws(websocket: WebSocket, token: str = Query(...)):
    await websocket.accept()
    user = storage.get_user_by_token(token)
    if not user:
        print(f"[WebSocket] Rejected invalid/expired token: {token[:8]}...")
        await websocket.send_json({"error": "Invalid or expired token. Please refresh your token from the app."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = user["id"]
    ws_hub.register(user_id, websocket)
    print(f"[WebSocket] Connector connected for user {user['email']}")

    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                msg = json.loads(data_str)
                request_id = msg.get("request_id")
                if "error" in msg:
                    ws_hub.reject_pending(request_id, msg["error"])
                else:
                    ws_hub.resolve_pending(request_id, msg.get("payload"))
            except Exception as parse_err:
                print(f"[WebSocket] Error parsing response: {parse_err}")
    except WebSocketDisconnect:
        print(f"[WebSocket] Connector disconnected for user {user['email']}")
    finally:
        ws_hub.unregister(user_id)


@router.get("/connector/status")
async def connector_status(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    is_connected = ws_hub.has_connection(user_id)
    return {"status": "success", "connected": is_connected}


@router.get("/connector/script")
async def get_connector_script():
    script_path = Path(__file__).resolve().parent.parent / "connector.py"
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Connector script not found")
    return FileResponse(script_path, filename="connector.py", media_type="text/x-python")


# ─────────────────────────────────────────────────────────────────────────────
# CHAT ENDPOINT (uses whichever connection is currently active)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    session_id = request.session_id or current_user["id"]
    active_conn = storage.get_active_connection(current_user["id"])
    if active_conn is None:
        return {
            "status": "error",
            "reply": "No database connection configured. Please add one first via POST /api/v1/connections.",
            "session_id": session_id,
            "active_connection": None,
            "connections": [],
        }

    connection_string = active_conn["connection_string"]
    db_dialect = active_conn["db_dialect"]

    # Load recent conversation history from SQLite so the LLM has context
    raw_history = storage.get_chat_history(current_user["id"], limit=20)
    chat_history = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in raw_history
    ]

    initial_state = {
        "question": request.user_message,
        "session_id": session_id,
        "tenant_id": current_user["id"],
        "user_id": current_user["id"],
        "connection_string": connection_string,
        "db_dialect": db_dialect,
        "source_type": "sql",
        "response_mode": request.response_mode,
        "gemini_api_key": current_user.get("gemini_api_key"),
        "pinecone_api_key": current_user.get("pinecone_api_key"),
        "chat_history": chat_history,
    }
    print(f"[Chat] user={current_user['email']}  active_db={active_conn['name']}  dialect={db_dialect}")
    storage.save_chat_message(
        current_user["id"],
        "user",
        request.user_message,
        response_mode=request.response_mode,
    )

    try:
        from app.graph import graph

        # Run sync graph in a thread so we don't block the FastAPI event loop
        final_state = await asyncio.to_thread(graph.invoke, initial_state)
    except Exception as e:
        error_reply = f"Pipeline failed: {str(e)}"
        storage.save_chat_message(
            current_user["id"],
            "assistant",
            error_reply,
            response_mode=request.response_mode,
        )
        return {
            "status": "error",
            "reply": error_reply,
            "session_id": session_id,
            "active_connection": active_conn["name"],
        }

    print("Pipeline finished")

    report_path = final_state.get("html_report_path", "")
    reply = final_state.get("answer", "No answer generated.")
    generated_sql = final_state.get("generated_query")
    query_results = final_state.get("query_results")
    chart_config = final_state.get("final_visualization")

    if request.response_mode == "answer":
        chart_config = None
    elif request.response_mode == "chart":
        reply = ""

    storage.save_chat_message(
        current_user["id"],
        "assistant",
        reply or "Chart generated.",
        generated_sql=generated_sql,
        query_results_json=json.dumps(jsonable_encoder(query_results)) if query_results is not None else None,
        chart_config_json=json.dumps(jsonable_encoder(chart_config)) if chart_config is not None else None,
        response_mode=request.response_mode,
    )

    return jsonable_encoder({
        "status": "success",
        "session_id": session_id,
        "active_connection": active_conn["name"],
        "reply": reply,
        "generated_sql": generated_sql,
        "query_results": query_results,
        "chart_config": chart_config,
        "report_url": f"/api/v1/report?path={report_path}" if report_path else None,
    })


@router.get("/chat/history")
async def chat_history(current_user: dict = Depends(get_current_user)):
    messages = []
    for item in storage.get_chat_history(current_user["id"]):
        messages.append({
            "role": item["role"],
            "content": item["content"],
            "generated_sql": item["generated_sql"],
            "query_results": json.loads(item["query_results_json"]) if item["query_results_json"] else None,
            "chart_config": json.loads(item["chart_config_json"]) if item["chart_config_json"] else None,
            "response_mode": item["response_mode"],
            "created_at": item["created_at"],
        })
    return {"status": "success", "messages": messages}


# ─────────────────────────────────────────────────────────────────────────────
# REPORT ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_report_path(path: str) -> Path:
    report_path = Path(path).resolve()
    if (
        REPORTS_DIR not in report_path.parents
        or report_path.suffix.lower() != ".html"
        or not report_path.name.startswith("da_report_")
    ):
        raise HTTPException(status_code=400, detail="Invalid report path")
    if not report_path.exists() or not report_path.is_file():
        raise HTTPException(status_code=404, detail="Report not found")
    return report_path


@router.get("/report")
async def get_report(path: str):
    return FileResponse(_resolve_report_path(path))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _mask_connection_string(conn_str: str) -> str:
    """Show only the host and database name from a connection string.
    e.g. 'postgresql://user:pass@localhost:5432/mydb' → 'localhost/mydb'
    """
    try:
        # Strip scheme
        after_scheme = conn_str.split("://", 1)[-1]
        # Strip user:pass@
        if "@" in after_scheme:
            after_scheme = after_scheme.split("@", 1)[-1]
        return after_scheme.split("?")[0]  # strip query params
    except Exception:
        return "***"
