from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text
from .config import settings
import logging

logger = logging.getLogger(__name__)

async def ensure_timescale(engine: AsyncEngine):
    """Initialize TimescaleDB extension and create tables with optimized settings"""
    
    ddl = f"""
    -- Enable TimescaleDB extension
    CREATE EXTENSION IF NOT EXISTS timescaledb;
    
    -- Create analytics schema
    CREATE SCHEMA IF NOT EXISTS analytics;
    
    -- Base table for usage events (will be converted to hypertable)
    CREATE TABLE IF NOT EXISTS analytics.usage_events (
        event_id      UUID PRIMARY KEY,
        event_time    TIMESTAMPTZ NOT NULL,
        user_id       TEXT NOT NULL,
        team          TEXT NOT NULL,
        service       TEXT NOT NULL,
        provider      TEXT NOT NULL,
        model         TEXT NOT NULL,
        total_tokens  INT NOT NULL DEFAULT 0,
        latency_ms    INT,
        status_code   INT,
        error_type    TEXT,
        prompt        TEXT,
        extra         JSONB,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    
    -- Convert to hypertable with daily chunks
    SELECT create_hypertable(
        'analytics.usage_events',
        'event_time',
        chunk_time_interval => INTERVAL '{settings.CHUNK_TIME_INTERVAL}',
        if_not_exists => TRUE
    );
    
    -- Create message archives table (cold storage)
    CREATE TABLE IF NOT EXISTS analytics.message_archives (
        event_id       UUID PRIMARY KEY REFERENCES analytics.usage_events(event_id) ON DELETE CASCADE,
        user_id        TEXT NOT NULL,
        service        TEXT NOT NULL,
        prompt_full    TEXT,
        response_full  TEXT,
        stored_at      TIMESTAMPTZ NOT NULL
    );
    
    -- Create optimized indexes for common query patterns
    CREATE INDEX IF NOT EXISTS idx_usage_events_time 
        ON analytics.usage_events (event_time DESC);
    
    CREATE INDEX IF NOT EXISTS idx_usage_events_team_time 
        ON analytics.usage_events (team, event_time DESC);
    
    CREATE INDEX IF NOT EXISTS idx_usage_events_user_time 
        ON analytics.usage_events (user_id, event_time DESC);
    
    CREATE INDEX IF NOT EXISTS idx_usage_events_service_model 
        ON analytics.usage_events (service, model, event_time DESC);
    
    CREATE INDEX IF NOT EXISTS idx_usage_events_status_time 
        ON analytics.usage_events (status_code, event_time DESC);
    
    CREATE INDEX IF NOT EXISTS idx_usage_events_provider 
        ON analytics.usage_events (provider, event_time DESC);
    
    CREATE INDEX IF NOT EXISTS idx_message_archives_user 
        ON analytics.message_archives (user_id);
    
    CREATE INDEX IF NOT EXISTS idx_message_archives_service 
        ON analytics.message_archives (service);
    
    CREATE INDEX IF NOT EXISTS idx_message_archives_stored_at 
        ON analytics.message_archives (stored_at DESC);
    
    -- Configure compression settings
    ALTER TABLE analytics.usage_events SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'team,service,model',
        timescaledb.compress_orderby = 'event_time DESC'
    );
    
    -- Add compression policy (compress after specified days)
    SELECT add_compression_policy(
        'analytics.usage_events', 
        INTERVAL '{settings.COMPRESSION_AFTER_DAYS} days'
    );
    
    -- Add retention policy (drop chunks older than specified days)
    SELECT add_retention_policy(
        'analytics.usage_events', 
        INTERVAL '{settings.RETENTION_DAYS} days'
    );
    """
    
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(ddl)
        logger.info("TimescaleDB initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to initialize TimescaleDB: {e}")
        raise


async def create_continuous_aggregates(engine: AsyncEngine):
    """Create continuous aggregates for common analytics queries"""
    
    ca_ddl = """
    -- Hourly aggregations
    CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.hourly_usage_stats
    WITH (timescaledb.continuous) AS
    SELECT 
        time_bucket('1 hour', event_time) AS hour,
        team,
        service,
        model,
        provider,
        COUNT(*) as request_count,
        SUM(total_tokens) as total_tokens,
        AVG(latency_ms) as avg_latency_ms,
        COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count
    FROM analytics.usage_events
    GROUP BY hour, team, service, model, provider;
    
    -- Daily aggregations
    CREATE MATERIALIZED VIEW IF NOT EXISTS analytics.daily_usage_stats
    WITH (timescaledb.continuous) AS
    SELECT 
        time_bucket('1 day', event_time) AS day,
        team,
        service,
        model,
        provider,
        COUNT(*) as request_count,
        SUM(total_tokens) as total_tokens,
        AVG(latency_ms) as avg_latency_ms,
        COUNT(CASE WHEN status_code >= 400 THEN 1 END) as error_count
    FROM analytics.usage_events
    GROUP BY day, team, service, model, provider;
    """
    
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(ca_ddl)
        logger.info("Continuous aggregates created successfully")
    except Exception as e:
        logger.warning(f"Failed to create continuous aggregates: {e}")


async def initialize_database(engine: AsyncEngine):
    """Complete database initialization"""
    await ensure_timescale(engine)
    await create_continuous_aggregates(engine)
