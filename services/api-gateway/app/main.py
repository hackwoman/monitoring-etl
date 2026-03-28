"""API Gateway - routes requests to backend services."""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from datetime import datetime

app = FastAPI(
    title="Monitoring ETL API Gateway",
    description="统一 API 入口",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CMDB_API_URL = os.getenv("CMDB_API_URL", "http://localhost:8001")
LOG_API_URL = os.getenv("LOG_API_URL", "http://localhost:8002")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "api-gateway", "timestamp": datetime.utcnow().isoformat()}


@app.api_route("/api/v1/cmdb/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_cmdb(request: Request, path: str):
    """Proxy to CMDB API."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/cmdb/{path}")


@app.api_route("/api/v1/logs/{path:path}", methods=["GET", "POST"])
async def proxy_logs(request: Request, path: str):
    """Proxy to Log API."""
    return await _proxy(request, f"{LOG_API_URL}/api/v1/logs/{path}")


async def _proxy(request: Request, target_url: str):
    """Generic proxy handler."""
    async with httpx.AsyncClient(timeout=30) as client:
        body = await request.body()
        headers = dict(request.headers)
        headers.pop("host", None)

        response = await client.request(
            method=request.method,
            url=target_url,
            params=dict(request.query_params),
            content=body,
            headers=headers,
        )

        return JSONResponse(
            content=response.json() if response.content else {},
            status_code=response.status_code,
        )
