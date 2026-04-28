"""
Phase 5: 智能 ETL 识别引擎
AI 驱动的数据格式识别 + 字段解析 + 模型映射
"""
import re
import json
from typing import Optional


class FormatIdentifier:
    """格式识别引擎"""
    
    # 已知格式的识别规则
    FORMAT_RULES = [
        {
            "name": "prometheus",
            "description": "Prometheus 指标格式",
            "patterns": [
                r"^# HELP ",
                r"^# TYPE ",
                r'\{[^}]*=[^}]*\}',
            ],
            "min_matches": 2,
        },
        {
            "name": "json_lines",
            "description": "JSON Lines 格式",
            "patterns": [
                r"^\{.*\}$",
            ],
            "min_matches": 1,
        },
        {
            "name": "logfmt",
            "description": "Logfmt 格式",
            "patterns": [
                r"\w+=[^\s]+",
            ],
            "min_matches": 3,
        },
        {
            "name": "csv",
            "description": "CSV/TSV 格式",
            "patterns": [
                r"^[^,]+\,[^,]+",
                r"^[^\t]+\t[^\t]+",
            ],
            "min_matches": 1,
        },
        {
            "name": "syslog",
            "description": "Syslog 格式",
            "patterns": [
                r"^<\d+>",
                r"\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}",
            ],
            "min_matches": 2,
        },
        {
            "name": "key_value",
            "description": "Key=Value 格式",
            "patterns": [
                r"\w+:\s*[^\s]+",
            ],
            "min_matches": 3,
        },
    ]
    
    def identify(self, data_sample: str) -> dict:
        """
        识别数据格式
        
        返回：
        {
            "format": str,
            "confidence": float,
            "description": str,
            "details": dict
        }
        """
        lines = data_sample.strip().split('\n')
        
        best_match = None
        best_score = 0
        
        for rule in self.FORMAT_RULES:
            matches = 0
            for line in lines[:10]:  # 只检查前10行
                for pattern in rule["patterns"]:
                    if re.search(pattern, line):
                        matches += 1
                        break
            
            score = matches / min(len(lines), 10)
            
            if score >= rule["min_matches"] / min(len(lines), 10) and score > best_score:
                best_score = score
                best_match = {
                    "format": rule["name"],
                    "confidence": min(score, 1.0),
                    "description": rule["description"],
                    "details": {"matches": matches, "total_lines": len(lines)}
                }
        
        if best_match:
            return best_match
        
        return {
            "format": "unknown",
            "confidence": 0.0,
            "description": "未知格式，需要 AI 推断",
            "details": {"lines": len(lines)}
        }


class FieldExtractor:
    """字段解析引擎"""
    
    def extract_prometheus(self, data: str) -> list:
        """解析 Prometheus 格式"""
        metrics = []
        current_help = ""
        current_type = ""
        
        for line in data.strip().split('\n'):
            line = line.strip()
            
            if line.startswith('# HELP'):
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    current_help = parts[3]
            elif line.startswith('# TYPE'):
                parts = line.split(' ', 3)
                if len(parts) >= 4:
                    current_type = parts[3]
            elif line and not line.startswith('#'):
                # 解析指标行: metric_name{labels} value timestamp
                match = re.match(r'^([^{]+)\{([^}]*)\}\s+([\d.e+-]+)\s*(.*)', line)
                if match:
                    name = match.group(1).strip()
                    labels_str = match.group(2)
                    value = float(match.group(3))
                    
                    # 解析标签
                    labels = {}
                    if labels_str:
                        for label in labels_str.split(','):
                            if '=' in label:
                                k, v = label.split('=', 1)
                                labels[k.strip()] = v.strip().strip('"')
                    
                    metrics.append({
                        "name": name,
                        "value": value,
                        "labels": labels,
                        "type": current_type,
                        "help": current_help,
                    })
                else:
                    # 无标签的指标
                    match = re.match(r'^(\S+)\s+([\d.e+-]+)', line)
                    if match:
                        metrics.append({
                            "name": match.group(1).strip(),
                            "value": float(match.group(2)),
                            "labels": {},
                            "type": current_type,
                            "help": current_help,
                        })
        
        return metrics
    
    def extract_json_lines(self, data: str) -> list:
        """解析 JSON Lines 格式"""
        records = []
        for line in data.strip().split('\n'):
            line = line.strip()
            if line:
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError:
                    pass
        return records
    
    def extract_csv(self, data: str, delimiter: str = ',') -> list:
        """解析 CSV/TSV 格式"""
        lines = data.strip().split('\n')
        if len(lines) < 2:
            return []
        
        headers = lines[0].split(delimiter)
        records = []
        
        for line in lines[1:]:
            values = line.split(delimiter)
            if len(values) == len(headers):
                record = {}
                for i, header in enumerate(headers):
                    record[header.strip()] = values[i].strip()
                records.append(record)
        
        return records
    
    def extract_logfmt(self, data: str) -> list:
        """解析 Logfmt 格式"""
        records = []
        for line in data.strip().split('\n'):
            record = {}
            for match in re.finditer(r'(\w+)=([^\s]+)', line):
                key = match.group(1)
                value = match.group(2).strip('"')
                record[key] = value
            if record:
                records.append(record)
        return records
    
    def extract_key_value(self, data: str) -> list:
        """解析 Key:Value 格式"""
        records = []
        for line in data.strip().split('\n'):
            record = {}
            for match in re.finditer(r'(\w+):\s*([^\s,]+)', line):
                key = match.group(1)
                value = match.group(2)
                record[key] = value
            if record:
                records.append(record)
        return records


