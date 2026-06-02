import uuid

from sqlalchemy import Column, DateTime, Index, Integer, Text, Date
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from .base import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_name = Column(Text, nullable=False)
    triggered_by = Column(Text, nullable=False, default="scheduler")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    status = Column(Text, nullable=False, default="running")
    target_date = Column(Date)
    rows_processed = Column(Integer, nullable=False, default=0)
    error = Column(Text)
    timings = Column(JSONB)

    __table_args__ = (
        Index("ix_pipeline_runs_job_started", "job_name", "started_at"),
        Index("ix_pipeline_runs_status", "status"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    entity = Column(Text, nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    before = Column(JSONB)
    after = Column(JSONB)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_audit_log_entity_id_occurred", "entity", "entity_id", "occurred_at"),
    )
