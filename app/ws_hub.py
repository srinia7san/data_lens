"""WebSocket Hub — in-memory registry of user ↔ WebSocket connections.

When a user runs ``connector.py`` on their machine, it opens a WebSocket to
the backend.  This module stores those connections keyed by ``user_id`` and
provides ``execute_remote`` to send requests (schema discovery / SQL execution)
through the tunnel and await the response.
"""

import asyncio
import json
import uuid
from typing import Any

from fastapi import WebSocket

# user_id → WebSocket
_connections: dict[str, WebSocket] = {}

# request_id → asyncio.Future  (pending responses from the connector)
_pending: dict[str, asyncio.Future] = {}

# Default timeout (seconds) for waiting on a connector response
REMOTE_TIMEOUT = 60


def register(user_id: str, ws: WebSocket) -> None:
    """Register a WebSocket connection for a user."""
    _connections[user_id] = ws


def unregister(user_id: str) -> None:
    """Remove the WebSocket connection for a user."""
    _connections.pop(user_id, None)
    # Cancel any pending futures for this user
    to_cancel = [rid for rid, fut in _pending.items() if not fut.done()]
    for rid in to_cancel:
        if rid in _pending:
            _pending[rid].cancel()
            del _pending[rid]


def has_connection(user_id: str) -> bool:
    """Check if a user currently has an active WebSocket connector."""
    return user_id in _connections


def resolve_pending(request_id: str, payload: Any) -> None:
    """Resolve a pending future with the connector's response."""
    future = _pending.pop(request_id, None)
    if future and not future.done():
        future.set_result(payload)


def reject_pending(request_id: str, error: str) -> None:
    """Reject a pending future with an error from the connector."""
    future = _pending.pop(request_id, None)
    if future and not future.done():
        future.set_exception(RuntimeError(error))


async def execute_remote(
    user_id: str,
    action: str,
    payload: Any,
    timeout: int = REMOTE_TIMEOUT,
) -> Any:
    """Send a request to the user's connector and wait for the response.

    Parameters
    ----------
    user_id : str
        The user whose connector should handle the request.
    action : str
        ``"discover_schema"`` or ``"execute_sql"``.
    payload : Any
        The data to send (e.g. the SQL string, or connection string).
    timeout : int
        Seconds to wait before timing out.

    Returns
    -------
    The parsed response payload from the connector.

    Raises
    ------
    RuntimeError
        If the user has no active connector, the connector returns an error,
        or the request times out.
    """
    ws = _connections.get(user_id)
    if ws is None:
        raise RuntimeError("No active WebSocket connector for this user.")

    request_id = uuid.uuid4().hex
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    _pending[request_id] = future

    # Send the request to the connector script
    message = json.dumps({
        "request_id": request_id,
        "action": action,
        "payload": payload,
    })

    try:
        await ws.send_text(message)
    except Exception as exc:
        _pending.pop(request_id, None)
        unregister(user_id)
        raise RuntimeError(f"Failed to send to connector: {exc}") from exc

    # Wait for the connector to respond
    try:
        result = await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        _pending.pop(request_id, None)
        raise RuntimeError(
            f"Connector did not respond within {timeout}s. "
            "Make sure connector.py is running on the user's machine."
        )
    except asyncio.CancelledError:
        raise RuntimeError("Connector disconnected while waiting for response.")

    return result
