# frontend_server.py
from http.server import SimpleHTTPRequestHandler, HTTPServer

# Configuration
# Do not change the PORT setting without changing the backend API CORS settings
PORT = 8002
DIRECTORY = "."  # folder where index.html lives

class MyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

if __name__ == "__main__":
    httpd = HTTPServer(("0.0.0.0", PORT), MyHandler)
    print(f"Serving index.html (user interface) at http://localhost:{PORT}/")
    httpd.serve_forever()
