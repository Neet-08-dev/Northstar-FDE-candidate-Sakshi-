import asyncio
import json
import threading
import unittest
import uuid

from evals.run import CASES, run_case
from northstar.api import APIServer
from northstar.http import request_json
from starter.actions import Decision
from starter.orchestration import process_async


class SchedulingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = uuid.uuid4().hex
        cls.server = APIServer(("127.0.0.1", 0), cls.admin)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_authored_scenarios(self):
        for case in json.loads(CASES.read_text()):
            with self.subTest(case=case["id"]):
                result = asyncio.run(run_case(case, self.url, self.admin))
                self.assertTrue(result["passed"], result)

    def test_repeat_request_does_not_duplicate_visit(self):
        session = request_json(self.url + "/admin/sessions", {}, self.admin)
        payload = {
            "api_url": self.url,
            "session_token": session["session_token"],
            "run_id": "repeat",
            "request": {
                "id": "repeat",
                "subject": "Visit",
                "body": "Book T001 at the earliest slot.",
            },
        }

        async def fixed(*_):
            return Decision(intent="schedule", ticket_id="T001", time_mode="earliest")

        try:
            one = asyncio.run(process_async(payload, fixed))
            two = asyncio.run(process_async(payload, fixed))
            self.assertEqual((one["status"], two["status"]), ("completed", "completed"))
            state = request_json(
                self.url + "/admin/sessions/" + session["session_id"] + "/finalize", {}, self.admin
            )
            self.assertEqual(len(state["state"]["visits"]), 1)
            self.assertEqual(sum(e["tool"] == "schedule_visit" for e in state["audit"]), 1)
        finally:
            request_json(
                self.url + "/admin/sessions/" + session["session_id"],
                token=self.admin,
                method="DELETE",
            )

    def test_model_unavailable_creates_real_handoff(self):
        session = request_json(self.url + "/admin/sessions", {}, self.admin)

        async def unavailable(*_):
            raise RuntimeError("synthetic provider failure")

        try:
            out = asyncio.run(
                process_async(
                    {
                        "api_url": self.url,
                        "session_token": session["session_token"],
                        "run_id": "failure",
                        "request": {"id": "failure", "subject": "Visit", "body": "Book T001."},
                    },
                    unavailable,
                )
            )
            state = request_json(
                self.url + "/admin/sessions/" + session["session_id"] + "/finalize", {}, self.admin
            )
            self.assertEqual(out["status"], "escalated")
            self.assertEqual(len(state["state"]["visits"]), 0)
            self.assertEqual(len(state["state"]["escalations"]), 1)
        finally:
            request_json(
                self.url + "/admin/sessions/" + session["session_id"],
                token=self.admin,
                method="DELETE",
            )

    def test_concurrent_sessions_are_isolated(self):
        case = json.loads(CASES.read_text())[0]

        async def run():
            return await asyncio.gather(
                run_case(case, self.url, self.admin), run_case(case, self.url, self.admin)
            )

        results = asyncio.run(run())
        self.assertTrue(all(r["passed"] for r in results))


class EvaluationRegressionTests(unittest.TestCase):
    def test_provider_failure_cannot_pass_handoff_case(self):
        from evals.run import model_completed

        self.assertFalse(model_completed({"usage": {"model": "gpt-6-luna", "input_tokens": None}}))
        self.assertTrue(model_completed({"usage": {"model": "none", "input_tokens": 0}}))
        self.assertTrue(model_completed({"usage": {"model": "gpt-6-luna", "input_tokens": 80}}))

    def test_invalid_request_never_reaches_backend(self):
        from unittest.mock import patch

        with patch("starter.orchestration.Backend") as backend:
            with self.assertRaises(ValueError):
                asyncio.run(process_async({"api_url": "http://localhost"}))
            backend.assert_not_called()

    def test_exhausted_budget_prevents_remote_attempt(self):
        import time
        from unittest.mock import AsyncMock

        from starter.backend import Backend, BackendError

        async def run():
            backend = Backend(
                "http://localhost:1", "test-only", time.monotonic() + 55, max_attempts=3
            )
            backend.http.post = AsyncMock()
            try:
                with self.assertRaises(BackendError):
                    await backend.call("schedule_visit", ticket_id="T001")
                backend.http.post.assert_not_called()
            finally:
                await backend.close()

        asyncio.run(run())
