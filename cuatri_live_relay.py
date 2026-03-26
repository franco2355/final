#!/usr/bin/env python3
"""
Tiny host-side relay for the live cuatri map.

It proxies the JSON exposed by sensores_web inside the `ros2` container and makes it
available on the host with permissive CORS so the local HTML file can poll it.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = os.environ.get("CUATRI_RELAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("CUATRI_RELAY_PORT", "8010"))
CONTAINER = os.environ.get("CUATRI_RELAY_CONTAINER", "ros2")
SOURCE_URL = os.environ.get("CUATRI_RELAY_SOURCE_URL", "http://127.0.0.1:8000/data")
DASHBOARD_HTML = Path(
    os.environ.get(
        "CUATRI_RELAY_DASHBOARD_HTML",
        "/home/franco/german/borrador-sensores/pixhawk_dashboard.html",
    )
)

last_good_payload: str | None = None
last_good_time: float | None = None


def fetch_container_data() -> str:
    command = [
        "docker",
        "exec",
        CONTAINER,
        "python3",
        "-c",
        (
            "import urllib.request; "
            f"print(urllib.request.urlopen('{SOURCE_URL}', timeout=2).read().decode('utf-8'))"
        ),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(stderr or f"relay command failed with code {result.returncode}")
    return result.stdout.strip()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        global last_good_payload, last_good_time

        if self.path in ("/", "/index.html"):
            try:
                html = DASHBOARD_HTML.read_text(encoding="utf-8")
            except Exception as exc:  # noqa: BLE001
                self._send_text(500, f"dashboard unavailable: {exc}")
                return
            self._send_raw(200, "text/html; charset=utf-8", html.encode("utf-8"))
            return

        if self.path == "/health":
            body = {
                "ok": last_good_payload is not None,
                "last_good_epoch": last_good_time,
                "container": CONTAINER,
                "source_url": SOURCE_URL,
            }
            self._send_json(200, body)
            return

        if self.path != "/data":
            self._send_json(404, {"ok": False, "error": "not_found"})
            return

        try:
            payload = fetch_container_data()
            last_good_payload = payload
            last_good_time = time.time()
            self._send_raw_json(200, payload)
        except Exception as exc:  # noqa: BLE001
            if last_good_payload is not None:
                body = json.loads(last_good_payload)
                body["_relay_warning"] = str(exc)
                body["_relay_stale"] = True
                body["_relay_last_good_epoch"] = last_good_time
                self._send_json(200, body)
                return

            self._send_json(
                503,
                {
                    "ok": False,
                    "error": "relay_unavailable",
                    "details": str(exc),
                    "container": CONTAINER,
                    "source_url": SOURCE_URL,
                },
            )

    def _send_raw_json(self, code: int, body: str) -> None:
        self._send_raw(code, "application/json", body.encode("utf-8"))

    def _send_raw(self, code: int, content_type: str, payload: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, code: int, body: dict) -> None:
        self._send_raw_json(code, json.dumps(body))

    def _send_text(self, code: int, body: str) -> None:
        self._send_raw(code, "text/plain; charset=utf-8", body.encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A003
        return


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"cuatri relay listening on http://{HOST}:{PORT}/data", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
