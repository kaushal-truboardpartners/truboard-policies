"""Auth routes: login redirect, callback, logout.

In dev mode (AUTH_DEV_MODE=true), login/callback are stubs — authentication is handled
by the X-Dev-User header in the middleware. Logout clears the server-side session.
"""

from fastapi import APIRouter, Depends, Response

from auth.middleware import get_current_user
from db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login() -> dict[str, str]:
    """Redirect target for Microsoft login. In dev mode, returns a stub message.
    In production, the frontend handles MSAL login directly — this endpoint exists
    for completeness / backend-initiated flows."""
    return {"message": "Use MSAL on the frontend to authenticate. This is a stub."}


@router.get("/callback")
async def callback() -> dict[str, str]:
    """OAuth callback. In production, the frontend (MSAL) handles the redirect and
    token exchange — the backend only validates JWTs. This endpoint is a stub."""
    return {"message": "OAuth callback stub. Token exchange is handled by MSAL on the frontend."}


@router.post("/logout")
async def logout(
    response: Response,
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Logout: clear server-side session. In production, the frontend also clears
    the MSAL token cache and redirects to the login screen."""
    # Session clearing (chat history) will be wired in M5 when session.py exists.
    return {"message": "Logged out", "user": user.email}
