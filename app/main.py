"""
Application Entry Point
-----------------------
Creates and configures the FastAPI application using the factory pattern.

The factory pattern (create_application function) is used instead of
creating the app at module level because:
- It makes testing easier — tests can call create_application() to get
  a fresh app instance with a test database instead of the real one.
- It keeps startup logic organised and explicit.
- It avoids circular import issues that arise with module-level app instances.

All routes are versioned under /api/v1/ so future breaking changes
can be introduced under /api/v2/ without affecting existing clients.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base
from app.logger import setup_logger
from app.api.v1.routers import auth, users, wallet

logger = setup_logger(__name__)

# Rate limiter keyed on client IP address.
# Prevents brute force attacks on auth endpoints and API abuse.
# Limits are applied per-route using the @limiter.limit decorator.
limiter = Limiter(key_func=get_remote_address)


def create_application() -> FastAPI:
    """
    Application factory — creates, configures, and returns the FastAPI instance.

    Configures in this order:
    1. FastAPI metadata and conditional docs visibility
    2. Rate limiting middleware
    3. CORS middleware
    4. API routers with versioned prefixes
    5. Startup and shutdown event handlers
    6. Global exception handler for unhandled errors
    7. Root and health check endpoints

    Returns:
        A fully configured FastAPI application instance.
    """

    application = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Production-ready Digital Wallet API. "
            "Supports user registration, JWT authentication, "
            "wallet management, and peer-to-peer fund transfers "
            "with atomic transactions and full audit history."
        ),

        # API documentation is only exposed in non-production environments.
        # Exposing /docs in production reveals your API structure to attackers.
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    # Attach the limiter to the app state so route decorators can access it.
    # The exception handler returns a clean 429 Too Many Requests response.
    application.state.limiter = limiter
    application.add_exception_handler(
        RateLimitExceeded,
        _rate_limit_exceeded_handler
    )

    # ── CORS Middleware ───────────────────────────────────────────────────────
    # Controls which frontend origins are allowed to make requests to this API.
    # allow_credentials=True is required for requests that include cookies
    # or Authorization headers (which our JWT auth uses).
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API Routers ───────────────────────────────────────────────────────────
    # All routes are prefixed with /api/v1.
    # When breaking changes are needed in the future, add a v2 router
    # alongside this one without modifying or removing v1.
    API_V1_PREFIX = "/api/v1"

    application.include_router(
        auth.router,
        prefix=f"{API_V1_PREFIX}/auth",
        tags=["Authentication"]        # groups endpoints in /docs
    )
    application.include_router(
        users.router,
        prefix=f"{API_V1_PREFIX}/users",
        tags=["Users"]
    )
    application.include_router(
        wallet.router,
        prefix=f"{API_V1_PREFIX}/wallet",
        tags=["Wallet"]
    )

    # ── Startup Event ─────────────────────────────────────────────────────────
    @application.on_event("startup")
    async def startup_event():
        """
        Runs once when the server starts.
        Logs environment info and verifies database tables exist.
        In production, table creation is handled by Alembic migrations.
        create_all() here acts as a safety net in development.
        """
        logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info(f"Environment  : {settings.APP_ENV}")
        logger.info(f"Debug mode   : {settings.DEBUG}")
        logger.info(f"Docs enabled : {not settings.is_production}")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified successfully")

    # ── Shutdown Event ────────────────────────────────────────────────────────
    @application.on_event("shutdown")
    async def shutdown_event():
        """
        Runs once when the server shuts down.
        Add cleanup logic here: close Redis connections, flush buffers, etc.
        """
        logger.info(f"Shutting down {settings.APP_NAME}")

    # ── Global Exception Handler ──────────────────────────────────────────────
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """
        Catches any unhandled exception that escapes the route handlers.
        Returns a clean, generic JSON error instead of exposing a stack trace.

        The actual exception is logged server-side with full traceback
        (exc_info=True) for debugging, but the client only receives a
        safe, generic message. Never expose internal error details to clients.
        """
        logger.error(
            f"Unhandled exception on {request.method} {request.url}: {exc}",
            exc_info=True   # includes full stack trace in the log
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected error occurred. Please try again later.",
                "path": str(request.url),
                "method": request.method
            }
        )

    # ── Root Endpoint ─────────────────────────────────────────────────────────
    @application.get(
        "/",
        tags=["Root"],
        summary="API root",
        description="Returns basic API information and links."
    )
    async def root():
        """Returns API metadata. Useful for confirming the service is up."""
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "status": "running",
            "docs": "/docs" if not settings.is_production else "disabled in production"
        }

    # ── Health Check Endpoint ─────────────────────────────────────────────────
    @application.get(
        "/health",
        tags=["Health"],
        summary="Health check",
        description=(
            "Used by load balancers and monitoring tools to verify "
            "the service is alive and ready to handle requests."
        )
    )
    async def health_check():
        """
        Lightweight health check endpoint.
        Should return 200 as long as the application process is running.
        For a deeper check (DB connectivity), a /health/ready endpoint
        can be added later that actually queries the database.
        """
        return {
            "status": "healthy",
            "environment": settings.APP_ENV,
            "version": settings.APP_VERSION
        }

    return application


# Module-level app instance used by uvicorn.
# uvicorn app.main:app reads this variable to start the server.
app = create_application()