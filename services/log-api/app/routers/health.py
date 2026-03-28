"""Health check routes."""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "log-api",
        "timestamp": datetime.utcnow().isoformat(),
    }
