"""
级联影响计算 — BFS 遍历关系图。

计算每个实体的：
- blast_radius: 受影响的实体总数（下游传播）
- propagation_hops: 最大传播深度
"""

import logging
from collections import deque

logger = logging.getLogger(__name__)


def calculate_blast_radius(
    entity_guid: str,
    relationships: list,
    direction: str = "downstream",
) -> int:
    """
    计算爆炸半径 — 受影响的实体总数。
    
    BFS 从当前实体出发，沿关系方向遍历，统计所有可达实体。
    
    Args:
        entity_guid: 当前实体 GUID
        relationships: [{"from_guid": "...", "to_guid": "...", "type_name": "..."}, ...]
        direction: "downstream" (沿 from→to 方向) 或 "upstream" (沿 to→from 方向)
    
    Returns:
        受影响实体数（不含自身）
    """
    visited = set()
    queue = deque([entity_guid])
    visited.add(entity_guid)

    # 建立邻接表
    adj = {}
    for rel in relationships:
        src = rel.get("from_guid", "")
        dst = rel.get("to_guid", "")
        if not src or not dst:
            continue
        if direction == "downstream":
            adj.setdefault(src, []).append(dst)
        else:
            adj.setdefault(dst, []).append(src)

    while queue:
        current = queue.popleft()
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return len(visited) - 1  # 不含自身


def calculate_propagation_hops(
    entity_guid: str,
    relationships: list,
    direction: str = "downstream",
) -> int:
    """
    计算最大传播深度 — BFS 的最大层数。
    
    Args:
        entity_guid: 当前实体 GUID
        relationships: 关系列表
        direction: "downstream" 或 "upstream"
    
    Returns:
        最大传播深度（0 = 无下游）
    """
    visited = set()
    queue = deque([(entity_guid, 0)])
    visited.add(entity_guid)

    # 建立邻接表
    adj = {}
    for rel in relationships:
        src = rel.get("from_guid", "")
        dst = rel.get("to_guid", "")
        if not src or not dst:
            continue
        if direction == "downstream":
            adj.setdefault(src, []).append(dst)
        else:
            adj.setdefault(dst, []).append(src)

    max_hops = 0
    while queue:
        current, depth = queue.popleft()
        max_hops = max(max_hops, depth)
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    return max_hops


def calculate_all_impacts(
    entities: list,
    relationships: list,
) -> dict:
    """
    批量计算所有实体的影响范围。
    
    Args:
        entities: [{"guid": "...", ...}, ...]
        relationships: [{"from_guid": "...", "to_guid": "...", ...}, ...]
    
    Returns:
        {
            "entity_guid": {
                "blast_radius": 5,
                "propagation_hops": 3,
            },
            ...
        }
    """
    result = {}

    # 预建邻接表（下游方向）
    adj_downstream = {}
    adj_upstream = {}
    for rel in relationships:
        src = rel.get("from_guid", "")
        dst = rel.get("to_guid", "")
        if not src or not dst:
            continue
        adj_downstream.setdefault(src, []).append(dst)
        adj_upstream.setdefault(dst, []).append(src)

    for entity in entities:
        guid = entity.get("guid", "")
        if not guid:
            continue

        # 下游影响
        downstream_reached = _bfs(guid, adj_downstream)
        # 上游影响
        upstream_reached = _bfs(guid, adj_upstream)

        blast_radius = len(downstream_reached) + len(upstream_reached)
        propagation_hops = max(
            _bfs_max_depth(guid, adj_downstream),
            _bfs_max_depth(guid, adj_upstream),
        )

        result[guid] = {
            "blast_radius": blast_radius,
            "propagation_hops": propagation_hops,
        }

    return result


def _bfs(start: str, adj: dict) -> set:
    """BFS 遍历，返回所有可达节点（不含起点）。"""
    visited = set()
    queue = deque([start])
    visited.add(start)

    while queue:
        current = queue.popleft()
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    visited.discard(start)
    return visited


def _bfs_max_depth(start: str, adj: dict) -> int:
    """BFS 遍历，返回最大深度。"""
    visited = set()
    queue = deque([(start, 0)])
    visited.add(start)
    max_depth = 0

    while queue:
        current, depth = queue.popleft()
        max_depth = max(max_depth, depth)
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    return max_depth
