"""业务映射管理 — URL模式 → 业务标签 CRUD"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json

router = APIRouter(prefix="/api/v1/cmdb", tags=["business-mapping"])


def get_pg():
    """Get PostgreSQL connection via docker network"""
    import psycopg2
    return psycopg2.connect("postgresql://postgres:M9kX#pL2vQ!zR7w@47.93.61.196:5432/cmdb")


class MappingCreate(BaseModel):
    url_pattern: str
    http_method: Optional[str] = None
    business_domain: str
    business_action: str
    biz_service: Optional[str] = None
    priority: int = 0
    description: Optional[str] = None
    enabled: bool = True


class MappingUpdate(BaseModel):
    url_pattern: Optional[str] = None
    http_method: Optional[str] = None
    business_domain: Optional[str] = None
    business_action: Optional[str] = None
    biz_service: Optional[str] = None
    priority: Optional[int] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


def row_to_dict(cur):
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if not row:
        return None
    return dict(zip(cols, row))


@router.get("/business-mappings")
def list_mappings(enabled: Optional[bool] = None):
    """列出所有业务映射规则"""
    pg = get_pg()
    cur = pg.cursor()
    if enabled is not None:
        cur.execute("SELECT * FROM business_mapping WHERE enabled = %s ORDER BY priority DESC, created_at DESC", (enabled,))
    else:
        cur.execute("SELECT * FROM business_mapping ORDER BY priority DESC, created_at DESC")
    cols = [d[0] for d in cur.description]
    items = [dict(zip(cols, r)) for r in cur.fetchall()]
    pg.close()
    return {"items": items, "total": len(items)}


@router.post("/business-mappings")
def create_mapping(m: MappingCreate):
    """创建业务映射规则"""
    pg = get_pg()
    cur = pg.cursor()
    cur.execute("""INSERT INTO business_mapping (url_pattern, http_method, business_domain, business_action, biz_service, priority, description, enabled)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING *""",
                (m.url_pattern, m.http_method, m.business_domain, m.business_action, m.biz_service, m.priority, m.description, m.enabled))
    result = row_to_dict(cur)
    pg.commit()
    pg.close()
    return result


@router.put("/business-mappings/{mapping_id}")
def update_mapping(mapping_id: str, m: MappingUpdate):
    """更新业务映射规则"""
    pg = get_pg()
    cur = pg.cursor()
    fields = []
    values = []
    for k, v in m.dict(exclude_none=True).items():
        fields.append(f"{k} = %s")
        values.append(v)
    if not fields:
        raise HTTPException(400, "No fields to update")
    fields.append("updated_at = now()")
    values.append(mapping_id)
    cur.execute(f"UPDATE business_mapping SET {', '.join(fields)} WHERE mapping_id = %s RETURNING *", values)
    result = row_to_dict(cur)
    pg.commit()
    pg.close()
    if not result:
        raise HTTPException(404, "Mapping not found")
    return result


@router.delete("/business-mappings/{mapping_id}")
def delete_mapping(mapping_id: str):
    """删除业务映射规则"""
    pg = get_pg()
    cur = pg.cursor()
    cur.execute("DELETE FROM business_mapping WHERE mapping_id = %s RETURNING mapping_id", (mapping_id,))
    deleted = cur.fetchone()
    pg.commit()
    pg.close()
    if not deleted:
        raise HTTPException(404, "Mapping not found")
    return {"deleted": True}


@router.post("/business-mappings/test")
def test_mapping(data: dict):
    """测试 URL 是否匹配业务映射规则"""
    url = data.get("url", "")
    method = data.get("method", "")
    pg = get_pg()
    cur = pg.cursor()
    cur.execute("""SELECT * FROM business_mapping WHERE enabled = true ORDER BY priority DESC""")
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        mapping = dict(zip(cols, row))
        pattern = mapping["url_pattern"].replace("*", ".*")
        import re
        if re.match(pattern, url):
            if not mapping["http_method"] or mapping["http_method"] == method:
                pg.close()
                return {"matched": True, "mapping": mapping}
    pg.close()
    return {"matched": False}
