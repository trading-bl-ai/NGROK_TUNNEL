"""
HTTP reverse proxy handler for tunneled requests
"""
import asyncio
import uuid
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from tunnel.tunnel_manager import tunnel_manager
from tunnel.message_protocol import serialize_request, create_tunnel_message, deserialize_response
from tunnel.tunnel_models import TunnelStatus
from logs.logger import tunnel_logger
from settings import settings

router = APIRouter(tags=["Proxy"])


@router.api_route("/{tunnel_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_request(tunnel_id: str, path: str, request: Request):
    """
    Proxy HTTP request through tunnel

    This endpoint handles all HTTP methods and forwards them to the local service
    through the WebSocket tunnel connection.

    Path format: /{tunnel_id}/{path}
    Example: /abc123/api/users -> proxied to localhost:PORT/api/users
    """
    # Get tunnel
    tunnel = await tunnel_manager.get_tunnel(tunnel_id)

    if not tunnel:
        tunnel_logger.warning(f"Tunnel not found: {tunnel_id}")
        raise HTTPException(status_code=404, detail="Tunnel not found")

    if tunnel.status != TunnelStatus.ACTIVE:
        tunnel_logger.warning(f"Tunnel not active: {tunnel_id} (status={tunnel.status})")
        raise HTTPException(status_code=503, detail=f"Tunnel not active (status: {tunnel.status})")

    if not tunnel.websocket:
        tunnel_logger.warning(f"No WebSocket connection for tunnel: {tunnel_id}")
        raise HTTPException(status_code=503, detail="Tunnel not connected")

    # Generate unique request ID
    request_id = str(uuid.uuid4())

    try:
        # Serialize the incoming request
        http_request = await serialize_request(request, f"/{path}", request_id)

        # Create future for response
        response_future = asyncio.Future()
        tunnel.pending_requests[request_id] = response_future

        # Send request to client via WebSocket
        message = create_tunnel_message("request", http_request.model_dump())

        try:
            await tunnel.websocket.send_text(message)
            tunnel.update_activity()
        except Exception as e:
            tunnel_logger.error(f"Failed to send request to tunnel {tunnel_id}: {e}")
            del tunnel.pending_requests[request_id]
            raise HTTPException(status_code=502, detail="Failed to send request to tunnel")

        # Wait for response with timeout
        try:
            response_data = await asyncio.wait_for(
                response_future,
                timeout=settings.TUNNEL_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            tunnel_logger.error(f"Request timeout for tunnel {tunnel_id}, request {request_id}")
            del tunnel.pending_requests[request_id]
            raise HTTPException(status_code=504, detail="Gateway timeout")

        # Clean up
        del tunnel.pending_requests[request_id]

        # Deserialize response
        from tunnel.tunnel_models import HTTPResponse
        http_response = HTTPResponse(**response_data)
        response_dict = deserialize_response(http_response)

        # Return response
        headers = {k: v for k, v in response_dict["headers"].items() if k.lower() != "x-tunnel-body-encoding"}

        return Response(
            content=response_dict.get("body", b""),
            status_code=response_dict["status_code"],
            headers=headers
        )

    except HTTPException:
        raise

    except Exception as e:
        tunnel_logger.error(f"Error proxying request to {tunnel_id}: {e}")
        if request_id in tunnel.pending_requests:
            del tunnel.pending_requests[request_id]
        raise HTTPException(status_code=500, detail=f"Internal proxy error: {str(e)}")


@router.get("/{tunnel_id}")
async def proxy_root(tunnel_id: str, request: Request):
    """
    Proxy request to tunnel root path

    This handles requests to /{tunnel_id} without a trailing path.
    """
    return await proxy_request(tunnel_id, "", request)
