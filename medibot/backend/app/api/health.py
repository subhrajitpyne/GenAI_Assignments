from fastapi import APIRouter
from app.ingestion.ingest import get_qdrant
from app.core.config import QDRANT_COLLECTION

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """System health check."""
    try:
        client = get_qdrant()
        collections = client.get_collections()
        coll_names = [c.name for c in collections.collections]
        ingested = QDRANT_COLLECTION in coll_names
        chunk_count = 0
        if ingested:
            chunk_count = client.count(QDRANT_COLLECTION).count

        return {
            "status": "healthy",
            "qdrant": "connected",
            "collection": QDRANT_COLLECTION,
            "ingested": ingested,
            "chunk_count": chunk_count,
        }
    except Exception as e:
        return {
            "status": "degraded",
            "qdrant": f"error: {str(e)}",
            "collection": QDRANT_COLLECTION,
            "ingested": False,
            "chunk_count": 0,
        }
