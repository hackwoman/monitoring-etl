"""SQLAlchemy models for CMDB."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base


class EntityTypeDef(Base):
    __tablename__ = "entity_type_def"

    type_name = Column(String(128), primary_key=True)
    super_types = Column(JSONB, default=list)
    attribute_defs = Column(JSONB, default=dict)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Entity(Base):
    __tablename__ = "entity"

    guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name = Column(String(128), ForeignKey("entity_type_def.type_name"), nullable=False)
    name = Column(String(512), nullable=False)
    qualified_name = Column(String(1024), unique=True, nullable=False)
    attributes = Column(JSONB, default=dict)
    labels = Column(JSONB, default=dict)
    status = Column(String(32), default="active")
    source = Column(String(64), default="manual")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class RelationshipTypeDef(Base):
    __tablename__ = "relationship_type_def"

    type_name = Column(String(128), primary_key=True)
    end1_type = Column(String(128))
    end1_name = Column(String(128))
    end2_type = Column(String(128))
    end2_name = Column(String(128))
    description = Column(Text)


class Relationship(Base):
    __tablename__ = "relationship"

    guid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name = Column(String(128), ForeignKey("relationship_type_def.type_name"), nullable=False)
    end1_guid = Column(UUID(as_uuid=True), ForeignKey("entity.guid"), nullable=False)
    end2_guid = Column(UUID(as_uuid=True), ForeignKey("entity.guid"), nullable=False)
    attributes = Column(JSONB, default=dict)
    source = Column(String(64), default="manual")
    confidence = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True)
    first_seen = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class LabelDefinition(Base):
    __tablename__ = "label_definition"

    label_key = Column(String(128), primary_key=True)
    label_name = Column(String(256))
    value_type = Column(String(32), default="string")
    enum_values = Column(JSONB)
    description = Column(Text)
    created_by = Column(String(128))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
