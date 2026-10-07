"""Exact UI requests through /demo, controlled interpretation and real scoped tools."""

import json
import os
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.request import urlopen

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
            examples = json.loads(html.split("const examples=", 1)[1].split(";", 1)[0])
            cases = load_cases("demo")
            self.assertEqual(set(examples), {c["example_id"] for c in cases})
            self.assertEqual(len(cases), 16)
            for group in ["Billing", "Scheduling", "Tickets", "Messages"]:
                self.assertEqual(sum(c["group"] == group for c in cases), 4)
                self.assertIn(f'aria-labelledby="{group.lower()}-heading"', html)
            for case in cases:
                with self.subTest(example=case["example_id"]):
                    self.assertEqual(case["fixture"], {}, "Every button uses baseline demo data")
                    self.assertEqual(examples[case["example_id"]], case["request"])
                    self.assertIn(f'data-example="{case["example_id"]}"', html)
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
