"""
Custom logger with PST timezone and rotating file handler
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
import pytz
from collections import deque
from typing import Deque, Tuple

# PST timezone
PST = pytz.timezone("US/Pacific")

# Recent logs storage (for API access)
recent_logs: Deque[Tuple[str, str, str]] = deque(maxlen=100)  # (timestamp, level, message)


class PSTFormatter(logging.Formatter):
    """Custom formatter that converts UTC to PST"""

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=pytz.UTC)
        pst_dt = dt.astimezone(PST)
        if datefmt:
            return pst_dt.strftime(datefmt)
        return pst_dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def setup_logger(name: str, log_file: str = None, level: str = "INFO") -> logging.Logger:
    """
    Set up a logger with PST timezone and optional file rotation

    Args:
        name: Logger name
        log_file: Optional log file path
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Formatter
    formatter = PSTFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S %Z"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Rotating file handler (1MB max, 10 backups)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,  # 1MB
            backupCount=10
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Add custom handler to store recent logs
    class RecentLogsHandler(logging.Handler):
        def emit(self, record):
            timestamp = PSTFormatter().formatTime(record)
            recent_logs.append((timestamp, record.levelname, record.getMessage()))

    recent_handler = RecentLogsHandler()
    logger.addHandler(recent_handler)

    return logger


# Global loggers
system_logger = setup_logger("system", "logs/system.log", "INFO")
dev_logger = setup_logger("dev", "logs/dev.log", "DEBUG")
tunnel_logger = setup_logger("tunnel", "logs/tunnel.log", "INFO")


def get_recent_logs(limit: int = 100) -> list:
    """Get recent logs for API access"""
    return list(recent_logs)[-limit:]
