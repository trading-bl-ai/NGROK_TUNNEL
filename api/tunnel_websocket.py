"""
WebSocket handler for tunnel connections
"""
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from tunnel.tunnel_manager import tunnel_manager
from tunnel.message_protocol import create_tunnel_message, parse_tunnel_message
from logs.logger import tunnel_logger
from settings import settings

router = APIRouter(tags=["Tunnel WebSocket"])


@router.websocket("/api/tunnel/connect/{tunnel_id}")
async def tunnel_connect(websocket: WebSocket, tunnel_id: str):
    """
    WebSocket endpoint for tunnel client connections

    The client must send auth_token in the first message after connecting.
    """
    await websocket.accept()
    tunnel_logger.info(f"WebSocket connection attempt for tunnel: {tunnel_id}")

    try:
        # Wait for authentication message
        auth_message = await asyncio.wait_for(
            websocket.receive_text(),
            timeout=10.0
        )

        try:
            auth_data = json.loads(auth_message)
            auth_token = auth_data.get("auth_token")
        except json.JSONDecodeError:
            await websocket.send_text(create_tunnel_message("error", {
                "message": "Invalid authentication message format"
            }))
            await websocket.close(code=1008)
            return

        if not auth_token:
            await websocket.send_text(create_tunnel_message("error", {
                "message": "Authentication token required"
            }))
            await websocket.close(code=1008)
            return

        # Authenticate and connect tunnel
        connected = await tunnel_manager.connect_tunnel(tunnel_id, auth_token, websocket)

        if not connected:
            await websocket.send_text(create_tunnel_message("error", {
                "message": "Authentication failed"
            }))
            await websocket.close(code=1008)
            return

        # Send success message
        await websocket.send_text(create_tunnel_message("connected", {
            "tunnel_id": tunnel_id,
            "message": "Tunnel connected successfully"
        }))

        tunnel_logger.info(f"Tunnel {tunnel_id} authenticated and connected")

        # Get tunnel instance
        tunnel = await tunnel_manager.get_tunnel(tunnel_id)
        if not tunnel:
            return

        # Start heartbeat task
        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(settings.TUNNEL_HEARTBEAT_INTERVAL)
                    try:
                        await websocket.send_text(create_tunnel_message("ping", {}))
                        tunnel.update_activity()
                    except Exception as e:
                        tunnel_logger.error(f"Heartbeat error for {tunnel_id}: {e}")
                        break
            except asyncio.CancelledError:
                pass

        heartbeat_task = asyncio.create_task(heartbeat())

        try:
            # Main message loop
            while True:
                message = await websocket.receive_text()

                try:
                    tunnel_msg = parse_tunnel_message(message)

                    if tunnel_msg.type == "pong":
                        # Client responded to ping
                        tunnel.update_activity()
                        continue

                    elif tunnel_msg.type == "response":
                        # HTTP response from client
                        if tunnel_msg.data:
                            request_id = tunnel_msg.data.get("request_id")
                            if request_id and request_id in tunnel.pending_requests:
                                future = tunnel.pending_requests[request_id]
                                if not future.done():
                                    future.set_result(tunnel_msg.data)
                                tunnel.update_activity()
                            else:
                                tunnel_logger.warning(
                                    f"Received response for unknown request: {request_id}"
                                )

                    elif tunnel_msg.type == "ping":
                        # Client sent ping, respond with pong
                        await websocket.send_text(create_tunnel_message("pong", {}))
                        tunnel.update_activity()

                    else:
                        tunnel_logger.warning(f"Unknown message type: {tunnel_msg.type}")

                except json.JSONDecodeError as e:
                    tunnel_logger.error(f"Failed to parse message: {e}")
                    continue

        except WebSocketDisconnect:
            tunnel_logger.info(f"WebSocket disconnected for tunnel: {tunnel_id}")

        except Exception as e:
            tunnel_logger.error(f"Error in WebSocket handler for {tunnel_id}: {e}")

        finally:
            # Cleanup
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

            await tunnel_manager.disconnect_tunnel(tunnel_id)

    except asyncio.TimeoutError:
        tunnel_logger.warning(f"Authentication timeout for tunnel: {tunnel_id}")
        await websocket.close(code=1008)

    except Exception as e:
        tunnel_logger.error(f"Unexpected error in tunnel_connect for {tunnel_id}: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass
