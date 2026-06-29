import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import router

load_dotenv()

# ensure workspace exists
os.makedirs("workspace", exist_ok=True)

app: FastAPI = FastAPI(
    title="Coding Assistant API",
    description="Multi-agent coding assistant powered by LangGraph",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# serve frontend
_frontend_path: str = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../frontend")
)

app.mount(
    "/static",
    StaticFiles(directory=_frontend_path),
    name="static",
)

@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(os.path.join(_frontend_path, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["workspace/*", "workspace/**/*"],  # ← exclude workspace
    )
