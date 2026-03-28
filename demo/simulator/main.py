#!/usr/bin/env python3
"""
监控 ETL 平台 - Demo 模拟器
持续产生结构化日志，走完整管道（OTel → Vector → ClickHouse → CMDB）

用法:
  python main.py                    # 默认 1 req/s
  python main.py --rps 5            # 5 req/s
  python main.py --scenario slow    # 慢查询场景
"""

import json
import time
import random
import uuid
import os
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ============================================================
# 配置
# ============================================================

LOG_DIR = os.getenv("LOG_DIR", "/var/log/app")
RPS_DEFAULT = 1.0

# 服务定义
SERVICES = {
    "gateway": {
        "host": "gw-01",
        "endpoints": [
            {"method": "POST", "path": "/api/order", "base_latency": 15, "weight": 40},
            {"method": "POST", "path": "/api/login", "base_latency": 10, "weight": 30},
            {"method": "GET", "path": "/api/inventory", "base_latency": 8, "weight": 20},
            {"method": "GET", "path": "/api/health", "base_latency": 2, "weight": 10},
        ]
    },
    "order-service": {
        "host": "app-01",
        "endpoints": [
            {"method": "POST", "path": "/order/create", "base_latency": 120, "weight": 50},
            {"method": "GET", "path": "/order/list", "base_latency": 45, "weight": 30},
            {"method": "GET", "path": "/order/detail", "base_latency": 30, "weight": 20},
        ]
    },
    "payment-service": {
        "host": "app-02",
        "endpoints": [
            {"method": "POST", "path": "/pay/process", "base_latency": 80, "weight": 60},
            {"method": "GET", "path": "/pay/status", "base_latency": 20, "weight": 40},
        ]
    },
    "inventory-service": {
        "host": "app-03",
        "endpoints": [
            {"method": "GET", "path": "/stock/query", "base_latency": 35, "weight": 50},
            {"method": "POST", "path": "/stock/deduct", "base_latency": 50, "weight": 30},
            {"method": "POST", "path": "/stock/restock", "base_latency": 40, "weight": 20},
        ]
    },
}

# 调用链定义
CALL_CHAINS = {
    "create_order": ["gateway", "order-service", "payment-service", "inventory-service"],
    "user_login": ["gateway", "order-service"],
    "query_inventory": ["gateway", "inventory-service"],
    "check_payment": ["gateway", "payment-service"],
}

# 场景故障配置
SCENARIOS = {
    "normal": {
        "description": "正常运营",
        "faults": {},
    },
    "slow_db": {
        "description": "payment-db 慢查询",
        "faults": {
            "payment-service": {"error_rate": 0.3, "latency_multiplier": 8, "error_msg": "ConnectionTimeout: payment-db:3306 after 5000ms"},
        },
    },
    "cascade": {
        "description": "级联故障：payment-db → payment → order",
        "faults": {
            "payment-service": {"error_rate": 0.6, "latency_multiplier": 10, "error_msg": "ConnectionTimeout: payment-db:3306"},
            "order-service": {"error_rate": 0.25, "latency_multiplier": 3, "error_msg": "PaymentServiceException: payment failed after 3 retries"},
        },
    },
    "high_load": {
        "description": "order-service 高负载",
        "faults": {
            "order-service": {"error_rate": 0.1, "latency_multiplier": 5, "error_msg": "Thread pool exhausted, request queued"},
        },
    },
}

# ============================================================
# 日志模板
# ============================================================

