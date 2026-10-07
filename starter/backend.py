"""Request-scoped transport; every retry preserves the complete operation."""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

import httpx

log = logging.getLogger("northstar.agent")
Record = dict[str, Any]


class BackendError(Exception):
    def __init__(self, code: str, retryable: bool = False):
        super().__init__(code)
        self.code, self.retryable = code, retryable


class Backend:
    def __init__(self, api_url: str, token: str, deadline: float, max_attempts: int = 48):
        self.http = httpx.AsyncClient(
            base_url=api_url.rstrip("/") + "/",
            headers={"Authorization": "Bearer " + token},
            follow_redirects=False,
            trust_env=False,
        )
        self.deadline, self.max_attempts = deadline, max_attempts
        self.attempts = 0
        self.evidence: list[dict[str, str]] = []

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def remember(self, collection: str, record_id: str) -> None:
        ref = {"collection": collection, "record_id": record_id}
        if ref not in self.evidence:
            self.evidence.append(ref)

    async def call(self, tool: str, *, recovery: bool = False, **arguments: Any) -> Record:
        # Reserve three attempts and five seconds for an operational handoff.
        limit = self.max_attempts if recovery else self.max_attempts - 3
        reserve = 0 if recovery else 5
        frozen = json.dumps({"arguments": arguments}, sort_keys=True)
        for attempt in range(3):
            remaining = self.remaining() - reserve
            if self.attempts >= limit or remaining <= 0.1:
                raise BackendError("BUDGET_EXHAUSTED")
            self.attempts += 1
            start = time.monotonic()
            code = "OK"
            try:
                async with asyncio.timeout(min(5.0, remaining)):
                    response = await self.http.post(
                        "v1/tools/" + tool,
                        content=frozen,
                        headers={"Content-Type": "application/json"},
                        timeout=min(5.0, remaining),
                    )
                try:
                    body = response.json()
                except ValueError:
                    raise BackendError("INVALID_TOOL_RESPONSE") from None
                if response.status_code != 200:
                    detail = body.get("error", {}) if isinstance(body, dict) else {}
                    raise BackendError(
                        detail.get("code", "HTTP_ERROR"),
                        detail.get("retryable", False) is True
                        or response.status_code in {429, 502, 503, 504},
                    )
                if not isinstance(body, dict) or not isinstance(body.get("result"), dict):
                    raise BackendError("INVALID_TOOL_RESPONSE")
                return body["result"]
            except (httpx.TransportError, TimeoutError):
                code = "TRANSPORT_UNCERTAIN"
                if attempt == 2:
                    raise BackendError(code) from None
            except BackendError as exc:
                code = exc.code
                if not exc.retryable or attempt == 2:
                    raise
            finally:
                log.info(
                    json.dumps(
                        {
                            "event": "tool",
                            "tool": tool,
                            "attempt": self.attempts,
                            "result": code,
                            "duration_ms": round((time.monotonic() - start) * 1000),
                        }
                    )
                )
            await asyncio.sleep(min(0.1 * 2**attempt, max(0, self.remaining() - reserve)))
        raise BackendError("RETRIES_EXHAUSTED")

    async def search(self, collection: str, query: str = "") -> list[Record]:
        result = await self.call("search_records", collection=collection, query=query)
        rows = result["records"]
        if not isinstance(rows, list):
            raise BackendError("INVALID_TOOL_RESPONSE")
        for row in rows:
            self.remember(collection, row["id"])
        return rows

    async def record(self, collection: str, record_id: str) -> Record:
        # Resolve within the scoped collection before attempting a direct lookup.
        if not any(row["id"] == record_id for row in await self.search(collection, record_id)):
            raise BackendError("RECORD_UNAVAILABLE")
        row = await self.call("get_record", collection=collection, record_id=record_id)
        self.remember(collection, row["id"])
        return row

    async def close(self) -> None:
        await self.http.aclose()


def operation_key(request_id: str, tool: str, arguments: Record) -> str:
    content = json.dumps([request_id, tool, arguments], sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()
