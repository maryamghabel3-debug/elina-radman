import os
import sys
import subprocess
import threading
import time
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MAIN] %(message)s",
)
logger = logging.getLogger("ElinaServer")

REQUIRED_ENV = [
    "INTAKE_BOT_TOKEN",
    "STUDIO_BOT_TOKEN",
    "OWNER_CHAT_ID",
    "SUPABASE_URL",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_BUCKET_NAME",
]

_processes = {}
_start_times = {}


def check_env():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    logger.info("Environment variable check:")
    for k in REQUIRED_ENV:
        present = "YES" if os.environ.get(k) else "NO"
        logger.info(f"  {k}: {present}")
    if missing:
        logger.error(f"MISSING ENV VARS: {missing}")
        logger.error("Bots that depend on missing vars will not start correctly.")
    return missing


def stream_output(name, proc):
    prefix = f"[{name}]"
    for line in iter(proc.stdout.readline, b""):
        try:
            text = line.decode(errors="replace").rstrip()
        except Exception:
            text = str(line)
        print(f"{prefix} {text}", flush=True)
    proc.stdout.close()


def start_bot(name, script_path):
    logger.info(f"Starting {name} from {script_path}...")
    try:
        proc = subprocess.Popen(
            [sys.executable, "-u", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        _processes[name] = proc
        _start_times[name] = time.time()
        t = threading.Thread(target=stream_output, args=(name, proc), daemon=True)
        t.start()
        return proc
    except Exception as e:
        logger.error(f"Failed to start {name}: {e}")
        return None


def watch_bot_health(name):
    def _watch():
        time.sleep(15)
        proc = _processes.get(name)
        if proc is None:
            return
        if proc.poll() is not None:
            logger.error(
                f"❌ {name} crashed within 15s (exit code {proc.returncode}). "
                f"See [{name}] lines above for reason."
            )
        else:
            logger.info(f"✅ {name} still alive after 15s")
    threading.Thread(target=_watch, daemon=True).start()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status":
            body = {
                "intake_alive": _processes.get("INTAKE") is not None
                and _processes["INTAKE"].poll() is None,
                "studio_alive": _processes.get("STUDIO") is not None
                and _processes["STUDIO"].poll() is None,
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())
            return
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"ElinaOS server is up.")

    def log_message(self, format, *args):
        return


def main():
    check_env()

    start_bot("INTAKE", "scripts/elina_intake_bot.py")
    watch_bot_health("INTAKE")

    start_bot("STUDIO", "scripts/elina_studio_bot.py")
    watch_bot_health("STUDIO")

    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Health server listening on 0.0.0.0:{port}")
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        for name, proc in _processes.items():
            try:
                proc.terminate()
            except Exception:
                pass
        server.server_close()


if __name__ == "__main__":
    main()
