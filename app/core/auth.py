"""
Basic HTTP Authentication for the Translation API.

Validates credentials against configured username/password from environment.
"""

import secrets
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings

logger = logging.getLogger(__name__)

security = HTTPBasic()


async def require_auth(
    credentials: HTTPBasicCredentials = Depends(security),
) -> str:
    """
    FastAPI dependency that enforces HTTP Basic Authentication.

    Compares provided credentials against the configured API_USERNAME and
    API_PASSWORD using constant-time comparison to prevent timing attacks.

    Returns the authenticated username on success.
    Raises HTTP 401 on failure.
    """
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.API_USERNAME.encode("utf-8"),
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.API_PASSWORD.encode("utf-8"),
    )

    if not (correct_username and correct_password):
        logger.warning("Authentication failed for user: %s", credentials.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
