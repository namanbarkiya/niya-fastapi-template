from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
import logging
from controller.user import router
from config.settings import settings
from core.exceptions import BaseAPIException
from core.logging import setup_logging
from middleware.rate_limit import rate_limit_middleware

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Niya FastAPI Template - Production-ready backend with Supabase authentication",
    version="1.0.0",
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Rate limiting middleware"""
    return await rate_limit_middleware(request, call_next)

# Include routers
app.include_router(router, prefix="/api/v1", tags=["authentication"])


@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions"""
    logger.error(f"API Exception: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "data": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled Exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "data": "Internal server error"}
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}


ROOT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Niya FastAPI</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a;
            --container-bg: rgba(30, 41, 59, 0.7);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #3b82f6;
            --success: #10b981;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Outfit', sans-serif; }
        body {
            background-color: var(--bg-color); color: var(--text-primary);
            min-height: 100vh; display: flex; justify-content: center; align-items: center;
            position: relative; overflow: hidden;
        }
        .blob {
            position: absolute; border-radius: 50%; filter: blur(80px); z-index: 0;
            animation: move 10s infinite alternate;
        }
        .blob-1 { width: 400px; height: 400px; background: rgba(59, 130, 246, 0.3); top: -100px; left: -100px; }
        .blob-2 { width: 300px; height: 300px; background: rgba(139, 92, 246, 0.3); bottom: -50px; right: -50px; animation-delay: -5s; }
        @keyframes move {
            0% { transform: translate(0, 0) scale(1); }
            100% { transform: translate(50px, 50px) scale(1.1); }
        }
        .container {
            background: var(--container-bg); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 24px; padding: 3rem;
            width: 90%; max-width: 600px; position: relative; z-index: 1;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            opacity: 0; animation: fadeUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        @keyframes fadeUp { to { transform: translateY(0); opacity: 1; } }
        .header { text-align: center; margin-bottom: 2rem; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 2rem; }
        .logo {
            font-size: 3rem; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 0.5rem;
        }
        .subtitle { color: var(--text-secondary); font-size: 1.1rem; font-weight: 300; }
        .status-badge {
            display: inline-flex; align-items: center; gap: 0.5rem; background: rgba(16, 185, 129, 0.1);
            color: var(--success); padding: 0.5rem 1rem; border-radius: 9999px; font-size: 0.875rem;
            font-weight: 600; margin-top: 1rem; border: 1px solid rgba(16, 185, 129, 0.2);
        }
        .pulse {
            width: 8px; height: 8px; border-radius: 50%; background-color: var(--success);
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); animation: pulse-animation 2s infinite;
        }
        @keyframes pulse-animation {
            0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
            100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }
        .links-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 2rem; }
        .card-link {
            display: flex; flex-direction: column; gap: 0.5rem; padding: 1.5rem;
            background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px; text-decoration: none; color: var(--text-primary); transition: all 0.3s ease;
        }
        .card-link:hover {
            background: rgba(255, 255, 255, 0.08); border-color: rgba(255, 255, 255, 0.2);
            transform: translateY(-5px); box-shadow: 0 10px 20px -10px rgba(0, 0, 0, 0.3);
        }
        .card-title { font-weight: 600; font-size: 1.25rem; display: flex; align-items: center; gap: 0.5rem; }
        .card-desc { color: var(--text-secondary); font-size: 0.875rem; line-height: 1.5; }
        .footer { margin-top: 2.5rem; text-align: center; color: var(--text-secondary); font-size: 0.875rem; }
        svg { width: 20px; height: 20px; }
    </style>
</head>
<body>
    <div class="blob blob-1"></div>
    <div class="blob blob-2"></div>
    <div class="container">
        <div class="header">
            <h1 class="logo">Niya API</h1>
            <p class="subtitle">Production-ready FastAPI Template</p>
            <div class="status-badge">
                <div class="pulse"></div>
                System Operational &bull; v1.0.0
            </div>
        </div>
        <div class="links-grid">
            <a href="/docs" class="card-link">
                <span class="card-title">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    Swagger UI
                </span>
                <span class="card-desc">Interactive API documentation and testing interface.</span>
            </a>
            <a href="/redoc" class="card-link">
                <span class="card-title">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
                    ReDoc
                </span>
                <span class="card-desc">Detailed, comprehensive and clean API documentation.</span>
            </a>
        </div>
        <div class="footer">
            Built with ❤️ using FastAPI & Python
        </div>
    </div>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def root():
    """Beautiful Root HTML endpoint"""
    return HTMLResponse(content=ROOT_HTML, status_code=200)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
