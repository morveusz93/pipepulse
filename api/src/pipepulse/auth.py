"""Admin authentication for self-hosted mode.

One admin password from PIPEPULSE_ADMIN_PASSWORD. A successful login sets a signed, HttpOnly,
SameSite=Strict session cookie. SameSite=Strict plus JSON-only endpoints is the CSRF defense.

The signing key is derived from the encryption key, not the password: a leaked cookie must not
allow offline brute-forcing of the admin password.
"""

import hashlib
import hmac
import time
from collections import defaultdict, deque
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from pipepulse.config import Settings, get_settings
from pipepulse.crypto import EncryptionKeyMissingError

SESSION_COOKIE = "pipepulse_session"
_SESSION_CONTEXT = b"pipepulse-session-v1"


def admin_configured(settings: Settings) -> bool:
    """Admin login needs both a password and the encryption key (sessions are signed with it)."""
    password = settings.admin_password.get_secret_value() if settings.admin_password else ""
    key = settings.encryption_key.get_secret_value().strip() if settings.encryption_key else ""
    return not settings.demo_mode and bool(password) and bool(key)


def _signing_key(settings: Settings) -> bytes:
    key = settings.encryption_key.get_secret_value().strip() if settings.encryption_key else ""
    if not key:
        raise EncryptionKeyMissingError("PIPEPULSE_ENCRYPTION_KEY is required for admin sessions")
    primary = key.split(",")[0].strip()
    return hmac.new(primary.encode(), _SESSION_CONTEXT, hashlib.sha256).digest()


def _sign(settings: Settings, expires_at: int) -> str:
    return hmac.new(_signing_key(settings), str(expires_at).encode(), hashlib.sha256).hexdigest()


def create_session(settings: Settings, now: float | None = None) -> str:
    expires_at = int((now or time.time()) + settings.session_ttl_hours * 3600)
    return f"{expires_at}.{_sign(settings, expires_at)}"


def verify_session(settings: Settings, token: str | None, now: float | None = None) -> bool:
    if not token or "." not in token:
        return False
    expires_raw, signature = token.split(".", 1)
    if not expires_raw.isdigit():
        return False
    expires_at = int(expires_raw)
    if expires_at < (now or time.time()):
        return False
    return hmac.compare_digest(signature, _sign(settings, expires_at))


def check_password(settings: Settings, candidate: str) -> bool:
    if not admin_configured(settings):
        return False
    expected = settings.admin_password.get_secret_value()  # type: ignore[union-attr]
    return hmac.compare_digest(candidate.encode(), expected.encode())


class LoginLimiter:
    """Per-client failed-login throttle. In-memory: fine for the single API replica we run."""

    def __init__(self, max_failures: int = 5, window_s: float = 900) -> None:
        self.max_failures = max_failures
        self.window_s = window_s
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, client: str, now: float) -> deque[float]:
        failures = self._failures[client]
        while failures and failures[0] <= now - self.window_s:
            failures.popleft()
        return failures

    def is_blocked(self, client: str, now: float | None = None) -> bool:
        return len(self._recent(client, now or time.time())) >= self.max_failures

    def record_failure(self, client: str, now: float | None = None) -> None:
        self._recent(client, now or time.time()).append(now or time.time())

    def reset(self, client: str | None = None) -> None:
        if client is None:
            self._failures.clear()
        else:
            self._failures.pop(client, None)


login_limiter = LoginLimiter()

SettingsDep = Annotated[Settings, Depends(get_settings)]


def reject_in_demo_mode(settings: SettingsDep) -> None:
    if settings.demo_mode:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Managing GitLab connections is disabled in demo mode"
        )


def require_admin(request: Request, settings: SettingsDep) -> None:
    reject_in_demo_mode(settings)
    if not admin_configured(settings) or not verify_session(
        settings, request.cookies.get(SESSION_COOKIE)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")


AdminDep = Annotated[None, Depends(require_admin)]
