"""Initial TimescaleDB setup

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable TimescaleDB extension
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    
    # Create analytics schema
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics;")
    
    # Create usage_events table with TimescaleDB-compatible constraints
    op.create_table('usage_events',
        sa.Column('event_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('team', sa.Text(), nullable=False),
        sa.Column('service', sa.Text(), nullable=False),
        sa.Column('provider', sa.Text(), nullable=False),
        sa.Column('model', sa.Text(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('error_type', sa.Text(), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('extra', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        # TimescaleDB requirement: Primary Key must include event_time (partitioning key)
        sa.PrimaryKeyConstraint('event_time', 'event_id'),
        schema='analytics'
    )
    
    # Convert to hypertable
    op.execute("""
        SELECT create_hypertable(
            'analytics.usage_events',
            'event_time',
            chunk_time_interval => INTERVAL '24 hours',
            if_not_exists => TRUE
        );
    """)
    
    # Create message_archives table (FK 제거 - TimescaleDB 제한)
    op.create_table('message_archives',
        sa.Column('event_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('service', sa.Text(), nullable=False),
        sa.Column('prompt_full', sa.Text(), nullable=True),
        sa.Column('response_full', sa.Text(), nullable=True),
        sa.Column('stored_at', sa.DateTime(timezone=True), nullable=False),
        # FK 제거! TimescaleDB가 하이퍼테이블 참조 FK를 금지함
        sa.PrimaryKeyConstraint('event_id'),
        schema='analytics'
    )
    
    # Create indexes (all include event_time for TimescaleDB compatibility)
    op.create_index('idx_usage_events_time', 'usage_events', ['event_time'], unique=False, schema='analytics')
    op.create_index('idx_usage_events_team_time', 'usage_events', ['team', 'event_time'], unique=False, schema='analytics')
    op.create_index('idx_usage_events_user_time', 'usage_events', ['user_id', 'event_time'], unique=False, schema='analytics')
    op.create_index('idx_usage_events_service_model', 'usage_events', ['service', 'model', 'event_time'], unique=False, schema='analytics')
    op.create_index('idx_usage_events_status_time', 'usage_events', ['status_code', 'event_time'], unique=False, schema='analytics')
    op.create_index('idx_usage_events_provider', 'usage_events', ['provider', 'event_time'], unique=False, schema='analytics')
    
    # Create non-unique index for event_id (for FK emulation and fast lookups)
    op.execute("CREATE INDEX IF NOT EXISTS idx_usage_events_event_id ON analytics.usage_events (event_id);")
    
    op.create_index('idx_message_archives_user', 'message_archives', ['user_id'], unique=False, schema='analytics')
    op.create_index('idx_message_archives_service', 'message_archives', ['service'], unique=False, schema='analytics')
    op.create_index('idx_message_archives_stored_at', 'message_archives', ['stored_at'], unique=False, schema='analytics')
    
    # Create trigger function for FK emulation (insert/update validation)
    op.execute("""
    CREATE OR REPLACE FUNCTION analytics.fn_check_usage_event_exists()
    RETURNS trigger AS $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM analytics.usage_events ue
        WHERE ue.event_id = NEW.event_id
      ) THEN
        RAISE EXCEPTION 'event_id % not found in analytics.usage_events', NEW.event_id;
      END IF;
      RETURN NEW;
    END
    $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for FK emulation (DROP and CREATE separated for asyncpg compatibility)
    op.execute("DROP TRIGGER IF EXISTS trg_message_archives_check_fk ON analytics.message_archives;")
    op.execute("""
    CREATE TRIGGER trg_message_archives_check_fk
    BEFORE INSERT OR UPDATE OF event_id ON analytics.message_archives
    FOR EACH ROW EXECUTE FUNCTION analytics.fn_check_usage_event_exists();
    """)
    
    # Create trigger function for cascade delete emulation
    op.execute("""
    CREATE OR REPLACE FUNCTION analytics.fn_usage_events_cascade_delete()
    RETURNS trigger AS $$
    BEGIN
      DELETE FROM analytics.message_archives WHERE event_id = OLD.event_id;
      RETURN OLD;
    END
    $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger for cascade delete (DROP and CREATE separated for asyncpg compatibility)
    op.execute("DROP TRIGGER IF EXISTS trg_usage_events_cascade_delete ON analytics.usage_events;")
    op.execute("""
    CREATE TRIGGER trg_usage_events_cascade_delete
    AFTER DELETE ON analytics.usage_events
    FOR EACH ROW EXECUTE FUNCTION analytics.fn_usage_events_cascade_delete();
    """)
    
    # Configure compression
    op.execute("""
        ALTER TABLE analytics.usage_events SET (
            timescaledb.compress,
            timescaledb.compress_segmentby = 'team,service,model',
            timescaledb.compress_orderby = 'event_time DESC'
        );
    """)
    
    # Add compression policy (7 days)
    op.execute("SELECT add_compression_policy('analytics.usage_events', INTERVAL '7 days');")
    
    # Add retention policy (180 days)
    op.execute("SELECT add_retention_policy('analytics.usage_events', INTERVAL '180 days');")


def downgrade() -> None:
    # Remove triggers first
    op.execute("DROP TRIGGER IF EXISTS trg_usage_events_cascade_delete ON analytics.usage_events;")
    op.execute("DROP TRIGGER IF EXISTS trg_message_archives_check_fk ON analytics.message_archives;")
    
    # Remove trigger functions
    op.execute("DROP FUNCTION IF EXISTS analytics.fn_usage_events_cascade_delete();")
    op.execute("DROP FUNCTION IF EXISTS analytics.fn_check_usage_event_exists();")
    
    # Remove policies
    op.execute("SELECT remove_retention_policy('analytics.usage_events');")
    op.execute("SELECT remove_compression_policy('analytics.usage_events');")
    
    # Drop tables
    op.drop_table('message_archives', schema='analytics')
    op.drop_table('usage_events', schema='analytics')
    
    # Drop schema
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE;")
    
    # Note: We don't drop the timescaledb extension as it might be used by other parts of the system