NORMAL_MESSAGES = {
    "gateway": [
        "Request received: {method} {path} from {client_ip}",
        "Upstream responded: {status_code} in {latency}ms",
        "Request forwarded to {target_service}",
    ],
    "order-service": [
        "Processing order for user_{user_id}",
        "Order created: order_{order_id}, amount={amount}",
        "Order queried: order_{order_id}",
        "Calling payment-service for order_{order_id}",
    ],
    "payment-service": [
        "Processing payment for order_{order_id}",
        "Payment recorded: pay_{pay_id}, amount={amount}",
        "Payment status queried: pay_{pay_id} = completed",
        "Calling alipay-gateway for order_{order_id}",
    ],
    "inventory-service": [
        "Stock queried: product_{product_id} = {stock} units",
        "Stock deducted: product_{product_id}, -1, remaining={stock}",
        "Stock restocked: product_{product_id}, +{qty}",
    ],
}

# ============================================================
# 工具函数
# ============================================================

def generate_trace_id():
    return uuid.uuid4().hex

def generate_span_id():
    return uuid.uuid4().hex[:16]

def random_ip():
    return f"10.{random.randint(0,255)}.{random.randint(1,254)}.{random.randint(1,254)}"

def random_user_id():
    return f"user_{random.randint(10000, 99999)}"

def random_order_id():
    return f"ord_{random.randint(100000, 999999)}"

def random_product_id():
    return f"prod_{random.randint(1000, 9999)}"

def random_amount():
    return round(random.uniform(9.9, 999.9), 2)

def pick_weighted(items):
    weights = [i["weight"] for i in items]
    return random.choices(items, weights=weights, k=1)[0]

# ============================================================
# 指标生成
# ============================================================

def generate_metrics(service: str, latency_ms: int, status_code: int, fault: dict = None):
    """生成与服务类型相关的核心指标"""
    base = {
        "latency_ms": latency_ms,
        "status_code": status_code,
    }

    if service == "gateway":
        base.update({
            "active_connections": random.randint(50, 200),
            "requests_per_sec": random.randint(800, 1500),
            "error_rate": round(random.uniform(0.001, 0.01), 4) if not fault else round(random.uniform(0.05, 0.3), 4),
            "upstream_timeout_count": 0 if not fault else random.randint(3, 15),
        })
    elif "service" in service:
        base.update({
            "thread_pool_active": random.randint(5, 30),
            "thread_pool_max": 64,
            "heap_used_mb": random.randint(300, 800),
            "heap_max_mb": 2048,
            "gc_pause_ms": random.randint(5, 50),
            "connections_db": random.randint(10, 50),
            "connections_redis": random.randint(5, 20),
        })
        if fault:
            base["thread_pool_active"] = random.randint(55, 64)
            base["heap_used_mb"] = random.randint(1500, 2000)

    return base

# ============================================================
# 日志写入
# ============================================================

class LogWriter:
    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.handles = {}

    def get_handle(self, service: str):
        if service not in self.handles:
            log_file = self.log_dir / f"{service}.log"
            self.handles[service] = open(log_file, "a")
        return self.handles[service]

    def write(self, service: str, entry: dict):
        handle = self.get_handle(service)
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        handle.flush()

    def close(self):
        for h in self.handles.values():
            h.close()

# ============================================================
# 请求流引擎
# ============================================================

