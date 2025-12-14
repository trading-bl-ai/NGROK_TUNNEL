"""
Pydantic models for tunnel management
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TunnelStatus(str, Enum):
    """Tunnel connection status"""
    ACTIVE = "active"
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    EXPIRED = "expired"


class CreateTunnelRequest(BaseModel):
    """Request model for creating a new tunnel"""
    name: Optional[str] = Field(None, description="Friendly name for the tunnel")
    local_port: Optional[int] = Field(None, description="Local port (for client reference)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class CreateTunnelResponse(BaseModel):
    """Response model for tunnel creation"""
    tunnel_id: str = Field(..., description="Unique tunnel identifier")
    auth_token: str = Field(..., description="Authentication token for this tunnel")
    url: str = Field(..., description="Public URL for accessing the tunnel")
    created_at: str = Field(..., description="Creation timestamp")


class TunnelInfo(BaseModel):
    """Information about a tunnel"""
    tunnel_id: str
    name: Optional[str] = None
    status: TunnelStatus
    created_at: str
    last_active: str
    local_port: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    connected: bool = False


class TunnelListResponse(BaseModel):
    """Response model for listing tunnels"""
    tunnels: list[TunnelInfo]
    total: int


class HTTPRequest(BaseModel):
    """Serialized HTTP request to send through tunnel"""
    request_id: str = Field(..., description="Unique request identifier")
    method: str = Field(..., description="HTTP method")
    path: str = Field(..., description="Request path")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    body: Optional[str] = Field(None, description="Request body (base64 encoded if binary)")
    query_params: Dict[str, str] = Field(default_factory=dict, description="Query parameters")


class HTTPResponse(BaseModel):
    """Serialized HTTP response to return through tunnel"""
    request_id: str = Field(..., description="Matching request identifier")
    status_code: int = Field(..., description="HTTP status code")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    body: Optional[str] = Field(None, description="Response body (base64 encoded if binary)")


class TunnelMessage(BaseModel):
    """WebSocket message wrapper"""
    type: str = Field(..., description="Message type: request, response, ping, pong, error")
    data: Optional[Dict[str, Any]] = Field(None, description="Message payload")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class HeartbeatMessage(BaseModel):
    """Heartbeat ping/pong message"""
    type: str = "ping"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
