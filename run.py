import uvicorn
import socket
import sys

def find_available_port(start_port=8000, max_attempts=10):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available ports found between {start_port} and {start_port + max_attempts}")

if __name__ == "__main__":
    try:
        # Try to use port 8000 first
        port = 8000
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
        except OSError:
            print(f"⚠️  Port {port} is in use. Finding available port...")
            port = find_available_port()
            print(f"✅ Using port {port}")
        
        print(f"🚀 Starting Niya FastAPI Template on http://localhost:{port}")
        print(f"📚 API Documentation: http://localhost:{port}/docs")
        print(f"🔄 Auto-reload enabled")
        print("Press Ctrl+C to stop the server")
        
        uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1) 