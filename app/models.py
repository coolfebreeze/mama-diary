from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, Integer, Text, JSON, DateTime as DT, text, Index
from sqlalchemy.dialects.postgresql import UUID
from .db import Base
import logging

logger = logging.getLogger(__name__)

SCHEMA = "analytics"

class UsageEvent(Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        {"schema": SCHEMA},
        # Optimized indexes for common query patterns
        Index("ix_usage_events_time", "event_time"),
        Index("ix_usage_events_team_time", "team", "event_time DESC"),
        Index("ix_usage_events_user_time", "user_id", "event_time DESC"),
        Index("ix_usage_events_service_model", "service", "model", "event_time DESC"),
        Index("ix_usage_events_status_time", "status_code", "event_time DESC"),
        Index("ix_usage_events_provider", "provider", "event_time DESC"),
    )

    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    event_time: Mapped[DT] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    team: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    service: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    model: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status_code: Mapped[int | None] = mapped_column(Integer, index=True)
    error_type: Mapped[str | None] = mapped_column(Text)
    prompt: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[DT] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    def __repr__(self):
        return f"<UsageEvent(event_id={self.event_id}, user_id={self.user_id}, service={self.service})>"


class MessageArchive(Base):
    __tablename__ = "message_archives"
    __table_args__ = (
        {"schema": SCHEMA},
        Index("ix_message_archives_user", "user_id"),
        Index("ix_message_archives_service", "service"),
        Index("ix_message_archives_stored_at", "stored_at"),
    )

    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    service: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    prompt_full: Mapped[str | None] = mapped_column(Text)
    response_full: Mapped[str | None] = mapped_column(Text)
    stored_at: Mapped[DT] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    def __repr__(self):
        return f"<MessageArchive(event_id={self.event_id}, user_id={self.user_id})>"
