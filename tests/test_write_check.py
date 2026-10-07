"""The independent write check runs once before the first business write and fails closed."""

import asyncio
import threading
import unittest
import uuid

from northstar.api import APIServer
from northstar.http import request_json
from starter.actions import Decision
from starter.orchestration import process_async

WRITES = {"create_ticket", "schedule_visit", "request_approval", "issue_credit"}


class WriteCheckTests(unittest.TestCase):
    def setUp(self):
        self.admin = uuid.uuid4().hex
        self.backend = APIServer(("127.0.0.1", 0), self.admin)
        self.thread = threading.Thread(target=self.backend.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.backend.server_port}"

    def tearDown(self):
        self.backend.shutdown()
        self.backend.server_close()
        self.thread.join()

    def run_request(self, decision, verdict, body="Request"):
        session = request_json(self.url + "/admin/sessions", {}, self.admin)
        actions = []

        self.facts = []

        async def checker(_payload, _usage, action, facts):
            actions.append(action)
            self.facts.append(facts)
            if isinstance(verdict, Exception):
                raise verdict
            return verdict

        async def interpreter(*_args):
            return decision

        out = asyncio.run(
            process_async(
                {
                    "api_url": self.url,
                    "session_token": session["session_token"],
                    "run_id": uuid.uuid4().hex,
                    "request": {"id": "r", "subject": "Service", "body": body},
                },
                interpreter,
                verifier=checker,
            )
        )
        state = request_json(
            self.url + "/admin/sessions/" + session["session_id"] + "/finalize", {}, self.admin
        )
        writes = [e["tool"] for e in state["audit"] if e["tool"] in WRITES]
        return out, actions, writes, state

    def test_rejected_check_writes_nothing_and_asks(self):
        # The observed Luna failure: no equipment was named, yet A101 was chosen.
        decision = Decision(
            intent="intake",
            asset_id="A101",
            site_id="S101",
            intake_mode="record_and_schedule",
            issue_category="maintenance",
            issue_summary="Service requested.",
            time_mode="earliest",
        )
        out, actions, writes, _ = self.run_request(
            decision, False, "Book ticket at the earliest available time."
        )
        self.assertEqual(out["status"], "needs_clarification")
        self.assertIn("Before I make any change, please confirm: should I create a new", out["reply"])
        self.assertIn("Nothing has been changed.", out["reply"])
        self.assertIn("Annex cooling unit (A101)", actions[0])
        self.assertEqual(writes, [])

    def test_approved_check_runs_once_for_create_then_book(self):
        decision = Decision(
            intent="intake",
            asset_id="A101",
            site_id="S101",
            intake_mode="record_and_schedule",
            issue_category="maintenance",
            issue_summary="Routine maintenance requested.",
            time_mode="earliest",
        )
        out, actions, writes, _ = self.run_request(decision, True)
        self.assertEqual(out["status"], "completed", out)
        self.assertEqual(writes, ["create_ticket", "schedule_visit"])
        self.assertEqual(len(actions), 1)
        self.assertIn("and book its earliest open technician visit", actions[0])

    def test_checks_describe_the_exact_credit_and_booking(self):
        _, actions, writes, _ = self.run_request(
            Decision(intent="credit", invoice_id="I001", amount_cents=7500), True
        )
        self.assertEqual(writes, ["issue_credit"])
        self.assertIn(
            "apply a $75.00 service credit to invoice I001 (the invoice for ticket T001 on HVAC unit 01 (A001)",
            actions[0],
        )
        # A pending approval only routes the credit to a supervisor, so it is not gated.
        out, actions, writes, _ = self.run_request(
            Decision(intent="credit", invoice_id="I001", amount_cents=30000), False
        )
        self.assertEqual(writes, ["request_approval"])
        self.assertEqual(actions, [])
        self.assertEqual(out["status"], "escalated")
        _, actions, writes, _ = self.run_request(
            Decision(intent="schedule", ticket_id="T001", time_mode="earliest"), True
        )
        self.assertEqual(writes, ["schedule_visit"])
        self.assertIn("book a one-hour technician visit for ticket T001", actions[0])
        self.assertIn("at the earliest open slot, 8 April 2030, 10:00 AM UTC", actions[0])

    def test_checker_listings_are_facts_not_evidence(self):
        out, _, writes, state = self.run_request(
            Decision(intent="schedule", ticket_id="T001", time_mode="earliest"), True
        )
        self.assertEqual(writes, ["schedule_visit"])
        self.assertEqual(self.facts[0]["site_timezones"], {"S001": "UTC", "S101": "UTC"})
        self.assertIn("Annex cooling unit (A101)", str(self.facts[0]["account_equipment"]))
        cited = {(e["collection"], e["record_id"]) for e in out["evidence"]}
        visit = state["state"]["visits"][0]["id"]
        for ref in [("tickets", "T001"), ("assets", "A001"), ("sites", "S001"), ("visits", visit)]:
            self.assertIn(ref, cited)
        # Records listed only for the checker or for discovery are not evidence.
        self.assertNotIn(("assets", "A101"), cited)
        self.assertNotIn(("sites", "S101"), cited)

    def test_reads_options_and_handoffs_are_never_gated(self):
        for decision in [
            Decision(intent="status", status_topic="ticket", ticket_id="T001"),
            Decision(intent="schedule", ticket_id="T001", time_mode="unclear"),
            Decision(intent="unsupported", unsupported_kind="reschedule_or_cancel"),
            Decision(intent="hazard"),
        ]:
            with self.subTest(intent=decision.intent):
                out, actions, writes, _ = self.run_request(decision, False)
                self.assertEqual(actions, [])
                self.assertEqual(writes, [])
                self.assertNotIn("please confirm", out["reply"])

    def test_check_failure_fails_closed_with_a_handoff(self):
        out, actions, writes, state = self.run_request(
            Decision(intent="schedule", ticket_id="T001", time_mode="earliest"),
            RuntimeError("synthetic provider failure"),
        )
        self.assertEqual(len(actions), 1)
        self.assertEqual(writes, [])
        self.assertEqual(out["status"], "escalated")
        self.assertEqual([e["queue"] for e in state["state"]["escalations"]], ["operations"])
