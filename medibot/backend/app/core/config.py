from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    openai_api_key: str = ""
    qdrant_path: str = r"C:\Users\Subhrajit.Pyne\OneDrive - Wolters Kluwer\Desktop\CodeBasics_Projects\medibot\backend\qdrant_storage"
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    secret_key: str = "39edaa67e507c77c8386a13fd05fb8b595228f56abd25fee7dfeb8d2007a6c70"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    data_dir: str = r"C:\Users\Subhrajit.Pyne\OneDrive - Wolters Kluwer\Desktop\CodeBasics_Projects\medibot\data"
    db_path: str = r"C:\Users\Subhrajit.Pyne\OneDrive - Wolters Kluwer\Desktop\CodeBasics_Projects\medibot\data\db\mediassist.db"

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        extra = "ignore"

settings = Settings()

ROLE_COLLECTIONS = {
    "doctor": ["clinical", "nursing", "general"],
    "nurse": ["nursing", "general"],
    "billing_executive": ["billing", "general"],
    "technician": ["equipment", "general"],
    "admin": ["clinical", "nursing", "billing", "equipment", "general"],
}

COLLECTION_ACCESS = {
    "general": ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical": ["doctor", "admin"],
    "nursing": ["nurse", "doctor", "admin"],
    "billing": ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}

SQL_ALLOWED_ROLES = ["billing_executive", "admin"]

DEMO_USERS = {
    "dr.subhrajit": {"password": "doctor123", "role": "doctor", "name": "Dr. Subhrajit Pyne"},
    "nurse.ankita": {"password": "nurse123", "role": "nurse", "name": "Ankita Pyne"},
    "billing.aradhana": {"password": "billing123", "role": "billing_executive", "name": "Aradhana Singh"},
    "tech.anand": {"password": "tech123", "role": "technician", "name": "Anand Singh"},
    "admin.sys": {"password": "admin123", "role": "admin", "name": "System Admin"},
}

QDRANT_COLLECTION = "mediassist"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
INITIAL_RETRIEVE_K = 10
RERANK_TOP_K = 3
