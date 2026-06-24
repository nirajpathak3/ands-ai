"""Day 15: API auth, JWT, per-tenant isolation, and rate limiting."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.auth import AuthError, Principal, authenticate, verify_jwt
from app.config import Settings, get_settings
from app.main import app
from app.ratelimit import RateLimiter, get_rate_limiter

client = TestClient(app)

_CRITICAL = {
    "id": "F-TEN-1", "ruleId": "formatted-sql-query", "title": "SQLi",
    "message": "user input in SQL", "file": "app/api/users.py", "startLine": 42,
    "cwe": "CWE-89", "scannerSeverity": "ERROR",
    "codeSnippet": "q = '...' + request.args['name']; cursor.execute(q)",
}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def make_jwt(claims: dict, secret: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    sig = _b64url(hmac.new(secret.encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


# --- pure unit tests: verify_jwt -------------------------------------------

def test_verify_jwt_roundtrip():
    token = make_jwt({"tenant": "acme", "sub": "alice"}, "s3cret")
    claims = verify_jwt(token, "s3cret")
    assert claims["tenant"] == "acme"
    assert claims["sub"] == "alice"


def test_verify_jwt_bad_signature():
    token = make_jwt({"tenant": "acme"}, "s3cret")
    with pytest.raises(AuthError):
        verify_jwt(token, "wrong-secret")


def test_verify_jwt_expired():
    token = make_jwt({"tenant": "acme", "exp": time.time() - 10}, "s3cret")
    with pytest.raises(AuthError):
        verify_jwt(token, "s3cret")


def test_verify_jwt_malformed():
    with pytest.raises(AuthError):
        verify_jwt("not-a-jwt", "s3cret")


# --- pure unit tests: authenticate -----------------------------------------

def test_authenticate_open_mode_uses_header_tenant():
    s = Settings(auth_enabled=False, default_tenant="public")
    p = authenticate({"x-tenant-id": "team-a"}, s)
    assert p == Principal(tenant_id="team-a", method="anonymous", subject="anonymous")


def test_authenticate_open_mode_defaults_tenant():
    s = Settings(auth_enabled=False, default_tenant="public")
    assert authenticate({}, s).tenant_id == "public"


def test_authenticate_rejects_bad_tenant_header():
    s = Settings(auth_enabled=False)
    with pytest.raises(AuthError):
        authenticate({"x-tenant-id": "bad tenant!"}, s)


def test_authenticate_api_key_maps_to_tenant():
    s = Settings(auth_enabled=True, api_keys_raw="keyA:acme,keyB:globex")
    assert authenticate({"x-api-key": "keyA"}, s).tenant_id == "acme"
    assert authenticate({"authorization": "Bearer keyB"}, s).tenant_id == "globex"


def test_authenticate_jwt_tenant_claim():
    s = Settings(auth_enabled=True, jwt_secret="s3cret")
    token = make_jwt({"tenant": "delta", "sub": "bob"}, "s3cret")
    p = authenticate({"authorization": f"Bearer {token}"}, s)
    assert p.tenant_id == "delta"
    assert p.method == "jwt"


def test_authenticate_missing_credentials():
    s = Settings(auth_enabled=True, api_keys_raw="keyA:acme")
    with pytest.raises(AuthError) as exc:
        authenticate({}, s)
    assert exc.value.status_code == 401


# --- pure unit tests: RateLimiter ------------------------------------------

def test_rate_limiter_allows_then_blocks():
    rl = RateLimiter()
    now = 1000.0
    assert rl.check("t", 2, now=now).allowed
    assert rl.check("t", 2, now=now).allowed
    blocked = rl.check("t", 2, now=now)
    assert not blocked.allowed
    assert blocked.retry_after_s > 0


def test_rate_limiter_window_resets():
    rl = RateLimiter()
    assert rl.check("t", 1, now=0.0).allowed
    assert not rl.check("t", 1, now=1.0).allowed
    assert rl.check("t", 1, now=61.0).allowed  # window rolled over


def test_rate_limiter_disabled_when_zero():
    rl = RateLimiter()
    for _ in range(100):
        assert rl.check("t", 0).allowed


# --- API: open-mode tenant isolation (no auth) -----------------------------

def test_header_tenant_isolation_without_auth():
    """Two tenants seeded via X-Tenant-Id never see each other's findings."""
    client.post("/demo/reset", headers={"X-Tenant-Id": "iso-a"})
    client.post("/demo/reset", headers={"X-Tenant-Id": "iso-b"})

    client.post("/analyze", json={"finding": _CRITICAL}, headers={"X-Tenant-Id": "iso-a"})

    a = client.get("/findings", headers={"X-Tenant-Id": "iso-a"}).json()
    b = client.get("/findings", headers={"X-Tenant-Id": "iso-b"}).json()
    assert a["count"] >= 1
    assert b["count"] == 0


# --- API: auth enforcement (dependency override) ---------------------------

@pytest.fixture
def auth_on():
    """Enable auth for the app via dependency override; reset the limiter after."""
    def _settings() -> Settings:
        return Settings(
            auth_enabled=True,
            api_keys_raw="keyA:acme,keyB:globex",
            jwt_secret="s3cret",
            rate_limit_rpm=0,
        )

    app.dependency_overrides[get_settings] = _settings
    get_rate_limiter().clear()
    try:
        yield _settings
    finally:
        app.dependency_overrides.clear()
        get_rate_limiter().clear()


def test_protected_endpoint_requires_credentials(auth_on):
    assert client.get("/metrics").status_code == 401


def test_api_key_grants_access(auth_on):
    res = client.get("/metrics", headers={"X-API-Key": "keyA"})
    assert res.status_code == 200


def test_jwt_grants_access(auth_on):
    token = make_jwt({"tenant": "acme", "sub": "alice"}, "s3cret")
    res = client.get("/metrics", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200


def test_health_open_without_auth(auth_on):
    """Liveness must not require credentials even when auth is enabled."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "tenancy" in body


def test_authenticated_tenant_isolation(auth_on):
    client.post("/demo/reset", headers={"X-API-Key": "keyA"})
    client.post("/demo/reset", headers={"X-API-Key": "keyB"})
    client.post("/demo/seed", headers={"X-API-Key": "keyA"})

    acme = client.get("/findings", headers={"X-API-Key": "keyA"}).json()
    globex = client.get("/findings", headers={"X-API-Key": "keyB"}).json()
    assert acme["count"] >= 1
    assert globex["count"] == 0


# --- API: rate limiting -----------------------------------------------------

def test_rate_limit_returns_429():
    def _settings() -> Settings:
        return Settings(
            auth_enabled=True, api_keys_raw="rlkey:rltenant", rate_limit_rpm=3
        )

    app.dependency_overrides[get_settings] = _settings
    get_rate_limiter().clear()
    try:
        headers = {"X-API-Key": "rlkey"}
        codes = [client.get("/metrics", headers=headers).status_code for _ in range(4)]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429
        blocked = client.get("/metrics", headers=headers)
        assert "retry-after" in {k.lower() for k in blocked.headers}
    finally:
        app.dependency_overrides.clear()
        get_rate_limiter().clear()
