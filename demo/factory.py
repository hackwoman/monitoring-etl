#!/usr/bin/env python3
"""
监控 ETL 平台 - Demo 数据工厂

统一入口，一个命令搞定所有 demo 数据。

用法:
  python factory.py init          # 创建 CMDB 实体和关系
  python factory.py run           # 启动日志模拟器
  python factory.py run --rps 5 --scenario slow_db
  python factory.py reset         # 清空 CMDB + 重建
  python factory.py status        # 查看当前数据状态

数据定义在 demo/topology.py，CMDB 和日志模拟共用一份。
"""

import json
import time
import random
import uuid
import os
import sys
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from topology import (
    BUSINESSES, HOSTS, SERVICES, MIDDLEWARES, NETWORK_DEVICES,
    RELATIONS, CALL_CHAINS, SCENARIOS, HEALTH_OVERRIDES,
)

CMDB_API = os.getenv("CMDB_API_URL", "http://localhost:8001/api/v1/cmdb")
LOG_DIR = os.getenv("LOG_DIR", "/var/log/app")

# ============================================================
# CMDB 操作
# ============================================================

def cmdb_post(path, data):
    r = requests.post(f"{CMDB_API}{path}", json=data, timeout=10)
    if r.status_code == 409:
        # 冲突：实体已存在，尝试查询返回
        qname = data.get("qualified_name") or f"{data['type_name']}:{data['name']}"
        existing = cmdb_get(f"/entities?search={data['name']}&type_name={data['type_name']}")
        if existing and existing.get("items"):
            return existing["items"][0]
    return r.json() if r.ok else None

def cmdb_put(path, data):
    r = requests.put(f"{CMDB_API}{path}", json=data, timeout=10)
    return r.ok

def cmdb_get(path):
    r = requests.get(f"{CMDB_API}{path}", timeout=10)
    return r.json() if r.ok else None


def clear_cmdb():
    """清空所有 CMDB 数据。"""
    print("🗑️  清空 CMDB 数据...")
    entities = cmdb_get("/entities?limit=500&status=active")
    if entities:
        for e in entities.get("items", []):
            r = requests.delete(f"{CMDB_API}/entities/{e['guid']}", timeout=10)
            status = "✅" if r.ok else "⚠️"
            print(f"  {status} 删除 {e['name']} ({e['type_name']})")
    print(f"  完成")


