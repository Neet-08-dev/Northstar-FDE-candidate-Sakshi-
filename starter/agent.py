import argparse
import asyncio
import json
import logging
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

from northstar.http import request_json

from .orchestration import process_async


def process(payload):
    return asyncio.run(process_async(payload))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, code, value):
        body = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == "/health":
            return self.respond(200, {"ok": True, "service": "candidate-agent", "protocol": 1})
        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/service_desk.css": ("service_desk.css", "text/css; charset=utf-8"),
            "/service_desk.js": ("service_desk.js", "text/javascript; charset=utf-8"),
        }
        path = urlsplit(self.path).path
        if path in files:
            filename, content_type = files[path]
            body = (Path(__file__).parent / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                "img-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
            self.end_headers()
            self.wfile.write(body)
            return
        self.respond(404, {"error": "Not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2_000_000:
                raise ValueError("Invalid request length")
            payload = json.loads(self.rfile.read(length))
            if self.path == "/process":
                return self.respond(200, process(payload))
            if self.path == "/demo":
                admin_token = os.environ.get("ADMIN_TOKEN", "")
                if not admin_token:
                    return self.respond(403, {"error": "Demo disabled during private grading"})
                api_url = os.environ.get("API_URL", "http://localhost:8001")
                session = request_json(
                    api_url + "/admin/sessions", {"request_id": str(uuid.uuid4())}, admin_token
                )
                try:
                    result = process(
                        {
                            "api_url": api_url,
                            "session_token": session["session_token"],
                            "run_id": str(uuid.uuid4()),
                            "request": {
                                "id": "demo",
                                "subject": payload.get("subject", ""),
                                "body": payload["body"],
                            },
                        }
                    )
                    return self.respond(200, result)
                finally:
                    request_json(
                        api_url + "/admin/sessions/" + session["session_id"],
                        token=admin_token,
                        method="DELETE",
                    )
            self.respond(404, {"error": "Not found"})
        except Exception:
            self.respond(400, {"error": "Invalid request or unavailable processing."})


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    print("Candidate agent ready on port", args.port, flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
