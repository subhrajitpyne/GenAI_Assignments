from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api import auth_router, chat_router, health_router

app = FastAPI(
    title="MediBot API",
    description="Advanced RAG system for MediAssist Health Network with RBAC",
    version="1.0.0",
)

# CORS — allow all origins so the plain HTML file works
# when opened from disk (file://) or any local server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(health_router)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")

@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_PATH, "index.html"))