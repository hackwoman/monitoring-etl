"""SQLAlchemy models for CMDB - Phase 2 认知层。"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from app.database import Base


class EntityTypeDef(Base):
    """实体类型定义 — 收敛属性/指标/关系/健康规则于一体。"""
    __tablename__ = "entity_type_def"

    type_name = Column(String(128), primary_key=True)
    display_name = Column(String(256))
    category = Column(String(64), default="custom")       # business / application / middleware / infrastructure / runtime / custom
    icon = Column(String(128))
    super_type = Column(String(128))                       # 单继承
    definition = Column(JSONB, default=dict)               # 核心：收敛一切的 JSONB
    description = Column(Text)
    is_custom = Column(Boolean, default=False)
    version = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Entity(Base):
    """实体实例 — 四个维度：身份/期望/观测/影响。"""
    __tablename__ = "entity"

    guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name = Column(String(128), ForeignKey("entity_type_def.type_name"), nullable=False)
    name = Column(String(512), nullable=False)
    qualified_name = Column(String(1024), unique=True, nullable=False)
    attributes = Column(JSONB, default=dict)
    labels = Column(JSONB, default=dict)
    status = Column(String(32), default="active")
    source = Column(String(64), default="manual")

    # ② 期望
    expected_metrics = Column(JSONB, default=list)
    expected_relations = Column(JSONB, default=list)

    # ③ 观测
    health_score = Column(Integer)
    health_level = Column(String(16))                      # healthy / warning / critical / down
    health_detail = Column(JSONB)
    last_observed = Column(DateTime(timezone=True))

    # ④ 影响
    biz_service = Column(String(256))
    risk_score = Column(Integer)
    propagation_hops = Column(Integer)
    blast_radius = Column(Integer)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class RelationshipTypeDef(Base):
    """关系类型定义。"""
    __tablename__ = "relationship_type_def"

    type_name = Column(String(128), primary_key=True)
    end1_type = Column(String(128))
    end1_name = Column(String(128))
    end2_type = Column(String(128))
    end2_name = Column(String(128))
    description = Column(Text)


class Relationship(Base):
    """关系实例 — 语义化列名 from/to。"""
    __tablename__ = "relationship"

    guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name = Column(String(128), nullable=False)
    # 兼容旧列
    end1_guid = Column(UUID(as_uuid=True), ForeignKey("entity.guid"), nullable=False)
    end2_guid = Column(UUID(as_uuid=True), ForeignKey("entity.guid"), nullable=False)
    # 语义化列
    from_guid = Column(UUID(as_uuid=True), ForeignKey("entity.guid"))
    to_guid = Column(UUID(as_uuid=True), ForeignKey("entity.guid"))

    attributes = Column(JSONB, default=dict)
    source = Column(String(64), default="manual")
    confidence = Column(Float, default=1.0)
    dimension = Column(String(16), default="vertical")  # horizontal=调用链, vertical=归属树
    is_active = Column(Boolean, default=True)
    first_seen = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class LabelDefinition(Base):
    """标签定义。"""
    __tablename__ = "label_definition"

    label_key = Column(String(128), primary_key=True)
    label_name = Column(String(256))
    value_type = Column(String(32), default="string")
    enum_values = Column(JSONB)
    description = Column(Text)
    created_by = Column(String(128))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class AttributeTemplate(Base):
    """属性组合模板 — 可复用的属性组。"""
    __tablename__ = "attribute_template"

    template_name = Column(String(128), primary_key=True)
    category = Column(String(64))
    attributes = Column(JSONB, nullable=False, default=list)
    description = Column(Text)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class CmdbEventSubscription(Base):
    """CMDB 事件订阅。"""
    __tablename__ = "cmdb_event_subscription"

    subscription_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscriber = Column(String(256), nullable=False)
    event_types = Column(ARRAY(String(64)), nullable=False)
    filter = Column(JSONB, default=dict)
    callback_url = Column(String(512))
    callback_mode = Column(String(16), default="webhook")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class CmdbEventLog(Base):
    """CMDB 事件日志。"""
    __tablename__ = "cmdb_event_log"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(64), nullable=False)
    entity_guid = Column(UUID(as_uuid=True))
    payload = Column(JSONB)
    published_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    status = Column(String(16), default="pending")


class DataCheckRule(Base):
    """数据质量检查规则。"""
    __tablename__ = "data_check_rule"

    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_name = Column(String(256), nullable=False)
    rule_type = Column(String(32), nullable=False)
    target_type = Column(String(128))
    check_sql = Column(Text, nullable=False)
    expected_result = Column(String(32), default="empty")
    severity = Column(String(16), default="warning")
    check_schedule = Column(String(64), default="0 2 * * *")
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class DataQualitySnapshot(Base):
    """数据质量快照。"""
    __tablename__ = "data_quality_snapshot"

    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_time = Column(DateTime(timezone=True), default=datetime.utcnow)
    overall_score = Column(Integer)
    total_entities = Column(Integer)
    total_rules = Column(Integer)
    passed_rules = Column(Integer)
    failed_rules = Column(Integer)
    type_scores = Column(JSONB, default=dict)
    issues = Column(JSONB, default=list)
