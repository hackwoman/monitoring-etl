from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import entities, types, health, overview, discover, heartbeat, chat, alerts, records, stats, business_mapping, etl, business_discovery, slo, topology, compensation, smart_etl, data_factory
from app.database import init_db

app = FastAPI(
    title="CMDB API",
    description="可观测智能平台 - 认知层API",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(topology.router, prefix="/api/v1/cmdb", tags=["topology"])
app.include_router(entities.router, prefix="/api/v1/cmdb", tags=["cmdb"])
app.include_router(types.router, prefix="/api/v1/cmdb", tags=["types"])
app.include_router(overview.router, prefix="/api/v1", tags=["overview"])
app.include_router(discover.router, prefix="/api/v1/cmdb", tags=["discover"])
app.include_router(heartbeat.router, prefix="/api/v1/cmdb", tags=["heartbeat"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(alerts.router, prefix="/api/v1", tags=["alerts"])
app.include_router(records.router, prefix="/api/v1", tags=["records"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(business_mapping.router, tags=["business-mapping"])
app.include_router(etl.router, tags=["etl"])
app.include_router(business_discovery.router, prefix="/api/v1", tags=["business-discovery"])
app.include_router(data_factory.router, prefix="/api/v1/cmdb", tags=["data_factory"])
app.include_router(smart_etl.router, prefix="/api/v1/cmdb", tags=["smart_etl"])
app.include_router(compensation.router, prefix="/api/v1/cmdb", tags=["compensation"])
app.include_router(slo.router, prefix="/api/v1", tags=["slo"])


@app.on_event("startup")
async def startup():
    await init_db()
