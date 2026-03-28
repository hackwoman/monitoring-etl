from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import entities, types, health
from app.database import init_db

app = FastAPI(
    title="CMDB API",
    description="配置管理数据库 - 实体/关系/类型管理",
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
app.include_router(entities.router, prefix="/api/v1/cmdb", tags=["cmdb"])
app.include_router(types.router, prefix="/api/v1/cmdb", tags=["types"])


@app.on_event("startup")
async def startup():
    await init_db()