def init_cmdb():
    """从 topology.py 创建所有 CMDB 实体和关系。"""
    print("=" * 50)
    print("  🏗️  CMDB 初始化")
    print("=" * 50)

    # 1. 业务实体
    print("\n🏢 业务实体...")
    biz_guids = {}
    for name, attrs in BUSINESSES.items():
        labels = attrs.pop("labels", {})
        result = cmdb_post("/entities", {
            "type_name": "Business",
            "name": name,
            "attributes": attrs,
            "labels": labels,
            "biz_service": name,
            "source": "factory",
        })
        if result:
            biz_guids[name] = result["guid"]
            print(f"  ✅ {name}")

    # 2. 主机
    print("\n🖥️  主机...")
    host_guids = {}
    for name, attrs in HOSTS.items():
        labels = attrs.pop("labels", {})
        # 查找该主机上的业务
        biz = None
        for svc in SERVICES.values():
            if svc["host"] == name:
                biz = svc["business"]
                break
        for mw in MIDDLEWARES.values():
            if mw["host"] == name:
                biz = mw["business"]
                break

        result = cmdb_post("/entities", {
            "type_name": "Host",
            "name": name,
            "attributes": attrs,
            "labels": labels,
            "biz_service": biz,
            "source": "factory",
        })
        if result:
            host_guids[name] = result["guid"]
            print(f"  ✅ {name} ({attrs['ip']})")

    # 3. 服务
    print("\n⚙️  服务...")
    svc_guids = {}
    for name, conf in SERVICES.items():
        result = cmdb_post("/entities", {
            "type_name": "Service",
            "name": name,
            "attributes": conf["attrs"],
            "labels": conf["labels"],
            "biz_service": conf["business"],
            "source": "factory",
        })
        if result:
            svc_guids[name] = result["guid"]
            print(f"  ✅ {name} (host={conf['host']}, biz={conf['business']})")

    # 4. 数据库/缓存
    print("\n🗄️  数据库/缓存...")
    mw_guids = {}
    for name, conf in MIDDLEWARES.items():
        result = cmdb_post("/entities", {
            "type_name": conf["type"],
            "name": name,
            "attributes": conf["attrs"],
            "labels": conf["labels"],
            "biz_service": conf["business"],
            "source": "factory",
        })
        if result:
            mw_guids[name] = result["guid"]
            print(f"  ✅ {name} ({conf['type']}, host={conf['host']})")

    # 5. 网络设备
    print("\n🌐 网络设备...")
    net_guids = {}
    for name, conf in NETWORK_DEVICES.items():
        result = cmdb_post("/entities", {
            "type_name": "NetworkDevice",
            "name": name,
            "attributes": conf["attrs"],
            "labels": conf["labels"],
            "source": "factory",
        })
        if result:
            net_guids[name] = result["guid"]
            print(f"  ✅ {name}")

    # 6. 关系
    print("\n🔗 关系...")
    all_guids = {**biz_guids, **svc_guids, **mw_guids, **host_guids, **net_guids}
    pools = {"businesses": biz_guids, "services": svc_guids, "middlewares": mw_guids}
    rel_count = 0

    for src_key, tgt_key, rel_type, src_pool, tgt_pool in RELATIONS:
        src_guid = pools.get(src_pool, {}).get(src_key) or all_guids.get(src_key)
        tgt_guid = pools.get(tgt_pool, {}).get(tgt_key) or all_guids.get(tgt_key)
        if src_guid and tgt_guid:
            r = cmdb_post(f"/entities/{src_guid}/relations", {
                "type_name": rel_type,
                "end2_guid": tgt_guid,
                "source": "factory",
            })
            status = "✅" if r else "⚠️"
            print(f"  {status} {src_key} --{rel_type}--> {tgt_key}")
            rel_count += 1

    # 服务/中间件 → 主机关系（隐含定义）
    print("\n  --- 部署关系 ---")
    for svc_name, conf in SERVICES.items():
        host_guid = host_guids.get(conf["host"])
        svc_guid = svc_guids.get(svc_name)
        if host_guid and svc_guid:
            r = cmdb_post(f"/entities/{svc_guid}/relations", {
                "type_name": "runs_on",
                "end2_guid": host_guid,
                "source": "factory",
            })
            print(f"  {'✅' if r else '⚠️'} {svc_name} --runs_on--> {conf['host']}")
            rel_count += 1

    for mw_name, conf in MIDDLEWARES.items():
        host_guid = host_guids.get(conf["host"])
        mw_guid = mw_guids.get(mw_name)
        if host_guid and mw_guid:
            r = cmdb_post(f"/entities/{mw_guid}/relations", {
                "type_name": "runs_on",
                "end2_guid": host_guid,
                "source": "factory",
            })
            print(f"  {'✅' if r else '⚠️'} {mw_name} --runs_on--> {conf['host']}")
            rel_count += 1

    # 7. 健康度覆盖（模拟异常）
    print("\n💚 健康度设置...")
    all_entity_guids = {**svc_guids, **mw_guids, **host_guids}
    for name, health in HEALTH_OVERRIDES.items():
        guid = all_entity_guids.get(name)
        if guid:
            cmdb_put(f"/entities/{guid}", health)
            print(f"  🔴 {name}: health={health['health_score']} risk={health['risk_score']}")

    # 设置正常实体的健康度
    for name, guid in all_entity_guids.items():
        if name not in HEALTH_OVERRIDES:
            cmdb_put(f"/entities/{guid}", {"health_score": random.randint(88, 100), "health_level": "healthy"})
    print(f"  ✅ 其余实体设为 healthy")

    print(f"\n{'=' * 50}")
    print(f"  ✅ CMDB 初始化完成")
    print(f"     业务: {len(biz_guids)} | 主机: {len(host_guids)} | 服务: {len(svc_guids)}")
    print(f"     中间件: {len(mw_guids)} | 网络设备: {len(net_guids)} | 关系: {rel_count}")
    print(f"{'=' * 50}")


# ============================================================
# 日志模拟器（引用共享拓扑）
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
    ],
    "inventory-service": [
        "Stock queried: product_{product_id} = {stock} units",
        "Stock deducted: product_{product_id}, -1, remaining={stock}",
        "Stock restocked: product_{product_id}, +{qty}",
    ],
    "user-service": [
        "User registered: user_{user_id}",
        "Profile queried: user_{user_id}",
        "Session created for user_{user_id}",
    ],
}

def random_ip():
    return f"10.{random.randint(0,255)}.{random.randint(1,254)}.{random.randint(1,254)}"

def pick_weighted(items):
    weights = [i["weight"] for i in items]
    return random.choices(items, weights=weights, k=1)[0]


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


