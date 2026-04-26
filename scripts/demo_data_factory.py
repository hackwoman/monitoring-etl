"""
Phase 6: Demo 数据工厂
支持多格式、场景化、持续造数据（时序数据）
"""
import asyncio
import json
import random
import time
from datetime import datetime, timedelta
from typing import Generator


class TimeSeriesGenerator:
    """时序数据生成器"""
    
    @staticmethod
    def cpu_usage(base: float = 50.0, variance: float = 20.0) -> float:
        """生成 CPU 使用率（正弦波 + 随机波动）"""
        t = time.time()
        sine = base + variance * __import__('math').sin(t / 60)  # 60秒周期
        noise = random.gauss(0, variance / 5)
        return max(0, min(100, sine + noise))
    
    @staticmethod
    def memory_usage(base: float = 60.0, variance: float = 10.0) -> float:
        """生成内存使用率"""
        t = time.time()
        sine = base + variance * __import__('math').sin(t / 300)  # 5分钟周期
        noise = random.gauss(0, variance / 10)
        return max(0, min(100, sine + noise))
    
    @staticmethod
    def qps(base: float = 1000.0, variance: float = 300.0) -> float:
        """生成 QPS"""
        t = time.time()
        sine = base + variance * __import__('math').sin(t / 120)  # 2分钟周期
        noise = random.gauss(0, variance / 5)
        return max(0, sine + noise)
    
    @staticmethod
    def latency(base: float = 50.0, variance: float = 30.0) -> float:
        """生成延迟"""
        t = time.time()
        sine = base + variance * __import__('math').sin(t / 60)
        noise = random.gauss(0, variance / 3)
        return max(0, sine + noise)
    
    @staticmethod
    def error_rate(base: float = 0.5, variance: float = 0.3) -> float:
        """生成错误率"""
        t = time.time()
        sine = base + variance * __import__('math').sin(t / 180)
        noise = random.gauss(0, variance / 5)
        return max(0, min(100, sine + noise))
    
    @staticmethod
    def network_bytes(base: float = 1000000, variance: float = 500000) -> float:
        """生成网络字节数"""
        t = time.time()
        sine = base + variance * __import__('math').sin(t / 60)
        noise = random.gauss(0, variance / 10)
        return max(0, sine + noise)


class PrometheusGenerator:
    """Prometheus 格式数据生成器"""
    
    def __init__(self):
        self.ts = TimeSeriesGenerator()
    
    def generate_host_metrics(self, hostname: str, instance: str) -> str:
        """生成主机指标"""
        lines = []
        ts = int(time.time())
        
        cpu = self.ts.cpu_usage()
        mem = self.ts.memory_usage()
        load1 = self.ts.cpu_usage(base=2.0, variance=1.0)
        
        lines.append(f'# HELP node_cpu_seconds_total Total CPU time spent in seconds')
        lines.append(f'# TYPE node_cpu_seconds_total counter')
        lines.append(f'node_cpu_seconds_total{{cpu="0",mode="idle",instance="{instance}",job="node-exporter"}} {random.uniform(100000, 200000):.2f}')
        lines.append(f'node_cpu_seconds_total{{cpu="0",mode="user",instance="{instance}",job="node-exporter"}} {random.uniform(5000, 15000):.2f}')
        lines.append(f'node_cpu_seconds_total{{cpu="0",mode="system",instance="{instance}",job="node-exporter"}} {random.uniform(2000, 8000):.2f}')
        
        lines.append(f'# HELP node_memory_MemTotal_bytes Total memory')
        lines.append(f'# TYPE node_memory_MemTotal_bytes gauge')
        lines.append(f'node_memory_MemTotal_bytes{{instance="{instance}",job="node-exporter"}} 8589934592')
        
        lines.append(f'# HELP node_memory_MemAvailable_bytes Available memory')
        lines.append(f'# TYPE node_memory_MemAvailable_bytes gauge')
        lines.append(f'node_memory_MemAvailable_bytes{{instance="{instance}",job="node-exporter"}} {8589934592 * (1 - mem/100):.0f}')
        
        lines.append(f'# HELP node_load1 1-minute load average')
        lines.append(f'# TYPE node_load1 gauge')
        lines.append(f'node_load1{{instance="{instance}",job="node-exporter"}} {load1:.2f}')
        
        return '\n'.join(lines)
    
    def generate_service_metrics(self, service_name: str, instance: str) -> str:
        """生成服务指标"""
        lines = []
        qps = self.ts.qps()
        latency = self.ts.latency()
        error_rate = self.ts.error_rate()
        
        lines.append(f'# HELP http_requests_total Total HTTP requests')
        lines.append(f'# TYPE http_requests_total counter')
        lines.append(f'http_requests_total{{service="{service_name}",instance="{instance}",job="prometheus",method="GET",status="200"}} {random.uniform(10000, 50000):.0f}')
        lines.append(f'http_requests_total{{service="{service_name}",instance="{instance}",job="prometheus",method="GET",status="500"}} {random.uniform(10, 100):.0f}')
        
        lines.append(f'# HELP http_request_duration_seconds HTTP request duration')
        lines.append(f'# TYPE http_request_duration_seconds histogram')
        lines.append(f'http_request_duration_seconds_bucket{{service="{service_name}",instance="{instance}",job="prometheus",le="0.1"}} {random.uniform(800, 1200):.0f}')
        lines.append(f'http_request_duration_seconds_bucket{{service="{service_name}",instance="{instance}",job="prometheus",le="0.5"}} {random.uniform(900, 1300):.0f}')
        lines.append(f'http_request_duration_seconds_bucket{{service="{service_name}",instance="{instance}",job="prometheus",le="1.0"}} {random.uniform(950, 1350):.0f}')
        lines.append(f'http_request_duration_seconds_bucket{{service="{service_name}",instance="{instance}",job="prometheus",le="+Inf"}} {random.uniform(1000, 1400):.0f}')
        
        lines.append(f'# HELP http_requests_qps Current QPS')
        lines.append(f'# TYPE http_requests_qps gauge')
        lines.append(f'http_requests_qps{{service="{service_name}",instance="{instance}",job="prometheus"}} {qps:.2f}')
        
        return '\n'.join(lines)
    
    def generate_redis_metrics(self, instance: str) -> str:
        """生成 Redis 指标"""
        lines = []
        
        lines.append(f'# HELP redis_connected_clients Connected clients')
        lines.append(f'# TYPE redis_connected_clients gauge')
        lines.append(f'redis_connected_clients{{instance="{instance}",job="redis-exporter"}} {random.randint(10, 50)}')
        
        lines.append(f'# HELP redis_memory_used_bytes Memory used')
        lines.append(f'# TYPE redis_memory_used_bytes gauge')
        lines.append(f'redis_memory_used_bytes{{instance="{instance}",job="redis-exporter"}} {random.randint(100000000, 500000000)}')
        
        lines.append(f'# HELP redis_commands_processed_total Commands processed')
        lines.append(f'# TYPE redis_commands_processed_total counter')
        lines.append(f'redis_commands_processed_total{{instance="{instance}",job="redis-exporter"}} {random.uniform(100000, 500000):.0f}')
        
        return '\n'.join(lines)


