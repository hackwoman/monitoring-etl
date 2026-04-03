"""智能 ETL — 日志格式识别 + 字段提取 + Vector 配置生成"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json, re

router = APIRouter(prefix="/api/v1/etl", tags=["etl"])


class ParseRequest(BaseModel):
    sample: str  # 用户粘贴的日志样例
    max_lines: int = 20  # 最多分析多少行


class FieldInfo(BaseModel):
    name: str
    type: str  # string/int/float/bool/timestamp/ip/url
    example: str
    confidence: float  # 0-1 置信度
    description: str = ""


class ParseResult(BaseModel):
    format: str  # json/syslog/apache/nginx/custom_regex/custom_kv
    fields: List[FieldInfo]
    sample_lines: int
    parse_method: str  # auto_regex/auto_json/auto_structured/ai
    suggested_vector_config: dict = {}


# ============================================================
# 格式检测
# ============================================================

def detect_format(lines: List[str]) -> str:
    """检测日志格式"""
    if not lines:
        return "unknown"
    
    # JSON 检测
    json_count = 0
    for line in lines[:5]:
        try:
            json.loads(line.strip())
            json_count += 1
        except:
            pass
    if json_count >= len(lines[:5]) * 0.8:
        return "json"
    
    # Syslog 检测 (RFC 3164 / RFC 5424)
    syslog_patterns = [
        r'^<\d+>\d{4}-\d{2}-\d{2}',  # RFC 5424
        r'^\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s+\S+',  # RFC 3164
    ]
    for p in syslog_patterns:
        if re.match(p, lines[0].strip()):
            return "syslog"
    
    # Apache/Nginx combined log
    apache_re = r'^\S+ - - \[.*?\] ".*?" \d+ \d+'
    if re.match(apache_re, lines[0].strip()):
        return "apache"
    
    nginx_re = r'^\S+ - \S+ \[.*?\] ".*?" \d+ \d+'
    if re.match(nginx_re, lines[0].strip()):
        return "nginx"
    
    # Key=Value 格式
    kv_count = 0
    for line in lines[:5]:
        kvs = re.findall(r'\w+=\S+', line)
        if len(kvs) >= 2:
            kv_count += 1
    if kv_count >= len(lines[:5]) * 0.8:
        return "kv"
    
    return "custom"


# ============================================================
# 字段提取
# ============================================================

def guess_type(value: str) -> str:
    """猜测值的类型"""
    if value in ('true', 'false', 'TRUE', 'FALSE'):
        return "bool"
    try:
        int(value)
        return "int"
    except:
        pass
    try:
        float(value)
        return "float"
    except:
        pass
    if re.match(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', value):
        return "timestamp"
    if re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', value):
        return "ip"
    if re.match(r'https?://', value):
        return "url"
    return "string"


def extract_json_fields(lines: List[str]) -> List[FieldInfo]:
    """从 JSON 日志提取字段"""
    field_values = {}
    for line in lines[:20]:
        try:
            obj = json.loads(line.strip())
            for k, v in obj.items():
                if k not in field_values:
                    field_values[k] = []
                if len(field_values[k]) < 5:
                    field_values[k].append(v)
        except:
            pass
    
    fields = []
    for name, values in field_values.items():
        str_vals = [str(v) for v in values if v is not None]
        example = str_vals[0] if str_vals else ""
        types = [guess_type(str(v)) for v in values if v is not None]
        # 多数票决定类型
        type_counts = {}
        for t in types:
            type_counts[t] = type_counts.get(t, 0) + 1
        best_type = max(type_counts, key=type_counts.get) if type_counts else "string"
        confidence = type_counts.get(best_type, 0) / len(types) if types else 0.5
        
        desc = ""
        if name in ('level', 'severity', 'log_level'):
            desc = "日志级别"
        elif name in ('message', 'msg', 'log'):
            desc = "日志消息"
        elif name in ('timestamp', 'time', '@timestamp', 'ts'):
            desc = "时间戳"
        elif name in ('host', 'hostname', 'server'):
            desc = "主机名"
        elif name in ('service', 'app', 'application'):
            desc = "服务名"
        elif name in ('trace_id', 'traceId', 'request_id', 'requestId'):
            desc = "调用链ID"
        elif name in ('status', 'http_status', 'statusCode'):
            desc = "状态码"
        elif name in ('method', 'http_method'):
            desc = "HTTP方法"
        elif name in ('path', 'url', 'uri', 'request_uri'):
            desc = "请求路径"
        elif name in ('duration', 'latency', 'response_time', 'elapsed'):
            desc = "响应耗时"
        elif name in ('error', 'err', 'exception'):
            desc = "错误信息"
        
        fields.append(FieldInfo(
            name=name, type=best_type, example=example[:100],
            confidence=round(confidence, 2), description=desc
        ))
    return fields


def extract_kv_fields(lines: List[str]) -> List[FieldInfo]:
    """从 Key=Value 日志提取字段"""
    field_values = {}
    for line in lines[:20]:
        kvs = re.findall(r'(\w+)=(\S+)', line)
        for k, v in kvs:
            if k not in field_values:
                field_values[k] = []
            if len(field_values[k]) < 5:
                field_values[k].append(v)
    
    fields = []
    for name, values in field_values.items():
        example = values[0] if values else ""
        types = [guess_type(v) for v in values]
        type_counts = {}
        for t in types:
            type_counts[t] = type_counts.get(t, 0) + 1
        best_type = max(type_counts, key=type_counts.get) if types else "string"
        
        desc = ""
        if name in ('level', 'severity', 'log_level'):
            desc = "日志级别"
        elif name in ('msg', 'message'):
            desc = "日志消息"
        elif name in ('ts', 'time', 'timestamp'):
            desc = "时间戳"
        
        fields.append(FieldInfo(
            name=name, type=best_type, example=example[:100],
            confidence=round(type_counts.get(best_type, 0) / len(types), 2) if types else 0.5,
            description=desc
        ))
    return fields


def extract_apache_fields(line: str) -> List[FieldInfo]:
    """提取 Apache/Nginx combined log 字段"""
    m = re.match(r'^(\S+) - (\S+) \[(.*?)\] "(.*?)" (\d+) (\d+)( "(.*?)" "(.*?)")?', line.strip())
    if not m:
        return []
    fields = [
        FieldInfo(name="remote_ip", type="ip", example=m.group(1), confidence=0.95, description="客户端IP"),
        FieldInfo(name="remote_user", type="string", example=m.group(2), confidence=0.9, description="远程用户"),
        FieldInfo(name="timestamp", type="timestamp", example=m.group(3), confidence=0.95, description="请求时间"),
        FieldInfo(name="request", type="string", example=m.group(4), confidence=0.95, description="请求行"),
        FieldInfo(name="status", type="int", example=m.group(5), confidence=0.95, description="HTTP状态码"),
        FieldInfo(name="body_bytes_sent", type="int", example=m.group(6), confidence=0.95, description="响应体大小"),
    ]
    if m.group(8):
        fields.append(FieldInfo(name="referer", type="url", example=m.group(8), confidence=0.9, description="来源页"))
    if m.group(9):
        fields.append(FieldInfo(name="user_agent", type="string", example=m.group(9), confidence=0.9, description="用户代理"))
    return fields


def extract_syslog_fields(line: str) -> List[FieldInfo]:
    """提取 Syslog 字段"""
    m = re.match(r'^(\w{3})\s+(\d{1,2})\s+(\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+?)(\[(\d+)\])?\s*:\s*(.*)', line.strip())
    if not m:
        return []
    return [
        FieldInfo(name="month", type="string", example=m.group(1), confidence=0.9, description="月份"),
        FieldInfo(name="day", type="int", example=m.group(2), confidence=0.9, description="日期"),
        FieldInfo(name="time", type="string", example=m.group(3), confidence=0.9, description="时间"),
        FieldInfo(name="hostname", type="string", example=m.group(4), confidence=0.9, description="主机名"),
        FieldInfo(name="program", type="string", example=m.group(5), confidence=0.9, description="程序名"),
        FieldInfo(name="pid", type="int", example=m.group(7) or "", confidence=0.8, description="进程ID"),
        FieldInfo(name="message", type="string", example=m.group(8)[:100], confidence=0.95, description="日志消息"),
    ]


# ============================================================
# Vector 配置生成
# ============================================================

def generate_vector_config(fmt: str, fields: List[FieldInfo], source: str = "demo_logs") -> dict:
    """生成 Vector pipeline 配置"""
    transforms = []
    
    if fmt == "json":
        transforms.append({
            "type": "remap",
            "inputs": [source],
            "source": ". = parse_json!(.message)",
        })
    elif fmt == "kv":
        field_names = [f.name for f in fields]
        kv_pattern = " ".join([f'{f.name}={{{{${f.name}}}}}' for f in fields])
        transforms.append({
            "type": "remap",
            "inputs": [source],
            "source": f'. = parse_key_value(.message, key_value_delimiter: "=", field_delimiter: " ")',
        })
    elif fmt in ("apache", "nginx"):
        format_str = r'%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"' if fmt == "apache" else r'$remote_addr - $remote_user [$time_local] "$request" $status $body_bytes_sent "$http_referer" "$http_user_agent"'
        transforms.append({
            "type": "remap",
            "inputs": [source],
            "source": f'# Apache/Nginx combined log parsing\n. = parse_apache_log(.message, format: "combined")',
        })
    elif fmt == "syslog":
        transforms.append({
            "type": "remap",
            "inputs": [source],
            "source": '. = parse_syslog(.message)',
        })
    else:
        # Custom regex suggestion
        transforms.append({
            "type": "remap",
            "inputs": [source],
            "source": '# TODO: 替换为实际的日志正则表达式\n# . = parse_regex!(.message, r"^...")',
        })
    
    # 类型转换
    type_conversions = []
    for f in fields:
        if f.type == "int":
            type_conversions.append(f'.{f.name} = to_int(.___{f.name}) ?? null')
        elif f.type == "float":
            type_conversions.append(f'.{f.name} = to_float(.___{f.name}) ?? null')
        elif f.type == "bool":
            type_conversions.append(f'.{f.name} = to_bool(.___{f.name}) ?? null')
        elif f.type == "timestamp":
            type_conversions.append(f'.{f.name} = parse_timestamp(.___{f.name}, format: "%+") ?? null')
    
    if type_conversions:
        transforms.append({
            "type": "remap",
            "inputs": [f"{source}_parsed"],
            "source": "\n".join(type_conversions),
        })
    
    # 最终 transform: 删除内部字段 + 添加元数据
    transforms.append({
        "type": "remap",
        "inputs": [f"{source}_typed"] if type_conversions else [f"{source}_parsed"],
        "source": f'.source_type = "parsed"\n._parsed_at = now()',
    })
    
    return {
        "sources": {
            source: {
                "type": "file",
                "include": ["/var/log/*.log"],
            }
        },
        "transforms": {f"{source}_parsed" if i == 0 else f"{source}_typed" if i == 1 else f"{source}_enriched": t for i, t in enumerate(transforms)},
        "sinks": {
            f"{source}_clickhouse": {
                "type": "clickhouse",
                "inputs": [f"{source}_enriched"],
                "endpoint": "http://clickhouse:8123",
                "table": "log_entries",
                "database": "logs",
            }
        }
    }


# ============================================================
# API 端点
# ============================================================

@router.post("/parse", response_model=ParseResult)
def parse_log(req: ParseRequest):
    """解析日志样例，返回字段结构"""
    lines = [l for l in req.sample.split("\n") if l.strip()]
    if not lines:
        raise HTTPException(400, "No log lines provided")
    
    lines = lines[:req.max_lines]
    fmt = detect_format(lines)
    
    if fmt == "json":
        fields = extract_json_fields(lines)
        method = "auto_json"
    elif fmt == "kv":
        fields = extract_kv_fields(lines)
        method = "auto_kv"
    elif fmt in ("apache", "nginx"):
        fields = extract_apache_fields(lines[0])
        method = "auto_regex"
    elif fmt == "syslog":
        fields = extract_syslog_fields(lines[0])
        method = "auto_regex"
    else:
        fields = extract_kv_fields(lines)
        method = "auto_kv_fallback"
    
    config = generate_vector_config(fmt, fields)
    
    return ParseResult(
        format=fmt,
        fields=fields,
        sample_lines=len(lines),
        parse_method=method,
        suggested_vector_config=config,
    )


@router.post("/validate-config")
def validate_config(data: dict):
    """验证 Vector 配置"""
    config = data.get("config", {})
    errors = []
    
    if not config.get("sources"):
        errors.append("Missing 'sources' section")
    if not config.get("sinks"):
        errors.append("Missing 'sinks' section - data has no destination")
    
    for name, transform in config.get("transforms", {}).items():
        if transform.get("type") == "remap" and not transform.get("source"):
            errors.append(f"Transform '{name}' has no VRL source")
    
    return {"valid": len(errors) == 0, "errors": errors}
