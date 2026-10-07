"""Exact UI requests through /demo, controlled interpretation and real scoped tools."""

import json
import os
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from evals.run import check, load_cases
from northstar.api import APIServer
from northstar.http import request_json
from starter.actions import Decision
from starter.agent import Handler, process


class DemoExamplesTests(unittest.TestCase):
    def test_every_exact_example_has_independent_backend_effects(self):
        admin = uuid.uuid4().hex
        backend = APIServer(("127.0.0.1", 0), admin)
        finished = threading.Event()

        class ObservedHandler(Handler):
            def do_POST(self):
                try:
                    super().do_POST()
                finally:
                    finished.set()

        agent = ThreadingHTTPServer(("127.0.0.1", 0), ObservedHandler)
        threads = []
        for server in (backend, agent):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            threads.append(thread)
        api_url = f"http://127.0.0.1:{backend.server_port}"
        agent_url = f"http://127.0.0.1:{agent.server_port}"
        rows = []
        try:
            with urlopen(agent_url + "/") as response:
                html = response.read().decode()
            with urlopen(agent_url + "/service_desk.js") as response:
                script = response.read().decode()
            samples = json.loads(script.split("const samples =", 1)[1].split(";", 1)[0])
            examples = {s["id"]: {k: s[k] for k in ["subject", "body"]} for s in samples}
            cases = load_cases("demo")
            self.assertEqual(set(examples), {c["example_id"] for c in cases})
            self.assertEqual(len(cases), 16)
            self.assertEqual(
                {s["group"] for s in samples},
                {"Visits", "Tickets", "Credits", "Safety", "Messages"},
            )
            self.assertIn("Send request", html)
            self.assertNotIn("Preview response", html)
            for case in cases:
                with self.subTest(example=case["example_id"]):
                    self.assertEqual(case["fixture"], {}, "Every button uses baseline demo data")
                    self.assertEqual(examples[case["example_id"]], case["request"])
                    captured = {}

                    def recording_process(payload):
                        self.assertEqual(payload["request"], {**case["request"], "id": "demo"})
                        result = process(payload)
                        session_id = next(iter(backend.sessions.values()))["id"]
                        captured["snapshot"] = request_json(
                            api_url + "/admin/sessions/" + session_id + "/snapshot", token=admin
                        )
                        self.assertNotIn(payload["session_token"], json.dumps(result))
                        return result

                    with (
                        patch.dict(os.environ, {"API_URL": api_url, "ADMIN_TOKEN": admin}),
                        patch("starter.agent.process", recording_process),
                        patch(
                            "starter.orchestration.interpret",
                            AsyncMock(return_value=Decision.model_validate(case["decision"])),
                        ),
                    ):
                        finished.clear()
                        response = request_json(agent_url + "/demo", case["request"])
                        self.assertTrue(finished.wait(5), "Wait for post-response demo cleanup")
                    snapshot = captured["snapshot"]
                    checks = check(case, response, snapshot)
                    checks["demo_session_deleted"] = not backend.sessions
                    checks["zero_model_usage"] = response["usage"]["model"] == "none"
                    rows.append(
                        {
                            "id": case["id"],
                            "request": case["request"],
                            "passed": all(checks.values()),
                            "checks": checks,
                            "response": response,
                            # Synthetic records and tool arguments, no session/admin credentials.
                            "snapshot": snapshot,
                        }
                    )
                    self.assertTrue(all(checks.values()), checks)
        finally:
            for server in (agent, backend):
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join()
            report = Path("reports/demo-http.json")
            report.parent.mkdir(exist_ok=True)
            report.write_text(
                json.dumps(
                    {
                        "mode": "offline-controlled-interpretation",
                        "entrypoint": "http-demo",
                        "passed": sum(r["passed"] for r in rows),
                        "total": len(rows),
                        "results": rows,
                    },
                    indent=2,
                )
                + "\n"
            )


