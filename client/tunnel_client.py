"""
Tunnel client CLI - Connects local service to tunnel server
"""
import asyncio
import argparse
import json
import sys
import signal
from typing import Optional
import httpx
import websockets
from websockets.exceptions import ConnectionClosed
from datetime import datetime


class TunnelClient:
    """Client that connects local service to tunnel server"""

    def __init__(
        self,
        server: str,
        api_key: str,
        local_port: int,
        local_host: str = "localhost",
        name: Optional[str] = None,
        use_https: bool = False
    ):
        self.server = server
        self.api_key = api_key
        self.local_port = local_port
        self.local_host = local_host
        self.name = name
        self.use_https = use_https

        self.tunnel_id: Optional[str] = None
        self.auth_token: Optional[str] = None
        self.public_url: Optional[str] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False

    async def create_tunnel(self) -> bool:
        """Create a tunnel on the server"""
        protocol = "https" if self.use_https else "http"
        url = f"{protocol}://{self.server}/api/tunnels/create"

        headers = {"x-api-key": self.api_key}
        payload = {
            "name": self.name,
            "local_port": self.local_port
        }

        print(f"[{self._timestamp()}] Creating tunnel...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()

                data = response.json()
                self.tunnel_id = data["tunnel_id"]
                self.auth_token = data["auth_token"]
                self.public_url = data["url"]

                print(f"[{self._timestamp()}] ✓ Tunnel created successfully!")
                print(f"[{self._timestamp()}] Tunnel ID: {self.tunnel_id}")
                print(f"[{self._timestamp()}] Public URL: {self.public_url}")
                print()

                return True

        except httpx.HTTPStatusError as e:
            print(f"[{self._timestamp()}] ✗ Failed to create tunnel: {e.response.status_code}")
            print(f"[{self._timestamp()}] Response: {e.response.text}")
            return False

        except Exception as e:
            print(f"[{self._timestamp()}] ✗ Failed to create tunnel: {e}")
            return False

    async def connect_websocket(self) -> bool:
        """Connect to tunnel server via WebSocket"""
        ws_protocol = "wss" if self.use_https else "ws"
        ws_url = f"{ws_protocol}://{self.server}/api/tunnel/connect/{self.tunnel_id}"

        print(f"[{self._timestamp()}] Connecting to tunnel server...")

        try:
            self.websocket = await websockets.connect(ws_url)

            # Send authentication
            auth_message = json.dumps({"auth_token": self.auth_token})
            await self.websocket.send(auth_message)

            # Wait for confirmation
            response = await self.websocket.recv()
            data = json.loads(response)

            if data.get("type") == "connected":
                print(f"[{self._timestamp()}] ✓ Connected to tunnel server!")
                print(f"[{self._timestamp()}] Forwarding: {self.public_url} -> http://{self.local_host}:{self.local_port}")
                print()
                print(f"[{self._timestamp()}] Tunnel is active. Press Ctrl+C to stop.")
                print()
                return True
            else:
                print(f"[{self._timestamp()}] ✗ Connection failed: {data}")
                return False

        except Exception as e:
            print(f"[{self._timestamp()}] ✗ Failed to connect: {e}")
            return False

    async def handle_request(self, message: dict):
        """Handle incoming HTTP request from server"""
        if message.get("type") != "request":
            return

        request_data = message.get("data", {})
        request_id = request_data.get("request_id")
        method = request_data.get("method")
        path = request_data.get("path")

        print(f"[{self._timestamp()}] {method} {path} (request_id: {request_id[:8]}...)")

        try:
            # Build local URL
            local_url = f"http://{self.local_host}:{self.local_port}{path}"

            # Prepare headers
            headers = request_data.get("headers", {})
            # Remove host header to avoid conflicts
            headers.pop("host", None)
            headers.pop("x-tunnel-body-encoding", None)

            # Prepare body
            body = None
            if request_data.get("body"):
                body_str = request_data["body"]
                if headers.get("x-tunnel-body-encoding") == "base64":
                    import base64
                    body = base64.b64decode(body_str)
                else:
                    body = body_str.encode("utf-8") if isinstance(body_str, str) else body_str

            # Make request to local service
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=local_url,
                    headers=headers,
                    content=body,
                    timeout=30.0,
                    follow_redirects=False
                )

                # Prepare response
                response_headers = dict(response.headers)
                response_body = response.content

                # Encode body if binary
                content_type = response_headers.get("content-type", "")
                if self._is_binary(content_type):
                    import base64
                    response_body_str = base64.b64encode(response_body).decode("utf-8")
                    response_headers["x-tunnel-body-encoding"] = "base64"
                else:
                    try:
                        response_body_str = response_body.decode("utf-8")
                    except UnicodeDecodeError:
                        import base64
                        response_body_str = base64.b64encode(response_body).decode("utf-8")
                        response_headers["x-tunnel-body-encoding"] = "base64"

                # Send response back through tunnel
                response_message = {
                    "type": "response",
                    "data": {
                        "request_id": request_id,
                        "status_code": response.status_code,
                        "headers": response_headers,
                        "body": response_body_str
                    }
                }

                await self.websocket.send(json.dumps(response_message))
                print(f"[{self._timestamp()}] → {response.status_code} ({len(response_body)} bytes)")

        except httpx.ConnectError:
            print(f"[{self._timestamp()}] ✗ Failed to connect to local service at http://{self.local_host}:{self.local_port}")
            await self._send_error_response(request_id, 502, "Bad Gateway: Local service not reachable")

        except httpx.TimeoutException:
            print(f"[{self._timestamp()}] ✗ Request timeout to local service")
            await self._send_error_response(request_id, 504, "Gateway Timeout")

        except Exception as e:
            print(f"[{self._timestamp()}] ✗ Error handling request: {e}")
            await self._send_error_response(request_id, 500, f"Internal Error: {str(e)}")

    async def _send_error_response(self, request_id: str, status_code: int, message: str):
        """Send error response back through tunnel"""
        try:
            response_message = {
                "type": "response",
                "data": {
                    "request_id": request_id,
                    "status_code": status_code,
                    "headers": {"content-type": "application/json"},
                    "body": json.dumps({"error": message})
                }
            }
            await self.websocket.send(json.dumps(response_message))
        except Exception as e:
            print(f"[{self._timestamp()}] Failed to send error response: {e}")

    async def message_loop(self):
        """Main message processing loop"""
        self.running = True

        try:
            while self.running:
                try:
                    message_str = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    message = json.loads(message_str)

                    if message.get("type") == "ping":
                        # Respond to heartbeat
                        pong = json.dumps({"type": "pong"})
                        await self.websocket.send(pong)

                    elif message.get("type") == "request":
                        # Handle HTTP request
                        await self.handle_request(message)

                    elif message.get("type") == "error":
                        print(f"[{self._timestamp()}] Server error: {message.get('data', {})}")

                except asyncio.TimeoutError:
                    # No message received, continue
                    continue

                except ConnectionClosed:
                    print(f"\n[{self._timestamp()}] WebSocket connection closed")
                    break

        except Exception as e:
            print(f"[{self._timestamp()}] Error in message loop: {e}")

        finally:
            self.running = False

    async def cleanup(self):
        """Cleanup resources"""
        print(f"\n[{self._timestamp()}] Shutting down tunnel...")

        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass

        # Optionally delete tunnel from server
        # (Commented out to allow reconnection)
        # await self.delete_tunnel()

        print(f"[{self._timestamp()}] Tunnel stopped.")

    async def delete_tunnel(self):
        """Delete tunnel from server"""
        if not self.tunnel_id:
            return

        protocol = "https" if self.use_https else "http"
        url = f"{protocol}://{self.server}/api/tunnels/{self.tunnel_id}"
        headers = {"x-api-key": self.api_key}

        try:
            async with httpx.AsyncClient() as client:
                await client.delete(url, headers=headers)
        except:
            pass

    async def run(self):
        """Main run loop"""
        # Create tunnel
        if not await self.create_tunnel():
            return False

        # Connect WebSocket
        if not await self.connect_websocket():
            return False

        # Run message loop
        await self.message_loop()

        # Cleanup
        await self.cleanup()

        return True

    def _timestamp(self) -> str:
        """Get formatted timestamp"""
        return datetime.now().strftime("%H:%M:%S")

    def _is_binary(self, content_type: str) -> bool:
        """Check if content type is binary"""
        binary_types = ["image/", "video/", "audio/", "application/octet-stream", "application/pdf"]
        return any(bt in content_type.lower() for bt in binary_types)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Tunnel Client - Connect local service to tunnel server")
    parser.add_argument("--server", required=True, help="Tunnel server address (e.g., ngrok.424th.com or localhost:8989)")
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    parser.add_argument("--port", type=int, required=True, help="Local port to forward")
    parser.add_argument("--host", default="localhost", help="Local host (default: localhost)")
    parser.add_argument("--name", help="Friendly name for the tunnel")
    parser.add_argument("--https", action="store_true", help="Use HTTPS/WSS (default: HTTP/WS)")

    args = parser.parse_args()

    # Create client
    client = TunnelClient(
        server=args.server,
        api_key=args.api_key,
        local_port=args.port,
        local_host=args.host,
        name=args.name,
        use_https=args.https
    )

    # Handle shutdown signals
    def signal_handler(sig, frame):
        print("\nReceived interrupt signal...")
        client.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run client
    try:
        await client.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
