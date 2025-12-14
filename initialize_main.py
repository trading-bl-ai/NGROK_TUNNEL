"""
Main initialization and startup script for Tunnel Server
"""
import asyncio
import uvicorn
from logs.logger import system_logger
from settings import settings
import kthread


def run_api_server():
    """Run the FastAPI server"""
    system_logger.info(f"Starting API server on {settings.SERVER_HOST}:{settings.API_PORT}")

    uvicorn.run(
        "api.app:app",
        host=settings.SERVER_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )


def main():
    """Main entry point"""
    system_logger.info("="*60)
    system_logger.info(f"Initializing {settings.APP_NAME} {settings.VERSION}")
    system_logger.info(f"Environment: {settings.ENVIRONMENT}")
    system_logger.info("="*60)

    # For production, we'll use kthread for daemon management
    # For development, run directly
    if settings.ENVIRONMENT == "PROD":
        system_logger.info("Starting server in production mode (daemon thread)")
        server_thread = kthread.KThread(target=run_api_server, daemon=True)
        server_thread.start()
        settings.SERVER_THREAD = server_thread

        system_logger.info("Server started. Press Ctrl+C to stop.")

        try:
            # Keep main thread alive
            while True:
                asyncio.sleep(1)
        except KeyboardInterrupt:
            system_logger.info("Received shutdown signal")
            if settings.SERVER_THREAD:
                system_logger.info("Stopping server thread...")
                settings.SERVER_THREAD.kill()
                system_logger.info("Server stopped")

    else:
        system_logger.info("Starting server in development mode (direct run)")
        try:
            run_api_server()
        except KeyboardInterrupt:
            system_logger.info("Received shutdown signal")
            system_logger.info("Server stopped")


if __name__ == "__main__":
    main()