class LogGenerator:
    """日志格式数据生成器"""
    
    LEVELS = ["info", "warn", "error", "debug"]
    SERVICES = ["api-gateway", "user-service", "order-service", "payment-service", "notification-service"]
    MESSAGES = {
        "info": [
            "Request completed successfully",
            "User authenticated",
            "Order created",
            "Payment processed",
            "Cache hit",
        ],
        "warn": [
            "Slow query detected",
            "High memory usage",
            "Connection pool nearly full",
            "Retry attempt",
        ],
        "error": [
            "Connection timeout",
            "Database error",
            "Service unavailable",
            "Invalid request",
        ],
        "debug": [
            "Processing request",
            "Cache miss",
            "Query executed",
        ],
    }
    
    def generate_json_log(self) -> str:
        """生成 JSON 格式日志"""
        level = random.choice(self.LEVELS)
        service = random.choice(self.SERVICES)
        message = random.choice(self.MESSAGES[level])
        
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "service": service,
            "message": message,
            "duration_ms": random.randint(1, 5000),
            "trace_id": f"trace-{random.randint(100000, 999999)}",
            "span_id": f"span-{random.randint(100000, 999999)}",
        }
        
        return json.dumps(record)
    
    def generate_logfmt_log(self) -> str:
        """生成 Logfmt 格式日志"""
        level = random.choice(self.LEVELS)
        service = random.choice(self.SERVICES)
        message = random.choice(self.MESSAGES[level])
        
        return f'ts={datetime.utcnow().isoformat()}Z level={level} msg="{message}" service={service} duration_ms={random.randint(1, 5000)} trace_id=trace-{random.randint(100000, 999999)}'
    
    def generate_syslog(self) -> str:
        """生成 Syslog 格式日志"""
        level = random.choice(["info", "warning", "error"])
        service = random.choice(self.SERVICES)
        message = random.choice(self.MESSAGES.get(level, self.MESSAGES["info"]))
        
        priority = {"info": 6, "warning": 4, "error": 3}.get(level, 6)
        timestamp = datetime.utcnow().strftime("%b %d %H:%M:%S")
        
        return f'<{priority}>{timestamp} {service} {message}'


