"""
Global settings and configuration for Tunnel Server
"""
import os
import asyncio
from datetime import datetime
from decouple import config
from typing import Optional
import kthread

# Initialize timestamp
ON_INITIALIZE_TIME = datetime.now()

# Environment Configuration
ENVIRONMENT = config("ENVIRONMENT_TYPE", default="LOCAL", cast=str)
APP_NAME = config("APP_NAME", default="TUNNEL_SERVER", cast=str)
VERSION = config("VERSION", default="v1.0.0", cast=str)
API_PORT = config("API_PORT", default=8989, cast=int)

# Security
REQUIRED_MATCHING_KEY = config("REQUIRED_MATCHING_KEY", default="", cast=str)
REQUIRED_MATCHING_ADMIN_KEY = config("REQUIRED_MATCHING_ADMIN_KEY", default="", cast=str)

# Tunnel Settings
TUNNEL_TIMEOUT_SECONDS = config("TUNNEL_TIMEOUT_SECONDS", default=30, cast=int)
TUNNEL_MAX_CONNECTIONS = config("TUNNEL_MAX_CONNECTIONS", default=100, cast=int)
TUNNEL_HEARTBEAT_INTERVAL = config("TUNNEL_HEARTBEAT_INTERVAL", default=10, cast=int)
TUNNEL_CLEANUP_INTERVAL = config("TUNNEL_CLEANUP_INTERVAL", default=60, cast=int)

# Logging
LOG_LEVEL = config("LOG_LEVEL", default="INFO", cast=str)
LOG_TIMEZONE = config("LOG_TIMEZONE", default="US/Pacific", cast=str)

# Runtime State
ASYNCIO_LOOP: Optional[asyncio.AbstractEventLoop] = None
SERVER_THREAD: Optional[kthread.KThread] = None

# OpenAPI Schema visibility
INCLUDE_SCHEMA = True if ENVIRONMENT in ["LOCAL", "SANDBOX"] else False

# Server Configuration
if ENVIRONMENT == "PROD":
    SERVER_HOST = "0.0.0.0"
else:
    SERVER_HOST = "localhost"
