"""Reply quality boundaries: safe record names, follow-up turns and demo conversation sessions."""

import asyncio
import json
import os
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from northstar.api import APIServer
from northstar.http import request_json
from starter.actions import Decision, name
from starter.agent import Handler
from starter.orchestration import SafetyScreen, interpret, validate_payload


# Interpretation is controlled in these tests; the independent write check approves.
# Its own behavior, including rejection and failure, is covered in test_write_check.py.
_approve_writes = patch("starter.orchestration.verify_write", AsyncMock(return_value=True))


def setUpModule():
    _approve_writes.start()


def tearDownModule():
    _approve_writes.stop()


def payload(**extra):
    return {
        "api_url": "http://localhost:1",
        "session_token": "token",
        "run_id": "run",
        "request": {"id": "r", "subject": "Visit", "body": "The second one."},
        **extra,
    }


class ReplyBoundaryTests(unittest.TestCase):
    def test_record_names_cannot_inject_markdown_or_lines(self):
        hostile = "[Click](javascript:alert(1)) **Pay** `now`\n# Heading <b>x</b>"
        cleaned = name(hostile)
        for token in ["[", "]", "(", ")", "*", "`", "#", "<", ">", "\n", ":"]:
            self.assertNotIn(token, cleaned)
        self.assertLessEqual(len(name("x" * 500)), 60)
        self.assertEqual(name("HVAC unit 01"), "HVAC unit 01")

    def test_conversation_turns_are_bounded_and_shaped(self):
        turn = {"subject": "Visit", "body": "Book T001.", "reply": "Which time?"}
        validate_payload(payload(conversation=[turn]))
        for bad in [
            [turn] * 5,
            [{**turn, "role": "system"}],
            [{"subject": "Visit", "body": "Book T001."}],
            [{**turn, "reply": 7}],
            [{**turn, "body": "x" * 16001}],
            "not a list",
        ]:
            with self.subTest(bad=str(bad)[:40]), self.assertRaises(ValueError):
                validate_payload(payload(conversation=bad))

    def test_earlier_turns_reach_only_the_interpreter_as_untrusted_data(self):
        inputs = {}

        async def fake_run(agent, text, **_kwargs):
            inputs[agent.name] = json.loads(text)
            output = (
                SafetyScreen(hazard=False)
                if agent.name == "Northstar safety screen"
                else Decision(intent="clarify", clarification="help")
            )
            return SimpleNamespace(
                final_output=output,
                context_wrapper=SimpleNamespace(
                    usage=SimpleNamespace(input_tokens=1, output_tokens=1)
                ),
            )

        turns = [{"subject": "Visit", "body": "Book T001.", "reply": "Which slot?"}]
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "offline-placeholder"}),
            patch("starter.orchestration.Runner.run", side_effect=fake_run),
        ):
            asyncio.run(
                interpret(
                    payload(conversation=turns),
                    None,
                    {"now": "2030-04-08T09:00:00Z", "actor": {"verified": True}},
                    {"rules": {"safety": {}}},
                    {},
                )
            )
        self.assertEqual(inputs["Northstar service interpreter"]["untrusted_earlier_turns"], turns)
        # The hazard screen judges only the current request.
        self.assertNotIn("untrusted_earlier_turns", inputs["Northstar safety screen"])


class DemoConversationTests(unittest.TestCase):
    def setUp(self):
        self.admin = uuid.uuid4().hex
        self.backend = APIServer(("127.0.0.1", 0), self.admin)
        self.agent = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.threads = []
        for server in (self.backend, self.agent):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)
        self.api_url = f"http://127.0.0.1:{self.backend.server_port}"
        self.agent_url = f"http://127.0.0.1:{self.agent.server_port}"
        self.env = patch.dict(os.environ, {"API_URL": self.api_url, "ADMIN_TOKEN": self.admin})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        for server in (self.agent, self.backend):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join()

    def test_follow_ups_share_one_session_until_the_conversation_ends(self):
        seen = []

        async def interpreter(task, *_args):
            seen.append(task.get("conversation"))
            return Decision(
                intent="intake",
                asset_id="A101",
                site_id="S101",
                issue_category="maintenance",
                issue_summary="Routine maintenance requested.",
            )

        conversation = uuid.uuid4().hex
        with patch("starter.orchestration.interpret", interpreter):
            first = request_json(
                self.agent_url + "/demo",
                {
                    "subject": "Issue",
                    "body": "Log maintenance for A101.",
                    "conversation_id": conversation,
                },
            )
            self.assertIn("Created ticket", first["reply"])
            self.assertEqual(len(self.backend.sessions), 1)
            turn = {
                "subject": "Issue",
                "body": "Log maintenance for A101.",
                "reply": first["reply"],
            }
            second = request_json(
                self.agent_url + "/demo",
                {
                    "subject": "Issue",
                    "body": "Log it again.",
                    "conversation_id": conversation,
                    "history": [turn],
                },
            )
        # The second turn sees the first turn's ticket in the same synthetic session.
        self.assertIn("Reused open ticket", second["reply"])
        self.assertEqual(len(self.backend.sessions), 1)
        self.assertEqual(seen, [None, [turn]])
        ended = request_json(self.agent_url + "/demo/end", {"conversation_id": conversation})
        self.assertTrue(ended["ended"])
        self.assertEqual(self.backend.sessions, {})

    def test_changing_customer_starts_a_fresh_session(self):
        conversation = uuid.uuid4().hex
        with patch(
            "starter.orchestration.interpret",
            AsyncMock(return_value=Decision(intent="clarify", clarification="help")),
        ):
            for customer in ["C001", "C002"]:
                request_json(
                    self.agent_url + "/demo",
                    {"body": "Hi", "conversation_id": conversation, "customer_id": customer},
                )
                actors = [
                    s["world"].actor["customer_ids"] for s in self.backend.sessions.values()
                ]
                self.assertEqual(actors, [[customer]])
        request_json(self.agent_url + "/demo/end", {"conversation_id": conversation})
        self.assertEqual(self.backend.sessions, {})

    def test_malformed_conversation_ids_are_rejected_before_any_session(self):
        for bad in ["short", "x" * 65, "has spaces here", "../../admin", 12345678]:
            with self.subTest(bad=bad):
                with self.assertRaises(Exception):
                    request_json(self.agent_url + "/demo", {"body": "Hi", "conversation_id": bad})
                self.assertEqual(self.backend.sessions, {})
