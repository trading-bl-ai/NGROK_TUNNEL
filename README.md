# Tunnel Server - NGrok Alternative

A self-hosted ngrok-like tunnel server that works within your existing infrastructure. Provides secure HTTP tunneling from public endpoints to local development services.

## Architecture

```
Cloudflare → Traefik → Tunnel Server (Kubernetes) ⟷ WebSocket ⟷ Local Client → localhost:PORT
```

**Public URL**: `https://ngrok.424th.com/{tunnel_id}` → Your local service

## Features

- ✅ **Self-hosted**: Runs in your Kubernetes cluster, no external dependencies
- ✅ **WebSocket-based**: Persistent bidirectional connections for low latency
- ✅ **HTTP Tunneling**: Supports all HTTP methods (GET, POST, PUT, DELETE, etc.)
- ✅ **Dynamic Endpoints**: Each tunnel gets a unique `/{tunnel_id}` path
- ✅ **Authentication**: API key + per-tunnel token authentication
- ✅ **Rate Limiting**: Built-in rate limiting for all endpoints
- ✅ **Auto-cleanup**: Automatic cleanup of expired/inactive tunnels
- ✅ **Production-ready**: FastAPI, Uvicorn, comprehensive logging, health checks
- ✅ **Docker & Kubernetes**: Multi-stage Dockerfile, complete K8s manifests

## Quick Start

### 1. Deploy Server (Kubernetes)

```bash
# Update secrets in kubernetes-config.yaml
kubectl apply -f kubernetes-config.yaml

# Verify deployment
kubectl get pods -n tunnel-server
kubectl logs -n tunnel-server deployment/tunnel-server
```

### 2. Install Client Dependencies

```bash
pip install httpx websockets
```

### 3. Run Local Service

Start your local development server (e.g., Flask, Express, etc.):

```bash
# Example: Simple Python HTTP server
python -m http.server 3000
```

### 4. Start Tunnel Client

```bash
python client/tunnel_client.py \
  --server ngrok.424th.com \
  --api-key your-api-key-here-change-this-32ch \
  --port 3000 \
  --name my-dev-server \
  --https
```

**Output**:
```
[14:23:45] Creating tunnel...
[14:23:45] ✓ Tunnel created successfully!
[14:23:45] Tunnel ID: abc12345
[14:23:45] Public URL: https://ngrok.424th.com/abc12345

[14:23:46] ✓ Connected to tunnel server!
[14:23:46] Forwarding: https://ngrok.424th.com/abc12345 -> http://localhost:3000

[14:23:46] Tunnel is active. Press Ctrl+C to stop.
```

### 5. Access Your Local Service

```bash
curl https://ngrok.424th.com/abc12345/
# → proxies to your localhost:3000
```

## Project Structure

```
tunnel-server/
├── api/
│   ├── app.py                  # Main FastAPI application
│   ├── tunnel_api.py           # Control plane API (create/delete/list tunnels)
│   ├── tunnel_websocket.py     # WebSocket handler for client connections
│   └── proxy_handler.py        # HTTP reverse proxy logic
│
├── tunnel/
│   ├── tunnel_manager.py       # Tunnel registry and lifecycle management
│   ├── tunnel_models.py        # Pydantic data models
│   └── message_protocol.py     # Request/response serialization
│
├── client/
│   └── tunnel_client.py        # CLI client for local tunneling
│
├── logs/
│   └── logger.py               # Custom logger with PST timezone
│
├── settings/
│   └── settings.py             # Global configuration
│
├── initialize_main.py          # Application entry point
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Multi-stage Docker build
├── kubernetes-config.yaml      # Kubernetes deployment manifests
├── .env                        # Environment configuration
└── README.md                   # This file
```

## API Endpoints

### Control Plane API

**Base URL**: `https://ngrok.424th.com/api/tunnels`

All endpoints require `x-api-key` header for authentication.

