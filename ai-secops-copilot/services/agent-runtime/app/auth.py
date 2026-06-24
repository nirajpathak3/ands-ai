"""API authentication + tenant resolution (Day 15, ADR-017).

Two credential mechanisms, both verified with the standard library only (no PyJWT
dependency, preserving the offline-first property):

  * **API key** — ``X-API-Key: <key>`` or ``Authorization: Bearer <key>``; the key is
    looked up in ``Settings.api_keys`` to find its tenant.
  * **JWT (HS256)** — ``Authorization: Bearer <jwt>`` signed with ``JWT_SECRET``; the
    ``tenant`` (or ``tid``) claim selects the tenant, ``exp`` is enforced.

When ``AUTH_ENABLED`` is false the runtime is open: a request still selects a tenant via
the ``X-Tenant-Id`` header (so isolation is demoable offline), defaulting to
``Settings.default_tenant``. Tenant ids are constrained to ``[a-z0-9_-]`` so they are safe
to use in filesystem paths (per-tenant SQLite) and metric labels.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass

from .config import Settings

_TENANT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class AuthError(Exception):
    """Raised on an authentication/authorization failure (mapped to HTTP by main)."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class Principal:
    """The authenticated caller: which tenant, by what method."""

    tenant_id: str
    method: str  # "anonymous" | "api_key" | "jwt"
    subject: str  # key fingerprint, JWT sub, or "anonymous"


def _valid_tenant(tenant: str) -> str:
    if not tenant or not _TENANT_RE.match(tenant):
        raise AuthError(400, f"Invalid tenant id: {tenant!r}")
    return tenant


def _b64url_decode(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + pad)
    except (binascii.Error, ValueError) as exc:
        raise AuthError(401, "Malformed token encoding") from exc


def verify_jwt(token: str, secret: str, algorithm: str = "HS256") -> dict:
    """Verify a compact HS256 JWT and return its claims (stdlib only).

    Raises ``AuthError`` on a malformed token, unexpected algorithm, bad signature,
    or an expired ``exp``. Only HS256 is supported by design.
    """
    if algorithm != "HS256":
        raise AuthError(401, f"Unsupported JWT algorithm: {algorithm}")
    if not secret:
        raise AuthError(401, "JWT auth not configured")
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError(401, "Malformed JWT")
    header_b64, payload_b64, sig_b64 = parts

    header = json.loads(_b64url_decode(header_b64) or b"{}")
    if header.get("alg") != "HS256":
        raise AuthError(401, "Unexpected JWT alg header")

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        raise AuthError(401, "Invalid JWT signature")

    try:
        claims = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthError(401, "Malformed JWT payload") from exc
    if not isinstance(claims, dict):
        raise AuthError(401, "Malformed JWT payload")

    exp = claims.get("exp")
    if exp is not None:
        try:
            if time.time() > float(exp):
                raise AuthError(401, "Token expired")
        except (TypeError, ValueError) as exc:
            raise AuthError(401, "Invalid exp claim") from exc
    return claims


def _bearer(headers: Mapping[str, str]) -> str | None:
    value = headers.get("authorization") or headers.get("Authorization")
    if value and value[:7].lower() == "bearer ":
        return value[7:].strip()
    return None


def authenticate(headers: Mapping[str, str], settings: Settings) -> Principal:
    """Resolve the calling principal (tenant + method) from request headers."""
    # Open mode: pick a tenant from the header so isolation is demoable offline.
    if not settings.auth_enabled:
        requested = headers.get("x-tenant-id") or headers.get("X-Tenant-Id")
        tenant = _valid_tenant(requested) if requested else settings.default_tenant
        return Principal(tenant_id=tenant, method="anonymous", subject="anonymous")

    api_keys = settings.api_keys
    bearer = _bearer(headers)

    # 1) API key via X-API-Key or a Bearer token that matches a configured key.
    candidate = headers.get("x-api-key") or headers.get("X-API-Key") or bearer
    if candidate and candidate in api_keys:
        fingerprint = hashlib.sha256(candidate.encode("utf-8")).hexdigest()[:12]
        return Principal(
            tenant_id=_valid_tenant(api_keys[candidate]),
            method="api_key",
            subject=f"key:{fingerprint}",
        )

    # 2) JWT bearer (HS256) with a tenant claim.
    if bearer and settings.jwt_secret:
        claims = verify_jwt(bearer, settings.jwt_secret, settings.jwt_algorithm)
        tenant = claims.get("tenant") or claims.get("tid")
        if not tenant:
            raise AuthError(403, "JWT missing tenant claim")
        return Principal(
            tenant_id=_valid_tenant(str(tenant)),
            method="jwt",
            subject=str(claims.get("sub", "jwt")),
        )

    raise AuthError(401, "Missing or invalid credentials")
