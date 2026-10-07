"""Offline message integration checks through the process/HTTP interfaces."""

import asyncio
import json
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from unittest.mock import AsyncMock, patch
from urllib.request import urlopen

from evals.run import check, load_cases
from northstar.api import APIServer
from northstar.http import request_json
from northstar.world import World
from starter.actions import Decision
from starter.agent import Handler
from starter.orchestration import process_async

# Interpretation is controlled in these tests; the independent write check approves.
# Its own behavior, including rejection and failure, is covered in test_write_check.py.
_approve_writes = patch("starter.orchestration.verify_write", AsyncMock(return_value=True))


def setUpModule():
    _approve_writes.start()


def tearDownModule():
    _approve_writes.stop()


class MessageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = uuid.uuid4().hex
        cls.backend = APIServer(("127.0.0.1", 0), cls.admin)
        cls.agent = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.threads = []
        for server in [cls.backend, cls.agent]:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)
        cls.url = f"http://127.0.0.1:{cls.backend.server_port}"
        cls.agent_url = f"http://127.0.0.1:{cls.agent.server_port}"

    @classmethod
    def tearDownClass(cls):
        for server in [cls.backend, cls.agent]:
            server.shutdown()
            server.server_close()
        for thread in cls.threads:
            thread.join()

    def session(self):
        session = request_json(self.url + "/admin/sessions", {}, self.admin)
        self.addCleanup(
            request_json,
            self.url + "/admin/sessions/" + session["session_id"],
            token=self.admin,
            method="DELETE",
        )
        return session

    def payload(self, session):
        return {
            "api_url": self.url,
            "session_token": session["session_token"],
            "run_id": "message-test",
            "request": {
                "id": "message-test",
                "subject": "Service message",
                "body": "Book T001 at the earliest slot and draft an appointment message for CONTACT001.",
            },
        }

    def snapshot(self, session):
        return request_json(
            self.url + "/admin/sessions/" + session["session_id"] + "/finalize", {}, self.admin
        )

    @staticmethod
    async def booking(*_):
        return Decision(
            intent="schedule",
            ticket_id="T001",
            time_mode="earliest",
            message_purpose="appointment_update",
            recipient_mode="named",
            contact_id="CONTACT001",
        )

    def test_http_response_and_replay_have_one_booking_and_no_stored_draft(self):
        session = self.session()
        with patch("starter.orchestration.interpret", self.booking):
            first = request_json(self.agent_url + "/process", self.payload(session))
            second = request_json(self.agent_url + "/process", self.payload(session))
        for response in [first, second]:
            self.assertEqual(response["status"], "completed", response)
            self.assertIn("Subject: Confirmed appointment for ticket T001", response["reply"])
            self.assertIn("8 April 2030, 3:30 PM IST (UTC+05:30)", response["reply"])
            self.assertIn("not been sent or saved as a draft", response["reply"])
            self.assertNotIn(session["session_token"], json.dumps(response))
        snapshot = self.snapshot(session)
        self.assertEqual(len(snapshot["state"]["visits"]), 1)
        self.assertEqual(snapshot["state"]["drafts"], [])
        self.assertEqual(sum(e["tool"] == "schedule_visit" for e in snapshot["audit"]), 1)
        self.assertFalse(any(e["tool"] == "draft_message" for e in snapshot["audit"]))

    def test_failure_after_booking_preserves_receipt_and_rechecks_recipient(self):
        original = World.call
        for change, status in [
            ("unavailable", "escalated"),
            ("revoked", "blocked"),
            ("handoff-fails", "error"),
        ]:
            with self.subTest(change=change):
                session = self.session()

                def changing_world(world, name, arguments):
                    result = original(world, name, arguments)
                    if name == "schedule_visit":
                        if change == "revoked":
                            contact = next(
                                c for c in world.data["contacts"] if c["id"] == "CONTACT001"
                            )
                            contact["authorized"] = False
                        else:
                            world.faults["get_record"] = [{"code": "TEMPORARY_UNAVAILABLE"}] * 3
                            if change == "handoff-fails":
                                world.faults["escalate"] = [{"code": "FORBIDDEN"}]
                    return result

                with patch.object(World, "call", changing_world):
                    response = asyncio.run(process_async(self.payload(session), self.booking))
                self.assertEqual(response["status"], status, response)
                self.assertIn("Booked: ticket T001 for HVAC unit 01 (A001)", response["reply"])
                self.assertNotIn("Subject: ", response["reply"])
                if status == "error":
                    self.assertIn("The remaining work could not be confirmed", response["reply"])
                snapshot = self.snapshot(session)
                self.assertEqual(len(snapshot["state"]["visits"]), 1)
                self.assertEqual(snapshot["state"]["drafts"], [])
                if status == "escalated":
                    self.assertEqual(
                        [e["ticket_id"] for e in snapshot["state"]["escalations"]], ["T001"]
                    )
                else:
                    self.assertEqual(snapshot["state"]["escalations"], [])

    def test_outer_timeout_preserves_confirmed_booking_and_handoff_link(self):
        session = self.session()
        with patch("starter.actions.Actions.compose_message", AsyncMock(side_effect=TimeoutError)):
            response = asyncio.run(process_async(self.payload(session), self.booking))
        self.assertEqual(response["status"], "escalated", response)
        self.assertIn("Booked: ticket T001 for HVAC unit 01 (A001)", response["reply"])
        snapshot = self.snapshot(session)
        self.assertEqual([e["ticket_id"] for e in snapshot["state"]["escalations"]], ["T001"])
        self.assertEqual(len(snapshot["state"]["visits"]), 1)

    def test_demo_message_examples_match_evaluated_requests(self):
        with urlopen(self.agent_url + "/service_desk.js") as response:
            script = response.read().decode()
        samples = json.loads(script.split("const samples =", 1)[1].split(";", 1)[0])
        cases = {c["example_id"]: c for c in load_cases("demo")}
        for sample in [s for s in samples if s["group"] == "Messages"]:
            self.assertEqual(
                {k: sample[k] for k in ["subject", "body"]}, cases[sample["id"]]["request"]
            )
        self.assertIn("Not sent or stored", script)


class MessageGraderTests(unittest.TestCase):
    def test_reply_cannot_hide_an_attempted_draft_or_mislinked_handoff(self):
        cases = {c["id"]: c for c in load_cases()}
        # The grader consumes independent backend state, not the runtime's own claims.
        initial = {"tickets": [], "visits": [], "escalations": []}
        snapshot = {
            "initial": initial,
            "state": {
                **initial,
                "escalations": [{"id": "H1", "queue": "operations", "ticket_id": "OTHER"}],
            },
            "audit": [{"tool": "draft_message", "arguments": {}, "committed": False}],
            "policy": {"version": "test"},
        }
        response = {
            "status": "escalated",
            "summary": "Handoff",
            "reply": "Handoff",
            "usage": {},
            "evidence": [],
        }
        result = check(cases["message-book-failed"], response, snapshot)
        self.assertFalse(result["handoff_linkage"])
        self.assertFalse(result["no_other_business_writes"])
        self.assertFalse(result["forbidden_attempts"])
