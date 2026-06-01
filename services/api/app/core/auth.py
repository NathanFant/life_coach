"""
Clerk JWT authentication — the swap seam for auth providers.

Public API:
  AuthError      — raised on any authentication failure
  JWKSClient     — fetches and caches Clerk's JSON Web Key Set
  decode_clerk_jwt — pure-function JWT verification (testable without HTTP)
  get_current_user — FastAPI dependency → CurrentUser

Architecture note (docs/DESIGN.md §7.3):
  Everything downstream of get_current_user depends only on CurrentUser, not on
  Clerk.  Swapping to WorkOS/self-hosted means replacing this file and updating
  the JWKS URL — nothing else changes.

JWKS caching:
  Keys are cached in memory with a configurable TTL (default 1 hour).  On a
  cache miss or kid-not-found the client re-fetches to handle key rotation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import ExpiredSignatureError, JWTError
from jose import jwt as jose_jwt

from app.core.config import get_settings

_settings = get_settings()


# ─── Exceptions ────────────────────────────────────────────────────────────────


class AuthError(Exception):
    """Raised when a JWT cannot be verified for any reason."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ─── CurrentUser dataclass ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class CurrentUser:
    """Resolved, verified identity.  The only auth type the rest of the app sees."""

    external_auth_id: str  # Clerk subject (sub)
    email: str
    email_verified: bool


# ─── JWKS client ───────────────────────────────────────────────────────────────


class JWKSClient:
    """
    Fetches and caches the Clerk JWKS document.

    Keys are indexed by kid.  On a cache miss or unknown kid, the document is
    re-fetched once — this handles Clerk's key-rotation events transparently.
    """

    def __init__(self, jwks_url: str, ttl_seconds: int = 3600) -> None:
        self._url = jwks_url
        self._ttl = ttl_seconds
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at: float = 0.0

    def _is_stale(self) -> bool:
        return time.monotonic() - self._fetched_at > self._ttl

    def _fetch(self) -> None:
        try:
            resp = httpx.get(self._url, timeout=5.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AuthError(f"JWKS fetch failed: {exc}") from exc

        data = resp.json()
        self._keys = {k["kid"]: k for k in data.get("keys", [])}
        self._fetched_at = time.monotonic()

    def get_key(self, kid: str) -> dict[str, Any]:
        """Return the JWK for the given kid, re-fetching if stale or missing."""
        if self._is_stale() or kid not in self._keys:
            self._fetch()
        if kid not in self._keys:
            raise AuthError(f"Unknown kid: {kid!r}")
        return self._keys[kid]


# Module-level singleton — shared across requests within one worker process.
_jwks_client: JWKSClient | None = None


def _get_jwks_client() -> JWKSClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = JWKSClient(jwks_url=_settings.clerk_jwks_url)
    return _jwks_client


# ─── JWT verification ──────────────────────────────────────────────────────────


def decode_clerk_jwt(
    token: str,
    *,
    jwks: dict[str, Any] | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    jwks_client: JWKSClient | None = None,
) -> dict[str, Any]:
    """
    Verify a Clerk JWT and return the decoded payload.

    Accepts an explicit `jwks` dict for unit testing (no network call).
    In production, pass `jwks_client` or leave both None to use the module
    singleton that fetches from CLERK_JWKS_URL.

    Raises AuthError on any verification failure (expired, bad sig, wrong iss, etc.).
    """
    iss = issuer or _settings.clerk_issuer
    aud = audience  # None → skip audience check (Clerk tokens may omit aud)

    try:
        # Peek at the header to find the kid
        unverified_header = jose_jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthError(f"Invalid JWT header: {exc}") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise AuthError("JWT missing kid header")

    # Resolve the public key
    if jwks is not None:
        keys_by_kid = {k["kid"]: k for k in jwks.get("keys", [])}
        if kid not in keys_by_kid:
            raise AuthError(f"Unknown kid: {kid!r}")
        public_key: Any = keys_by_kid[kid]
    else:
        client = jwks_client or _get_jwks_client()
        public_key = client.get_key(kid)

    # Verify signature, expiry, and issuer
    try:
        options: dict[str, Any] = {"verify_aud": aud is not None}
        payload: dict[str, Any] = jose_jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=iss,
            audience=aud,
            options=options,
        )
    except ExpiredSignatureError as exc:
        raise AuthError("JWT expired") from exc
    except JWTError as exc:
        # jose raises JWTError for bad signature AND wrong issuer;
        # inspect the message to give callers a more specific error.
        msg = str(exc).lower()
        if "issuer" in msg:
            raise AuthError(f"Invalid issuer: {exc}") from exc
        raise AuthError(f"JWT verification failed: {exc}") from exc

    return payload


# ─── FastAPI dependency ──────────────────────────────────────────────────────────


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> CurrentUser:
    """
    FastAPI dependency.  Validates the Bearer JWT and returns a CurrentUser.

    Raises HTTP 401 on any auth failure, 503 if the JWKS endpoint is unreachable.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len("Bearer ") :].strip()

    try:
        payload = decode_clerk_jwt(token)
    except AuthError as exc:
        msg = exc.message.lower()
        if "fetch failed" in msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service temporarily unavailable",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {exc.message}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    sub = payload.get("sub")
    email = payload.get("email", "")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing sub claim",
        )

    return CurrentUser(
        external_auth_id=sub,
        email=email,
        email_verified=payload.get("email_verified", False),
    )


CurrentUserDep = Depends(get_current_user)
