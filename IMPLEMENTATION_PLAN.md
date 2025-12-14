# NGrok Alternative Implementation Plan

## Research Summary

### How NGrok Works

NGrok operates as a **reverse proxy with secure tunneling**:

1. **Client-Server Architecture**:
   - Local client initiates outbound TCP connection to cloud server (firewall-friendly)
   - Server provides public endpoint (e.g., `abc123.ngrok.io`)
   - Traffic flows: User → Public Endpoint → Tunnel → Local Service

2. **Key Features**:
   - Persistent encrypted TCP connection
   - WebSocket support (Connection: upgrade header forwarding)
   - Traffic inspection/debugging capabilities
   - Dynamic subdomain/endpoint generation

### Open Source Alternatives Studied

- **Localtunnel**: npm-based, simple HTTP/HTTPS tunnels (maintenance stale)
- **inlets**: Cloud-native, supports HTTP/HTTPS/WebSocket/TCP
- **Zrok**: Zero-trust networking, built on OpenZiti
- **Chisel**: SSH-based, auto LetsEncrypt certs, Go
- **bore/rathole/frp**: Minimal, high-performance, Rust-based

**Sources**:
- [What is Ngrok and How Does It Work? | BrowserStack](https://www.browserstack.com/guide/what-is-ngrok)
- [Demystifying Ngrok | Medium](https://medium.com/@thealgorithmicgambit/demystifying-ngrok-what-really-happens-when-you-share-localhost-27a4c317af59)
- [awesome-tunneling GitHub](https://github.com/anderspitman/awesome-tunneling)
- [Top 10 Ngrok alternatives | Pinggy](https://pinggy.io/blog/best_ngrok_alternatives/)

---

## Requirements Analysis

### Your Infrastructure
```
Cloudflare → Router → Traefik → Kubernetes App Instance
```

### Goal
- **Public endpoint**: `ngrok.424th.com`
- **Dynamic endpoints**: `ngrok.424th.com/{tunnel_id}` → maps to local service
- **Within your infrastructure**: No external cloud dependency
- **Works exactly like ngrok**: Tunnel manager + reverse proxy

---

## Architecture Design

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                     ngrok.424th.com                          │
│                   (Cloudflare DNS)                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                        Traefik                               │
│              (IngressRoute to Tunnel Server)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│               Tunnel Server (Kubernetes Pod)                 │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          FastAPI Application                         │   │
│  │                                                       │   │
│  │  [1] Control Plane API                               │   │
│  │      - POST /api/tunnels/create                      │   │
│  │      - DELETE /api/tunnels/{tunnel_id}               │   │
│  │      - GET /api/tunnels/list                         │   │
│  │      - GET /api/tunnels/{tunnel_id}/status           │   │
│  │                                                       │   │
│  │  [2] WebSocket Tunnel Handler                        │   │
│  │      - WS /api/tunnel/connect/{tunnel_id}            │   │
│  │      - Maintains persistent client connections       │   │
│  │      - Bidirectional message passing                 │   │
│  │                                                       │   │
│  │  [3] Data Plane (HTTP Reverse Proxy)                 │   │
│  │      - GET/POST/PUT/DELETE /{tunnel_id}/*            │   │
│  │      - Routes traffic to WebSocket tunnel            │   │
│  │      - Forwards headers, body, method                │   │
│  │                                                       │   │
│  │  [4] Tunnel Registry (In-Memory)                     │   │
│  │      - tunnel_id → WebSocket connection mapping      │   │
│  │      - Metadata: created_at, last_active, target_url │   │
│  │                                                       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ WebSocket Tunnel
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Local Client (Python)                      │
│                                                               │
│  - Connects to WS /api/tunnel/connect/{tunnel_id}           │
│  - Receives HTTP requests from server                        │
│  - Proxies to localhost:PORT                                 │
│  - Returns responses back through WebSocket                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Strategy

### Phase 1: Core Server Application (FastAPI)

**Based on base_backend template**:
- FastAPI with Uvicorn ASGI server
- API key + 2FA authentication (reuse helper/six_digit.py pattern)
- Rate limiting via slowapi
- Custom logger with PST timezone and rotating files
- Environment-based config (LOCAL/SANDBOX/PROD)

**New Components**:
1. **Tunnel Registry** (`tunnel_manager.py`)
   - Data structure: `Dict[str, TunnelConnection]`
   - TunnelConnection: `{tunnel_id, websocket, created_at, last_active, metadata}`
   - Thread-safe with asyncio locks
   - Auto-cleanup of stale tunnels (heartbeat pattern)

2. **Control Plane API** (`api/tunnel_api.py`)
   ```python
   POST /api/tunnels/create
   {
     "name": "my-dev-server",  # Optional friendly name
     "local_port": 3000,        # For client reference
     "auth_token": "..."        # Tunnel-specific auth
   }
   Response: {"tunnel_id": "abc123", "url": "ngrok.424th.com/abc123"}

   DELETE /api/tunnels/{tunnel_id}
   GET /api/tunnels/list
   GET /api/tunnels/{tunnel_id}/status
   ```

3. **WebSocket Handler** (`api/tunnel_websocket.py`)
   ```python
   @app.websocket("/api/tunnel/connect/{tunnel_id}")
   async def tunnel_connect(websocket: WebSocket, tunnel_id: str):
       - Authenticate tunnel_id + auth_token
       - Register in tunnel registry
       - Keep connection alive
       - Handle request/response message passing
       - Implement heartbeat/ping-pong
   ```

4. **HTTP Reverse Proxy** (`api/proxy_handler.py`)
   ```python
   @app.api_route("/{tunnel_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", ...])
   async def proxy_request(tunnel_id: str, path: str, request: Request):
       - Lookup tunnel_id in registry
       - Serialize HTTP request (method, headers, body, path)
       - Send to WebSocket client
       - Await response from client
       - Deserialize and return to original requester
   ```

### Phase 2: Client Library (Python Package)

**Client CLI** (`client/tunnel_client.py`):
```python
# Usage: python tunnel_client.py --server ngrok.424th.com --port 3000
import websockets
import httpx

async def run_tunnel(server, port, auth_token):
    tunnel_id = await create_tunnel(server, auth_token)
    print(f"Tunnel active: https://{server}/{tunnel_id}")

    async with websockets.connect(f"wss://{server}/api/tunnel/connect/{tunnel_id}") as ws:
        while True:
            msg = await ws.recv()  # Receive proxied HTTP request
            request = deserialize_request(msg)

            # Forward to local service
            response = await httpx.request(
                method=request.method,
                url=f"http://localhost:{port}{request.path}",
                headers=request.headers,
                content=request.body
            )

            # Send response back
            await ws.send(serialize_response(response))
```

### Phase 3: Docker & Deployment

**Dockerfile** (multi-stage like base_backend):
```dockerfile
FROM python:3.10 AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.10-slim
WORKDIR /app
COPY --from=build /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY . .
CMD ["python", "initialize_main.py"]
```

**Kubernetes Config**:
- Service: ClusterIP on port 8989
- IngressRoute (Traefik): `ngrok.424th.com` → service
- Secrets: API keys, auth tokens

---

## Technical Decisions

### 1. **WebSocket vs HTTP Long-Polling**
**Choice**: WebSocket
- Persistent bidirectional connection
- Lower latency for request/response cycle
- Native support in FastAPI and modern browsers

### 2. **State Storage: In-Memory vs Database**
**Choice**: In-Memory (with optional Redis persistence)
- Tunnels are ephemeral (like ngrok)
- Fast lookups (tunnel_id → WebSocket)
- Can add Redis later for multi-pod horizontal scaling

### 3. **Message Serialization**
**Choice**: JSON with base64-encoded binary bodies
- Simple, human-readable debugging
- Well-supported in Python/JavaScript
- Alternative: MessagePack for performance

### 4. **Authentication**
**Two levels**:
- **Server API**: API key + 2FA (existing base_backend pattern)
- **Tunnel-specific**: JWT or random token per tunnel (prevents hijacking)

### 5. **Request Timeout**
- Default: 30 seconds for WebSocket request/response cycle
- Configurable per tunnel
- Prevents hung connections

---

## File Structure

```
ngrok-alternative/
├── api/
│   ├── __init__.py
│   ├── tunnel_api.py           # Control plane endpoints
│   ├── tunnel_websocket.py     # WebSocket handler
│   ├── proxy_handler.py        # HTTP reverse proxy
│   └── health.py               # Health checks
│
├── tunnel/
│   ├── __init__.py
│   ├── tunnel_manager.py       # Tunnel registry + lifecycle
│   ├── message_protocol.py     # Request/response serialization
│   └── tunnel_models.py        # Pydantic models
│
├── client/
│   ├── __init__.py
│   ├── tunnel_client.py        # CLI client for local tunneling
│   └── client_config.py        # Client configuration
│
├── logs/
│   ├── __init__.py
│   └── logger.py               # Custom logger (from base_backend)
│
├── settings/
│   ├── __init__.py
│   └── settings.py             # Global config (from base_backend)
│
├── helper/
│   ├── __init__.py
│   ├── six_digit.py            # 2FA (from base_backend)
│   └── get_time.py             # Time utilities
│
├── initialize_main.py          # Entry point
├── requirements.txt
├── Dockerfile
├── kubernetes-config.yaml
├── .env.example
└── README.md
```

---

## Dependencies (requirements.txt)

```
# Web Framework
fastapi==0.123.0
uvicorn[standard]==0.38.0
websockets==14.1

# HTTP Client
httpx==0.28.1

# Data Validation
pydantic==2.12.5

# Security
pycryptodome==3.23.0
slowapi==0.1.9

# Utilities
python-decouple==3.8
pytz==2025.2

# Optional: Persistence
# redis==5.2.0

# Testing
pytest==8.4.2
pytest-asyncio==0.24.0
```

---

## Implementation Sequence

### Step 1: Project Setup
- Create directory structure
- Copy base_backend template files (logger, settings, helper)
- Initialize requirements.txt and Dockerfile
- Set up .env configuration

### Step 2: Core Tunnel Management
- Implement `tunnel_models.py` (Pydantic models)
- Implement `tunnel_manager.py` (registry with thread-safe operations)
- Implement `message_protocol.py` (serialize/deserialize HTTP)

### Step 3: Control Plane API
- Implement `tunnel_api.py` endpoints
- Add authentication middleware
- Add rate limiting

### Step 4: WebSocket Handler
- Implement `tunnel_websocket.py`
- Integrate with tunnel_manager
- Add heartbeat/keepalive

### Step 5: HTTP Reverse Proxy
- Implement `proxy_handler.py`
- Add request timeout handling
- Add error handling (tunnel not found, timeout, etc.)

### Step 6: Client Implementation
- Implement `tunnel_client.py` CLI
- Add command-line argument parsing
- Test end-to-end flow

### Step 7: Docker & Deployment
- Build Dockerfile
- Create kubernetes-config.yaml
- Document deployment steps

### Step 8: Testing
- Unit tests for tunnel_manager
- Integration tests for WebSocket flow
- End-to-end test with real HTTP traffic

---

## Configuration (.env)

```env
# Environment
ENVIRONMENT_TYPE=LOCAL  # LOCAL, SANDBOX, PROD
APP_NAME=TUNNEL_SERVER
VERSION=v1.0.0
API_PORT=8989

# Security
REQUIRED_MATCHING_KEY=your-32-char-api-key-here
REQUIRED_MATCHING_ADMIN_KEY=your-admin-key-here
AES_KEY=base64-encoded-encryption-key

# Tunnel Settings
TUNNEL_TIMEOUT_SECONDS=30
TUNNEL_MAX_CONNECTIONS=100
TUNNEL_HEARTBEAT_INTERVAL=10

# Logging
LOG_LEVEL=INFO
LOG_TIMEZONE=US/Pacific
```

---

## Testing Strategy

### Local Development Flow
1. Start tunnel server: `python initialize_main.py`
2. Start local app (e.g., Flask on :3000)
3. Start tunnel client: `python client/tunnel_client.py --server localhost:8989 --port 3000`
4. Client prints: `Tunnel active: http://localhost:8989/abc123`
5. Test: `curl http://localhost:8989/abc123/` → proxies to localhost:3000

### Production Flow
1. Deploy to Kubernetes (ngrok.424th.com)
2. Local client connects: `python tunnel_client.py --server ngrok.424th.com --port 3000`
3. Public access: `https://ngrok.424th.com/abc123/` → your laptop's :3000

---

## Security Considerations

1. **Tunnel Isolation**: Each tunnel has unique token (prevents cross-tunnel access)
2. **Rate Limiting**: Prevent abuse of tunnel creation and proxy endpoints
3. **Timeout**: Auto-close idle tunnels after N minutes
4. **HTTPS**: All traffic encrypted via Cloudflare → Traefik TLS
5. **Authentication**:
   - Server API: API key + 2FA
   - Tunnel creation: Requires valid auth
   - WebSocket connection: Requires tunnel-specific token

---

## Future Enhancements (Out of Scope for MVP)

1. **Traffic Inspection Dashboard**: Web UI to view proxied requests
2. **Custom Subdomains**: `my-app.ngrok.424th.com` instead of `/{tunnel_id}`
3. **TCP Tunneling**: Support non-HTTP protocols (SSH, databases)
4. **Multi-Pod Scaling**: Redis-backed tunnel registry for horizontal scaling
5. **Tunnel Replay**: Record/replay requests for debugging
6. **Webhook Testing**: Store webhook payloads for inspection
7. **Access Control**: IP whitelisting, password protection per tunnel

---

## Success Criteria

✅ Server runs in Kubernetes, accessible at `ngrok.424th.com`
✅ Client can create tunnel and get unique endpoint
✅ HTTP requests to `ngrok.424th.com/{tunnel_id}/...` proxy to local service
✅ Supports all HTTP methods (GET, POST, PUT, DELETE, etc.)
✅ Headers and request bodies forwarded correctly
✅ WebSocket connections remain stable
✅ Dockerfile builds successfully
✅ Works with Cloudflare → Traefik → Kubernetes stack

---

## Next Steps

1. Review this plan and confirm approach
2. Begin implementation starting with Step 1 (Project Setup)
3. Iterate through implementation sequence
4. Test locally before deployment

---

**Estimated Complexity**: Medium
**Key Risks**:
- WebSocket connection stability under load
- Request/response serialization for binary data
- Timeout handling for slow local services

**Mitigation**:
- Implement robust heartbeat and reconnection logic
- Use base64 encoding for binary bodies
- Configurable timeouts with clear error messages
