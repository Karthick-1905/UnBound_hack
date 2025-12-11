"""Authentication helpers for FastAPI routes."""

from __future__ import annotations

from fastapi import Header, HTTPException, status, Depends

from services.users import CreatedUser, UserLookupError, get_user_by_api_key


HEADER_NAME = "X-API-Key"


def require_api_key(x_api_key: str = Header(..., alias=HEADER_NAME)) -> CreatedUser:
    """Fetch the user associated with the provided API key header."""

    try:
        user = get_user_by_api_key(x_api_key)
    except UserLookupError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to validate API key") from exc

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    return user


def require_admin(user: CreatedUser = Depends(require_api_key)) -> CreatedUser:
    """Require that the authenticated user has admin role."""
    
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )
    
    return user
