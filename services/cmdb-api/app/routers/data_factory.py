"""
Phase 6: Demo 数据工厂 API + 持续数据生成
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import time
from datetime import datetime

router = APIRouter()

# 全局状态
pipeline_state = {"running": False, "count": 0, "scenario": None}


class ScenarioRequest(BaseModel):
    scenario: str = "microservice"  # microservice / k8s / hybrid
    count: int = 1


class ContinuousRequest(BaseModel):
    scenario: str = "microservice"
    interval_seconds: int = 10


# ---- 数据生成函数 ----

def generate_prometheus_host(hostname: str, instance: str) -> str:
    """生成主机 Prometheus 指标"""
    import random
    ts = int(time.time())
    cpu = 50 + 20 * __import__('math').sin(ts / 60) + random.gauss(0, 4)
    mem = 60 + 10 * __import__('math').sin(ts / 300) + random.gauss(0, 1)
    
    return f"""# HELP node_cpu_seconds_total Total CPU time
# TYPE node_cpu_seconds_total counter
node_cpu_seconds_total{{cpu="0",mode="idle",instance="{instance}",job="node-exporter"}} {random.uniform(100000, 200000):.2f}
node_cpu_seconds_total{{cpu="0",mode="user",instance="{instance}",job="node-exporter"}} {random.uniform(5000, 15000):.2f}
# HELP node_memory_MemTotal_bytes Total memory
# TYPE node_memory_MemTotal_bytes gauge
node_memory_MemTotal_bytes{{instance="{instance}",job="node-exporter"}} 8589934592
# HELP node_load1 1-minute load
# TYPE node_load1 gauge
node_load1{{instance="{instance}",job="node-exporter"}} {cpu/25:.2f}"""


def generate_prometheus_service(service: str, instance: str) -> str:
    """生成服务 Prometheus 指标"""
    import random
    qps = 1000 + 300 * __import__('math').sin(time.time() / 120) + random.gauss(0, 60)
    
    return f"""# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{{service="{service}",instance="{instance}",job="prometheus",method="GET",status="200"}} {random.uniform(10000, 50000):.0f}
http_requests_total{{service="{service}",instance="{instance}",job="prometheus",method="GET",status="500"}} {random.uniform(10, 100):.0f}
# HELP http_requests_qps Current QPS
# TYPE http_requests_qps gauge
http_requests_qps{{service="{service}",instance="{instance}",job="prometheus"}} {qps:.2f}"""


def generate_json_log() -> str:
    """生成 JSON 日志"""
    import random
    levels = ["info", "warn", "error"]
    services = ["api-gateway", "user-service", "order-service"]
    messages = {
        "info": "Request completed",
        "warn": "Slow query detected",
        "error": "Connection timeout",
    }
    level = random.choice(levels)
    
    return json.dumps({
        "timestamp": datetime.now().isoformat() + "Z",
        "level": level,
        "service": random.choice(services),
        "message": messages[level],
        "duration_ms": random.randint(1, 5000),
    })


def generate_logfmt_log() -> str:
    """生成 Logfmt 日志"""
    import random
    level = random.choice(["info", "warn", "error"])
    service = random.choice(["api-gateway", "user-service", "order-service"])
    
    return f'ts={datetime.now().isoformat()}Z level={level} msg="Request processed" service={service} duration_ms={random.randint(1, 5000)}'


# ---- API 端点 ----

@router.post("/data-factory/generate")
async def generate_data(body: ScenarioRequest):
    """生成一批数据"""
    results = []
    
    for _ in range(body.count):
        if body.scenario == "microservice":
            prom_data = []
            for svc in ["api-gateway", "user-service", "order-service", "payment-service"]:
                prom_data.append(generate_prometheus_service(svc, f"10.0.0.{hash(svc) % 255}:8080"))
            
            log_data = [generate_json_log() for _ in range(5)]
            
            results.append({
                "prometheus": '\n'.join(prom_data),
                "json_logs": '\n'.join(log_data),
            })
        
        elif body.scenario == "k8s":
            prom_data = []
            for node in ["k8s-node-01", "k8s-node-02", "k8s-node-03"]:
                prom_data.append(generate_prometheus_host(node, f"{node}:9100"))
            
            log_data = [generate_logfmt_log() for _ in range(3)]
            
            results.append({
                "prometheus": '\n'.join(prom_data),
                "logfmt_logs": '\n'.join(log_data),
            })
        
        elif body.scenario == "hybrid":
            prom_data = [
                generate_prometheus_host("web-server-01", "10.0.0.1:9100"),
                generate_prometheus_host("db-server-01", "10.0.0.2:9100"),
            ]
            
            log_data = [generate_json_log() for _ in range(4)]
            
            results.append({
                "prometheus": '\n'.join(prom_data),
                "json_logs": '\n'.join(log_data),
            })
    
    return {
        "scenario": body.scenario,
        "count": len(results),
        "data": results,
    }


@router.post("/data-factory/continuous/start")
async def start_continuous(body: ContinuousRequest, background_tasks: BackgroundTasks):
    """启动持续数据生成"""
    if pipeline_state["running"]:
        return {"status": "already_running", "count": pipeline_state["count"]}
    
    pipeline_state["running"] = True
    pipeline_state["scenario"] = body.scenario
    pipeline_state["count"] = 0
    
    async def run_pipeline():
        while pipeline_state["running"]:
            pipeline_state["count"] += 1
            await asyncio.sleep(body.interval_seconds)
    
    background_tasks.add_task(run_pipeline)
    
    return {
        "status": "started",
        "scenario": body.scenario,
        "interval": body.interval_seconds,
    }


@router.post("/data-factory/continuous/stop")
async def stop_continuous():
    """停止持续数据生成"""
    pipeline_state["running"] = False
    return {
        "status": "stopped",
        "total_count": pipeline_state["count"],
    }


@router.get("/data-factory/status")
async def get_status():
    """获取数据工厂状态"""
    return {
        "running": pipeline_state["running"],
        "count": pipeline_state["count"],
        "scenario": pipeline_state["scenario"],
    }


@router.get("/data-factory/scenarios")
async def list_scenarios():
    """列出支持的场景"""
    return {
        "scenarios": [
            {"name": "microservice", "description": "微服务架构：API网关 + 3个后端服务", "formats": ["prometheus", "json_logs"]},
            {"name": "k8s", "description": "K8s集群：3个节点 + Pod日志", "formats": ["prometheus", "logfmt_logs"]},
            {"name": "hybrid", "description": "混合环境：物理机 + 数据库 + Redis", "formats": ["prometheus", "json_logs"]},
        ]
    }
