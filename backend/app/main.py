"""FastAPI application entry point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as v1_router
from app.config import settings
from app.database import async_engine
from app.dependencies import PASSCODE_COOKIE, passcode_ok


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    Manages startup and shutdown events, including database engine cleanup.
    """
    # Startup
    yield
    # Shutdown
    await async_engine.dispose()


app = FastAPI(
    title="Delivery Agent",
    description="AI-powered delivery agent for smart sprint planning and team coordination",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Alternative dev port
    ],
    # Azure DevOps serves packaged extension content (our hub iframe) from the
    # extension gallery CDN, e.g. https://<publisher>.gallerycdn.vsassets.io.
    # Allow that origin so the embedded hub can call this backend cross-origin.
    # Confirm the exact origin from the browser Network tab once sideloaded and
    # tighten this regex if needed.
    allow_origin_regex=r"https://.*\.(vsassets\.io|visualstudio\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(v1_router, prefix="/api/v1")


# Optional passcode gate for exposed deployments (issue #8). Off unless
# PASSCODE is set. Exempt: the unlock page itself, health probes, and CORS
# preflights (browsers send neither cookies nor custom headers on OPTIONS).
@app.middleware("http")
async def passcode_gate(request: Request, call_next):
    path = request.url.path
    if (
        settings.passcode
        and request.method != "OPTIONS"
        and not path.startswith(("/api/v1/passcode", "/api/v1/health"))
        and not passcode_ok(
            request.cookies.get(PASSCODE_COOKIE) or request.headers.get("X-Passcode")
        )
    ):
        return JSONResponse(
            {"detail": "Passcode required. Unlock at /api/v1/passcode or send X-Passcode."},
            status_code=401,
        )
    return await call_next(request)
