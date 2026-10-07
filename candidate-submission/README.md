# Local review: scheduling slice

Candidate: Sakshi. This is the first working slice, not the final assessment submission.

From the worktree root:

```sh
make setup
make check
make dev
```

`make setup` uses installed uv or bootstraps a pinned local copy. Python 3.12 is selected by `.python-version`; dependencies are locked in `uv.lock`. `make dev` starts the mock and assistant on ports 8001/8000 and stops both on exit. Configure `OPENAI_API_KEY` in ignored `.env`. `OPENAI_MODEL` defaults to `gpt-6-luna`; use `gpt-6.1-sol` for final validation. Environment variables override `.env`. No model call occurs in `make check`.

For the isolated Docker demo used in this review:

```sh
AGENT_PORT=8010 MOCK_PORT=8011 docker compose -p northstar-scheduling up --build -d
```

Open http://localhost:8010. Health endpoints: http://localhost:8010/health and http://localhost:8011/health. Stop with `docker compose -p northstar-scheduling down`. Each demo submission uses fresh synthetic state. The default example books T001 at 2030-04-08T10:00:00Z. Buttons also cover ambiguity, a safety hazard and an exact time. The request body, not this example's IDs, drives interpretation.

Verification commands:

```sh
make eval-offline
make eval-live
OPENAI_MODEL=gpt-6.1-sol .tools/uv/bin/uv run python -m evals.run --cases earliest,ambiguous-equipment,indirect-hazard --out reports/sol-smoke.json
```

Live evaluations consume the existing API balance and stop on provider failure. `--cases`, `--trials` (1–5), `--interval` and `--out` select the run. Reports are ignored local artifacts. Run the original full public suite with `make public-evals` against the default local ports; it includes ticket creation and billing workflows not yet implemented.

POST /process honors per-request api_url/session_token and finishes synchronously. The runtime never requires an administrative credential. ADMIN_TOKEN is for the optional local demo only; remove it from the environment to disable /demo during grading. Keys are excluded from Git and Docker build context.

Ten-minute walkthrough: ordinary booking and confirmed evidence (3 min), unclear equipment (2 min), safety escalation (2 min), timeout replay and independent evaluation results (3 min). Review this local branch with `git diff origin/main...HEAD`; the exact local commit is available from `git rev-parse HEAD`. No push or code review has been performed.