class ScenarioGenerator:
    """场景化数据生成器"""
    
    def __init__(self):
        self.prom = PrometheusGenerator()
        self.log = LogGenerator()
    
    def microservice_scenario(self) -> dict:
        """微服务架构场景"""
        services = [
            {"name": "api-gateway", "instance": "10.0.0.1:8080"},
            {"name": "user-service", "instance": "10.0.0.2:8081"},
            {"name": "order-service", "instance": "10.0.0.3:8082"},
            {"name": "payment-service", "instance": "10.0.0.4:8083"},
        ]
        
        prometheus_data = []
        for svc in services:
            prometheus_data.append(self.prom.generate_service_metrics(svc["name"], svc["instance"]))
        
        log_data = []
        for _ in range(5):
            log_data.append(self.log.generate_json_log())
        
        return {
            "prometheus": '\n'.join(prometheus_data),
            "json_logs": '\n'.join(log_data),
            "description": "微服务架构场景：API网关 + 3个后端服务",
        }
    
    def k8s_cluster_scenario(self) -> dict:
        """K8s 集群场景"""
        nodes = ["k8s-node-01", "k8s-node-02", "k8s-node-03"]
        
        prometheus_data = []
        for node in nodes:
            prometheus_data.append(self.prom.generate_host_metrics(node, f"{node}:9100"))
        
        log_data = []
        for _ in range(3):
            log_data.append(self.log.generate_logfmt_log())
        
        return {
            "prometheus": '\n'.join(prometheus_data),
            "logfmt_logs": '\n'.join(log_data),
            "description": "K8s集群场景：3个节点 + Pod日志",
        }
    
    def hybrid_environment_scenario(self) -> dict:
        """混合环境场景"""
        prometheus_data = [
            self.prom.generate_host_metrics("web-server-01", "10.0.0.1:9100"),
            self.prom.generate_host_metrics("db-server-01", "10.0.0.2:9100"),
            self.prom.generate_redis_metrics("redis-01:6379"),
        ]
        
        log_data = []
        for _ in range(4):
            log_data.append(self.log.generate_syslog())
        
        return {
            "prometheus": '\n'.join(prometheus_data),
            "syslog": '\n'.join(log_data),
            "description": "混合环境：物理机 + 数据库 + Redis + 网络设备",
        }


class ContinuousDataPipeline:
    """持续数据管道"""
    
    def __init__(self, interval_seconds: int = 10):
        self.interval = interval_seconds
        self.scenario_gen = ScenarioGenerator()
        self.running = False
    
    async def start(self, scenario: str = "microservice"):
        """启动持续数据生成"""
        self.running = True
        print(f"=== 启动持续数据管道（场景: {scenario}，间隔: {self.interval}秒）===")
        
        count = 0
        while self.running:
            count += 1
            timestamp = datetime.utcnow().strftime("%H:%M:%S")
            
            # 生成数据
            if scenario == "microservice":
                data = self.scenario_gen.microservice_scenario()
            elif scenario == "k8s":
                data = self.scenario_gen.k8s_cluster_scenario()
            elif scenario == "hybrid":
                data = self.scenario_gen.hybrid_environment_scenario()
            else:
                data = self.scenario_gen.microservice_scenario()
            
            # 输出统计
            print(f"[{timestamp}] 第{count}轮：")
            for fmt, content in data.items():
                if fmt != "description":
                    lines = content.strip().split('\n')
                    print(f"  {fmt}: {len(lines)} 行")
            
            await asyncio.sleep(self.interval)
    
    def stop(self):
        """停止数据生成"""
        self.running = False


def demo_data_factory():
    """演示数据工厂"""
    gen = ScenarioGenerator()
    
    print("=== Demo 数据工厂演示 ===\n")
    
    # 场景1: 微服务架构
    print("场景1: 微服务架构")
    data = gen.microservice_scenario()
    print(f"  Prometheus: {len(data['prometheus'].split(chr(10)))} 行")
    print(f"  JSON日志: {len(data['json_logs'].split(chr(10)))} 行")
    print(f"  描述: {data['description']}")
    print()
    
    # 场景2: K8s 集群
    print("场景2: K8s 集群")
    data = gen.k8s_cluster_scenario()
    print(f"  Prometheus: {len(data['prometheus'].split(chr(10)))} 行")
    print(f"  Logfmt日志: {len(data['logfmt_logs'].split(chr(10)))} 行")
    print(f"  描述: {data['description']}")
    print()
    
    # 场景3: 混合环境
    print("场景3: 混合环境")
    data = gen.hybrid_environment_scenario()
    print(f"  Prometheus: {len(data['prometheus'].split(chr(10)))} 行")
    print(f"  Syslog: {len(data['syslog'].split(chr(10)))} 行")
    print(f"  描述: {data['description']}")
    print()
    
    print("=== 演示完成 ===")


if __name__ == "__main__":
    demo_data_factory()
