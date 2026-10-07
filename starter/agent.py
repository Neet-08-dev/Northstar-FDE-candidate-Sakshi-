import argparse
import asyncio
import json
import logging
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

from northstar.http import request_json

from .orchestration import process_async


def process(payload, include_message=False):
    return asyncio.run(process_async(payload, include_message=include_message))


# Local demo administration only: the presenter chooses which synthetic customer
# the fresh session belongs to. Identity reaches the agent solely through the
# session actor; request text never selects or widens it.
DEFAULT_DEMO_CUSTOMER = "C001"
_catalog_lock = threading.Lock()
_catalog_cache: dict[str, dict] = {}


def demo_catalog(api_url, admin_token):
    """Summarize each synthetic customer's records from an admin snapshot."""
    with _catalog_lock:
        if api_url not in _catalog_cache:
            session = request_json(
                api_url + "/admin/sessions", {"request_id": str(uuid.uuid4())}, admin_token
            )
            try:
                data = request_json(
                    api_url + "/admin/sessions/" + session["session_id"] + "/snapshot",
                    token=admin_token,
                )["initial"]
            finally:
                request_json(
                    api_url + "/admin/sessions/" + session["session_id"],
                    token=admin_token,
                    method="DELETE",
                )
            fields = {
                "sites": ["id", "name", "access_window"],
                "assets": ["id", "label", "site_id", "required_skill"],
                "tickets": ["id", "summary", "severity", "status", "asset_id"],
                "invoices": ["id", "ticket_id", "total_cents", "currency", "status"],
                "contacts": ["id", "name", "authorized"],
            }
            customers = [
                {
                    "id": customer["id"],
                    "name": customer["name"],
                    "tier": customer["tier"],
                    "account_status": customer["account_status"],
                    **{
                        collection: [
                            {key: row.get(key) for key in keys}
                            for row in data.get(collection, [])
                            if row.get("customer_id") == customer["id"]
                        ]
                        for collection, keys in fields.items()
                    },
                }
                for customer in sorted(data["customers"], key=lambda c: c["id"])
            ]
            _catalog_cache[api_url] = {
                "default": DEFAULT_DEMO_CUSTOMER,
                "customers": customers,
            }
        return _catalog_cache[api_url]


# Demo follow-ups keep one synthetic session per conversation, so a later turn sees
# what an earlier turn did. Sessions expire, are capped and are freed on /demo/end.
DEMO_SESSION_TTL = 30 * 60
DEMO_SESSION_LIMIT = 20
_sessions_lock = threading.Lock()
_demo_sessions: dict[str, dict] = {}


def _valid_conversation_id(value) -> bool:
    return (
        isinstance(value, str)
        and 8 <= len(value) <= 64
        and all(ch.isalnum() or ch == "-" for ch in value)
    )


def _delete_session(api_url, admin_token, session_id):
    try:
        request_json(api_url + "/admin/sessions/" + session_id, token=admin_token, method="DELETE")
    except Exception:
        pass


def _expire_sessions(api_url, admin_token):
    now = time.monotonic()
    with _sessions_lock:
        stale = [k for k, v in _demo_sessions.items() if v["expires"] < now]
        oldest = sorted(
            (k for k in _demo_sessions if k not in stale),
            key=lambda k: _demo_sessions[k]["expires"],
        )
        stale += oldest[: max(0, len(oldest) - DEMO_SESSION_LIMIT + 1)]
        removed = [_demo_sessions.pop(k) for k in stale]
    for entry in removed:
        _delete_session(api_url, admin_token, entry["session"]["session_id"])


def _conversation_session(api_url, admin_token, conversation_id, config, customer_id):
    """Reuse this conversation's session for the same customer, or start a new one."""
    _expire_sessions(api_url, admin_token)
    with _sessions_lock:
        entry = _demo_sessions.get(conversation_id)
        if entry and entry["customer_id"] == customer_id:
            entry["expires"] = time.monotonic() + DEMO_SESSION_TTL
            return entry["session"]
    session = request_json(api_url + "/admin/sessions", config, admin_token)
    with _sessions_lock:
        previous = _demo_sessions.pop(conversation_id, None)
        _demo_sessions[conversation_id] = {
            "session": session,
            "customer_id": customer_id,
            "expires": time.monotonic() + DEMO_SESSION_TTL,
        }
    if previous:
        _delete_session(api_url, admin_token, previous["session"]["session_id"])
    return session


def _demo_history(value) -> list[dict]:
    """Earlier turns from the dashboard: untrusted text, bounded like the request."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Invalid history")
    return [
        {key: str(turn.get(key, ""))[:4000] for key in ("subject", "body", "reply")}
        for turn in value[-4:]
        if isinstance(turn, dict)
    ]


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
        if self.path == "/demo/customers":
            admin_token = os.environ.get("ADMIN_TOKEN", "")
            if not admin_token:
                return self.respond(403, {"error": "Demo disabled during private grading"})
            try:
                api_url = os.environ.get("API_URL", "http://localhost:8001")
                return self.respond(200, demo_catalog(api_url, admin_token))
            except Exception:
                return self.respond(502, {"error": "Demo customers unavailable"})
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
            if self.path == "/demo/end":
                admin_token = os.environ.get("ADMIN_TOKEN", "")
                if not admin_token:
                    return self.respond(403, {"error": "Demo disabled during private grading"})
                if not _valid_conversation_id(payload.get("conversation_id")):
                    return self.respond(400, {"error": "Unknown conversation"})
                with _sessions_lock:
                    entry = _demo_sessions.pop(payload["conversation_id"], None)
                if entry:
                    _delete_session(
                        os.environ.get("API_URL", "http://localhost:8001"),
                        admin_token,
                        entry["session"]["session_id"],
                    )
                return self.respond(200, {"ended": bool(entry)})
            if self.path == "/demo":
                admin_token = os.environ.get("ADMIN_TOKEN", "")
                if not admin_token:
                    return self.respond(403, {"error": "Demo disabled during private grading"})
                api_url = os.environ.get("API_URL", "http://localhost:8001")
                config: dict = {"request_id": str(uuid.uuid4())}
                conversation_id = payload.get("conversation_id")
                if conversation_id is not None and not _valid_conversation_id(conversation_id):
                    return self.respond(400, {"error": "Unknown conversation"})
                history = _demo_history(payload.get("history"))
                customer_id = DEFAULT_DEMO_CUSTOMER
                if "customer_id" in payload:
                    customer_id = payload["customer_id"]
                    known = {c["id"] for c in demo_catalog(api_url, admin_token)["customers"]}
                    if not isinstance(customer_id, str) or customer_id not in known:
                        return self.respond(400, {"error": "Unknown demo customer"})
                    config["actor"] = {
                        "role": "customer",
                        "customer_ids": [customer_id],
                        "verified": True,
                    }
                if conversation_id:
                    session = _conversation_session(
                        api_url, admin_token, conversation_id, config, customer_id
                    )
                else:
                    session = request_json(api_url + "/admin/sessions", config, admin_token)
                task = {
                    "api_url": api_url,
                    "session_token": session["session_token"],
                    "run_id": str(uuid.uuid4()),
                    "request": {
                        "id": "demo",
                        "subject": payload.get("subject", ""),
                        "body": payload["body"],
                    },
                }
                if history:
                    task["conversation"] = history
                try:
                    return self.respond(200, process(task, include_message=True))
                finally:
                    if not conversation_id:
                        _delete_session(api_url, admin_token, session["session_id"])
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
