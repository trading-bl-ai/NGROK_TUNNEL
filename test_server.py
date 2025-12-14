"""
Simple test server for testing the tunnel
Run with: python test_server.py
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime


class TestHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for testing"""

    def do_GET(self):
        """Handle GET requests"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response = {
            "message": "Hello from test server!",
            "path": self.path,
            "method": "GET",
            "timestamp": datetime.now().isoformat(),
            "headers": dict(self.headers)
        }

        self.wfile.write(json.dumps(response, indent=2).encode())
        print(f"[GET] {self.path}")

    def do_POST(self):
        """Handle POST requests"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        try:
            body_json = json.loads(body) if body else {}
        except json.JSONDecodeError:
            body_json = {"raw": body}

        response = {
            "message": "Received POST request",
            "path": self.path,
            "method": "POST",
            "timestamp": datetime.now().isoformat(),
            "body": body_json,
            "headers": dict(self.headers)
        }

        self.wfile.write(json.dumps(response, indent=2).encode())
        print(f"[POST] {self.path} - Body: {body[:100]}")

    def do_PUT(self):
        """Handle PUT requests"""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response = {
            "message": "Received PUT request",
            "path": self.path,
            "method": "PUT",
            "timestamp": datetime.now().isoformat()
        }

        self.wfile.write(json.dumps(response, indent=2).encode())
        print(f"[PUT] {self.path}")

    def do_DELETE(self):
        """Handle DELETE requests"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        response = {
            "message": "Received DELETE request",
            "path": self.path,
            "method": "DELETE",
            "timestamp": datetime.now().isoformat()
        }

        self.wfile.write(json.dumps(response, indent=2).encode())
        print(f"[DELETE] {self.path}")

    def log_message(self, format, *args):
        """Override to suppress default logging"""
        pass


def run_server(port=3000):
    """Run the test server"""
    server_address = ("", port)
    httpd = HTTPServer(server_address, TestHandler)

    print("="*60)
    print(f"Test Server Running on http://localhost:{port}")
    print("="*60)
    print()
    print("This server will respond to all HTTP methods (GET, POST, PUT, DELETE)")
    print("Use this to test your tunnel connection.")
    print()
    print("Example endpoints:")
    print(f"  - http://localhost:{port}/")
    print(f"  - http://localhost:{port}/api/users")
    print(f"  - http://localhost:{port}/test/path")
    print()
    print("Press Ctrl+C to stop the server")
    print("="*60)
    print()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.shutdown()


if __name__ == "__main__":
    import sys

    port = 3000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}")
            sys.exit(1)

    run_server(port)
