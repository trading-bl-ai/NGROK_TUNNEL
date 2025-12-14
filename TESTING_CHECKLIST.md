# Testing Checklist

Complete testing checklist for the Tunnel Server implementation.

## ✅ Pre-Deployment Testing (Local)

### 1. Environment Setup
- [ ] Python 3.10+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created and configured
- [ ] All required environment variables set

### 2. Server Startup
```bash
python initialize_main.py
```
- [ ] Server starts without errors
- [ ] Logs show "Starting API server on localhost:8989"
- [ ] No import errors
- [ ] Health endpoint responds: `curl http://localhost:8989/health`
- [ ] API info endpoint responds: `curl http://localhost:8989/api`

### 3. Test Server
```bash
python test_server.py
```
- [ ] Test server starts on port 3000
- [ ] Responds to requests: `curl http://localhost:3000/`
- [ ] Returns JSON response

### 4. Tunnel Client Connection
```bash
python client/tunnel_client.py \
  --server localhost:8989 \
  --api-key dev-api-key-12345678901234567890 \
  --port 3000
```
- [ ] Tunnel created successfully
- [ ] Tunnel ID displayed
- [ ] Public URL displayed
- [ ] WebSocket connected
- [ ] No connection errors

### 5. Basic HTTP Proxying

Get the tunnel ID from client output, then test:

```bash
TUNNEL_ID=<your-tunnel-id>

# GET request
curl http://localhost:8989/$TUNNEL_ID/

# Should return response from test_server.py
```

**Verify:**
- [ ] Request appears in client logs
- [ ] Request appears in test server logs
- [ ] Response returned to curl
- [ ] Response matches test server output
- [ ] Status code is 200

### 6. HTTP Methods Testing

```bash
# POST request
curl -X POST http://localhost:8989/$TUNNEL_ID/api/data \
  -H "Content-Type: application/json" \
  -d '{"name":"test","value":123}'

# PUT request
curl -X PUT http://localhost:8989/$TUNNEL_ID/api/update \
  -H "Content-Type: application/json" \
  -d '{"id":1}'

# DELETE request
curl -X DELETE http://localhost:8989/$TUNNEL_ID/api/delete/1
```

**Verify:**
- [ ] POST request proxied correctly with body
- [ ] PUT request proxied correctly
- [ ] DELETE request proxied correctly
- [ ] All methods logged in client
- [ ] All methods logged in test server
- [ ] Responses returned correctly

### 7. Path Proxying

```bash
# Various paths
curl http://localhost:8989/$TUNNEL_ID/api/users
curl http://localhost:8989/$TUNNEL_ID/api/users/123
curl http://localhost:8989/$TUNNEL_ID/deeply/nested/path/test
```

**Verify:**
- [ ] All paths proxied correctly
- [ ] Test server receives correct paths
- [ ] Query parameters preserved

### 8. Headers & Content

```bash
# Custom headers
curl http://localhost:8989/$TUNNEL_ID/ \
  -H "X-Custom-Header: test-value" \
  -H "Authorization: Bearer token123"
```

**Verify:**
- [ ] Custom headers forwarded to local server
- [ ] Headers visible in test server response
- [ ] Response headers returned to client

### 9. Control API Testing

```bash
API_KEY="dev-api-key-12345678901234567890"

# List tunnels
curl -H "x-api-key: $API_KEY" \
  http://localhost:8989/api/tunnels/list

# Get tunnel status
curl -H "x-api-key: $API_KEY" \
  http://localhost:8989/api/tunnels/$TUNNEL_ID/status

# Create tunnel programmatically
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-tunnel","local_port":3000}' \
  http://localhost:8989/api/tunnels/create

# Delete tunnel
curl -X DELETE \
  -H "x-api-key: $API_KEY" \
  http://localhost:8989/api/tunnels/$TUNNEL_ID
```

**Verify:**
- [ ] List shows active tunnels
- [ ] Status returns correct tunnel info
- [ ] Create returns tunnel_id and auth_token
- [ ] Delete removes tunnel successfully
- [ ] Invalid API key returns 403

### 10. Multiple Tunnels

