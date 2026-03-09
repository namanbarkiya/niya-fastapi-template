"""
Middleware stack.

Execution order in main.py (outermost → innermost):
  1. request_logging_middleware     — measures total wall-clock time, logs after response
  2. product_identification_middleware — sets request.state.product/.user_id, enforces 403
  3. rate_limit_middleware           — per-IP sliding-window rate limiter
  4. CORSMiddleware                  — CORS headers (added via app.add_middleware)

All three are plain async middleware functions registered with @app.middleware("http").
They execute in definition order: first defined = outermost.

request.state fields set by this module:
  .product    str | None  — product identifier ("alpha", "taskboard", …) or None
  .user_id    str | None  — UUID string from JWT claims (no DB hit) or None
  .start_time float       — perf_counter value, set by logging middleware
"""
import logging
import time
from typing import Callable, Dict

from fastapi import HTTPException, Request, Response, status
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

_PASSTHROUGH_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json", "/")


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
# 2. Product Identification Middleware
# ---------------------------------------------------------------------------
async def product_identification_middleware(
    request: Request, call_next: Callable
) -> Response:
    """
    Identifies the product being accessed and validates JWT product claims.

    Sets on request.state:
      .product  — product identifier ("alpha", "taskboard", …) or None
      .user_id  — str(UUID) from JWT, or None

    Access check logic:
      - If the path targets a known product (/api/<product>/...):
          - Decode JWT (no DB hit)
          - If JWT present AND valid:
              - Check payload["products"] includes the product
              - If not → 403 Forbidden
      - Shared platform routes (/api/auth/*, /api/billing/*, etc.) are skipped
      - If no JWT is present on a product route, pass through —
        get_current_user() will return 401 as appropriate

    Why not 401 here?
      This middleware only enforces product-level authorization for users
      who ARE authenticated but lack access. Unauthenticated requests are
      handled by the get_current_user dependency on each route.
    """
    path = request.url.path

    # Initialize state
    request.state.product = None
    request.state.user_id = None

    # Decode JWT early so user_id is available for logging on all routes
    claims = _decode_jwt_claims(request)
    if claims:
        request.state.user_id = claims.get("sub")

    # Skip check for non-product routes
    if _is_shared_or_passthrough(path):
        return await call_next(request)

    # Identify product from URL segment
    product = _extract_product(path)
    request.state.product = product

    if product is None:
        # Unknown /api/<segment>/ — not a registered product, pass through
        return await call_next(request)

    # Validate product access claim when a token is present
    if claims is not None:
        allowed: list[str] = claims.get("products") or []
        if product not in allowed:
            logger.warning(
                "Product access denied | user=%s product=%s allowed=%s",
                claims.get("sub", "?"),
                product,
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
