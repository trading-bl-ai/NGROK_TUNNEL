"""
Tunnel control plane API endpoints
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from tunnel.tunnel_models import (
    CreateTunnelRequest,
    CreateTunnelResponse,
    TunnelListResponse,
    TunnelInfo
)
from tunnel.tunnel_manager import tunnel_manager
from logs.logger import tunnel_logger
from settings import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Router
router = APIRouter(prefix="/api/tunnels", tags=["Tunnels"])


def authenticate_api_key(api_key: str = Header(None, alias="x-api-key")):
    """Authenticate API key"""
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    if api_key not in [settings.REQUIRED_MATCHING_KEY, settings.REQUIRED_MATCHING_ADMIN_KEY]:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key


@router.post("/create", response_model=CreateTunnelResponse)
@limiter.limit("10/minute")
async def create_tunnel(
    request: CreateTunnelRequest,
    api_key: str = Depends(authenticate_api_key)
):
    """
    Create a new tunnel

    Requires authentication with x-api-key header.

    Returns tunnel_id, auth_token, and public URL.
    """
    try:
        tunnel = await tunnel_manager.create_tunnel(
            name=request.name,
            local_port=request.local_port,
            metadata=request.metadata
        )

        # Construct public URL
        # In production, this would be the actual domain
        domain = "ngrok.424th.com" if settings.ENVIRONMENT == "PROD" else f"localhost:{settings.API_PORT}"
        protocol = "https" if settings.ENVIRONMENT == "PROD" else "http"
        url = f"{protocol}://{domain}/{tunnel.tunnel_id}"

        tunnel_logger.info(f"Created tunnel {tunnel.tunnel_id} via API")

        return CreateTunnelResponse(
            tunnel_id=tunnel.tunnel_id,
            auth_token=tunnel.auth_token,
            url=url,
            created_at=tunnel.created_at.isoformat()
        )

    except Exception as e:
        tunnel_logger.error(f"Error creating tunnel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tunnel_id}")
@limiter.limit("20/minute")
async def delete_tunnel(
    tunnel_id: str,
    api_key: str = Depends(authenticate_api_key)
):
    """
    Delete a tunnel

    Requires authentication with x-api-key header.
    """
    deleted = await tunnel_manager.delete_tunnel(tunnel_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Tunnel not found")

    tunnel_logger.info(f"Deleted tunnel {tunnel_id} via API")
    return {"status": "success", "tunnel_id": tunnel_id}


@router.get("/list", response_model=TunnelListResponse)
@limiter.limit("30/minute")
async def list_tunnels(api_key: str = Depends(authenticate_api_key)):
    """
    List all active tunnels

    Requires authentication with x-api-key header.
    """
    tunnels = await tunnel_manager.list_tunnels()

    return TunnelListResponse(
        tunnels=tunnels,
        total=len(tunnels)
    )


@router.get("/{tunnel_id}/status", response_model=TunnelInfo)
@limiter.limit("60/minute")
async def get_tunnel_status(
    tunnel_id: str,
    api_key: str = Depends(authenticate_api_key)
):
    """
    Get status of a specific tunnel

    Requires authentication with x-api-key header.
    """
    tunnel = await tunnel_manager.get_tunnel(tunnel_id)

    if not tunnel:
        raise HTTPException(status_code=404, detail="Tunnel not found")

    return tunnel.to_info()
