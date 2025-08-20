import gzip
import json
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .db import get_db
from .models import UsageEvent, MessageArchive
from .schemas import BulkEvents, BulkArchives, IngestResponse
from .config import settings
from .auth import require_analytics_token

logger = logging.getLogger(__name__)
router = APIRouter()


def _read_json_from_request(raw: bytes, content_encoding: str | None) -> dict:
    """Parse JSON from request body, handling gzip compression"""
    try:
        # Handle gzip compression
        if content_encoding and content_encoding.lower() == "gzip":
            if len(raw) > settings.MAX_GZIP_SIZE:
                raise HTTPException(
                    status_code=413, 
                    detail=f"Gzip payload too large. Max size: {settings.MAX_GZIP_SIZE} bytes"
                )
            try:
                raw = gzip.decompress(raw)
            except Exception as e:
                logger.error(f"Failed to decompress gzip: {e}")
                raise HTTPException(status_code=400, detail="Invalid gzip payload")
        
        # Parse JSON
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object")
        
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        logger.error(f"Unexpected error parsing request: {e}")
        raise HTTPException(status_code=400, detail="Invalid request payload")


async def _bulk_insert_usage_events(session: AsyncSession, events: List[dict]) -> tuple[int, List[str]]:
    """Bulk insert usage events with error handling"""
    if not events:
        return 0, []
    
    try:
        stmt = insert(UsageEvent).values(events).on_conflict_do_nothing(index_elements=["event_id"])
        result = await session.execute(stmt)
        await session.commit()
        
        # Count actual inserted rows (approximate)
        accepted = len(events)
        logger.info(f"Successfully inserted {accepted} usage events")
        return accepted, []
        
    except IntegrityError as e:
        await session.rollback()
        logger.warning(f"Integrity error during bulk insert: {e}")
        # Try individual inserts to get better error reporting
        return await _individual_insert_usage_events(session, events)
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error during bulk insert: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


async def _individual_insert_usage_events(session: AsyncSession, events: List[dict]) -> tuple[int, List[str]]:
    """Insert events individually to handle conflicts gracefully"""
    accepted = 0
    errors = []
    
    for event in events:
        try:
            stmt = insert(UsageEvent).values(event).on_conflict_do_nothing(index_elements=["event_id"])
            result = await session.execute(stmt)
            if result.rowcount > 0:
                accepted += 1
        except Exception as e:
            errors.append(f"Event {event.get('event_id', 'unknown')}: {str(e)}")
    
    await session.commit()
    return accepted, errors


async def _bulk_insert_archives(session: AsyncSession, archives: List[dict]) -> tuple[int, List[str]]:
    """Bulk insert message archives with error handling"""
    if not archives:
        return 0, []
    
    try:
        stmt = insert(MessageArchive).values(archives).on_conflict_do_nothing(index_elements=["event_id"])
        result = await session.execute(stmt)
        await session.commit()
        
        accepted = len(archives)
        logger.info(f"Successfully inserted {accepted} message archives")
        return accepted, []
        
    except IntegrityError as e:
        await session.rollback()
        logger.warning(f"Integrity error during bulk insert: {e}")
        return await _individual_insert_archives(session, archives)
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Database error during bulk insert: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


async def _individual_insert_archives(session: AsyncSession, archives: List[dict]) -> tuple[int, List[str]]:
    """Insert archives individually to handle conflicts gracefully"""
    accepted = 0
    errors = []
    
    for archive in archives:
        try:
            stmt = insert(MessageArchive).values(archive).on_conflict_do_nothing(index_elements=["event_id"])
            result = await session.execute(stmt)
            if result.rowcount > 0:
                accepted += 1
        except Exception as e:
            errors.append(f"Archive {archive.get('event_id', 'unknown')}: {str(e)}")
    
    await session.commit()
    return accepted, errors


@router.post("/v1/ingest/requests:bulk", response_model=IngestResponse)
async def ingest_requests(
    req: Request, 
    session: AsyncSession = Depends(get_db),
    token: str = Depends(require_analytics_token())
):
    """Bulk ingest usage events with gzip support and validation"""
    
    # Read and parse request body
    body = await req.body()
    data = _read_json_from_request(body, req.headers.get("content-encoding"))
    
    # Validate payload
    try:
        payload = BulkEvents.model_validate(data)
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    
    if not payload.items:
        return IngestResponse(accepted=0, rejected=0)
    
    # Check bulk size limit
    if len(payload.items) > settings.MAX_BULK_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"Too many items. Max allowed: {settings.MAX_BULK_SIZE}"
        )
    
    # Transform data for database insertion
    rows = []
    for event in payload.items:
        try:
            rows.append({
                "event_id": str(event.event_id),
                "event_time": datetime.fromtimestamp(event.event_time_epoch, tz=timezone.utc),
                "user_id": event.user_id,
                "team": event.team,
                "service": event.service,
                "provider": event.provider,
                "model": event.model,
                "total_tokens": event.total_tokens,
                "latency_ms": event.latency_ms,
                "status_code": event.status_code,
                "error_type": event.error_type,
                "prompt": event.prompt,
                "extra": event.extra,
            })
        except Exception as e:
            logger.error(f"Error processing event {event.event_id}: {e}")
            continue
    
    # Insert into database
    accepted, errors = await _bulk_insert_usage_events(session, rows)
    rejected = len(payload.items) - accepted
    
    logger.info(f"Bulk ingest completed: {accepted} accepted, {rejected} rejected")
    
    return IngestResponse(
        accepted=accepted,
        rejected=rejected,
        errors=errors[:10]  # Limit error messages in response
    )


@router.post("/v1/ingest/archives:bulk", response_model=IngestResponse)
async def ingest_archives(
    req: Request, 
    session: AsyncSession = Depends(get_db),
    token: str = Depends(require_analytics_token())
):
    """Bulk ingest message archives with gzip support and validation"""
    
    # Read and parse request body
    body = await req.body()
    data = _read_json_from_request(body, req.headers.get("content-encoding"))
    
    # Validate payload
    try:
        payload = BulkArchives.model_validate(data)
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    
    if not payload.items:
        return IngestResponse(accepted=0, rejected=0)
    
    # Check bulk size limit
    if len(payload.items) > settings.MAX_BULK_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"Too many items. Max allowed: {settings.MAX_BULK_SIZE}"
        )
    
    # Transform data for database insertion
    rows = []
    for archive in payload.items:
        try:
            rows.append({
                "event_id": str(archive.event_id),
                "user_id": archive.user_id,
                "service": archive.service,
                "prompt_full": archive.prompt_full,
                "response_full": archive.response_full,
                "stored_at": datetime.fromtimestamp(archive.stored_at, tz=timezone.utc),
            })
        except Exception as e:
            logger.error(f"Error processing archive {archive.event_id}: {e}")
            continue
    
    # Insert into database
    accepted, errors = await _bulk_insert_archives(session, rows)
    rejected = len(payload.items) - accepted
    
    logger.info(f"Bulk archive ingest completed: {accepted} accepted, {rejected} rejected")
    
    return IngestResponse(
        accepted=accepted,
        rejected=rejected,
        errors=errors[:10]  # Limit error messages in response
    )
