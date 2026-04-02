"""
级联影响分析。

BFS 遍历 CMDB 关系图，计算告警的 blast_radius。
"""

import logging
from collections import defaultdict, deque
from typing import Optional
from uuid import UUID

logger = logging.getLogger("alert-engine.impact")


def calculate_blast_radius(
    entity_guid: str,
    relationships: list,
    max_hops: int = 5,
) -> dict:
    """
    BFS 计算一个实体的影响范围。

    Returns:
        {
            "blast_radius": int,          # 受影响实体总数
            "propagation_hops": int,      # 最大传播深度
            "affected_entities": list,    # 受影响的实体 GUID 列表
            "affected_biz": list,         # 受影响的业务服务
        }
    """
    # 建邻接表（双向）
    adj = defaultdict(set)
    for rel in relationships:
        from_g = str(rel.get("from_guid", rel.get("end1_guid", "")))
        to_g = str(rel.get("to_guid", rel.get("end2_guid", "")))
        if from_g and to_g:
            adj[from_g].add(to_g)
            adj[to_g].add(from_g)

    if entity_guid not in adj:
        return {"blast_radius": 0, "propagation_hops": 0, "affected_entities": [], "affected_biz": []}

    visited = {entity_guid}
    queue = deque([(entity_guid, 0)])
    affected = []
    max_hop = 0

    while queue:
        current, hop = queue.popleft()
        if hop >= max_hops:
            continue
        for neighbor in adj.get(current, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                affected.append(neighbor)
                max_hop = max(max_hop, hop + 1)
                queue.append((neighbor, hop + 1))

    return {
        "blast_radius": len(affected),
        "propagation_hops": max_hop,
        "affected_entities": affected,
        "affected_biz": [],  # 由调用方根据实体类型筛选
    }


def find_group_id(
    entity_guid: str,
    alert_entity_map: dict,
    relationships: list,
) -> Optional[str]:
    """
    判断一个新告警是否属于已有级联组。

    如果新告警的实体与已有 firing 告警的实体在关系图中相连，
    则归入同一 group_id。
    """
    # 建邻接表
    adj = defaultdict(set)
    for rel in relationships:
        from_g = str(rel.get("from_guid", rel.get("end1_guid", "")))
        to_g = str(rel.get("to_guid", rel.get("end2_guid", "")))
        if from_g and to_g:
            adj[from_g].add(to_g)
            adj[to_g].add(from_g)

    # BFS 搜索附近的 firing 告警
    visited = {entity_guid}
    queue = deque([entity_guid])
    while queue:
        current = queue.popleft()
        for neighbor in adj.get(current, set()):
            if neighbor in alert_entity_map:
                return alert_entity_map[neighbor]  # 返回已有 group_id
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return None
