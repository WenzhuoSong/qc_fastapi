"""
API Security — Bearer Token Authentication
"""

from fastapi import Depends, HTTPException, Query, status
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


async def verify_token_flexible(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str = Query("", description="API token (fallback for QC self.Download)"),
) -> str:
    """Validate token from either Bearer header or query parameter.

    Priority: Bearer header > query param > skip if API_TOKEN not configured.
    This allows QuantConnect's self.Download() to use ?token=xxx since it
    cannot set custom HTTP headers.
    """
    configured_token = settings.API_TOKEN

    if not configured_token:
        return "anonymous"

    # Try Bearer token first
    if credentials is not None and credentials.credentials == configured_token:
        return credentials.credentials

    # Fallback to query param
    if token and token == configured_token:
        return token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API token (provide via Authorization header or ?token=xxx)",
        headers={"WWW-Authenticate": "Bearer"},
    )
