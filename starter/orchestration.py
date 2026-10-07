"""SDK interpretation and scoped investigation, followed by deterministic execution."""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from agents import Agent, ModelSettings, OpenAIResponsesModel, RunConfig, Runner, function_tool
from openai import AsyncOpenAI
from openai.types.shared import Reasoning
from pydantic import BaseModel, ConfigDict

from .actions import SAFETY_FALLBACK, Actions, Decision, Outcome, RequestedTime, utc
from .backend import Backend, Record

log = logging.getLogger("northstar.agent")
Interpreter = Callable[[Record, Backend, Record, Record, Record], Awaitable[Decision]]
MODEL = "gpt-6.1-sol"
PROMPTS = Path(__file__).with_name("prompts")


class SafetyScreen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hazard: bool


def resolve_requested_time(requested: RequestedTime, now: str) -> str:
    """Resolve model-read calendar fields using only the request-scoped clock.

    The model decides what the user meant; this only does calendar arithmetic.
    An omitted year means the current calendar year in the requested zone, even
    when that date has passed. Availability checks decide whether it is bookable.
    """
    offset = 330 if requested.utc_offset_minutes is None else requested.utc_offset_minutes
    if not -720 <= offset <= 840:
        raise ValueError("Invalid UTC offset")
    zone = timezone(timedelta(minutes=offset))
    scoped_now = utc(now).astimezone(zone)
    if requested.relative_day != "none":
        if any(v is not None for v in [requested.year, requested.month, requested.day]):
            raise ValueError("Relative day conflicts with a calendar date")
        day = scoped_now.date() + timedelta(days=int(requested.relative_day == "tomorrow"))
    else:
        if requested.month is None or requested.day is None:
            raise ValueError("One calendar date required")
        day = datetime(requested.year or scoped_now.year, requested.month, requested.day).date()
    return (
        datetime.combine(day, datetime.min.time(), zone)
        .replace(hour=requested.hour, minute=requested.minute)
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_time(decision: Decision, context: Record) -> Decision:
    if decision.requested_time is None:
        return decision
    try:
        if decision.time_mode != "exact":
            raise ValueError("Conflicting time modes")
        resolved = resolve_requested_time(decision.requested_time, context["now"])
        if decision.starts_at and utc(decision.starts_at) != utc(resolved):
            raise ValueError("Conflicting instants")
        return decision.model_copy(update={"starts_at": resolved})
    except (ValueError, TypeError, OverflowError):
        return decision.model_copy(update={"time_mode": "unclear", "starts_at": ""})


def model_settings(max_tokens: int) -> ModelSettings:
    return ModelSettings(
        reasoning=Reasoning(effort="low"),
        max_tokens=max_tokens,
        parallel_tool_calls=False,
        store=False,
    )


async def screen_hazard(model: OpenAIResponsesModel, payload: Record, policy: Record) -> Any:
    """A focused model check for physical hazards, independent of the request's other asks."""
    agent = Agent(
        name="Northstar safety screen",
        instructions=PROMPTS.joinpath("safety.md").read_text(),
        model=model,
        model_settings=model_settings(800),
        output_type=SafetyScreen,
    )
    return await Runner.run(
        agent,
        json.dumps(
            {
                "current_safety_policy": policy["rules"].get("safety", {}),
                "untrusted_request": payload["request"],
            }
        ),
        max_turns=1,
        run_config=RunConfig(tracing_disabled=True),
    )


async def interpret_request(
    model: OpenAIResponsesModel,
    payload: Record,
    backend: Backend,
    context: Record,
    policy: Record,
    screened: asyncio.Future[bool],
) -> Any:
    fields = {
        "id",
        "customer_id",
        "site_id",
        "asset_id",
        "name",
        "label",
        "model",
        "address",
        "status",
        "required_skill",
        "timezone",
        "ticket_id",
        "currency",
        "site_ids",
    }

    @function_tool(failure_error_function=None)
    async def inspect_records(
        collection: Literal["tickets", "sites", "assets", "invoices", "contacts"],
    ) -> str:
        """List the requester's scoped records of one kind, to match a description or reference.

        Args:
            collection: Kind of record to list.
        """
        # No customer record is read until the safety screen has cleared the request.
        if await asyncio.shield(screened):
            return json.dumps({"records": [], "stopped": "safety review"})
        # List the whole scoped collection: the model matches meaning, not substrings.
        rows = await backend.search(collection)
        return json.dumps(
            {
                "records": [{k: v for k, v in row.items() if k in fields} for row in rows[:40]],
                "truncated": len(rows) > 40,
            }
        )

    agent = Agent(
        name="Northstar service interpreter",
        instructions=PROMPTS.joinpath("assistant.md").read_text(),
        model=model,
        model_settings=model_settings(1600),
        tools=[inspect_records],
        output_type=Decision,
    )
    # The immutable context is separately labeled; the request remains user data.
    return await Runner.run(
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


async def interpret(
    payload: Record, backend: Backend, context: Record, policy: Record, usage: Record
) -> Decision:
    usage.update(
        model=MODEL,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        pricing_source="unknown",
    )
    async with AsyncOpenAI(max_retries=0, timeout=20) as client:
        model = OpenAIResponsesModel(MODEL, client)
        screen = asyncio.create_task(screen_hazard(model, payload, policy))
        hazard: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        # Unverified requesters get no record access, but hazards still take priority.
        # Interpretation starts in parallel; its record lookups wait for the screen.
        main = (
            asyncio.create_task(interpret_request(model, payload, backend, context, policy, hazard))
            if context["actor"].get("verified")
            else None
        )
        try:
            screened = await screen
            hazard.set_result(SafetyScreen.model_validate(screened.final_output).hazard)
            results = [screened]
            if main and not hazard.result():
                results.append(await main)
        finally:
            # Stop unfinished interpretation and collect any exception it raised.
            if main:
                main.cancel()
                await asyncio.gather(main, return_exceptions=True)
    usage.update(
        input_tokens=sum(r.context_wrapper.usage.input_tokens for r in results),
        output_tokens=sum(r.context_wrapper.usage.output_tokens for r in results),
    )
    if hazard.result():
        return Decision(intent="hazard")
    if main is None:
        # Actions route an unverified requester to identity review.
        return Decision(intent="clarify", clarification="identity")
    decision = Decision.model_validate(results[1].final_output)
    if decision.time_mode == "exact" and decision.requested_time is None:
        decision = decision.model_copy(update={"time_mode": "unclear"})
    return decision


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


async def process_async(
    payload: Record, interpreter: Interpreter | None = None, *, include_message: bool = False
) -> Record:
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
    decision: Decision | None = None
    outcome = Outcome(
        "error",
        SAFETY_FALLBACK + " The request could not be investigated. Please contact operations.",
    )
    try:
        async with asyncio.timeout(max(0.1, backend.remaining() - 5)):
            context = await backend.call("get_context")
            policy = await backend.call("get_policy")
            backend.remember("policy", policy["rules"]["version"])
            actions = Actions(backend, context, policy)
            # The model screens every request for hazards before any record access or write.
            decision = await (interpreter or interpret)(payload, backend, context, policy, usage)
            outcome = await actions.handle(normalize_time(decision, context))
    except Exception as exc:
        # Record only exception type; provider errors can contain request text or credentials.
        log.warning(json.dumps({"event": "processing_failed", "error_type": type(exc).__name__}))
        if usage["model"] != "none" and usage["input_tokens"] is None:
            usage["provider_error"] = type(exc).__name__
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
        if actions and decision is None:
            # No safety screen completed, so a human must also rule out a hazard.
            outcome = await actions.handoff(
                actions.recovery_queue,
                "The request could not be safety screened or completed because processing was unavailable. A human must review it for hazards and reconcile any uncertain action before retrying.",
            )
            outcome = Outcome(outcome.status, SAFETY_FALLBACK + " " + outcome.reply)
        elif actions:
            outcome = await actions.handoff(
                actions.recovery_queue,
                "The request could not be completed because processing was unavailable. A human must reconcile any uncertain action before retrying.",
            )
    finally:
        await backend.close()
    result: Record = {
        "status": outcome.status,
        "summary": outcome.reply,
        "reply": outcome.reply,
        "evidence": backend.evidence,
        "usage": usage,
    }
    if include_message and outcome.message and outcome.reply.endswith(outcome.message.text()):
        # Demo-only structured copy, so the UI never parses reply prose.
        result["message"] = {
            "subject": outcome.message.subject,
            "body": outcome.message.body,
            "contact_id": outcome.message.contact_id,
            "preface": outcome.reply.removesuffix(outcome.message.text()).rstrip(),
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
