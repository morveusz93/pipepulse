from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from pipepulse.auth import (
    SESSION_COOKIE,
    SettingsDep,
    admin_configured,
    check_password,
    create_session,
    login_limiter,
    reject_in_demo_mode,
    verify_session,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


class AuthState(BaseModel):
    demo_mode: bool
    # False when admin password or encryption key is missing — the UI can explain how to enable it.
    admin_enabled: bool
    authenticated: bool


@router.get("/me")
async def me(request: Request, settings: SettingsDep) -> AuthState:
    admin_enabled = admin_configured(settings)
    return AuthState(
        demo_mode=settings.demo_mode,
        admin_enabled=admin_enabled,
        authenticated=admin_enabled
        and verify_session(settings, request.cookies.get(SESSION_COOKIE)),
    )


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(
    body: LoginRequest, request: Request, response: Response, settings: SettingsDep
) -> None:
    reject_in_demo_mode(settings)
    if not admin_configured(settings):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Admin login is not configured: "
            "set PIPEPULSE_ADMIN_PASSWORD and PIPEPULSE_ENCRYPTION_KEY",
        )
    client = request.client.host if request.client else "unknown"
    if login_limiter.is_blocked(client):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts, try again later"
        )
    if not check_password(settings, body.password):
        login_limiter.record_failure(client)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid password")

    login_limiter.reset(client)
    response.set_cookie(
        SESSION_COOKIE,
        create_session(settings),
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, settings: SettingsDep) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path="/api", httponly=True, secure=settings.cookie_secure, samesite="strict"
    )
