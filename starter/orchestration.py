"""SDK interpretation and scoped investigation, followed by deterministic execution."""

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from agents import Agent, ModelSettings, OpenAIResponsesModel, RunConfig, Runner, function_tool
from openai import AsyncOpenAI
from openai.types.shared import Reasoning

from .actions import SAFETY_REPLY, Actions, Decision, Outcome, utc
from .backend import Backend, Record

log = logging.getLogger("northstar.agent")
Interpreter = Callable[[Record, Backend, Record, Record, Record], Awaitable[Decision]]


def resolve_requested_time(value: str, now: str) -> str:
    """Resolve a bounded literal time using only the request-scoped clock.

    Omitted years mean the current calendar year in the requested zone, even
    when that date has passed. Availability checks decide whether it is bookable.
    Named DST zones, date-only requests and alternative times require clarification.
    """
    text = value.strip()
    zone = timezone(timedelta(hours=5, minutes=30))
    match = re.search(r"\s*(IST|UTC|GMT)?([+-]\d{1,2}:\d{2})?\s*$", text, re.I)
    if match and (match[1] or match[2]):
        if match[1] and match[1].upper() == "IST" and match[2]:
            raise ValueError("Contradictory timezone")
        minutes = 330 if (match[1] or "").upper() == "IST" else 0
        if match[2]:
            hours, mins = map(int, match[2][1:].split(":"))
            if hours > 14 or mins > 59 or (hours == 14 and mins):
                raise ValueError("Invalid UTC offset")
            minutes = (hours * 60 + mins) * (1 if match[2][0] == "+" else -1)
        zone = timezone(timedelta(minutes=minutes))
        text = text[: match.start()].strip()
    elif text.endswith("Z"):
        zone = timezone.utc
        text = text[:-1]
    # The suffix is removed first so ISO dates cannot be mistaken for offsets.
    clock = re.fullmatch(
        r"(.+?)(?:\s+(?:at\s+)?|T)(\d{1,2})(?::(\d{2}))?(?::(\d{2}))?\s*(AM|PM)?",
        text,
        re.I,
    )
    if not clock:
        raise ValueError("One date and exact time required")
    date_text, hour_text, minute_text, second_text, period = clock.groups()
    hour, minute = int(hour_text), int(minute_text or "0")
    second = int(second_text or "0")
    if minute > 59 or hour > 23 or second > 59:
        raise ValueError("Invalid clock time")
    if period:
        if not 1 <= hour <= 12:
            raise ValueError("Invalid twelve-hour time")
        hour = hour % 12 + (12 if period.upper() == "PM" else 0)
    elif minute_text is None or len(hour_text) != 2:
        raise ValueError("Use AM/PM or HH:MM")
    scoped_now = utc(now).astimezone(zone)
    date_text = date_text.strip().lower()
    if date_text in {"today", "tomorrow"}:
        day = scoped_now.date() + timedelta(days=int(date_text == "tomorrow"))
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
        day = datetime.strptime(date_text, "%Y-%m-%d").date()
    else:
        date_match = re.fullmatch(r"(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?", date_text)
        month_first = re.fullmatch(r"([a-z]+)\s+(\d{1,2})(?:,?\s+(\d{4}))?", date_text)
        if date_match:
            day_text, month_text, year_text = date_match.groups()
        elif month_first:
            month_text, day_text, year_text = month_first.groups()
        else:
            raise ValueError("Unsupported or ambiguous date")
        months = {
            name: index
            for index, name in enumerate(
                [
                    "january",
                    "february",
                    "march",
                    "april",
                    "may",
                    "june",
                    "july",
                    "august",
                    "september",
                    "october",
                    "november",
                    "december",
                ],
                1,
            )
        }
        months.update({name[:3]: index for name, index in list(months.items())})
        month = months.get(month_text)
        if month is None:
            raise ValueError("Unsupported month")
        day = datetime(int(year_text or scoped_now.year), month, int(day_text)).date()
    return (
        datetime.combine(day, datetime.min.time(), zone)
        .replace(hour=hour, minute=minute, second=second)
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def normalize_time(decision: Decision, context: Record) -> Decision:
    if not decision.requested_time:
        return decision
    try:
        if decision.time_mode != "exact":
            raise ValueError("Conflicting time modes")
        resolved = resolve_requested_time(decision.requested_time, context["now"])
        if decision.starts_at and utc(decision.starts_at) != utc(resolved):
            raise ValueError("Conflicting instants")
        return decision.model_copy(update={"starts_at": resolved})
    except (ValueError, TypeError):
        return decision.model_copy(update={"time_mode": "unclear", "starts_at": ""})


async def interpret(
    payload: Record, backend: Backend, context: Record, policy: Record, usage: Record
) -> Decision:
    model_name = os.environ.get("OPENAI_MODEL", "gpt-6.1-sol")
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
        "ticket_id",
        "currency",
        "site_ids",
    }

    @function_tool(failure_error_function=None)
    async def inspect_records(
        collection: Literal["tickets", "sites", "assets", "invoices", "contacts"], query: str
    ) -> str:
        """Find scoped records to resolve an ambiguous invoice, ticket, site, equipment or registered contact.

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
    decision = Decision.model_validate(result.final_output)
    if decision.time_mode == "exact":
        request_text = payload["request"]["subject"] + "\n" + payload["request"]["body"]
        literal = " ".join(decision.requested_time.lower().split())
        supplied = " ".join(request_text.lower().split())
        # The SDK extracts a literal; it cannot replace the date, add a year or
        # invent a timezone before Python resolves the scoped calendar.
        if not literal or literal not in supplied:
            decision = decision.model_copy(update={"time_mode": "unclear", "starts_at": ""})
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
                outcome = await actions.handle(normalize_time(decision, context))
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
                actions.recovery_queue,
                "The request could not be completed because processing was unavailable. A human must reconcile any uncertain action before retrying.",
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
