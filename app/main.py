"""ASGI entrypoint for the backend API.

Run with:
    uvicorn app.main:app --reload
"""

from routes.server import app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
