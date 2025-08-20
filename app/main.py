import logging
import structlog
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from .api_ingest import router as ingest_router
from .db import engine, check_db_connection
from .bootstrap import initialize_database
from .schemas import HealthResponse
from .config import settings

# Configure structured logging
def setup_logging():
    """Setup structured logging with JSON format"""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format="%(message)s"
    )
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    setup_logging()
    logger = structlog.get_logger()
    logger.info("Starting Analytics API")
    
    try:
        # Initialize database
        await initialize_database(engine)
        logger.info("Database initialization completed")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Analytics API")
    await engine.dispose()


def custom_openapi():
    """Custom OpenAPI schema with authentication"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Analytics API",
        version="1.0.0",
        description="LLM usage analytics ingestion API with TimescaleDB",
        routes=app.routes,
    )
    
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": "Analytics token for API access"
        }
    }
    
    # Add security requirement to all endpoints
    for path in openapi_schema["paths"]:
        if path.startswith("/api/"):  # Only protect API endpoints
            for method in openapi_schema["paths"][path]:
                if method in ["post", "put", "delete", "patch"]:
                    openapi_schema["paths"][path][method]["security"] = [
                        {"BearerAuth": []}
                    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Create FastAPI app
app = FastAPI(
    title="Analytics API",
    description="LLM usage analytics ingestion API with TimescaleDB",
    version="1.0.0",
    lifespan=lifespan
)

# Set custom OpenAPI schema
app.openapi = custom_openapi

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest_router, prefix="/api", tags=["ingest"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger = structlog.get_logger()
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_healthy = await check_db_connection()
    
    return HealthResponse(
        status="healthy" if db_healthy else "unhealthy",
        database=db_healthy,
        timestamp=datetime.utcnow()
    )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Analytics API",
        "version": "1.0.0",
        "description": "LLM usage analytics ingestion API",
        "authentication": "Bearer token required for API endpoints",
        "endpoints": {
            "health": "/healthz",
            "ingest_requests": "/api/v1/ingest/requests:bulk",
            "ingest_archives": "/api/v1/ingest/archives:bulk",
            "docs": "/docs"
        }
    }
