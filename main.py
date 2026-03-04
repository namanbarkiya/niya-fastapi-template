from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

import logging

from config.database import check_db_connection
from config.settings import settings
from controller.user import auth_router, users_router
from core.exceptions import BaseAPIException
from core.logging import setup_logging
from middleware.rate_limit import rate_limit_middleware

setup_logging()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    healthy = await check_db_connection()
    if healthy:
        logger.info("Database connection: OK")
    else:
        logger.error("Database connection: FAILED — check DATABASE_URL")
    yield
    # Shutdown (nothing to do for now)
    logger.info("Shutting down API")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.app_name,
    description="Niya FastAPI Template — production-ready SaaS backend with PostgreSQL auth",
    version="2.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    return await rate_limit_middleware(request, call_next)


# Routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException):
    logger.error(f"API Exception [{exc.status_code}]: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "unreachable",
        "version": "2.0.0",
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
        <p class="sub">Production-ready SaaS Backend — PostgreSQL + JWT</p>
        <div class="badge"><div class="dot"></div>System Operational &bull; v2.0.0</div>
        <div class="grid">
            <a href="/docs" class="card"><span class="ct">Swagger UI</span><span class="cd">Interactive API docs &amp; testing.</span></a>
            <a href="/redoc" class="card"><span class="ct">ReDoc</span><span class="cd">Clean, detailed API reference.</span></a>
            <a href="/health" class="card"><span class="ct">Health Check</span><span class="cd">Database &amp; system status.</span></a>
            <a href="/api/v1/auth/signin" class="card"><span class="ct">Auth API</span><span class="cd">Sign in, sign up, refresh.</span></a>
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
