"""Authentication middleware — OAuth2 token introspection.

Two modes controlled by AUTH_DEV_MODE:
- Production (false): validates access token via introspection endpoint, caches in DB.
- Dev (true): resolves user from X-Dev-User header (email) against seeded users.

Auto-creates user on first successful introspection if not in DB.
require_admin: verifies is_admin from DB on every call — never from token (CLAUDE.md).
"""

import time
import uuid

import httpx
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from db.connection import get_db
from db.models import OAuthToken, User


async def _resolve_dev_user(request: Request, db: AsyncSession, settings: Settings) -> User:
    """Dev-mode: resolve the current user from the X-Dev-User header (email).
    Falls back to AUTH_DEV_DEFAULT_USER if header is absent."""
    email = request.headers.get("X-Dev-User") or settings.auth_dev_default_user
    if not email:
        raise HTTPException(status_code=401, detail="X-Dev-User header required in dev mode")

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=401, detail=f"Dev user not found: {email}. Run seed_dev_users.py first."
        )
    return user


async def _call_introspect(token: str, settings: Settings) -> dict:
    """POST to the OAuth introspection endpoint. Returns the introspect response dict."""
    introspect_url = f"{settings.oauth_introspect_url.rstrip('/')}/o/introspect/"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            introspect_url,
            data={
                "token": token,
                "client_id": settings.oauth_client_id,
                "client_secret": settings.oauth_client_secret,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _get_or_create_user(db: AsyncSession, token_info: dict) -> User:
    """Look up user by slug; auto-create if not found (IDP returned success)."""
    slug = token_info.get("slug") or token_info.get("username", "")
    if not slug:
        raise HTTPException(status_code=401, detail="Token introspection returned no user slug")

    user = (await db.execute(select(User).where(User.slug == slug))).scalar_one_or_none()

    if user is None:
        first = token_info.get("first_name", "")
        last = token_info.get("last_name", "")
        display_name = f"{first} {last}".strip() or slug

        user = User(
            id=uuid.uuid4(),
            slug=slug,
            email=token_info.get("email", ""),
            display_name=display_name,
            is_admin=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Update name/email if changed
        changed = False
        email = token_info.get("email")
        if email and user.email != email:
            user.email = email
            changed = True
        first = token_info.get("first_name", "")
        last = token_info.get("last_name", "")
        name = f"{first} {last}".strip()
        if name and user.display_name != name:
            user.display_name = name
            changed = True
        if changed:
            await db.commit()
            await db.refresh(user)

    return user


async def _cache_token(db: AsyncSession, token: str, token_info: dict) -> None:
    """Upsert token into oauth_tokens cache."""
    existing = (
        await db.execute(select(OAuthToken).where(OAuthToken.token == token))
    ).scalar_one_or_none()

    if existing:
        existing.is_active = token_info.get("active", True)
        existing.exp = token_info.get("exp", 0)
        existing.slug = token_info.get("slug") or token_info.get("username", "")
        existing.email = token_info.get("email")
    else:
        db.add(
            OAuthToken(
                token=token,
                is_active=token_info.get("active", True),
                scope=token_info.get("scope"),
                exp=token_info.get("exp", 0),
                slug=token_info.get("slug") or token_info.get("username", ""),
                email=token_info.get("email"),
            )
        )
    await db.commit()


async def _resolve_oauth_user(request: Request, db: AsyncSession, settings: Settings) -> User:
    """Production: validate token via introspection, cache, and resolve/create user."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")

    now = int(time.time())

    # 1. Check token cache
    cached = (
        await db.execute(select(OAuthToken).where(OAuthToken.token == token))
    ).scalar_one_or_none()

    if cached:
        if cached.exp <= now:
            # Expired — remove from cache
            await db.delete(cached)
            await db.commit()
            raise HTTPException(status_code=401, detail="Token expired")

        # Valid cached token — resolve user by slug
        user = (await db.execute(select(User).where(User.slug == cached.slug))).scalar_one_or_none()
        if user:
            return user
        # User was deleted? Fall through to re-introspect

    # 2. Call introspection endpoint
    try:
        token_info = await _call_introspect(token, settings)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=401, detail=f"Introspection failed: {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"OAuth provider unreachable: {exc}") from exc

    if not token_info.get("active"):
        raise HTTPException(status_code=401, detail="Token is inactive")

    exp = token_info.get("exp", 0)
    if exp and exp <= now:
        raise HTTPException(status_code=401, detail="Token expired")

    # 3. Get or create user
    user = await _get_or_create_user(db, token_info)

    # 4. Cache the token
    await _cache_token(db, token, token_info)

    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """FastAPI dependency: returns the authenticated User. Raises 401 if invalid."""
    if settings.auth_dev_mode:
        return await _resolve_dev_user(request, db, settings)
    return await _resolve_oauth_user(request, db, settings)


async def get_current_user_from_token(
    token: str | None,
    db: AsyncSession,
    settings: Settings,
) -> User:
    """Resolve a User from a raw bearer token string (no Request object).
    Used by SSE endpoints where EventSource cannot send Authorization headers."""
    if settings.auth_dev_mode:
        # In dev mode there is no real token; accept any non-empty value and
        # resolve the default dev user.
        slug = token or settings.auth_dev_default_user
        if not slug:
            raise HTTPException(status_code=401, detail="No token or dev user provided")
        user = (await db.execute(select(User).where(User.slug == slug))).scalar_one_or_none()
        if user is None:
            user = (
                await db.execute(select(User).where(User.email == slug))
            ).scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=401,
                detail=f"Dev user not found: {slug}. Run seed_dev_users.py first.",
            )
        return user

    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    # Reuse the production introspection path by synthesising a minimal Request.
    # Simpler: inline the same logic as _resolve_oauth_user but accept the raw token.
    now = int(time.time())

    cached = (
        await db.execute(select(OAuthToken).where(OAuthToken.token == token))
    ).scalar_one_or_none()

    if cached:
        if cached.exp <= now:
            await db.delete(cached)
            await db.commit()
            raise HTTPException(status_code=401, detail="Token expired")
        user = (
            await db.execute(select(User).where(User.slug == cached.slug))
        ).scalar_one_or_none()
        if user:
            return user

    try:
        token_info = await _call_introspect(token, settings)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=401, detail=f"Introspection failed: {exc.response.status_code}"
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail=f"OAuth provider unreachable: {exc}") from exc

    if not token_info.get("active"):
        raise HTTPException(status_code=401, detail="Token is inactive")

    exp = token_info.get("exp", 0)
    if exp and exp <= now:
        raise HTTPException(status_code=401, detail="Token expired")

    user = await _get_or_create_user(db, token_info)
    await _cache_token(db, token, token_info)
    return user


async def require_admin_user(user: User) -> User:
    """Raise 403 if ``user`` is not an admin. Non-dependency variant for manual auth."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency: ensures the current user is an admin.
    Always checks is_admin from DB — never from token claims or client headers (CLAUDE.md)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
