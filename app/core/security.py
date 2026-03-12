"""
API Security — Bearer Token Authentication
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Validate the Bearer token from the Authorization header.

    When ``API_TOKEN`` is empty (local dev), authentication is skipped so
    the API remains usable without configuration.  In production you MUST
    set ``API_TOKEN`` in the environment.
    """
    configured_token = settings.API_TOKEN

    if not configured_token:
        return "anonymous"

    if credentials is None or credentials.credentials != configured_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials
