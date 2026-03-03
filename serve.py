#!/usr/bin/env python3
"""
Simple HTTP server for the icon browser.
"""

import http.server
import socketserver
import webbrowser
import os
from pathlib import Path

def main():
    """Start the HTTP server."""
    # Change to the icon-browser directory
    icon_browser_dir = Path(__file__).parent
    os.chdir(icon_browser_dir)
    
    PORT = 8001
    
    class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            # Add CORS headers to allow local file access
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            super().end_headers()
    
    try:
        with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
            print(f"Serving icon browser at http://localhost:{PORT}")
            print("Press Ctrl+C to stop the server")
            
            # Try to open the browser automatically
            try:
                webbrowser.open(f'http://localhost:{PORT}')
            except:
                pass
            
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"Port {PORT} is already in use. Try a different port or stop the existing server.")
        else:
            print(f"Error starting server: {e}")

if __name__ == "__main__":
    main()
