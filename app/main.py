"""
FastAPI application — multi-product backend.

Mounts shared auth/user routes and product routers.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.config import settings
from app.core.database import check_db_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import (
    product_identification_middleware,
    rate_limit_middleware,
    request_logging_middleware,
)
from app.shared.routes.auth import router as auth_router
from app.shared.routes.users import router as users_router
from app.shared.routes.orgs import router as orgs_router
from app.shared.routes.billing import router as billing_router
from app.shared.routes.notifications import router as notifications_router
from app.shared.routes.admin import router as admin_router
# Register all ORM models on Base.metadata BEFORE the app variable is created.
# These imports MUST come before `app = FastAPI(...)` — if they appear after,
# `import app.xxx` rebinds the local name `app` to the package, overwriting the
# FastAPI instance and causing AttributeError on the first app.include_router call.
import app.shared.models  # noqa: F401
import app.products.product_alpha.models  # noqa: F401
import app.products.taskboard.models  # noqa: F401

from app.products.product_alpha.routes.router import router as alpha_router
from app.products.taskboard.routes.router import router as taskboard_router

setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    healthy = await check_db_connection()
    if healthy:
        logger.info("Database connection: OK")
    else:
        logger.error("Database connection: FAILED — check DATABASE_URL")
    yield
    logger.info("Shutting down API")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    description="Multi-product FastAPI backend with schema-per-product architecture",
    version="3.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware stack
# ---------------------------------------------------------------------------
# @app.middleware("http") decorators execute in definition order: first = outermost.
#
# Execution order (outermost → innermost):
#   1. request_logging_middleware        — logs method/path/status/product/user/ms
#   2. product_identification_middleware — sets request.state.product, enforces 403
#   3. rate_limit_middleware             — per-IP sliding window (429)
#   4. CORSMiddleware                    — CORS response headers (added last = innermost)

# 1. Outermost — must be first so it wraps everything and captures total time
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    return await request_logging_middleware(request, call_next)


# 2. Product identification and access enforcement
@app.middleware("http")
async def product_middleware(request: Request, call_next):
    return await product_identification_middleware(request, call_next)


# 3. Rate limiting
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    return await rate_limit_middleware(request, call_next)


# 4. CORS — add_middleware is LIFO relative to @app.middleware, so this is innermost
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
register_exception_handlers(app)

# ---------------------------------------------------------------------------
# Shared routes
# ---------------------------------------------------------------------------
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(orgs_router, prefix="/api/orgs", tags=["orgs"])
app.include_router(billing_router, prefix="/api/billing", tags=["billing"])
app.include_router(notifications_router, prefix="/api/notifications", tags=["notifications"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Product routers
# ---------------------------------------------------------------------------
app.include_router(alpha_router, prefix="/api/alpha", tags=["product_alpha"])
app.include_router(taskboard_router, prefix="/api/taskboard", tags=["taskboard"])

# Add new products below following the same pattern:
# from app.products.product_name.routes.router import router as product_name_router
# app.include_router(product_name_router, prefix="/api/product_name", tags=["product_name"])


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "products": settings.products,
        "version": "3.0.0",
    }


ROOT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Niya FastAPI</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #0f172a; --card: rgba(30,41,59,.7); --text: #f8fafc; --muted: #94a3b8; --accent: #3b82f6; --green: #10b981; }
        * { margin:0; padding:0; box-sizing:border-box; font-family:'Outfit',sans-serif; }
        body { background:var(--bg); color:var(--text); min-height:100vh; display:flex; justify-content:center; align-items:center; overflow:hidden; }
        .blob { position:absolute; border-radius:50%; filter:blur(80px); animation:move 10s infinite alternate; }
        .b1 { width:400px;height:400px;background:rgba(59,130,246,.3);top:-100px;left:-100px; }
        .b2 { width:300px;height:300px;background:rgba(139,92,246,.3);bottom:-50px;right:-50px;animation-delay:-5s; }
        @keyframes move { 100% { transform:translate(50px,50px) scale(1.1); } }
        .box { background:var(--card);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,.1);border-radius:24px;padding:3rem;width:90%;max-width:600px;position:relative;z-index:1;box-shadow:0 25px 50px -12px rgba(0,0,0,.5); }
        h1 { font-size:3rem;font-weight:700;background:linear-gradient(135deg,#60a5fa,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent; }
        .sub { color:var(--muted);font-size:1.1rem;font-weight:300;margin-top:.25rem; }
        .badge { display:inline-flex;align-items:center;gap:.5rem;background:rgba(16,185,129,.1);color:var(--green);padding:.5rem 1rem;border-radius:9999px;font-size:.875rem;font-weight:600;margin-top:1rem;border:1px solid rgba(16,185,129,.2); }
        .dot { width:8px;height:8px;border-radius:50%;background:var(--green);animation:pulse 2s infinite; }
        @keyframes pulse { 70%{box-shadow:0 0 0 10px rgba(16,185,129,0);} 100%{box-shadow:0 0 0 0 rgba(16,185,129,0);} }
        .grid { display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:2rem; }
        a.card { display:flex;flex-direction:column;gap:.5rem;padding:1.5rem;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.05);border-radius:16px;text-decoration:none;color:var(--text);transition:all .3s; }
        a.card:hover { background:rgba(255,255,255,.08);transform:translateY(-4px); }
        .ct { font-weight:600;font-size:1.1rem; }
        .cd { color:var(--muted);font-size:.875rem; }
        footer { margin-top:2rem;text-align:center;color:var(--muted);font-size:.875rem; }
    </style>
</head>
<body>
    <div class="blob b1"></div><div class="blob b2"></div>
    <div class="box">
        <h1>Niya API</h1>
        <p class="sub">Multi-Product Backend — Schema-per-Product Architecture</p>
        <div class="badge"><div class="dot"></div>System Operational &bull; v3.0.0</div>
        <div class="grid">
            <a href="/docs" class="card"><span class="ct">Swagger UI</span><span class="cd">Interactive API docs &amp; testing.</span></a>
            <a href="/redoc" class="card"><span class="ct">ReDoc</span><span class="cd">Clean, detailed API reference.</span></a>
            <a href="/health" class="card"><span class="ct">Health Check</span><span class="cd">Database &amp; system status.</span></a>
            <a href="/api/auth/signin" class="card"><span class="ct">Auth API</span><span class="cd">Sign in, sign up, refresh.</span></a>
        </div>
        <footer>Built with FastAPI &amp; PostgreSQL</footer>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content=ROOT_HTML)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