class EntityInferrer:
    """实体推断引擎"""
    
    # 指标前缀 → 实体类型映射
    PREFIX_MAP = {
        "node_": "Host",
        "host_": "Host",
        "container_": "Container",
        "kube_pod_": "K8sPod",
        "kube_node_": "K8sNode",
        "kube_cluster_": "K8sCluster",
        "kube_namespace_": "K8sNamespace",
        "http_": "Service",
        "grpc_": "Service",
        "redis_": "Redis",
        "mysql_": "Database",
        "postgres_": "Database",
        "kafka_": "MessageQueue",
        "process_": "Process",
        "system_": "Host",
        "net_": "NetworkDevice",
    }
    
    # 标签 → 实体类型映射
    LABEL_MAP = {
        "instance": "Host",
        "pod": "K8sPod",
        "container": "Container",
        "namespace": "K8sNamespace",
        "node": "K8sNode",
        "service": "Service",
        "job": "Service",
        "host": "Host",
    }
    
    def infer_from_metric(self, metric_name: str) -> str:
        """从指标名推断实体类型"""
        for prefix, entity_type in self.PREFIX_MAP.items():
            if metric_name.startswith(prefix):
                return entity_type
        return None
    
    def infer_from_labels(self, labels: dict) -> str:
        """从标签推断实体类型"""
        for label_key, entity_type in self.LABEL_MAP.items():
            if label_key in labels:
                return entity_type
        return None
    
    def infer_entity_name(self, entity_type: str, labels: dict) -> str:
        """推断实体名称"""
        if entity_type == "Host":
            return labels.get("instance", labels.get("host", "unknown-host")).split(":")[0]
        elif entity_type == "K8sPod":
            return labels.get("pod", "unknown-pod")
        elif entity_type == "Container":
            return labels.get("container", "unknown-container")
        elif entity_type == "Service":
            return labels.get("service", labels.get("job", "unknown-service"))
        elif entity_type == "K8sNode":
            return labels.get("node", "unknown-node")
        elif entity_type == "Redis":
            return labels.get("instance", "unknown-redis")
        elif entity_type == "Database":
            return labels.get("instance", "unknown-database")
        elif entity_type == "MessageQueue":
            return labels.get("instance", "unknown-mq")
        return "unknown"