def run_simulator(rps=1.0, scenario="normal", log_dir=LOG_DIR, switch_after=0):
    """启动日志模拟器。"""
    print("=" * 50)
    print("  🚀 日志模拟器启动")
    print("=" * 50)
    print(f"  场景: {scenario} - {SCENARIOS[scenario]['description']}")
    print(f"  速率: {rps} req/s")
    print(f"  日志: {log_dir}")
    print(f"  服务: {', '.join(SERVICES.keys())}")
    print(f"  Ctrl+C 停止")
    print("=" * 50)

    writer = LogWriter(log_dir)
    current_scenario = SCENARIOS[scenario]
    scenario_name = scenario
    request_count = 0
    error_count = 0
    scenario_list = list(SCENARIOS.keys())
    scenario_index = scenario_list.index(scenario)
    last_switch = time.time()

    try:
        while True:
            # 自动切换场景
            if switch_after > 0 and time.time() - last_switch > switch_after:
                scenario_index = (scenario_index + 1) % len(scenario_list)
                scenario_name = scenario_list[scenario_index]
                current_scenario = SCENARIOS[scenario_name]
                last_switch = time.time()
                print(f"  🎬 场景切换: {scenario_name} - {current_scenario['description']}")

            # 模拟一个请求流
            chain_name = random.choice(list(CALL_CHAINS.keys()))
            chain = CALL_CHAINS[chain_name]
            trace_id = uuid.uuid4().hex
            user_id = f"user_{random.randint(10000, 99999)}"
            order_id = f"ord_{random.randint(100000, 999999)}"
            client_ip = random_ip()

            for service in chain:
                if service not in SERVICES:
                    continue

                config = SERVICES[service]
                endpoint = pick_weighted(config["endpoints"])
                fault = current_scenario["faults"].get(service)

                base_latency = endpoint["base_latency"]
                if fault:
                    latency = int(base_latency * fault["latency_multiplier"] * random.uniform(0.8, 1.2))
                else:
                    latency = int(base_latency * random.uniform(0.7, 1.3))

                is_error = fault and random.random() < fault["error_rate"]
                status_code = 500 if is_error else 200
                level = "error" if is_error else ("warn" if latency > base_latency * 3 else "info")

                if is_error and fault:
                    message = fault["error_msg"]
                else:
                    templates = NORMAL_MESSAGES.get(service, ["Request processed"])
                    template = random.choice(templates)
                    message = template.format(
                        method=endpoint["method"], path=endpoint["path"],
                        client_ip=client_ip, user_id=user_id, order_id=order_id,
                        amount=round(random.uniform(9.9, 999.9), 2),
                        pay_id=f"pay_{random.randint(100000, 999999)}",
                        product_id=f"prod_{random.randint(1000, 9999)}",
                        stock=random.randint(10, 500), qty=random.randint(10, 100),
                        target_service=random.choice(list(SERVICES.keys())),
                        status_code=status_code, latency=latency,
                    )

                entry = {
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                    "level": level,
                    "service_name": service,
                    "host_name": config["host"],
                    "message": message,
                    "trace_id": trace_id,
                    "span_id": uuid.uuid4().hex[:16],
                    "endpoint": f"{endpoint['method']} {endpoint['path']}",
                    "http_status": status_code,
                    "labels": config["labels"],
                }

                writer.write(service, entry)
                if is_error:
                    error_count += 1

            request_count += 1
            if request_count % 100 == 0:
                print(f"  📊 请求: {request_count} | 错误: {error_count} | 场景: {scenario_name}")

            time.sleep(max(0.01, 1.0 / rps + random.uniform(-0.1, 0.1) / rps))

    except KeyboardInterrupt:
        print(f"\n  ✅ 停止。总请求: {request_count}, 错误: {error_count}")
    finally:
        writer.close()


# ============================================================
# CLI
# ============================================================

def show_status():
    """查看当前数据状态。"""
    overview = cmdb_get("/entities") if True else None
    types = cmdb_get("/types")
    if types:
        print("📦 类型定义:")
        for t in types.get("items", []):
            defn = t.get("definition", {})
            metrics = defn.get("metrics", [])
            print(f"  {t['type_name']:20s} ({t['category']}) - {len(metrics)} 指标")

    ov = requests.get(f"{CMDB_API.replace('/cmdb', '')}/overview").json()
    print(f"\n📊 总览:")
    print(f"  实体总数: {ov.get('total_entities', 0)}")
    print(f"  资源分布: {ov.get('resource_size', {})}")
    print(f"  健康分布: {ov.get('health_distribution', {})}")
    if ov.get('anomaly_entities'):
        print(f"  异常实体:")
        for e in ov['anomaly_entities']:
            print(f"    🔴 {e['name']} ({e['type_name']}): health={e['health_score']} risk={e['risk_score']}")


def main():
    parser = argparse.ArgumentParser(description="Demo 数据工厂")
    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="创建 CMDB 实体和关系")

    # run
    run_p = sub.add_parser("run", help="启动日志模拟器")
    run_p.add_argument("--rps", type=float, default=1.0, help="每秒请求数")
    run_p.add_argument("--scenario", default="normal", choices=list(SCENARIOS.keys()))
    run_p.add_argument("--log-dir", default=LOG_DIR)
    run_p.add_argument("--switch-after", type=int, default=0, help="N秒后自动切场景")

    # clear
    sub.add_parser("clear", help="清空 CMDB 数据")

    # reset
    sub.add_parser("reset", help="清空 CMDB 并重建")

    # status
    sub.add_parser("status", help="查看当前数据状态")

    args = parser.parse_args()

    if args.command == "init":
        init_cmdb()
    elif args.command == "clear":
        clear_cmdb()
    elif args.command == "reset":
        clear_cmdb()
        init_cmdb()
    elif args.command == "run":
        run_simulator(rps=args.rps, scenario=args.scenario, log_dir=args.log_dir, switch_after=args.switch_after)
    elif args.command == "status":
        show_status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
