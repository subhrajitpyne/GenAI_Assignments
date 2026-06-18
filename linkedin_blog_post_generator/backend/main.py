import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles      # ← add this
from fastapi.responses import FileResponse       # ← add this

from api.routes import router

load_dotenv()

app: FastAPI = FastAPI(
    title="Blog Post Generator API",
    description="AI-powered LinkedIn post generator built on LangGraph multi-agent system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# ── Serve frontend ────────────────────────────────────────────────────────────

# path to frontend folder relative to backend/main.py
_frontend_path: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../frontend")
)

# serve css/ and js/ as static files
app.mount(
    "/static",
    StaticFiles(directory=_frontend_path),
    name="static",
)

# serve index.html at root URL
@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(os.path.join(_frontend_path, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)