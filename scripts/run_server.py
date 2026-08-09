import os
import sys
import subprocess
import threading
import time
import json
import logging
import urllib.request
from typing import Optional
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [MAIN] %(message)s",
)

from agents.security.log_redaction import install_secret_redaction
install_secret_redaction()

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

BOT_DIAG = {
    "intake_getme_ok": False,
    "intake_bot_username": None,
    "intake_bot_id": None,
    "studio_getme_ok": False,
    "studio_bot_username": None,
    "studio_bot_id": None,
    "same_bot_tokens": False,
    "last_startup_message_ok": None,
    "last_startup_message_error": None,
    "last_intake_update_ts": None,
    "last_studio_update_ts": None
}


def fetch_bot_getme(token: str) -> Optional[dict]:
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ElinaDiagnostics"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                if data.get("ok"):
                    return data.get("result")
    except Exception as e:
        logger.error(f"Failed to fetch getMe for bot: {e}")
    return None


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
        elif self.path == "/diag":
            intake_last_update = None
            intake_last_update_path = "/tmp/elina_intake_last_update.json"
            if os.path.exists(intake_last_update_path):
                try:
                    with open(intake_last_update_path, "r") as f:
                        intake_last_update = json.load(f).get("timestamp")
                except Exception:
                    pass

            studio_last_update = None
            studio_last_update_path = "/tmp/elina_studio_last_update.json"
            if os.path.exists(studio_last_update_path):
                try:
                    with open(studio_last_update_path, "r") as f:
                        studio_last_update = json.load(f).get("timestamp")
                except Exception:
                    pass

            startup_ok = None
            startup_error = None
            studio_startup_path = "/tmp/elina_studio_startup.json"
            if os.path.exists(studio_startup_path):
                try:
                    with open(studio_startup_path, "r") as f:
                        startup_data = json.load(f)
                        startup_ok = startup_data.get("ok")
                        startup_error = startup_data.get("error")
                except Exception:
                    pass

            body = {
                "intake": {
                    "getme_ok": BOT_DIAG["intake_getme_ok"],
                    "bot_username": BOT_DIAG["intake_bot_username"],
                    "bot_id": BOT_DIAG["intake_bot_id"],
                    "last_update_ts": intake_last_update
                },
                "studio": {
                    "getme_ok": BOT_DIAG["studio_getme_ok"],
                    "bot_username": BOT_DIAG["studio_bot_username"],
                    "bot_id": BOT_DIAG["studio_bot_id"],
                    "last_update_ts": studio_last_update
                },
                "same_bot_tokens": BOT_DIAG["same_bot_tokens"],
                "startup_message": {
                    "ok": startup_ok,
                    "error": startup_error
                }
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

    intake_token = os.environ.get("INTAKE_BOT_TOKEN", "").strip()
    studio_token = os.environ.get("STUDIO_BOT_TOKEN", "").strip()

    intake_info = fetch_bot_getme(intake_token)
    if intake_info:
        BOT_DIAG["intake_getme_ok"] = True
        BOT_DIAG["intake_bot_username"] = intake_info.get("username")
        BOT_DIAG["intake_bot_id"] = intake_info.get("id")

    studio_info = fetch_bot_getme(studio_token)
    if studio_info:
        BOT_DIAG["studio_getme_ok"] = True
        BOT_DIAG["studio_bot_username"] = studio_info.get("username")
        BOT_DIAG["studio_bot_id"] = studio_info.get("id")

    if BOT_DIAG["intake_bot_id"] and BOT_DIAG["studio_bot_id"]:
        if BOT_DIAG["intake_bot_id"] == BOT_DIAG["studio_bot_id"]:
            BOT_DIAG["same_bot_tokens"] = True

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