class SmartETLEngine:
    """智能 ETL 识别引擎"""
    
    def __init__(self):
        self.identifier = FormatIdentifier()
        self.extractor = FieldExtractor()
        self.inferrer = EntityInferrer()
    
    def process(self, data_sample: str, source_system: str = "unknown") -> dict:
        """
        处理数据样例
        
        返回：
        {
            "format": str,
            "confidence": float,
            "entities": list,
            "metrics": list,
            "labels": dict,
            "raw_records": list
        }
        """
        # Step 1: 识别格式
        format_info = self.identifier.identify(data_sample)
        
        # Step 2: 提取字段
        raw_records = []
        if format_info["format"] == "prometheus":
            raw_records = self.extractor.extract_prometheus(data_sample)
        elif format_info["format"] == "json_lines":
            raw_records = self.extractor.extract_json_lines(data_sample)
        elif format_info["format"] == "csv":
            raw_records = self.extractor.extract_csv(data_sample)
        elif format_info["format"] == "logfmt":
            raw_records = self.extractor.extract_logfmt(data_sample)
        elif format_info["format"] == "key_value":
            raw_records = self.extractor.extract_key_value(data_sample)
        
        # Step 3: 推断实体
        entities = []
        all_labels = {}
        
        for record in raw_records:
            # 从指标名推断
            if "name" in record:
                entity_type = self.inferrer.infer_from_metric(record["name"])
                if entity_type:
                    labels = record.get("labels", {})
                    entity_name = self.inferrer.infer_entity_name(entity_type, labels)
                    entities.append({
                        "type": entity_type,
                        "name": entity_name,
                        "labels": labels,
                    })
                    all_labels.update(labels)
            
            # 从标签推断
            if "labels" in record:
                for label_key in ["instance", "pod", "container", "service", "job", "host"]:
                    if label_key in record["labels"]:
                        entity_type = self.inferrer.LABEL_MAP.get(label_key)
                        if entity_type:
                            entity_name = record["labels"][label_key].split(":")[0]
                            entities.append({
                                "type": entity_type,
                                "name": entity_name,
                                "labels": record["labels"],
                            })
                            all_labels.update(record["labels"])
        
        # 去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e["type"], e["name"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)
        
        return {
            "format": format_info["format"],
            "confidence": format_info["confidence"],
            "description": format_info["description"],
            "entities": unique_entities,
            "metrics_count": len(raw_records),
            "labels": all_labels,
            "raw_records": raw_records[:5],  # 只返回前5条作为样本
        }


def demo_smart_etl():
    """演示智能 ETL 识别"""
    engine = SmartETLEngine()
    
    print("=== 智能 ETL 识别演示 ===\n")
    
    # 测试1: Prometheus 格式
    print("测试1: Prometheus 格式")
    prom_data = """# HELP node_cpu_seconds_total Total CPU time spent
# TYPE node_cpu_seconds_total counter
node_cpu_seconds_total{cpu="0",mode="idle"} 123456.78
node_cpu_seconds_total{cpu="0",mode="user"} 7890.12
node_cpu_seconds_total{cpu="1",mode="idle"} 234567.89
# HELP node_memory_MemTotal_bytes Total memory
# TYPE node_memory_MemTotal_bytes gauge
node_memory_MemTotal_bytes 8589934592"""
    
    result = engine.process(prom_data, "prometheus")
    print(f"  格式: {result['format']} (置信度: {result['confidence']:.2f})")
    print(f"  实体: {len(result['entities'])} 个")
    for e in result['entities']:
        print(f"    {e['type']}: {e['name']}")
    print(f"  指标数: {result['metrics_count']}")
    print()
    
    # 测试2: JSON 日志
    print("测试2: JSON 日志格式")
    json_data = '{"timestamp":"2026-04-25T10:30:00Z","level":"info","service":"api-server","message":"Request completed","duration_ms":123}'
    result = engine.process(json_data, "json_logs")
    print(f"  格式: {result['format']} (置信度: {result['confidence']:.2f})")
    print(f"  指标数: {result['metrics_count']}")
    print()
    
    # 测试3: CSV 格式
    print("测试3: CSV 格式")
    csv_data = """timestamp,host,cpu_usage,memory_usage
2026-04-25T10:30:00Z,web-01,85.2,67.8
2026-04-25T10:30:00Z,web-02,72.1,55.3"""
    result = engine.process(csv_data, "csv_export")
    print(f"  格式: {result['format']} (置信度: {result['confidence']:.2f})")
    print(f"  指标数: {result['metrics_count']}")
    print()
    
    # 测试4: Logfmt 格式
    print("测试4: Logfmt 格式")
    logfmt_data = """ts=2026-04-25T10:30:00Z level=info msg=request_complete duration_ms=123 service=api-server
ts=2026-04-25T10:30:01Z level=error msg=connection_timeout host=redis-01 port=6379"""
    result = engine.process(logfmt_data, "logfmt_logs")
    print(f"  格式: {result['format']} (置信度: {result['confidence']:.2f})")
    print(f"  指标数: {result['metrics_count']}")
    print()
    
    print("=== 演示完成 ===")


if __name__ == "__main__":
    demo_smart_etl()