Start two test servers on different ports:
```bash
# Terminal 1
python -m http.server 3001

# Terminal 2
python -m http.server 3002

# Terminal 3
python client/tunnel_client.py --server localhost:8989 \
  --api-key dev-api-key-12345678901234567890 --port 3001

# Terminal 4
python client/tunnel_client.py --server localhost:8989 \
  --api-key dev-api-key-12345678901234567890 --port 3002
```

**Verify:**
- [ ] Both tunnels connect successfully
- [ ] Each tunnel has unique ID
- [ ] Requests to tunnel 1 go to port 3001
- [ ] Requests to tunnel 2 go to port 3002
- [ ] No cross-tunnel interference

### 11. Error Handling

```bash
# Non-existent tunnel
curl http://localhost:8989/nonexistent/

# Tunnel not connected (create but don't connect)
curl -X POST \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"disconnected"}' \
  http://localhost:8989/api/tunnels/create
# Use returned tunnel_id without connecting client
curl http://localhost:8989/<disconnected-tunnel-id>/

# Local service not running (stop test server)
# Stop test_server.py, then make request through tunnel
curl http://localhost:8989/$TUNNEL_ID/
```

**Verify:**
- [ ] Non-existent tunnel returns 404
- [ ] Disconnected tunnel returns 503
- [ ] Offline local service returns 502
- [ ] Error messages are clear
- [ ] Client logs show appropriate errors

### 12. Heartbeat & Keepalive

```bash
# Keep tunnel connected for 60+ seconds
# Watch client logs for heartbeat messages
```

**Verify:**
- [ ] Ping/pong messages exchanged
- [ ] Connection stays alive
- [ ] No unexpected disconnects
- [ ] Last active timestamp updates

### 13. Reconnection

```bash
# Stop client (Ctrl+C)
# Wait 5 seconds
# Restart same client with same tunnel ID
```

**Verify:**
- [ ] Client disconnects cleanly
- [ ] Tunnel status shows disconnected
- [ ] Client can create new tunnel
- [ ] New tunnel works correctly

### 14. Rate Limiting

```bash
# Send many requests rapidly
for i in {1..15}; do
  curl http://localhost:8989/ &
done
wait
```

**Verify:**
- [ ] Some requests return 429 (Too Many Requests)
- [ ] Rate limit messages appear in logs
- [ ] Server doesn't crash

### 15. Cleanup

```bash
# Stop all clients
# Wait 120 seconds (2x TUNNEL_TIMEOUT_SECONDS)
# Check tunnel list
curl -H "x-api-key: $API_KEY" \
  http://localhost:8989/api/tunnels/list
```

**Verify:**
- [ ] Inactive tunnels cleaned up
- [ ] Cleanup logs appear
- [ ] Memory doesn't leak

---

## ✅ Docker Testing

### 1. Build Image
```bash
docker build -t tunnel-server:test .
```
- [ ] Build succeeds
- [ ] No errors in build output
- [ ] Image size reasonable (<500MB)

### 2. Run Container
```bash
docker run -d --name tunnel-test \
  -p 8989:8989 \
  --env-file .env \
  tunnel-server:test
```
- [ ] Container starts
- [ ] Health check passes: `docker ps` shows "healthy"
- [ ] Logs look correct: `docker logs tunnel-test`

### 3. Test in Container
```bash
# Health check
curl http://localhost:8989/health

# Start client
python client/tunnel_client.py --server localhost:8989 \
  --api-key dev-api-key-12345678901234567890 --port 3000
```
- [ ] Health check responds
- [ ] Tunnel connects
- [ ] Proxying works
- [ ] No connectivity issues

### 4. Cleanup
```bash
docker stop tunnel-test
docker rm tunnel-test
docker rmi tunnel-server:test
```

---

## ✅ Kubernetes Testing (Production)

### 1. Apply Manifests
```bash
kubectl apply -f kubernetes-config.yaml
```
- [ ] Namespace created
- [ ] ConfigMap created
- [ ] Secret created
- [ ] Deployment created
- [ ] Service created
- [ ] IngressRoute created

### 2. Check Deployment
```bash
kubectl get all -n tunnel-server
kubectl get pods -n tunnel-server
```
- [ ] Pod running
- [ ] 1/1 ready
- [ ] No crashes or restarts
- [ ] Age shows recent deployment

