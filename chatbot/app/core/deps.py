"""FastAPI dependency providers — resolved from app state set at startup."""
from typing import Annotated
from fastapi import Depends, HTTPException, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

_bearer = HTTPBearer(auto_error=False)


def get_db_pool(request: Request):
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise RuntimeError("DB pool not initialised")
    return pool


def get_qdrant(request: Request):
    client = getattr(request.app.state, "qdrant", None)
    if client is None:
        raise RuntimeError("Qdrant client not initialised")
    return client


def get_redis(request: Request):
    client = getattr(request.app.state, "redis", None)
    if client is None:
        raise RuntimeError("Redis client not initialised")
    return client


def require_admin(
    x_admin_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> str:
    """Verify a Django Simple JWT access token and return the user's UUID.

    The frontend sends the token received from the Django BE login endpoint:
      POST /api/v1/login/  →  { "access": "<token>", "refresh": "..." }

    Simple JWT signs with Django's SECRET_KEY (HS256).
    The user UUID is in the 'user_id' claim (Simple JWT default).
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    if not settings.django_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Auth not configured — set DJANGO_SECRET_KEY in .env",
        )

    try:
        from jose import jwt

        payload = jwt.decode(
            credentials.credentials,
            settings.django_secret_key,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Simple JWT stores the user PK in 'user_id', not 'sub'
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user_id claim")

    return str(user_id)
