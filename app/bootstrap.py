from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text
from .config import settings
import logging
import subprocess
import sys
import os

logger = logging.getLogger(__name__)

async def ensure_timescale_extension(engine: AsyncEngine):
    """Ensure TimescaleDB extension is enabled"""
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS timescaledb;")
        logger.info("TimescaleDB extension enabled")
    except Exception as e:
        logger.error(f"Failed to enable TimescaleDB extension: {e}")
        raise



async def run_alembic_migrations():
    """Run Alembic migrations"""
    try:
        # Set PYTHONPATH to include the app directory
        env = os.environ.copy()
        env['PYTHONPATH'] = '/app'
        
        # Try to run alembic upgrade
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True, cwd="/app", env=env)
        
        if result.returncode == 0:
            logger.info("Alembic migrations completed successfully")
            if result.stdout:
                logger.debug(f"Alembic output: {result.stdout}")
        else:
            logger.error(f"Alembic migration failed. Return code: {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            raise Exception(f"Alembic migration failed: {result.stderr}")
            
    except Exception as e:
        logger.error(f"Failed to run Alembic migrations: {e}")
        raise

async def initialize_database(engine: AsyncEngine):
    """Complete database initialization using Alembic"""
    # First ensure TimescaleDB extension is enabled
    await ensure_timescale_extension(engine)
    
    # Then run Alembic migrations
    await run_alembic_migrations()
    
    logger.info("Database initialization completed successfully")
