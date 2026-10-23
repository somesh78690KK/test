"""T.A.R.O. - WebSocket authentication and request origin guard (TASK-081).

ARCHITECTURE reference: section 24 & 27.
RULES reference: section 15.
TASKS: TASK-081.

Security rules:
1. Token generated per session (never exposed in URL, passed via PyWebView bridge or first message).
2. First message must be {"type": "auth", "token": "..."} received within 2 seconds.
3. Host header must match 127.0.0.1 or localhost (DNS rebinding prevention).
4. Origin header must match local server origin or null (local file / webview).
"""

from __future__ import annotations

import hmac
import secrets
from typing import Any
from urllib.parse import urlparse

from core.log.setup import get_logger

logger = get_logger(__name__)

# Allowed host names (without port)
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


class SessionAuthManager:
    """Manages session tokens and validates incoming connections and auth messages."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or secrets.token_hex(32)
        self._authenticated_clients: set[str] = set()

    def regenerate_token(self) -> str:
        """Generate a fresh session token."""
        self.token = secrets.token_hex(32)
        self._authenticated_clients.clear()
        return self.token

    def validate_token(self, provided_token: str) -> bool:
        """Constant-time token comparison."""
        if not provided_token or not self.token:
            return False
        return hmac.compare_digest(provided_token.strip(), self.token.strip())

    def validate_host(self, host_header: str | None) -> bool:
        """Verify Host header is strictly 127.0.0.1 or localhost."""
        if not host_header:
            return False
        host = host_header.split(":")[0].strip().lower()
        return host in ALLOWED_HOSTS

    def validate_origin(self, origin_header: str | None, expected_port: int | None = None) -> bool:
        """Verify Origin header to prevent cross-site hijacking."""
        if not origin_header:
            # Native webview / file / local requests often have null or empty origin
            return True

        origin = origin_header.strip().lower()
        if origin in ("null", "file://"):
            return True

        try:
            parsed = urlparse(origin)
            hostname = parsed.hostname or ""
            if hostname not in ALLOWED_HOSTS:
                return False
            if expected_port and parsed.port and parsed.port != expected_port:
                return False
            return True
        except Exception:
            return False

    def mark_client_authenticated(self, client_id: str) -> None:
        self._authenticated_clients.add(client_id)

    def is_client_authenticated(self, client_id: str) -> bool:
        return client_id in self._authenticated_clients

    def remove_client(self, client_id: str) -> None:
        self._authenticated_clients.discard(client_id)
