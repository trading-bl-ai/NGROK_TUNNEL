"""
Main FastAPI application
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from settings import settings
from logs.logger import system_logger
import time

# Import routers
from api import tunnel_api, tunnel_websocket, proxy_handler

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/docs" if settings.INCLUDE_SCHEMA else None,
    redoc_url="/redoc" if settings.INCLUDE_SCHEMA else None,
    openapi_url="/openapi.json" if settings.INCLUDE_SCHEMA else None,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Include routers
app.include_router(tunnel_api.router)
app.include_router(tunnel_websocket.router)
app.include_router(proxy_handler.router)


# Root endpoint
@app.get("/")
@limiter.limit("10/minute")
async def root(request: Request):
    """Root endpoint - returns 404 to discourage scanning"""
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"}
    )


# Health check
@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


# API info endpoint
@app.get("/api")
@limiter.limit("50/minute")
async def api_info(request: Request):
    """API information endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs" if settings.INCLUDE_SCHEMA else None,
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup"""
    from tunnel.tunnel_manager import tunnel_manager

    system_logger.info(f"Starting {settings.APP_NAME} {settings.VERSION}")
    system_logger.info(f"Environment: {settings.ENVIRONMENT}")
    system_logger.info(f"API Port: {settings.API_PORT}")

    # Start cleanup task
    await tunnel_manager.start_cleanup_task(
        cleanup_interval=settings.TUNNEL_CLEANUP_INTERVAL,
        timeout_seconds=settings.TUNNEL_TIMEOUT_SECONDS * 2  # Double timeout for cleanup
    )

    system_logger.info("Application startup complete")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown"""
    from tunnel.tunnel_manager import tunnel_manager

    system_logger.info("Shutting down application...")

    # Stop cleanup task
    await tunnel_manager.stop_cleanup_task()

    # Close all tunnels
    tunnels = await tunnel_manager.list_tunnels()
    for tunnel_info in tunnels:
        await tunnel_manager.delete_tunnel(tunnel_info.tunnel_id)

    system_logger.info("Application shutdown complete")
