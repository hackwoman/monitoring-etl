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


@app.api_route("/api/v1/chat", methods=["POST"])
async def proxy_chat(request: Request):
    """Proxy to CMDB API chat endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/chat")


@app.api_route("/api/v1/alerts/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_alerts(request: Request, path: str):
    """Proxy to CMDB API alerts endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/alerts/{path}")


@app.api_route("/api/v1/alerts", methods=["GET", "POST"])
async def proxy_alerts_root(request: Request):
    """Proxy to CMDB API alerts root."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/alerts")


@app.api_route("/api/v1/records", methods=["GET"])
async def proxy_records(request: Request):
    """Proxy to CMDB API records endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/records")


@app.api_route("/api/v1/stacktraces", methods=["GET"])
async def proxy_stacktraces(request: Request):
    """Proxy to CMDB API stacktraces endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/stacktraces")


@app.api_route("/api/v1/business-discovery/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_business_discovery(request: Request, path: str):
    """Proxy to CMDB API business discovery endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/business-discovery/{path}")


@app.api_route("/api/v1/slo/{path:path}", methods=["GET"])
async def proxy_slo(request: Request, path: str):
    """Proxy to CMDB API SLO endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/slo/{path}")


@app.api_route("/api/v1/slo", methods=["GET"])
async def proxy_slo_root(request: Request):
    """Proxy to CMDB API SLO root."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/slo")


@app.api_route("/api/v1/overview", methods=["GET"])
async def proxy_overview(request: Request):
    """Proxy to CMDB API overview endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/overview")


@app.api_route("/api/v1/stats", methods=["GET"])
async def proxy_stats(request: Request):
    """Proxy to CMDB API stats endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/stats")


@app.api_route("/api/v1/health", methods=["GET"])
async def proxy_health(request: Request):
    """Proxy to CMDB API health endpoint."""
    return await _proxy(request, f"{CMDB_API_URL}/api/v1/health")


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

        try:
            content = response.json() if response.content else {}
        except Exception:
            content = {"raw": response.text[:500] if response.content else ""}

        return JSONResponse(
            content=content,
            status_code=response.status_code,
        )