class RequestFlowEngine:
    def __init__(self, writer: LogWriter, scenario: str = "normal"):
        self.writer = writer
        self.scenario_name = scenario
        self.scenario = SCENARIOS[scenario]
        self.request_count = 0
        self.error_count = 0

    def set_scenario(self, name: str):
        self.scenario_name = name
        self.scenario = SCENARIOS[name]
        print(f"  🎬 场景切换: {name} - {self.scenario['description']}")

    def simulate_request(self):
        """模拟一个完整请求流"""
        chain_name = random.choice(list(CALL_CHAINS.keys()))
        chain = CALL_CHAINS[chain_name]
        trace_id = generate_trace_id()
        user_id = random_user_id()
        order_id = random_order_id()
        product_id = random_product_id()
        amount = random_amount()
        client_ip = random_ip()

        total_latency = 0

        for service in chain:
            span_id = generate_span_id()
            config = SERVICES[service]
            endpoint = pick_weighted(config["endpoints"])
            fault = self.scenario["faults"].get(service)

            # 计算延迟
            base_latency = endpoint["base_latency"]
            if fault:
                latency = int(base_latency * fault["latency_multiplier"] * random.uniform(0.8, 1.2))
            else:
                latency = int(base_latency * random.uniform(0.7, 1.3))
            total_latency += latency

            # 是否错误
            is_error = fault and random.random() < fault["error_rate"]
            status_code = 500 if is_error else 200
            level = "error" if is_error else ("warn" if latency > base_latency * 3 else "info")

            # 选择消息
            if is_error and fault:
                message = fault["error_msg"]
            else:
                template = random.choice(NORMAL_MESSAGES[service])
                message = template.format(
                    method=endpoint["method"],
                    path=endpoint["path"],
                    client_ip=client_ip,
                    user_id=user_id,
                    order_id=order_id,
                    product_id=product_id,
                    amount=amount,
                    pay_id=f"pay_{random.randint(100000, 999999)}",
                    stock=random.randint(10, 500),
                    qty=random.randint(10, 100),
                    target_service=random.choice(list(SERVICES.keys())),
                    status_code=status_code,
                    latency=latency,
                )

            # 生成指标
            metrics = generate_metrics(service, latency, status_code, fault)

            # 构建日志条目
            entry = {
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{random.randint(0,999):03d}Z",
                "level": level,
                "service_name": service,
                "host_name": config["host"],
                "message": message,
                "trace_id": trace_id,
                "span_id": span_id,
                "endpoint": f"{endpoint['method']} {endpoint['path']}",
                "http_status": status_code,
                "metrics": metrics,
                "labels": {
                    "env": "production",
                    "region": "cn-east-1",
                    "team": "platform",
                },
            }

            # 写日志
            self.writer.write(service, entry)

            if is_error:
                self.error_count += 1

        self.request_count += 1

# ============================================================
# 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="监控 ETL 平台 Demo 模拟器")
    parser.add_argument("--rps", type=float, default=RPS_DEFAULT, help="每秒请求数")
    parser.add_argument("--scenario", default="normal", choices=list(SCENARIOS.keys()), help="场景")
    parser.add_argument("--log-dir", default=LOG_DIR, help="日志输出目录")
    parser.add_argument("--switch-after", type=int, default=0, help="N 秒后自动切换到下一个场景")
    args = parser.parse_args()

    writer = LogWriter(args.log_dir)
    engine = RequestFlowEngine(writer, args.scenario)

    print("=" * 50)
    print("  🚀 监控 ETL Demo 模拟器")
    print("=" * 50)
    print(f"  场景: {args.scenario} - {SCENARIOS[args.scenario]['description']}")
    print(f"  速率: {args.rps} req/s")
    print(f"  日志: {args.log_dir}")
    print(f"  Ctrl+C 停止")
    print("=" * 50)

    scenario_index = 0
    scenario_list = list(SCENARIOS.keys())
    last_switch = time.time()

    try:
        while True:
            # 自动切换场景
            if args.switch_after > 0 and time.time() - last_switch > args.switch_after:
                scenario_index = (scenario_index + 1) % len(scenario_list)
                engine.set_scenario(scenario_list[scenario_index])
                last_switch = time.time()

            # 产生请求
            engine.simulate_request()

            # 统计
            if engine.request_count % 100 == 0:
                print(f"  📊 请求: {engine.request_count} | 错误: {engine.error_count} | 场景: {engine.scenario_name}")

            # 速率控制
            sleep_time = 1.0 / args.rps + random.uniform(-0.1, 0.1) / args.rps
            time.sleep(max(0.01, sleep_time))

    except KeyboardInterrupt:
        print(f"\n  ✅ 停止。总请求: {engine.request_count}, 错误: {engine.error_count}")
    finally:
        writer.close()

if __name__ == "__main__":
    main()
