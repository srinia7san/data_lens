from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.api import router as api_router

app = FastAPI(
    title="Data Analysis API",
    description="Backend API for the LangGraph data analysis pipeline",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"status": "healthy", "message": "API is running"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("routes.server:app", host="0.0.0.0", port=8000, reload=True)

