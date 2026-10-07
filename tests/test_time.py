"""Time and safety interpretation boundaries and real HTTP scheduling effects, without model calls."""

import asyncio
import json
import os
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError
from urllib.request import urlopen

from agents.tool_context import ToolContext

from northstar.api import APIServer
from northstar.http import request_json
from starter.actions import Decision, RequestedTime
from starter.agent import Handler
from starter.orchestration import SafetyScreen, interpret, resolve_requested_time


def requested(relative="none", month=None, day=None, hour=0, minute=0, offset=None, year=None):
    return RequestedTime(
        relative_day=relative,
        year=year,
        month=month,
        day=day,
        hour=hour,
        minute=minute,
        utc_offset_minutes=offset,
    )


def run_result(output):
    return SimpleNamespace(
        final_output=output,
        context_wrapper=SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=1)),
    )


class NaturalTimeTests(unittest.TestCase):
    def test_defaults_overrides_and_scoped_calendar(self):
        cases = [
            # 8 april 7:30 PM, defaulting to IST and the scoped year.
            (
                requested(month=4, day=8, hour=19, minute=30),
                "2030-04-08T09:00:00Z",
                "2030-04-08T14:00:00Z",
            ),
            (
                requested(month=4, day=8, hour=19, minute=30, year=2031, offset=330),
                "2030-04-08T09:00:00Z",
                "2031-04-08T14:00:00Z",
            ),
            (
                requested(month=4, day=8, hour=14, offset=0),
                "2030-04-08T09:00:00Z",
                "2030-04-08T14:00:00Z",
            ),
            (
                requested(month=4, day=8, hour=7, offset=-180),
                "2030-04-08T09:00:00Z",
                "2030-04-08T10:00:00Z",
            ),
            (requested("today", hour=0), "2030-12-31T20:00:00Z", "2030-12-31T18:30:00Z"),
            (
                requested("tomorrow", hour=19, minute=30),
                "2030-12-31T20:00:00Z",
                "2031-01-02T14:00:00Z",
            ),
            # The scoped IST date has already rolled into 2031.
            (
                requested(month=1, day=1, hour=19, minute=30),
                "2030-12-31T20:00:00Z",
                "2031-01-01T14:00:00Z",
            ),
            (
                requested(month=1, day=1, hour=19, minute=30, offset=0),
                "2030-12-31T20:00:00Z",
                "2030-01-01T19:30:00Z",
            ),
            (
                requested(month=2, day=29, hour=19, minute=30),
                "2032-01-01T00:00:00Z",
                "2032-02-29T14:00:00Z",
            ),
        ]
        for value, now, expected in cases:
            with self.subTest(value=value, now=now):
                self.assertEqual(resolve_requested_time(value, now), expected)

    def test_impossible_or_incomplete_fields_are_rejected(self):
        for value in [
            requested(month=4, day=31, hour=19),
            requested(month=2, day=29, hour=19),
            requested(month=13, day=8, hour=19),
            requested(month=4, day=8, hour=24),
            requested(month=4, day=8, hour=19, minute=60),
            requested(month=4, day=8, hour=-1),
            requested(month=4, day=8, hour=19, offset=841),
            requested(month=4, day=8, hour=19, offset=-721),
            requested(month=4, hour=19),
            requested(hour=19),
            requested("tomorrow", month=4, day=8, hour=19),
            requested("today", year=2030, hour=19),
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_requested_time(value, "2030-04-08T09:00:00Z")

    def test_time_fields_are_strict_and_starts_at_is_not_model_output(self):
        with self.assertRaises(ValueError):
            RequestedTime.model_validate(
                {**requested(month=4, day=8, hour=19).model_dump(), "hour": "19"}
            )
        schema = json.dumps(Decision.model_json_schema())
        self.assertNotIn("starts_at", schema)
        self.assertIn("utc_offset_minutes", schema)

    def run_interpret(self, *, screen, decision=None, verified=True, backend=None, tool_args=None):
        names = []

        async def fake_run(agent, *_args, **_kwargs):
            names.append(agent.name)
            if agent.name == "Northstar safety screen":
                await asyncio.sleep(0.05)
                if isinstance(screen, Exception):
                    raise screen
                return run_result(SafetyScreen(hazard=screen))
            if tool_args is not None:
                # Invoke the real lookup tool the way the SDK would, before the screen finishes.
                tool = agent.tools[0]
                ctx = ToolContext(
                    None, tool_name=tool.name, tool_call_id="call", tool_arguments=tool_args
                )
                names.append(json.loads(await tool.on_invoke_tool(ctx, tool_args)))
            return run_result(decision or Decision(intent="clarify", clarification="intent"))

        context = {"now": "2030-04-08T09:00:00Z", "actor": {"verified": verified}}
        usage: dict = {}
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "offline-placeholder"}),
            patch("starter.orchestration.Runner.run", side_effect=fake_run),
        ):
            out = asyncio.run(
                interpret(
                    {"request": {"subject": "Visit", "body": "Book T001."}},
                    backend,
                    context,
                    {"rules": {"safety": {"emergency_signals": ["smoke"]}}},
                    usage,
                )
            )
        return out, names, usage

    def test_exact_time_requires_structured_fields_from_the_model(self):
        for value, expected_mode in [
            (requested(month=4, day=8, hour=19, minute=30), "exact"),
            (None, "unclear"),
        ]:
            with self.subTest(value=value):
                decision = Decision(
                    intent="schedule", ticket_id="T001", time_mode="exact", requested_time=value
                )
                out, _, usage = self.run_interpret(screen=False, decision=decision)
                self.assertEqual(out.time_mode, expected_mode)
                self.assertEqual((usage["input_tokens"], usage["output_tokens"]), (2, 2))
                self.assertEqual(usage["model"], "gpt-6.1-sol")

    def test_model_safety_screen_overrides_interpretation(self):
        booking = Decision(intent="schedule", ticket_id="T001", time_mode="earliest")
        out, _, _ = self.run_interpret(screen=True, decision=booking)
        self.assertEqual(out.intent, "hazard")
        out, _, _ = self.run_interpret(screen=False, decision=booking)
        self.assertEqual(out.intent, "schedule")

    def test_record_lookup_waits_for_the_safety_screen(self):
        for hazard in [True, False]:
            with self.subTest(hazard=hazard):
                backend = SimpleNamespace(
                    search=AsyncMock(return_value=[{"id": "T001", "summary": "untrusted"}])
                )
                out, names, _ = self.run_interpret(
                    screen=hazard, backend=backend, tool_args='{"collection": "tickets"}'
                )
                if hazard:
                    self.assertEqual(out.intent, "hazard")
                    backend.search.assert_not_called()
                else:
                    backend.search.assert_awaited_once_with("tickets")
                    # Untrusted free text is not shown to the model.
                    self.assertEqual(names[-1]["records"], [{"id": "T001"}])

    def test_unverified_requester_is_screened_without_interpretation(self):
        for hazard, intent in [(True, "hazard"), (False, "clarify")]:
            with self.subTest(hazard=hazard):
                out, names, usage = self.run_interpret(screen=hazard, verified=False)
                self.assertEqual(out.intent, intent)
                self.assertEqual(names, ["Northstar safety screen"])
                self.assertEqual(usage["input_tokens"], 1)

    def test_screen_failure_propagates_instead_of_assuming_safety(self):
        with self.assertRaises(RuntimeError):
            self.run_interpret(screen=RuntimeError("synthetic provider failure"))

    def test_real_process_http_effects_and_static_contract(self):
        admin = uuid.uuid4().hex
        backend = APIServer(("127.0.0.1", 0), admin)
        agent = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threads = []
        for server in (backend, agent):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)
        api_url = f"http://127.0.0.1:{backend.server_port}"
        agent_url = f"http://127.0.0.1:{agent.server_port}"
        evening = requested(month=4, day=8, hour=19, minute=30)
        cases = [
            ("8 april 7:30 PM", evening, {}, "completed", "2030-04-08T14:00:00Z", "7:30 PM IST"),
            (
                "8 april 14:00 UTC",
                requested(month=4, day=8, hour=14, offset=0),
                {},
                "completed",
                "2030-04-08T14:00:00Z",
                "7:30 PM IST",
            ),
            (
                "8 april 5:30 PM",
                requested(month=4, day=8, hour=17, minute=30),
                {},
                "needs_clarification",
                None,
                "3:30 PM IST",
            ),
            # The model reports an ambiguous time as unclear with no fields.
            ("8 april 7:30", None, {}, "needs_clarification", None, "AM or PM"),
            (
                "31 april 7:30 PM",
                requested(month=4, day=31, hour=19, minute=30),
                {},
                "needs_clarification",
                None,
                "exact time",
            ),
            (
                "8 april 7:30 PM",
                evening,
                {"now": "2030-04-09T09:00:00Z"},
                "needs_clarification",
                None,
                "No new visit was booked",
            ),
            (
                "8 april 7:30 PM",
                evening,
                {"patches": [{"collection": "assets", "id": "A001", "set": {"safety_hold": True}}]},
                "escalated",
                None,
                "Move away",
            ),
        ]
        try:
            for literal, value, fixture, status, instant, reply in cases:
                with self.subTest(literal=literal, fixture=fixture):
                    session = request_json(api_url + "/admin/sessions", fixture, admin)
                    payload = {
                        "api_url": api_url,
                        "session_token": session["session_token"],
                        "run_id": uuid.uuid4().hex,
                        "request": {
                            "id": "time",
                            "subject": "Visit",
                            "body": f"Book T001 on {literal}.",
                        },
                    }
                    decision = Decision(
                        intent="schedule",
                        ticket_id="T001",
                        time_mode="exact" if value else "unclear",
                        requested_time=value,
                    )
                    with patch("starter.orchestration.interpret", AsyncMock(return_value=decision)):
                        result = request_json(agent_url + "/process", payload)
                    snapshot = request_json(
                        api_url + "/admin/sessions/" + session["session_id"] + "/snapshot",
                        token=admin,
                    )
                    self.assertEqual(result["status"], status)
                    self.assertIn(reply, result["reply"])
                    self.assertEqual(
                        set(result), {"status", "summary", "reply", "evidence", "usage"}
                    )
                    self.assertNotIn(session["session_token"], json.dumps(result))
                    visits = snapshot["state"]["visits"]
                    self.assertEqual([v["starts_at"] for v in visits], [instant] if instant else [])
                    self.assertEqual(
                        sum(e["tool"] == "schedule_visit" for e in snapshot["audit"]),
                        int(instant is not None),
                    )
                    self.assertTrue(all(v["duration_minutes"] == 60 for v in visits))
                    self.assertEqual(snapshot["state"]["tickets"], snapshot["initial"]["tickets"])
                    if "safety_hold" in str(fixture):
                        self.assertEqual(snapshot["state"]["escalations"][0]["queue"], "safety")
                    request_json(
                        api_url + "/admin/sessions/" + session["session_id"],
                        token=admin,
                        method="DELETE",
                    )
            for path, kind in [
                ("/", "text/html"),
                ("/service_desk.js", "text/javascript"),
                ("/service_desk.css", "text/css"),
            ]:
                with urlopen(agent_url + path) as response:
                    self.assertIn(kind, response.headers["Content-Type"])
                    self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
            for path in ["/ui_prototype.js", "/.env", "/../starter/actions.py"]:
                with self.assertRaises(HTTPError):
                    urlopen(agent_url + path)
        finally:
            for server in (agent, backend):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join()
