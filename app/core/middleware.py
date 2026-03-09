"""
Middleware stack.

Execution order in main.py (outermost → innermost):
  1. request_logging_middleware        — measures total wall-clock time, logs after response
  2. product_identification_middleware — identifies product via X-Product-Client-Key header,
                                         validates Origin, enforces 401/403
  3. rate_limit_middleware             — per-IP sliding-window rate limiter
  4. CORSMiddleware                    — CORS headers (added via app.add_middleware)

All three are plain async middleware functions registered with @app.middleware("http").
They execute in definition order: first defined = outermost.

request.state fields set by this module:
  .product    str | None  — product identifier ("alpha", "taskboard", …) or None
  .user_id    str | None  — UUID string from JWT claims (no DB hit) or None
  .start_time float       — perf_counter value, set by logging middleware

Product identification:
  Every request (except passthrough routes) must carry an X-Product-Client-Key header.
  The middleware looks up this key in the shared.product_clients table to identify
  which product the request belongs to. This prevents clients from self-reporting
  their product identifier.

  In development (ENVIRONMENT=development), localhost origins are always allowed.
"""
import fnmatch
import logging
import time
from typing import Callable, Dict

from fastapi import Request, Response, status
from jose import JWTError

from app.core.config import settings
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared platform prefixes — product check is skipped for these
# ---------------------------------------------------------------------------
_SHARED_PREFIXES = frozenset({
    "/api/auth",
    "/api/users",
    "/api/orgs",
    "/api/billing",
    "/api/notifications",
})

_PASSTHROUGH_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")
_PASSTHROUGH_EXACT = frozenset({"/"})  # exact match only


# ---------------------------------------------------------------------------
# JWT decode helper — no DB, reads claims only
# ---------------------------------------------------------------------------
def _decode_jwt_claims(request: Request) -> dict | None:
    """
    Decode JWT from cookie or Authorization Bearer header.
    Returns payload dict, or None if absent or invalid.
    Never raises — middleware must not break unauthenticated requests.
    """
    token: str | None = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        return None
    try:
        return decode_access_token(token)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_product(path: str) -> str | None:
    """
    Return the product identifier from a path like /api/<product>/...
    Only returns a value if the segment is in settings.products.

    Examples:
      /api/alpha/resources → "alpha"
      /api/taskboard/projects → "taskboard"
      /api/auth/login → None  (in _SHARED_PREFIXES, handled separately)
      /api/unknown/x → None   (not in settings.products)
    """
    parts = path.lstrip("/").split("/")
    # Expect: ["api", "<product>", ...]
    if len(parts) < 2 or parts[0] != "api":
        return None
    candidate = parts[1]
    return candidate if candidate in settings.products else None


def _is_shared_or_passthrough(path: str) -> bool:
    if path.startswith(_PASSTHROUGH_PREFIXES):
        return True
    return any(path.startswith(p) for p in _SHARED_PREFIXES)


# ---------------------------------------------------------------------------
# 1. Request Logging Middleware
# ---------------------------------------------------------------------------
async def request_logging_middleware(request: Request, call_next: Callable) -> Response:
    """
    Outermost middleware — records start time, then logs after the response.

    Log format:
      METHOD /path/... STATUS | product=X user=UUID 12.3ms
    """
    start = time.perf_counter()
    request.state.start_time = start

    response = await call_next(request)

    duration_ms = (time.perf_counter() - start) * 1000
    product = getattr(request.state, "product", None)
    user_id = getattr(request.state, "user_id", None)

    logger.info(
        "%s %s %d | product=%s user=%s %.1fms",
        request.method,
        request.url.path,
        response.status_code,
        product or "-",
        user_id or "anonymous",
        duration_ms,
    )
    return response


# ---------------------------------------------------------------------------
# Helpers — Origin validation
# ---------------------------------------------------------------------------
def _is_origin_allowed(origin: str | None, allowed_origins: list[str]) -> bool:
    """
    Return True if the origin is permitted.
    In development mode, any localhost origin is always allowed.
    Supports wildcard patterns via fnmatch (e.g. "http://localhost:*").
    """
    if settings.environment == "development":
        if not origin:
            return True
        if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
            return True

    if not origin:
        # Non-browser clients (Postman, server-to-server) — allow in dev, check in prod
        return settings.environment == "development"

    return any(fnmatch.fnmatch(origin, pattern) for pattern in allowed_origins)


