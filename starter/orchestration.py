"""SDK interpretation and scoped investigation, followed by deterministic execution."""

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from agents import Agent, ModelSettings, OpenAIResponsesModel, RunConfig, Runner, function_tool
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

from .actions import SAFETY_REPLY, Actions, Decision, Outcome
from .backend import Backend, Record

log = logging.getLogger("northstar.agent")
Interpreter = Callable[[Record, Backend, Record, Record, Record], Awaitable[Decision]]


async def interpret(
    payload: Record, backend: Backend, context: Record, policy: Record, usage: Record
) -> Decision:
    model_name = os.environ.get("OPENAI_MODEL", "gpt-6-luna")
    usage.update(
        model=model_name,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        pricing_source="unknown",
    )
    fields = {
        "id",
        "customer_id",
        "site_id",
        "asset_id",
        "name",
        "label",
        "status",
        "required_skill",
        "timezone",
    }

    @function_tool(failure_error_function=None)
    async def inspect_records(collection: Literal["tickets", "sites", "assets"], query: str) -> str:
        """Find scoped records to resolve an ambiguous ticket, site or equipment description.

        Args:
            collection: Kind of record to inspect.
            query: Search term, or empty to list scoped records.
        """
        rows = await backend.search(collection, query[:200])
        return json.dumps(
            {
                "records": [{k: v for k, v in row.items() if k in fields} for row in rows[:40]],
                "truncated": len(rows) > 40,
            }
        )

    async with AsyncOpenAI(max_retries=0, timeout=20) as client:
        agent = Agent(
            name="Northstar service interpreter",
            instructions=Path(__file__).with_name("prompts").joinpath("assistant.md").read_text(),
            model=OpenAIResponsesModel(model_name, client),
            model_settings=ModelSettings(
                reasoning=Reasoning(effort="low"),
                max_tokens=1600,
                parallel_tool_calls=False,
                store=False,
            ),
            tools=[inspect_records],
            output_type=Decision,
        )
        # The immutable context is separately labeled; the request remains user data.
        result = await Runner.run(
            agent,
            json.dumps(
                {
                    "trusted_context": {"now": context["now"]},
                    "current_policy": policy["rules"],
                    "untrusted_request": payload["request"],
                }
            ),
            max_turns=8,
            run_config=RunConfig(tracing_disabled=True),
        )
    counted = result.context_wrapper.usage
    usage.update(input_tokens=counted.input_tokens, output_tokens=counted.output_tokens)
    return Decision.model_validate(result.final_output)


def validate_payload(payload: Record) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Expected request object")
    for key in ["api_url", "session_token", "run_id"]:
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ValueError("Missing request configuration")
    url = urlsplit(payload["api_url"])
    if (
        url.scheme not in {"http", "https"}
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ValueError("Invalid tool URL")
    request = payload.get("request")
    if not isinstance(request, dict) or any(
        not isinstance(request.get(k), str) for k in ["id", "subject", "body"]
    ):
        raise ValueError("Invalid request fields")
    if len(request["subject"]) + len(request["body"]) > 16000:
        raise ValueError("Request text exceeds limit")


async def process_async(payload: Record, interpreter: Interpreter | None = None) -> Record:
    start = time.monotonic()
    validate_payload(payload)
    backend = Backend(payload["api_url"], payload["session_token"], start + 55)
    usage: Record = {
        "model": "none",
        "input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0,
        "pricing_source": "No model calls",
    }
    actions: Actions | None = None
    request_text = payload["request"]["subject"] + "\n" + payload["request"]["body"]
    emergency = bool(
        re.search(r"\b(smoke|sparks|shock|burning smell|gas smell)\b", request_text, re.IGNORECASE)
    )
    outcome = Outcome("error", "The request could not be investigated. Please contact operations.")
    try:
        async with asyncio.timeout(max(0.1, backend.remaining() - 5)):
            context = await backend.call("get_context")
            policy = await backend.call("get_policy")
            backend.remember("policy", policy["rules"]["version"])
            actions = Actions(backend, context, policy)
            text = payload["request"]["subject"] + "\n" + payload["request"]["body"]
            signals = policy["rules"]["safety"]["emergency_signals"]
            # Conservative early screen; semantic hazard detection also runs in the model.
            if any(re.search(r"\b" + re.escape(s) + r"\b", text, re.IGNORECASE) for s in signals):
                outcome = await actions.handle(Decision(intent="hazard"))
            elif not context["actor"].get("verified"):
                outcome = await actions.handoff(
                    "identity",
                    "Requester identity must be verified before accessing service records.",
                )
            else:
                decision = await (interpreter or interpret)(
                    payload, backend, context, policy, usage
                )
                outcome = await actions.handle(decision)
    except Exception as exc:
        # Record only exception type; provider errors can contain request text or credentials.
        log.warning(json.dumps({"event": "processing_failed", "error_type": type(exc).__name__}))
        if usage["model"] != "none" and usage["input_tokens"] is None:
            usage["provider_error"] = type(exc).__name__
        if emergency and actions is None:
            outcome = Outcome(
                "error",
                SAFETY_REPLY
                + " The safety handoff could not be confirmed. Please contact operations directly.",
            )
        headers = getattr(getattr(exc, "response", None), "headers", {})
        limits = {
            k: headers[k]
            for k in [
                "retry-after",
                "x-ratelimit-limit-requests",
                "x-ratelimit-remaining-requests",
                "x-ratelimit-reset-requests",
                "x-ratelimit-limit-tokens",
                "x-ratelimit-remaining-tokens",
                "x-ratelimit-reset-tokens",
            ]
            if k in headers
        }
        if limits:
            log.warning(json.dumps({"event": "provider_limits", "limits": limits}))
        if actions:
            outcome = await actions.handoff(
                "operations",
                "The request could not be completed because processing was unavailable. Operations must reconcile any uncertain action.",
            )
    finally:
        await backend.close()
    result = {
        "status": outcome.status,
        "summary": outcome.reply,
        "reply": outcome.reply,
        "evidence": backend.evidence,
        "usage": usage,
    }
    log.info(
        json.dumps(
            {
                "event": "request_finished",
                "run_id": payload["run_id"],
                "status": outcome.status,
                "attempts": backend.attempts,
                "duration_ms": round((time.monotonic() - start) * 1000),
                "usage": usage,
            }
        )
    )
    return result
