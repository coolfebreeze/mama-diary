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
    
    # Create message_archives table
    op.create_table('message_archives',
        sa.Column('event_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('service', sa.Text(), nullable=False),
        sa.Column('prompt_full', sa.Text(), nullable=True),
        sa.Column('response_full', sa.Text(), nullable=True),
        sa.Column('stored_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['analytics.usage_events.event_id'], ondelete='CASCADE'),
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
    
    # Create unique index for event_id (for foreign key reference) - includes event_time
    op.create_index('idx_usage_events_event_id_unique', 'usage_events', ['event_time', 'event_id'], unique=True, schema='analytics')
    
    op.create_index('idx_message_archives_user', 'message_archives', ['user_id'], unique=False, schema='analytics')
    op.create_index('idx_message_archives_service', 'message_archives', ['service'], unique=False, schema='analytics')
    op.create_index('idx_message_archives_stored_at', 'message_archives', ['stored_at'], unique=False, schema='analytics')
    
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
    # Remove policies
    op.execute("SELECT remove_retention_policy('analytics.usage_events');")
    op.execute("SELECT remove_compression_policy('analytics.usage_events');")
    
    # Drop tables
    op.drop_table('message_archives', schema='analytics')
    op.drop_table('usage_events', schema='analytics')
    
    # Drop schema
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE;")
    
    # Note: We don't drop the timescaledb extension as it might be used by other parts of the system
