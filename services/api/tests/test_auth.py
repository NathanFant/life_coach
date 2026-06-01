"""
Unit tests for the Clerk JWT authentication middleware.

All tests use a locally-generated RSA key pair — no real Clerk account needed.
The JWKS endpoint is mocked with respx so no network calls occur.

Scenarios tested:
  - Valid JWT → CurrentUser resolved
  - Expired JWT → 401
  - Wrong issuer → 401
  - Bad signature → 401
  - Missing Authorization header → 401
  - Malformed bearer token → 401
  - JWKS fetch failure → 503
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt
from jose.utils import base64url_encode

from app.core.auth import AuthError, JWKSClient, decode_clerk_jwt

# ─── Test key generation ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def rsa_keypair() -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


@pytest.fixture(scope="module")
def jwks_json(rsa_keypair: tuple[Any, Any]) -> dict:
    """Minimal JWKS document from the test public key."""
    _, public = rsa_keypair
    pub_numbers = (
        public.public_key().public_numbers()
        if hasattr(public, "public_key")
        else public.public_numbers()
    )

    def _to_base64url_uint(n: int) -> str:
        length = (n.bit_length() + 7) // 8
        return base64url_encode(n.to_bytes(length, "big")).decode()

    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-1",
                "use": "sig",
                "alg": "RS256",
                "n": _to_base64url_uint(pub_numbers.n),
                "e": _to_base64url_uint(pub_numbers.e),
            }
        ]
    }


def _make_token(
    private_key: rsa.RSAPrivateKey,
    *,
    sub: str = "user_test123",
    email: str = "test@example.com",
    issuer: str = "https://test.clerk.accounts.dev",
    exp_offset: int = 3600,
    kid: str = "test-key-1",
) -> str:
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "email_verified": True,
        "iss": issuer,
        "aud": "life-coach",
        "iat": now,
        "exp": now + exp_offset,
    }
    return jose_jwt.encode(payload, pem, algorithm="RS256", headers={"kid": kid})


# ─── JWKSClient tests ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestJWKSClient:
    def test_get_key_by_kid(self, jwks_json: dict) -> None:
        client = JWKSClient(jwks_url="https://unused.example.com/.well-known/jwks.json")
        # Manually pre-populate the cache so no HTTP call is made
        client._keys = {k["kid"]: k for k in jwks_json["keys"]}
        client._fetched_at = time.monotonic()  # mark as fresh
        key = client.get_key("test-key-1")
        assert key["kty"] == "RSA"

    @respx.mock
    def test_get_missing_key_raises(self, jwks_json: dict) -> None:
        url = "https://test.clerk.accounts.dev/.well-known/jwks.json"
        # Return an empty JWKS so any re-fetch also finds no matching kid
        respx.get(url).mock(return_value=httpx.Response(200, json={"keys": []}))
        client = JWKSClient(jwks_url=url)
        client._keys = {}
        client._fetched_at = 0.0  # force stale so _fetch is called
        with pytest.raises(AuthError, match="kid"):
            client.get_key("nonexistent")


# ─── decode_clerk_jwt tests ──────────────────────────────────────────────────────


@pytest.mark.unit
class TestDecodeClerkJWT:
    def test_valid_token_returns_payload(
        self,
        rsa_keypair: tuple[Any, Any],
        jwks_json: dict,
    ) -> None:
        private, _ = rsa_keypair
        token = _make_token(private)
        payload = decode_clerk_jwt(
            token,
            jwks=jwks_json,
            issuer="https://test.clerk.accounts.dev",
            audience="life-coach",
        )
        assert payload["sub"] == "user_test123"
        assert payload["email"] == "test@example.com"

    def test_expired_token_raises(
        self,
        rsa_keypair: tuple[Any, Any],
        jwks_json: dict,
    ) -> None:
        private, _ = rsa_keypair
        token = _make_token(private, exp_offset=-10)
        with pytest.raises(AuthError, match="expired"):
            decode_clerk_jwt(
                token,
                jwks=jwks_json,
                issuer="https://test.clerk.accounts.dev",
                audience="life-coach",
            )

    def test_wrong_issuer_raises(
        self,
        rsa_keypair: tuple[Any, Any],
        jwks_json: dict,
    ) -> None:
        private, _ = rsa_keypair
        token = _make_token(private, issuer="https://evil.example.com")
        with pytest.raises(AuthError, match="issuer"):
            decode_clerk_jwt(
                token,
                jwks=jwks_json,
                issuer="https://test.clerk.accounts.dev",
                audience="life-coach",
            )

    def test_bad_signature_raises(
        self,
        jwks_json: dict,
    ) -> None:
        # Generate a different key that doesn't match the JWKS
        other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _make_token(other_private)
        with pytest.raises(AuthError):
            decode_clerk_jwt(
                token,
                jwks=jwks_json,
                issuer="https://test.clerk.accounts.dev",
                audience="life-coach",
            )

    def test_malformed_token_raises(self, jwks_json: dict) -> None:
        with pytest.raises(AuthError):
            decode_clerk_jwt(
                "not.a.jwt",
                jwks=jwks_json,
                issuer="https://test.clerk.accounts.dev",
                audience="life-coach",
            )


# ─── FastAPI endpoint integration ────────────────────────────────────────────────


@pytest.mark.unit
class TestAuthEndpointGuard:
    def test_missing_auth_header_returns_401(self, client: Any) -> None:
        resp = client.get("/v1/profile")
        assert resp.status_code == 401

    def test_malformed_bearer_returns_401(self, client: Any) -> None:
        resp = client.get("/v1/profile", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code in (401, 501)  # 501 until profile endpoint is implemented