#### Create Tunnel
```bash
POST /api/tunnels/create
Headers: x-api-key: your-api-key

Body:
{
  "name": "my-dev-server",      # Optional
  "local_port": 3000,            # Optional
  "metadata": {}                 # Optional
}

Response:
{
  "tunnel_id": "abc12345",
  "auth_token": "...",
  "url": "https://ngrok.424th.com/abc12345",
  "created_at": "2025-12-14T14:23:45..."
}
```

#### List Tunnels
```bash
GET /api/tunnels/list
Headers: x-api-key: your-api-key

Response:
{
  "tunnels": [
    {
      "tunnel_id": "abc12345",
      "name": "my-dev-server",
      "status": "active",
      "created_at": "...",
      "last_active": "...",
      "connected": true
    }
  ],
  "total": 1
}
```

#### Get Tunnel Status
```bash
GET /api/tunnels/{tunnel_id}/status
Headers: x-api-key: your-api-key
```

#### Delete Tunnel
```bash
DELETE /api/tunnels/{tunnel_id}
Headers: x-api-key: your-api-key
```

### Data Plane (Proxy)

**Base URL**: `https://ngrok.424th.com/{tunnel_id}`

```bash
# All HTTP methods supported
GET    https://ngrok.424th.com/{tunnel_id}/api/users
POST   https://ngrok.424th.com/{tunnel_id}/api/data
PUT    https://ngrok.424th.com/{tunnel_id}/api/update
DELETE https://ngrok.424th.com/{tunnel_id}/api/remove
```

### WebSocket Connection

**URL**: `wss://ngrok.424th.com/api/tunnel/connect/{tunnel_id}`

First message must be authentication:
```json
{"auth_token": "your-tunnel-auth-token"}
```

## Configuration

### Environment Variables (.env)

```bash
# Environment
ENVIRONMENT_TYPE=LOCAL          # LOCAL, SANDBOX, PROD
APP_NAME=TUNNEL_SERVER
VERSION=v1.0.0
API_PORT=8989

# Security
REQUIRED_MATCHING_KEY=your-api-key-here-change-this-32ch
REQUIRED_MATCHING_ADMIN_KEY=your-admin-key-here-change-this-3

# Tunnel Settings
TUNNEL_TIMEOUT_SECONDS=30       # Request timeout
TUNNEL_MAX_CONNECTIONS=100      # Max concurrent tunnels
TUNNEL_HEARTBEAT_INTERVAL=10    # WebSocket heartbeat (seconds)
TUNNEL_CLEANUP_INTERVAL=60      # Cleanup task interval (seconds)

# Logging
LOG_LEVEL=INFO
LOG_TIMEZONE=US/Pacific
```

## Development

### Run Server Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Run server
python initialize_main.py
```

Server runs on `http://localhost:8989`

### Run Client Locally

```bash
# Start your local service
python -m http.server 3000

# In another terminal, start tunnel client
python client/tunnel_client.py \
  --server localhost:8989 \
  --api-key dev-api-key-12345678901234567890 \
  --port 3000
```

### Test the Flow

```bash
# Server should print tunnel URL, e.g., http://localhost:8989/abc12345

# Test the tunnel
curl http://localhost:8989/abc12345/

# Should proxy to localhost:3000 and return response
```

## Docker Build

```bash
# Build image
docker build -t tunnel-server:latest .

# Run container
docker run -d \
  --name tunnel-server \
  -p 8989:8989 \
  --env-file .env \
  tunnel-server:latest

# Check logs
docker logs -f tunnel-server
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster with Traefik ingress controller
- Domain configured in Cloudflare (e.g., ngrok.424th.com)
- Traefik configured with Cloudflare cert resolver

### Deploy

```bash
# Update secrets in kubernetes-config.yaml
vim kubernetes-config.yaml

# Apply manifests
kubectl apply -f kubernetes-config.yaml

# Check deployment
kubectl get all -n tunnel-server

