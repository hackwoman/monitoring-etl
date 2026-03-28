"""Health check routes."""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "cmdb-api",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/api/v1/health")
async def health_v1():
    return await health()
