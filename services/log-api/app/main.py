from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import logs, health

app = FastAPI(
    title="Log API",
    description="日志查询服务 - ClickHouse 查询",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["logs"])