# ---------------------------------------------------------------------------
# 2. Product Identification Middleware
# ---------------------------------------------------------------------------
async def product_identification_middleware(
    request: Request, call_next: Callable
) -> Response:
    """
    Identifies the product via the X-Product-Client-Key header and validates
    the request Origin against the client's allowed_origins list.

    Sets on request.state:
      .product  — product identifier ("alpha", "taskboard", …) or None
      .user_id  — str(UUID) from JWT, or None

    Rules:
      - Passthrough routes (health, docs): skipped entirely.
      - All other routes: X-Product-Client-Key is required.
          - 401 if header is missing or key is unknown/inactive.
          - 403 if Origin doesn't match allowed_origins (skipped in development).
      - Product-specific routes (/api/<product>/...): additionally validate
          JWT products claim when a token is present.

    Why not enforce JWT here for product routes?
      Unauthenticated requests are handled by get_current_user() on each route.
      This middleware only enforces product-level authorization for authenticated
      users who lack access to the product.
    """
    from app.core.database import AsyncSessionFactory
    from app.shared.repos.product_client_repo import ProductClientRepo

    path = request.url.path

    # Initialize state
    request.state.product = None
    request.state.user_id = None

    # Decode JWT early so user_id is available for logging on all routes
    claims = _decode_jwt_claims(request)
    if claims:
        request.state.user_id = claims.get("sub")

    # Passthrough — skip all checks
    if path in _PASSTHROUGH_EXACT or path.startswith(_PASSTHROUGH_PREFIXES):
        return await call_next(request)

    # --- Client key validation ---
    client_key = request.headers.get("X-Product-Client-Key")
    if not client_key:
        return Response(
            content='{"detail":"Missing X-Product-Client-Key header"}',
            status_code=status.HTTP_401_UNAUTHORIZED,
            media_type="application/json",
        )

    async with AsyncSessionFactory() as session:
        repo = ProductClientRepo(session)
        client = await repo.get_by_client_key(client_key)

    if not client:
        return Response(
            content='{"detail":"Invalid or inactive client key"}',
            status_code=status.HTTP_401_UNAUTHORIZED,
            media_type="application/json",
        )

    # --- Origin validation ---
    origin = request.headers.get("origin")
    if not _is_origin_allowed(origin, client.allowed_origins):
        logger.warning(
            "Origin rejected | key=%s origin=%s allowed=%s",
            client_key[:12],
            origin,
            client.allowed_origins,
        )
        return Response(
            content='{"detail":"Origin not allowed for this client key"}',
            status_code=status.HTTP_403_FORBIDDEN,
            media_type="application/json",
        )

    # Set product from the trusted DB lookup
    request.state.product = client.product

    # --- Product-route JWT claim check ---
    # For /api/<product>/... routes, additionally verify the JWT grants access.
    url_product = _extract_product(path)
    if url_product is not None and claims is not None:
        allowed: list[str] = claims.get("products") or []
        if url_product not in allowed:
            logger.warning(
                "Product access denied | user=%s product=%s allowed=%s",
                claims.get("sub", "?"),
                url_product,
                allowed,
            )
            return Response(
                content='{"detail":"You do not have access to this product"}',
                status_code=status.HTTP_403_FORBIDDEN,
                media_type="application/json",
            )

    return await call_next(request)


# ---------------------------------------------------------------------------
# 3. Rate Limiting Middleware
# ---------------------------------------------------------------------------
class RateLimiter:
    """In-memory sliding-window rate limiter (per client IP + user-agent prefix)."""

    def __init__(self) -> None:
        self.requests: Dict[str, list] = {}
        self._cleanup_interval = 60
        self._last_cleanup = time.time()

    def is_allowed(self, client_id: str, max_requests: int | None = None) -> bool:
        now = time.time()

        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup(now)
            self._last_cleanup = now

        window = self.requests.setdefault(client_id, [])
        self.requests[client_id] = [t for t in window if now - t < 60]

        limit = max_requests or settings.rate_limit_per_minute
        if len(self.requests[client_id]) >= limit:
            return False

        self.requests[client_id].append(now)
        return True

    def _cleanup(self, now: float) -> None:
        stale = [k for k, ts in self.requests.items() if not any(now - t < 120 for t in ts)]
        for k in stale:
            del self.requests[k]


_rate_limiter = RateLimiter()


def _client_id(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")[:50]
    return f"{ip}:{ua}"


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """Per-IP sliding-window rate limiter."""
    cid = _client_id(request)
    if not _rate_limiter.is_allowed(cid):
        logger.warning("Rate limit exceeded: %s", cid)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later.",
        )
    return await call_next(request)