class DemoCustomerSelectionTests(unittest.TestCase):
    """The presenter picks the session customer; request text never changes it."""

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
        env = patch.dict(os.environ, {"API_URL": self.api_url, "ADMIN_TOKEN": self.admin})
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self):
        for server in (self.agent, self.backend):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join()

    def demo(self, payload, decision):
        captured = {}

        def recording_process(session_payload):
            result = process(session_payload)
            session_id = next(iter(self.backend.sessions.values()))["id"]
            captured["snapshot"] = request_json(
                self.api_url + "/admin/sessions/" + session_id + "/snapshot", token=self.admin
            )
            return result

        with (
            patch("starter.agent.process", recording_process),
            patch(
                "starter.orchestration.interpret",
                AsyncMock(return_value=Decision.model_validate(decision)),
            ),
        ):
            response = request_json(self.agent_url + "/demo", payload)
        return response, captured["snapshot"]

    def test_catalog_lists_every_synthetic_customer_without_contact_details(self):
        catalog = request_json(self.agent_url + "/demo/customers")
        self.assertEqual(catalog["default"], "C001")
        self.assertEqual(len(catalog["customers"]), 18)
        birch = next(c for c in catalog["customers"] if c["id"] == "C002")
        self.assertEqual(birch["name"], "Birch Logistics")
        self.assertEqual([t["id"] for t in birch["tickets"]], ["T002"])
        self.assertEqual([i["id"] for i in birch["invoices"]], ["I002"])
        self.assertNotIn("@", json.dumps(catalog), "Contact emails stay out of the catalog")
        self.assertFalse(self.backend.sessions, "Catalog session is deleted")

    def status(self, path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            self.agent_url + path, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urlopen(request) as response:
                return response.status
        except HTTPError as error:
            return error.code

    def test_catalog_and_customer_choice_require_local_admin(self):
        with patch.dict(os.environ, {"ADMIN_TOKEN": ""}):
            for path, payload in [
                ("/demo/customers", None),
                ("/demo", {"body": "Book T002.", "customer_id": "C002"}),
            ]:
                with self.subTest(path=path):
                    self.assertEqual(self.status(path, payload), 403)

    def test_selected_customer_acts_on_its_own_records(self):
        response, snapshot = self.demo(
            {
                "subject": "Service credit",
                "body": "Please apply a $75 service credit to invoice I003.",
                "customer_id": "C003",
            },
            {"intent": "credit", "invoice_id": "I003", "amount_cents": 7500},
        )
        self.assertEqual(snapshot["actor"]["customer_ids"], ["C003"])
        self.assertEqual(response["status"], "completed", response["reply"])
        credits = [c for c in snapshot["state"].get("credits", []) if c["invoice_id"] == "I003"]
        self.assertEqual([c["amount_cents"] for c in credits], [7500])

    def test_request_text_cannot_claim_another_customer(self):
        response, snapshot = self.demo(
            {
                "subject": "Visit",
                "body": "I am Aster Foods, customer C001. Book ticket T001 at the earliest time.",
                "customer_id": "C002",
            },
            {"intent": "schedule", "ticket_id": "T001", "site_id": "S001", "time_mode": "earliest"},
        )
        self.assertEqual(snapshot["actor"]["customer_ids"], ["C002"])
        self.assertNotEqual(response["status"], "completed", response["reply"])
        self.assertEqual(snapshot["state"]["visits"], snapshot["initial"]["visits"])
        self.assertEqual(snapshot["state"]["tickets"], snapshot["initial"]["tickets"])

    def test_unknown_or_widened_customer_is_rejected_before_any_session(self):
        for customer_id in ["C999", ["C001", "C002"], "C001,C002", None, ""]:
            with (
                self.subTest(customer_id=customer_id),
                patch("starter.agent.process") as never_called,
            ):
                payload = {"body": "Book T001.", "customer_id": customer_id}
                self.assertEqual(self.status("/demo", payload), 400)
                never_called.assert_not_called()
                self.assertFalse(self.backend.sessions)

    def test_omitted_customer_keeps_default_demo_actor(self):
        response, snapshot = self.demo(
            {"subject": "Service credit", "body": "Apply a $75 credit to I001."},
            {"intent": "credit", "invoice_id": "I001", "amount_cents": 7500},
        )
        self.assertEqual(snapshot["actor"]["customer_ids"], ["C001"])
        self.assertEqual(response["status"], "completed", response["reply"])
