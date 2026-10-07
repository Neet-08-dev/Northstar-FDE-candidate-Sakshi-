# Submission

This is the local intake and scheduling slice, not the final assessment submission. Original submission fields are retained below so remaining work is visible.

- Candidate identifier: Sakshi.
- Repository and exact commit: [Northstar repository](https://github.com/Neet-08-dev/Northstar-FDE-candidate-Sakshi-), branch `codex/scheduling-workflow`, [draft PR #1](https://github.com/Neet-08-dev/Northstar-FDE-candidate-Sakshi-/pull/1) against `staging`. The intake changes are committed locally on top of documentation commit `13c2154`, which follows runtime checkpoint `071a6f2`. PR #1 has not been updated for intake. Use `git rev-parse HEAD` for the exact checkout revision, and include the final selected SHA when submitting.
- Actual time spent: The candidate estimates 10 to 20 minutes of planning and about 30 minutes of review per slice, or 40 to 50 minutes combined. This excludes implementation/testing time and is not a measured total assessment duration. The complete total remains unrecorded.
- Start command and health check: Run `make setup`, configure ignored `.env`, then `make dev`. The default demo is http://localhost:8000; health checks are http://localhost:8000/health and http://localhost:8001/health. See the isolated Docker command below for ports 8010/8011.
- Model/provider, settings and environment variable names (no values): OpenAI Responses through the Agents SDK. Development defaults to `gpt-6-luna`; final validation uses `gpt-6.1-sol`. Low reasoning, 1,600 maximum output tokens and eight SDK turns. Configure `OPENAI_API_KEY` and optionally `OPENAI_MODEL`; environment values override `.env`. `ADMIN_TOKEN` is only for local demo administration. `AGENT_PORT` and `MOCK_PORT` select Docker host ports.
- Run public and authored evals: `make check` runs offline lint, formatting, types and tests. `make eval-offline` runs authored cases with controlled interpretation. `make eval-live` runs the current configured model and consumes credit. `make public-evals` runs the original public suite against default local service ports; unsupported workflows mean full success is not claimed. See [EVALS.md](EVALS.md) for Sol and repeated-trial commands.
- Expected costs and required access: Offline checks require no model key. Setup needs Python/bootstrap tooling and network access to dependencies. Docker is required for the container demo. Live requests need an OpenAI key with model access and available capacity. Dollar cost is unavailable; [EVALS.md](EVALS.md) reports measured tokens and explains the missing pricing/billing evidence. No fixed spend estimate is claimed.
- Supported scope, limitations and known failures: Ticket-only intake, intake followed by authorized booking, existing open-ticket reuse, earliest or exact times, clarification and real handoffs. Billing, ticket updates, cancellation, rescheduling and message drafting are unsupported. The demo resets state per submission; persistent clarification remains incomplete. See [DESIGN.md](DESIGN.md) and [EVALS.md](EVALS.md) for specific failure modes and verification limits.
- Ten-minute demo plan: Show ticket-only intake and a combined service request, then ambiguous equipment, a safety handoff and a ticket retained after an unavailable booking time. Inspect the retry and duplicate-race evidence.
- Relevant files and any interface/image changes: [Design](DESIGN.md), [evaluation report](EVALS.md), [build log](AI_BUILD_LOG.md), [sanitized evidence](evidence/scheduling-evaluations.json), [repository instructions](../AGENTS.md), [runtime prompt](../starter/prompts/assistant.md), [authored cases](../evals/scheduling.json) and [tests](../tests/test_scheduling.py). Runtime modules are `starter/orchestration.py`, `starter/actions.py` and `starter/backend.py`. `starter/index.html` provides the demo, and the Docker image installs locked Python dependencies. The existing `/process` contract remains intact; `/demo` is a local convenience route.

POST `/process` accepts the per-request API URL and session token from [docs/API.md](../docs/API.md). The hiring team's injected backend remains authoritative. The processing path neither reads fixture files nor requires administrative access. Remove `ADMIN_TOKEN` from the runtime environment to disable `/demo` during grading. Credentials are excluded from Git and the Docker build context.

## Local setup and demo

```sh
make setup
make check
make dev
```

`make setup` uses installed uv or bootstraps a pinned local copy. `.python-version` selects Python 3.12 and `uv.lock` pins dependencies. Put the key in ignored `.env`; never include it in a commit. `make dev` stops its child services on exit.

For the isolated Docker demo used during development:

```sh
AGENT_PORT=8010 MOCK_PORT=8011 docker compose -p northstar-scheduling up --build -d
```

Open http://localhost:8010. Health endpoints are http://localhost:8010/health and http://localhost:8011/health. Stop it with `docker compose -p northstar-scheduling down`.

Each submission starts fresh synthetic state at the fixed scenario time of 8 April 2030, 14:30 IST. This keeps availability and contract checks repeatable. The default example books T001 at 15:30 IST that day. Backend timestamps remain UTC. The example buttons include a named annex issue without internal IDs, intake with a maintenance visit, existing-ticket booking, ambiguity, a safety hazard and an exact time. To see partial completion, request: "A101 at S101 stopped cooling. Create a ticket and book a visit at 18:30 IST on 8 April 2030."

## Review status

The implementation PR is a draft and remains unmerged. The user is reviewing it. No code-review workflow has been run and auto-merge is off. The documentation correction is committed locally. Intake code and its results are committed locally for review; no new PR or push was made. Full model results, later IST checks and unmeasured production claims are distinguished in [EVALS.md](EVALS.md).

`make check` already exercises every authored scenario offline. Run `make eval-offline` only when you need its separate JSON report. The live intake sample and repeat commands are recorded in [EVALS.md](EVALS.md).
