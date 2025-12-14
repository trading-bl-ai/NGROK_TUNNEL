"""
Tunnel registry and lifecycle management
"""
import asyncio
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from fastapi import WebSocket
from tunnel.tunnel_models import TunnelStatus, TunnelInfo
from logs.logger import tunnel_logger
import pytz

PST = pytz.timezone("US/Pacific")


class TunnelConnection:
    """Represents a single tunnel connection"""

    def __init__(
        self,
        tunnel_id: str,
        auth_token: str,
        name: Optional[str] = None,
        local_port: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.tunnel_id = tunnel_id
        self.auth_token = auth_token
        self.name = name
        self.local_port = local_port
        self.metadata = metadata or {}
        self.created_at = datetime.now(PST)
        self.last_active = datetime.now(PST)
        self.websocket: Optional[WebSocket] = None
        self.status = TunnelStatus.CONNECTING
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.lock = asyncio.Lock()

    def update_activity(self):
        """Update last active timestamp"""
        self.last_active = datetime.now(PST)

    def is_expired(self, timeout_seconds: int) -> bool:
        """Check if tunnel has expired due to inactivity"""
        if self.status == TunnelStatus.DISCONNECTED:
            return True
        elapsed = (datetime.now(PST) - self.last_active).total_seconds()
        return elapsed > timeout_seconds

    def to_info(self) -> TunnelInfo:
        """Convert to TunnelInfo model"""
        return TunnelInfo(
            tunnel_id=self.tunnel_id,
            name=self.name,
            status=self.status,
            created_at=self.created_at.isoformat(),
            last_active=self.last_active.isoformat(),
            local_port=self.local_port,
            metadata=self.metadata,
            connected=(self.websocket is not None)
        )


class TunnelManager:
    """Manages all active tunnels"""

    def __init__(self):
        self.tunnels: Dict[str, TunnelConnection] = {}
        self.lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def generate_tunnel_id(self, length: int = 8) -> str:
        """Generate a random tunnel ID"""
        chars = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))

    def generate_auth_token(self, length: int = 32) -> str:
        """Generate a random auth token"""
        return secrets.token_urlsafe(length)

    async def create_tunnel(
        self,
        name: Optional[str] = None,
        local_port: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TunnelConnection:
        """
        Create a new tunnel

        Args:
            name: Friendly name for the tunnel
            local_port: Local port (for client reference)
            metadata: Additional metadata

        Returns:
            TunnelConnection instance
        """
        async with self.lock:
            # Generate unique tunnel ID
            tunnel_id = self.generate_tunnel_id()
            while tunnel_id in self.tunnels:
                tunnel_id = self.generate_tunnel_id()

            # Generate auth token
            auth_token = self.generate_auth_token()

            # Create tunnel connection
            tunnel = TunnelConnection(
                tunnel_id=tunnel_id,
                auth_token=auth_token,
                name=name,
                local_port=local_port,
                metadata=metadata
            )

            self.tunnels[tunnel_id] = tunnel
            tunnel_logger.info(f"Created tunnel: {tunnel_id} (name={name})")

            return tunnel

    async def connect_tunnel(self, tunnel_id: str, auth_token: str, websocket: WebSocket) -> bool:
        """
        Connect a WebSocket to an existing tunnel

        Args:
            tunnel_id: Tunnel identifier
            auth_token: Authentication token
            websocket: WebSocket connection

        Returns:
            True if successful, False otherwise
        """
        async with self.lock:
            tunnel = self.tunnels.get(tunnel_id)

            if not tunnel:
                tunnel_logger.warning(f"Tunnel not found: {tunnel_id}")
                return False

            if tunnel.auth_token != auth_token:
                tunnel_logger.warning(f"Invalid auth token for tunnel: {tunnel_id}")
                return False

            tunnel.websocket = websocket
            tunnel.status = TunnelStatus.ACTIVE
            tunnel.update_activity()

            tunnel_logger.info(f"Connected tunnel: {tunnel_id}")
            return True

    async def disconnect_tunnel(self, tunnel_id: str):
        """
        Disconnect a tunnel

        Args:
            tunnel_id: Tunnel identifier
        """
        async with self.lock:
            tunnel = self.tunnels.get(tunnel_id)

            if tunnel:
                tunnel.websocket = None
                tunnel.status = TunnelStatus.DISCONNECTED
                tunnel_logger.info(f"Disconnected tunnel: {tunnel_id}")

                # Cancel any pending requests
                for request_id, future in tunnel.pending_requests.items():
                    if not future.done():
                        future.set_exception(Exception("Tunnel disconnected"))

    async def delete_tunnel(self, tunnel_id: str) -> bool:
        """
        Delete a tunnel

        Args:
            tunnel_id: Tunnel identifier

        Returns:
            True if deleted, False if not found
        """
        async with self.lock:
            tunnel = self.tunnels.pop(tunnel_id, None)

            if tunnel:
                # Close WebSocket if connected
                if tunnel.websocket:
                    try:
                        await tunnel.websocket.close()
                    except Exception as e:
                        tunnel_logger.error(f"Error closing websocket for {tunnel_id}: {e}")

                # Cancel pending requests
                for request_id, future in tunnel.pending_requests.items():
                    if not future.done():
                        future.set_exception(Exception("Tunnel deleted"))

                tunnel_logger.info(f"Deleted tunnel: {tunnel_id}")
                return True

            return False

    async def get_tunnel(self, tunnel_id: str) -> Optional[TunnelConnection]:
        """Get a tunnel by ID"""
        return self.tunnels.get(tunnel_id)

    async def list_tunnels(self) -> list[TunnelInfo]:
        """List all tunnels"""
        async with self.lock:
            return [tunnel.to_info() for tunnel in self.tunnels.values()]

    async def cleanup_expired_tunnels(self, timeout_seconds: int):
        """Clean up expired tunnels"""
        async with self.lock:
            expired = [
                tunnel_id
                for tunnel_id, tunnel in self.tunnels.items()
                if tunnel.is_expired(timeout_seconds)
            ]

            for tunnel_id in expired:
                tunnel_logger.info(f"Cleaning up expired tunnel: {tunnel_id}")
                await self.delete_tunnel(tunnel_id)

            if expired:
                tunnel_logger.info(f"Cleaned up {len(expired)} expired tunnels")

    async def start_cleanup_task(self, cleanup_interval: int, timeout_seconds: int):
        """Start background task to clean up expired tunnels"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(cleanup_interval)
                    await self.cleanup_expired_tunnels(timeout_seconds)
                except asyncio.CancelledError:
                    tunnel_logger.info("Cleanup task cancelled")
                    break
                except Exception as e:
                    tunnel_logger.error(f"Error in cleanup task: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        tunnel_logger.info(f"Started cleanup task (interval={cleanup_interval}s, timeout={timeout_seconds}s)")

    async def stop_cleanup_task(self):
        """Stop the cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


# Global tunnel manager instance
tunnel_manager = TunnelManager()
