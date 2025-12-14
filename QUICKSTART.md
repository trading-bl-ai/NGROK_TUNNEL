# Quick Start Guide

Get your tunnel server running in 5 minutes!

## Local Development Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy example environment
cp .env.example .env

# .env is already configured for local development
# You can edit it if needed
```

### Step 3: Start the Tunnel Server

```bash
python initialize_main.py
```

You should see:
```
============================================================
Initializing TUNNEL_SERVER v1.0.0
Environment: LOCAL
============================================================
Starting server in development mode (direct run)
Starting API server on localhost:8989
INFO:     Started server process
INFO:     Uvicorn running on http://localhost:8989
```

### Step 4: Test Server is Running

Open a new terminal:

```bash
# Health check
curl http://localhost:8989/health

# Should return:
# {"status":"healthy","app":"TUNNEL_SERVER","version":"v1.0.0","environment":"LOCAL"}

# API info
curl http://localhost:8989/api
```

### Step 5: Start Test Application

Open another terminal and start the test server:

```bash
python test_server.py
```

You should see:
```
============================================================
Test Server Running on http://localhost:3000
============================================================
```

### Step 6: Create a Tunnel

Open another terminal and start the tunnel client:

```bash
python client/tunnel_client.py \
  --server localhost:8989 \
  --api-key dev-api-key-12345678901234567890 \
  --port 3000 \
  --name "my-test-server"
```

You should see:
```
[14:23:45] Creating tunnel...
[14:23:45] ✓ Tunnel created successfully!
[14:23:45] Tunnel ID: abc12345
[14:23:45] Public URL: http://localhost:8989/abc12345

[14:23:46] ✓ Connected to tunnel server!
[14:23:46] Forwarding: http://localhost:8989/abc12345 -> http://localhost:3000

[14:23:46] Tunnel is active. Press Ctrl+C to stop.
```

### Step 7: Test the Tunnel!

Open another terminal and test the tunnel:

```bash
# Replace abc12345 with your actual tunnel_id from Step 6
TUNNEL_ID=abc12345

# Test GET request
curl http://localhost:8989/$TUNNEL_ID/

# Test with path
curl http://localhost:8989/$TUNNEL_ID/api/users

# Test POST request
curl -X POST http://localhost:8989/$TUNNEL_ID/api/data \
  -H "Content-Type: application/json" \
  -d '{"name":"test","value":123}'

# Test PUT request
curl -X PUT http://localhost:8989/$TUNNEL_ID/api/update

# Test DELETE request
curl -X DELETE http://localhost:8989/$TUNNEL_ID/api/remove
```

You should see:
- Tunnel client showing proxied requests
- Test server showing received requests
- Responses returned through the tunnel

## What's Happening?

```
Your curl → Tunnel Server → WebSocket → Tunnel Client → Test Server (localhost:3000)
                                                               ↓
Your curl ← Tunnel Server ← WebSocket ← Tunnel Client ← Response
```

## Management API

### List All Tunnels

```bash
curl -H "x-api-key: dev-api-key-12345678901234567890" \
  http://localhost:8989/api/tunnels/list
```

### Get Tunnel Status

```bash
curl -H "x-api-key: dev-api-key-12345678901234567890" \
  http://localhost:8989/api/tunnels/$TUNNEL_ID/status
```

### Delete Tunnel

```bash
curl -X DELETE \
  -H "x-api-key: dev-api-key-12345678901234567890" \
  http://localhost:8989/api/tunnels/$TUNNEL_ID
```

## Troubleshooting

### "Tunnel not found" error

Make sure you're using the correct tunnel_id from the client output.

### "Tunnel not active" error

The tunnel client must be running and connected. Check the client terminal for errors.

### "Connection refused" on localhost:3000

Make sure the test server (or your application) is running on port 3000.

### Client can't authenticate

Check that the API key in the client command matches the `REQUIRED_MATCHING_KEY` in `.env`.

## Next Steps

1. **Try with your own app**: Stop the test server and start your actual application on port 3000 (or any port)
2. **Multiple tunnels**: Run multiple clients on different ports
3. **Production deployment**: See README.md for Kubernetes deployment instructions

## Stopping Everything

```bash
# Stop tunnel client: Ctrl+C in client terminal
# Stop test server: Ctrl+C in test server terminal
# Stop tunnel server: Ctrl+C in server terminal
```

## Production Deployment

See [README.md](README.md) for complete Kubernetes deployment instructions with:
- Docker build
- Kubernetes manifests
- Traefik ingress configuration
- Production configuration
