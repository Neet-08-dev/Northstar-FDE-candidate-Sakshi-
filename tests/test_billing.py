import asyncio
import json
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError

from evals.run import BILLING_CASES, check, run_case
from northstar.api import APIServer
from northstar.http import request_json
from starter.actions import Decision
from starter.agent import Handler
from starter.backend import Backend
from starter.orchestration import process_async

# Interpretation is controlled in these tests; the independent write check approves.
# Its own behavior, including rejection and failure, is covered in test_write_check.py.
_approve_writes = patch("starter.orchestration.verify_write", AsyncMock(return_value=True))


def setUpModule():
    _approve_writes.start()


def tearDownModule():
    _approve_writes.stop()


class BillingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = uuid.uuid4().hex
        cls.backend = APIServer(("127.0.0.1", 0), cls.admin)
        cls.candidate = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.threads = []
        for server in [cls.backend, cls.candidate]:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.threads.append(thread)
        cls.url = f"http://127.0.0.1:{cls.backend.server_port}"
        cls.process_url = f"http://127.0.0.1:{cls.candidate.server_port}"

    @classmethod
    def tearDownClass(cls):
        for server in [cls.backend, cls.candidate]:
            server.shutdown()
            server.server_close()
        for thread in cls.threads:
            thread.join()

    def test_money_requires_integer_cents_without_coercion(self):
        for amount in [True, 75.5, "7500", 7500.0]:
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                Decision(intent="credit", invoice_id="I001", amount_cents=amount)

    def test_billing_http_contract_and_effects(self):
        cases = json.loads(BILLING_CASES.read_text())
        selected = {
            "billing-ordinary",
            "billing-above-limit",
            "billing-valid-grant",
            "billing-credit-timeout",
            "billing-approval-timeout",
            "billing-unpaid",
            "billing-viewer",
            "billing-mixed",
            "billing-mixed-message",
            "billing-handoff-outage",
        }
        for case in cases:
            if case["id"] not in selected:
                continue

            async def fixed(*_, decision=case["decision"]):
                return Decision.model_validate(decision)

            with self.subTest(case=case["id"]), patch("starter.orchestration.interpret", fixed):
                result = asyncio.run(
                    run_case(case, self.url, self.admin, process_url=self.process_url)
                )
                self.assertTrue(result["passed"], result)

    def test_policy_is_refreshed_after_interpretation(self):
        session = request_json(self.url + "/admin/sessions", {}, self.admin)

        async def fixed(*_):
            # External update after the initial policy read, before action execution.
            self.backend.sessions[session["session_token"]]["world"].policy["credit"][
                "auto_limit_cents"
            ] = 5000
            return Decision(intent="credit", invoice_id="I001", amount_cents=7500)

        try:
            response = asyncio.run(
                process_async(
                    {
                        "api_url": self.url,
                        "session_token": session["session_token"],
                        "run_id": "policy",
                        "request": {
                            "id": "policy",
                            "subject": "Credit",
                            "body": "Credit $75 to I001.",
                        },
                    },
                    fixed,
                )
            )
            snapshot = request_json(
                self.url + "/admin/sessions/" + session["session_id"] + "/finalize", {}, self.admin
            )
            self.assertEqual(response["status"], "escalated")
            self.assertEqual(snapshot["state"]["credits"], [])
            self.assertEqual(len(snapshot["state"]["approvals"]), 1)
            self.assertFalse(any(e["tool"] == "issue_credit" for e in snapshot["audit"]))
        finally:
            request_json(
                self.url + "/admin/sessions/" + session["session_id"],
                token=self.admin,
                method="DELETE",
            )

    def test_billing_timeout_recovery_preserves_queue_and_ticket(self):
        original = Backend.call

        async def timeout(backend, tool, **kwargs):
            if tool == "issue_credit":
                raise TimeoutError("processing deadline")
            return await original(backend, tool, **kwargs)

        case = next(
            c for c in json.loads(BILLING_CASES.read_text()) if c["id"] == "billing-ordinary"
        )
        case["expected"] = dict(
            status="escalated", new_visits=0, queue="billing", escalation_ticket_id="T001"
        )
        with patch.object(Backend, "call", timeout):
            result = asyncio.run(run_case(case, self.url, self.admin))
        self.assertTrue(result["passed"], result)

    def test_grader_rejects_missing_handoff_link(self):
        from pathlib import Path

        from evals.run import CASES

        case = next(
            c for c in json.loads(Path(CASES).read_text()) if c["id"] == "persistent-outage"
        )
        snapshot = {
            "initial": {"tickets": [], "visits": []},
            "state": {
                "tickets": [],
                "visits": [],
                "escalations": [{"queue": "operations", "ticket_id": ""}],
            },
            "audit": [],
        }
        response = {
            "status": "escalated",
            "summary": "Handoff",
            "reply": "Handoff",
            "usage": {},
            "evidence": [],
        }
        self.assertFalse(check(case, response, snapshot)["handoff_linkage"])
