"""
CMDB 实体关联匹配器。

将外部告警的 labels 映射到 CMDB 实体。
"""

import logging
from typing import Optional

logger = logging.getLogger("alert-engine.matcher")


def match_entity(labels: dict, entities: list) -> Optional[dict]:
    """
    将 Prometheus 风格的 labels 匹配到 CMDB entity。

    匹配优先级:
    1. labels.instance (host:port) → entity.attributes.ip 或 entity.name
    2. labels.service → entity.name (type=Service)
    3. labels.host / labels.hostname → entity.name
    4. labels.job → entity.type_name 映射
    """
    # 建立索引
    entity_by_name = {}
    entity_by_ip = {}
    for e in entities:
        entity_by_name.setdefault(e["name"].lower(), e)
        ip = (e.get("attributes") or {}).get("ip")
        if ip:
            entity_by_ip[ip] = e

    # 1. 匹配 instance (格式: ip:port 或 hostname:port)
    instance = labels.get("instance", "")
    if instance:
        host_part = instance.split(":")[0]
        if host_part in entity_by_ip:
            return entity_by_ip[host_part]
        if host_part.lower() in entity_by_name:
            return entity_by_name[host_part.lower()]

    # 2. 匹配 service
    service = labels.get("service", "")
    if service and service.lower() in entity_by_name:
        return entity_by_name[service.lower()]

    # 3. 匹配 host / hostname
    for key in ("host", "hostname"):
        host = labels.get(key, "")
        if host and host.lower() in entity_by_name:
            return entity_by_name[host.lower()]

    # 4. job → type 映射
    job = labels.get("job", "")
    job_type_map = {
        "node-exporter": "Host",
        "mysqld-exporter": "MySQL",
        "redis-exporter": "Redis",
        "cadvisor": "K8sPod",
        "kubernetes-pods": "K8sPod",
    }
    mapped_type = job_type_map.get(job)
    if mapped_type:
        # 找第一个匹配类型的实体（进一步用 instance 限定）
        instance_host = instance.split(":")[0] if instance else ""
        for e in entities:
            if e["type_name"] == mapped_type:
                if instance_host and (
                    instance_host == e["name"]
                    or instance_host == (e.get("attributes") or {}).get("ip")
                ):
                    return e
                elif not instance_host:
                    return e

    return None
