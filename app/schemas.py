from pydantic import BaseModel, Field, conint, validator
from typing import Optional, List
import uuid
from datetime import datetime, timezone


class UsageEventIn(BaseModel):
    event_id: uuid.UUID
    event_time_epoch: conint(ge=0)
    user_id: str = Field(..., min_length=1, max_length=255)
    team: str = Field(..., min_length=1, max_length=100)
    service: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=100)
    total_tokens: int = Field(default=0, ge=0)
    latency_ms: Optional[int] = Field(None, ge=0)
    status_code: Optional[int] = Field(None, ge=100, le=599)
    error_type: Optional[str] = Field(None, max_length=100)
    prompt: Optional[str] = Field(None, max_length=10000)
    extra: Optional[dict] = None

    @validator('event_time_epoch')
    def validate_event_time(cls, v):
        # Check if timestamp is not too far in the future (max 1 hour)
        max_future = datetime.now(timezone.utc).timestamp() + 3600
        if v > max_future:
            raise ValueError('Event time cannot be more than 1 hour in the future')
        return v

    @validator('user_id', 'team', 'service', 'provider', 'model')
    def validate_string_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty or whitespace only')
        return v.strip()


class ArchiveIn(BaseModel):
    event_id: uuid.UUID
    user_id: str = Field(..., min_length=1, max_length=255)
    service: str = Field(..., min_length=1, max_length=100)
    prompt_full: Optional[str] = Field(None, max_length=50000)
    response_full: Optional[str] = Field(None, max_length=50000)
    stored_at: conint(ge=0)

    @validator('stored_at')
    def validate_stored_at(cls, v):
        # Check if timestamp is not too far in the future (max 1 hour)
        max_future = datetime.now(timezone.utc).timestamp() + 3600
        if v > max_future:
            raise ValueError('Stored time cannot be more than 1 hour in the future')
        return v


class BulkEvents(BaseModel):
    items: List[UsageEventIn] = Field(default_factory=list, max_items=1000)

    @validator('items')
    def validate_items_count(cls, v):
        if len(v) > 1000:
            raise ValueError('Maximum 1000 items allowed per bulk request')
        return v


class BulkArchives(BaseModel):
    items: List[ArchiveIn] = Field(default_factory=list, max_items=1000)

    @validator('items')
    def validate_items_count(cls, v):
        if len(v) > 1000:
            raise ValueError('Maximum 1000 items allowed per bulk request')
        return v


class IngestResponse(BaseModel):
    accepted: int
    rejected: int = 0
    errors: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    database: bool
    timestamp: datetime
