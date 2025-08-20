from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime, Integer, Text, JSON, DateTime as DT, text, Index, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from .db import Base
import logging

logger = logging.getLogger(__name__)

SCHEMA = "analytics"

class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_time", "event_time"),
        Index("ix_usage_events_team_time", "team", "event_time"),
        Index("ix_usage_events_user_time", "user_id", "event_time"),
        Index("ix_usage_events_service_model", "service", "model", "event_time"),
        Index("ix_usage_events_status_time", "status_code", "event_time"),
        Index("ix_usage_events_provider", "provider", "event_time"),
        # TimescaleDB requirement: Primary Key must include event_time (partitioning key)
        PrimaryKeyConstraint("event_time", "event_id"),
        {"schema": SCHEMA}
    )

    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    event_time: Mapped[DT] = mapped_column(DateTime(timezone=True), nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    team: Mapped[str] = mapped_column(Text, nullable=False)
    service: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status_code: Mapped[int | None] = mapped_column(Integer)
    error_type: Mapped[str | None] = mapped_column(Text)
    prompt: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[DT] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    def __repr__(self):
        return f"<UsageEvent(event_id={self.event_id}, user_id={self.user_id}, service={self.service})>"


class MessageArchive(Base):
    __tablename__ = "message_archives"
    __table_args__ = (
        Index("ix_message_archives_user", "user_id"),
        Index("ix_message_archives_service", "service"),
        Index("ix_message_archives_stored_at", "stored_at"),
        {"schema": SCHEMA}
    )

    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    service: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_full: Mapped[str | None] = mapped_column(Text)
    response_full: Mapped[str | None] = mapped_column(Text)
    stored_at: Mapped[DT] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationship without FK (TimescaleDB doesn't support FK to hypertables)
    usage_event = relationship(
        "UsageEvent",
        primaryjoin="MessageArchive.event_id==UsageEvent.event_id",
        viewonly=True,  # Read-only relationship without FK
        uselist=False
    )

    def __repr__(self):
        return f"<MessageArchive(event_id={self.event_id}, user_id={self.user_id})>"
