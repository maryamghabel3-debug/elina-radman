import os
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ElinaServer")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ElinaOS Bots are running successfully!")

    def log_message(self, format, *args):
        # Suppress standard HTTP logging to keep console clean
        pass

def main():
    # Start Intake Bot in background
    logger.info("Starting Intake Bot...")
    intake_process = subprocess.Popen([sys.executable, "scripts/elina_intake_bot.py"])

    # Start Studio Bot in background
    logger.info("Starting Studio Bot...")
    studio_process = subprocess.Popen([sys.executable, "scripts/elina_studio_bot.py"])

    # Start dummy HTTP server to satisfy cloud health checks (Render, etc.)
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"Listening on port {port} for health checks...")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.server_close()
        intake_process.terminate()
        studio_process.terminate()

if __name__ == "__main__":
    main()