### 3. Check Logs
```bash
kubectl logs -n tunnel-server deployment/tunnel-server -f
```
- [ ] Application starts
- [ ] No errors
- [ ] Cleanup task started
- [ ] Logs show "Application startup complete"

### 4. Health Check (Internal)
```bash
kubectl exec -n tunnel-server deployment/tunnel-server -- \
  curl http://localhost:8989/health
```
- [ ] Returns 200 OK
- [ ] JSON response correct

### 5. External Access
```bash
# Verify DNS
dig ngrok.424th.com

# Health check
curl https://ngrok.424th.com/health

# API info
curl https://ngrok.424th.com/api
```
- [ ] DNS resolves correctly
- [ ] HTTPS works (Cloudflare + Traefik)
- [ ] Health check responds
- [ ] No certificate errors

### 6. Production Tunnel Test
```bash
# From your laptop/local machine
python client/tunnel_client.py \
  --server ngrok.424th.com \
  --api-key <your-production-api-key> \
  --port 3000 \
  --https
```
- [ ] Tunnel creates successfully
- [ ] WebSocket connects (WSS)
- [ ] Public URL accessible
- [ ] HTTPS works end-to-end

### 7. Production Proxy Test
```bash
# Get tunnel ID from client
# Test from external machine
curl https://ngrok.424th.com/<tunnel-id>/
```
- [ ] Request reaches local service
- [ ] Response returned correctly
- [ ] HTTPS throughout
- [ ] No SSL errors

### 8. Control API (Production)
```bash
API_KEY="<your-production-api-key>"

curl -H "x-api-key: $API_KEY" \
  https://ngrok.424th.com/api/tunnels/list
```
- [ ] API responds
- [ ] Returns tunnel list
- [ ] Authentication works

### 9. Monitoring
```bash
# Watch logs
kubectl logs -n tunnel-server deployment/tunnel-server -f

# Watch pod status
watch kubectl get pods -n tunnel-server

# Check resource usage
kubectl top pods -n tunnel-server
```
- [ ] No error spikes
- [ ] Memory usage stable
- [ ] CPU usage reasonable
- [ ] No pod restarts

### 10. Load Testing (Optional)
```bash
# Send 100 concurrent requests
for i in {1..100}; do
  curl -s https://ngrok.424th.com/<tunnel-id>/ &
done
wait
```
- [ ] All requests succeed or rate-limited
- [ ] No crashes
- [ ] Pod stays healthy
- [ ] Memory doesn't spike excessively

---

## ✅ Security Testing

### 1. Authentication
```bash
# Without API key
curl http://localhost:8989/api/tunnels/list

# With wrong API key
curl -H "x-api-key: wrong-key" \
  http://localhost:8989/api/tunnels/list
```
- [ ] No API key returns 401
- [ ] Wrong API key returns 403

### 2. Tunnel Token
```bash
# Try to connect with wrong token
# Modify client code or use websockets directly
```
- [ ] Wrong token rejected
- [ ] Connection closed with error

### 3. Rate Limiting
- [ ] Excessive requests return 429
- [ ] Rate limits enforced per endpoint

---

## ✅ Documentation Testing

### 1. README Accuracy
- [ ] All commands in README work
- [ ] Examples are correct
- [ ] Code snippets accurate

### 2. QUICKSTART Accuracy
- [ ] Follow QUICKSTART step by step
- [ ] All commands work
- [ ] Can complete in 5 minutes

### 3. Code Comments
- [ ] All modules have docstrings
- [ ] Complex functions documented
- [ ] Type hints present

---

## Final Checklist

- [ ] All local tests pass
- [ ] Docker build and run successful
- [ ] Kubernetes deployment healthy
- [ ] Production tunnel works end-to-end
- [ ] Documentation accurate
- [ ] No security issues
- [ ] Performance acceptable
- [ ] Logs clean and informative
- [ ] Error handling robust
- [ ] Ready for production use

---

## Issue Reporting

If any test fails, document:
1. **Test name**: Which test failed
2. **Expected**: What should happen
3. **Actual**: What actually happened
4. **Logs**: Relevant error messages
5. **Environment**: Local/Docker/K8s
6. **Steps to reproduce**: How to trigger the issue
