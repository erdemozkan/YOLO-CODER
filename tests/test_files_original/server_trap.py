# server_trap.py
import http.server
import socketserver

PORT = 8080

Handler = http.server.SimpleHTTPRequestHandler

print(f"🚀 Attempting to start server on port {PORT}...")

# This will CRASH if something (like netcat) is already on port 8080
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"✅ Serving at port {PORT}")
    httpd.serve_forever()