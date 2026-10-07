import asyncio
import json
import threading
import unittest
import uuid

from evals.run import CASES, load_cases, run_case
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
        for case in load_cases():
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
            for response in (one, two):
                self.assertIn("8 April 2030, 3:30 PM IST (UTC+05:30)", response["reply"])

            async def different_time(*_):
                return Decision(
                    intent="schedule",
                    ticket_id="T001",
                    time_mode="exact",
                    starts_at="2030-04-08T19:30:00+05:30",
                )

            conflict = asyncio.run(process_async(payload, different_time))
            self.assertEqual(conflict["status"], "needs_clarification")
            self.assertIn("8 April 2030, 3:30 PM IST (UTC+05:30)", conflict["reply"])
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

    def test_ist_display_preserves_booking_instant(self):
        cases = [
            (
                "2030-04-08T19:30:00+05:30",
                {},
                "completed",
                "8 April 2030, 7:30 PM",
                "2030-04-08T14:00:00Z",
            ),
            ("2030-04-08T18:30:00+05:30", {}, "needs_clarification", "8 April 2030, 3:30 PM", None),
            (
                "2030-04-09T01:30:00+05:30",
                {
                    "patches": [
                        {
                            "collection": "technicians",
                            "id": "TECH001",
                            "set": {"available_slots": ["2030-04-08T20:00:00Z"]},
                        },
                        {
                            "collection": "sites",
                            "id": "S001",
                            "set": {"access_window": "00:00-23:59 UTC"},
                        },
                    ]
                },
                "completed",
                "9 April 2030, 1:30 AM",
                "2030-04-08T20:00:00Z",
            ),
        ]
        for requested, fixture, status, displayed, stored in cases:
            with self.subTest(requested=requested):
                session = request_json(self.url + "/admin/sessions", fixture, self.admin)

                async def fixed(*_):
                    return Decision(
                        intent="schedule", ticket_id="T001", time_mode="exact", starts_at=requested
                    )

                try:
                    out = asyncio.run(
                        process_async(
                            {
                                "api_url": self.url,
                                "session_token": session["session_token"],
                                "run_id": "ist",
                                "request": {"id": "ist", "subject": "Visit", "body": "Book T001."},
                            },
                            fixed,
                        )
                    )
                    self.assertEqual(out["status"], status, out)
                    self.assertIn(displayed + " IST (UTC+05:30)", out["reply"])
                    state = request_json(
                        self.url + "/admin/sessions/" + session["session_id"] + "/finalize",
                        {},
                        self.admin,
                    )
                    visits = state["state"]["visits"]
                    self.assertEqual(
                        [visit["starts_at"] for visit in visits], [stored] if stored else []
                    )
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


