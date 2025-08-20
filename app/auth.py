from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .config import settings
import logging

logger = logging.getLogger(__name__)

# HTTP Bearer scheme
security = HTTPBearer(auto_error=False)


async def verify_analytics_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the analytics token from Authorization header"""
    if not credentials:
        logger.warning("Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if credentials.scheme.lower() != "bearer":
        logger.warning(f"Invalid authentication scheme: {credentials.scheme}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    if not token:
        logger.warning("Empty token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if token != settings.ANALYTICS_TOKEN:
        logger.warning("Invalid token provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug("Token verification successful")
    return token


# Dependency for protected endpoints
def require_analytics_token():
    """Dependency that requires valid analytics token"""
    return verify_analytics_token