# View logs
kubectl logs -n tunnel-server deployment/tunnel-server -f
```

### Verify

```bash
# Health check
curl https://ngrok.424th.com/health

# API info
curl https://ngrok.424th.com/api
```

## Client Usage Examples

### Basic Usage

```bash
python client/tunnel_client.py \
  --server ngrok.424th.com \
  --api-key YOUR_API_KEY \
  --port 3000 \
  --https
```

### With Custom Name

```bash
python client/tunnel_client.py \
  --server ngrok.424th.com \
  --api-key YOUR_API_KEY \
  --port 8080 \
  --name "my-awesome-app" \
  --https
```

### Tunnel to Custom Host

```bash
python client/tunnel_client.py \
  --server ngrok.424th.com \
  --api-key YOUR_API_KEY \
  --port 5000 \
  --host 192.168.1.100 \
  --https
```

## How It Works

### 1. Client Creates Tunnel

Client calls `POST /api/tunnels/create` with API key:
- Server generates unique `tunnel_id` and `auth_token`
- Returns public URL: `https://ngrok.424th.com/{tunnel_id}`

### 2. Client Connects via WebSocket

Client connects to `wss://ngrok.424th.com/api/tunnel/connect/{tunnel_id}`:
- Sends `auth_token` for authentication
- Server registers WebSocket connection in tunnel registry
- Heartbeat keeps connection alive

### 3. User Makes HTTP Request

User accesses `https://ngrok.424th.com/{tunnel_id}/api/users`:
- Traefik routes to tunnel server
- Server looks up `tunnel_id` in registry
- Server serializes HTTP request (method, headers, body, path)
- Server sends request to client via WebSocket

### 4. Client Proxies to Local Service

Client receives request via WebSocket:
- Deserializes HTTP request
- Makes request to `http://localhost:PORT/api/users`
- Serializes HTTP response
- Sends response back via WebSocket

### 5. Server Returns Response

Server receives response via WebSocket:
- Deserializes HTTP response
- Returns to original requester
- User receives response as if from ngrok.424th.com

## Security Considerations

1. **API Authentication**: All control plane endpoints require API key
2. **Tunnel Authentication**: Each tunnel has unique auth token
3. **Rate Limiting**: Built-in rate limiting prevents abuse
4. **Timeouts**: Request timeout prevents hung connections
5. **HTTPS**: All traffic encrypted via Cloudflare → Traefik TLS
6. **Automatic Cleanup**: Inactive tunnels auto-deleted

## Troubleshooting

### Client Can't Connect

```bash
# Check server is running
curl https://ngrok.424th.com/health

# Verify API key is correct
# Check .env or kubernetes-config.yaml secrets

# Check tunnel exists
curl -H "x-api-key: YOUR_API_KEY" https://ngrok.424th.com/api/tunnels/list
```

### Tunnel Not Proxying

```bash
# Check tunnel status
curl -H "x-api-key: YOUR_API_KEY" \
  https://ngrok.424th.com/api/tunnels/{tunnel_id}/status

# Verify local service is running
curl http://localhost:3000

# Check client logs for errors
```

### Server Logs

```bash
# Kubernetes
kubectl logs -n tunnel-server deployment/tunnel-server -f

# Docker
docker logs -f tunnel-server

# Local
# Check logs/ directory
tail -f logs/system.log
tail -f logs/tunnel.log
```

## Future Enhancements

- [ ] Traffic inspection dashboard (web UI)
- [ ] Custom subdomains (e.g., `my-app.ngrok.424th.com`)
- [ ] TCP tunneling support (non-HTTP protocols)
- [ ] Multi-pod scaling with Redis-backed registry
- [ ] Request replay for debugging
- [ ] Webhook payload storage and inspection
- [ ] IP whitelisting per tunnel
- [ ] Password protection per tunnel

## License

MIT

## Support

For issues, questions, or contributions, please contact your infrastructure team.
