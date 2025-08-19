"""Add continuous aggregates

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create hourly continuous aggregate
    op.execute("""
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
    """)
    
    # Create daily continuous aggregate
    op.execute("""
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
    """)


def downgrade() -> None:
    # Drop continuous aggregates
    op.execute("DROP MATERIALIZED VIEW IF EXISTS analytics.daily_usage_stats CASCADE;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS analytics.hourly_usage_stats CASCADE;")