class RecoveryAndExistingVisitTests(unittest.TestCase):
    """Real action/transport/world behavior, with cancellable HTTP delays."""

    def run_world(
        self,
        *,
        decision=None,
        body="Book T001 at the earliest slot.",
        patches=(),
        visits=(),
        delay_tool="",
        after_commit=False,
        faults=None,
    ):
        import time
        from unittest.mock import patch

        import httpx

        from northstar.world import ToolError, World, load_data
        from starter.backend import Backend

        world = World(
            load_data(),
            {"role": "customer", "customer_ids": ["C001"], "verified": True},
            "2030-04-08T09:00:00Z",
            faults=faults,
        )
        for collection, record_id, values in patches:
            next(row for row in world.data[collection] if row["id"] == record_id).update(values)
        world.data["visits"].extend(visits)
        requests = []
        cancelled = []
        original_client = httpx.AsyncClient

        async def transport(request):
            tool = request.url.path.rsplit("/", 1)[-1]
            args = json.loads(request.content)["arguments"]
            self.assertEqual(request.headers["authorization"], "Bearer scoped-test-token")
            self.assertEqual(request.url.host, "scoped.test")
            requests.append((tool, args))
            delayed = tool == delay_tool and sum(t == tool for t, _ in requests) == 1
            try:
                if delayed and not after_commit:
                    await asyncio.sleep(0.6)
                result = world.call(tool, args)
                if delayed and after_commit:
                    await asyncio.sleep(0.6)
                return httpx.Response(200, json={"result": result})
            except asyncio.CancelledError:
                cancelled.append(tool)
                raise
            except ToolError as exc:
                return httpx.Response(400, json={"error": exc.payload()})

        def backend_factory(url, token, deadline):
            return Backend(url, token, time.monotonic() + 5.3 if delay_tool else deadline)

        async def fixed(*_):
            return decision or Decision(intent="schedule", ticket_id="T001", time_mode="earliest")

        with (
            patch(
                "starter.backend.httpx.AsyncClient",
                side_effect=lambda **kw: original_client(
                    **kw, transport=httpx.MockTransport(transport)
                ),
            ),
            patch("starter.orchestration.Backend", side_effect=backend_factory),
        ):
            out = asyncio.run(
                process_async(
                    {
                        "api_url": "http://scoped.test",
                        "session_token": "scoped-test-token",
                        "run_id": "regression",
                        "request": {"id": "regression", "subject": "Service", "body": body},
                    },
                    fixed,
                )
            )
        return out, world, requests, cancelled

    def test_safety_handoff_survives_actual_cancellation(self):
        for source in ["request", "model", "asset", "ticket"]:
            for after_commit in [False, True]:
                with self.subTest(source=source, after_commit=after_commit):
                    patches = []
                    if source == "asset":
                        patches = [("assets", "A001", {"safety_hold": True})]
                    if source == "ticket":
                        patches = [("tickets", "T001", {"severity": "S1"})]
                    out, world, requests, cancelled = self.run_world(
                        body="Smoke is coming from the unit."
                        if source == "request"
                        else "Book T001.",
                        decision=Decision(intent="hazard") if source == "model" else None,
                        patches=patches,
                        delay_tool="escalate",
                        after_commit=after_commit,
                    )
                    self.assertEqual(cancelled, ["escalate"])
                    self.assertIn("Move away", out["reply"], out)
                    self.assertIn("emergency personnel", out["reply"])
                    self.assertEqual(out["status"], "escalated", out)
                    self.assertEqual([r["queue"] for r in world.data["escalations"]], ["safety"])
                    attempts = [args for tool, args in requests if tool == "escalate"]
                    self.assertEqual(len(attempts), 2)
                    self.assertEqual(attempts[0], attempts[1])
                    self.assertFalse(
                        any(
                            tool
                            in {
                                "schedule_visit",
                                "create_ticket",
                                "update_ticket",
                                "issue_credit",
                                "draft_message",
                                "request_approval",
                            }
                            for tool, _ in requests
                        )
                    )

    @staticmethod
    def visit(**changes):
        return {
            "id": "VISIT-EXISTING",
            "customer_id": "C001",
            "ticket_id": "T001",
            "technician_id": "TECH001",
            "starts_at": "2030-04-08T10:00:00Z",
            "duration_minutes": 60,
            "status": "scheduled",
            **changes,
        }

    def test_invalid_existing_visits_require_reconciliation(self):
        for values in [
            {"starts_at": "2030-04-07T10:00:00Z", "duration_minutes": 30},
            {"starts_at": "2030-04-08T09:00:00Z"},
            {"duration_minutes": 30},
            {"starts_at": "invalid"},
            {"starts_at": None},
            {"starts_at": "2030-04-08T10:00:00"},
            {"duration_minutes": "60"},
            {"technician_id": "UNKNOWN"},
            {"technician_id": "TECH003"},
            {"starts_at": "2030-04-08T23:00:00Z"},
        ]:
            with self.subTest(values=values):
                out, world, requests, _ = self.run_world(visits=[self.visit(**values)])
                self.assertEqual(out["status"], "escalated", out)
                self.assertNotIn("Already scheduled", out["reply"])
                self.assertNotIn("for one hour", out["reply"])
                self.assertEqual(len(world.data["visits"]), 1)
                self.assertEqual([r["queue"] for r in world.data["escalations"]], ["operations"])
                self.assertFalse(any(t in {"schedule_visit", "list_slots"} for t, _ in requests))

    def test_failed_safety_handoff_retains_guidance_without_claiming_success(self):
        for delay_tool in ["", "escalate"]:
            with self.subTest(delay_tool=delay_tool):
                out, world, requests, cancelled = self.run_world(
                    patches=[("assets", "A001", {"safety_hold": True})],
                    delay_tool=delay_tool,
                    faults={"escalate": [{"code": "DENIED"}]},
                )
                self.assertEqual(out["status"], "error", out)
                self.assertIn("Move away", out["reply"])
                self.assertIn("emergency personnel", out["reply"])
                self.assertIn("handoff could not be confirmed", out["reply"])
                self.assertNotIn("handoff is recorded", out["reply"])
                self.assertEqual(world.data["escalations"], [])
                self.assertFalse(any(t == "schedule_visit" for t, _ in requests))
                self.assertEqual(cancelled, ["escalate"] if delay_tool else [])

    def test_record_hazard_is_handled_before_further_reads(self):
        for collection, record_id, fields, forbidden in [
            ("tickets", "T001", {"severity": "S1"}, "assets"),
            ("assets", "A001", {"safety_hold": True}, "sites"),
        ]:
            for intent in ["schedule", "compose"]:
                with self.subTest(collection=collection, intent=intent):
                    out, world, requests, _ = self.run_world(
                        patches=[(collection, record_id, fields)],
                        decision=Decision(
                            intent=intent,
                            ticket_id="T001",
                            time_mode="earliest",
                            message_purpose="ticket_update" if intent == "compose" else "none",
                        ),
                    )
                    self.assertEqual(out["status"], "escalated", out)
                    self.assertEqual(world.data["escalations"][0]["queue"], "safety")
                    self.assertFalse(
                        any(args.get("collection") == forbidden for _, args in requests)
                    )

    def test_existing_visit_conflicts_and_changed_eligibility(self):
        from northstar.world import load_data

        contract = next(c["id"] for c in load_data()["contracts"] if "S001" in c["site_ids"])
        fixtures = [
            ([], [self.visit(id="VISIT-DUPLICATE")]),
            (
                [],
                [
                    self.visit(
                        id="VISIT-OVERLAP", ticket_id="T002", starts_at="2030-04-08T10:30:00Z"
                    )
                ],
            ),
            ([("technicians", "TECH001", {"active": False})], []),
            ([("technicians", "TECH001", {"available_slots": []})], []),
            ([("contracts", contract, {"ends_at": "2030-04-08"})], []),
        ]
        for index, (patches, extra) in enumerate(fixtures):
            with self.subTest(index=index):
                visit = self.visit(starts_at="2030-04-09T10:00:00Z") if index == 4 else self.visit()
                out, world, requests, _ = self.run_world(patches=patches, visits=[visit, *extra])
                self.assertEqual(out["status"], "escalated", out)
                self.assertEqual(len(world.data["visits"]), 1 + len(extra))
                self.assertFalse(any(t == "schedule_visit" for t, _ in requests))

    def test_valid_existing_visit_and_exact_time_conflict(self):
        for mode, requested, status in [
            ("earliest", "", "completed"),
            ("exact", "2030-04-08T15:30:00+05:30", "completed"),
            ("exact", "2030-04-08T14:00:00Z", "needs_clarification"),
        ]:
            with self.subTest(mode=mode, requested=requested):
                out, world, requests, _ = self.run_world(
                    visits=[self.visit()],
                    decision=Decision(
                        intent="schedule", ticket_id="T001", time_mode=mode, starts_at=requested
                    ),
                )
                self.assertEqual(out["status"], status, out)
                self.assertIn("8 April 2030, 3:30 PM IST", out["reply"])
                self.assertEqual(len(world.data["visits"]), 1)
                self.assertFalse(
                    any(t in {"schedule_visit", "list_slots", "escalate"} for t, _ in requests)
                )
