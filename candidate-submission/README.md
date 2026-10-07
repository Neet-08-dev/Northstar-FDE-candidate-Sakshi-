# Submission

This is the integrated intake, scheduling, service-credit and copyable-message implementation. The grouped demo adds sixteen independent customer requests. See [demo verification](EVALS.md#grouped-demo-examples-7-october-2026) for this slice; original submission fields remain below so remaining work is visible.

- Candidate identifier: Sakshi.
- Repository and exact commit: [Northstar repository](https://github.com/Neet-08-dev/Northstar-FDE-candidate-Sakshi-). Billing PR #5 and message PR #4 are merged. This demo slice starts at integrated staging `4f0fef4009c502be85de076c6d330774a0f35b9b`. Use `git rev-parse HEAD` for the exact checkout revision. Historical evaluations retain their original revisions and hashes.
- Actual time spent: The candidate estimates 10 to 20 minutes of planning and about 30 minutes of review per slice, or 40 to 50 minutes combined. This excludes implementation/testing time and is not a measured total assessment duration. The complete total remains unrecorded.
- Start command and health check: Run `make setup`, configure ignored `.env`, then `make dev`. The default demo is http://localhost:8000; health checks are http://localhost:8000/health and http://localhost:8001/health. See the isolated Docker command below for ports 8020/8021.
- Model/provider, settings and environment variable names (no values): OpenAI Responses through the Agents SDK. The default model is `gpt-6.1-sol`. Development can explicitly select `gpt-6-luna`, whose observed interpretation failures are retained in EVALS.md. Low reasoning, 1,600 maximum output tokens and eight SDK turns. Configure `OPENAI_API_KEY` and optionally `OPENAI_MODEL`; environment values override `.env`. `ADMIN_TOKEN` is only for local demo administration. `AGENT_PORT` and `MOCK_PORT` select Docker host ports.
- Run public and authored evals: `make check` runs offline lint, formatting, types and tests. `make eval-offline` runs authored cases with controlled interpretation. `make eval-live` runs the current configured model and consumes credit. `make public-evals` runs the original public suite against default local service ports. See [EVALS.md](EVALS.md) for exact results, Sol checks and repeated-trial commands.
- Expected costs and required access: Offline checks require no model key. Setup needs Python/bootstrap tooling and network access to dependencies. Docker is required for the container demo. Live requests need an OpenAI key with model access and available capacity. Dollar cost is unavailable; [EVALS.md](EVALS.md) reports measured tokens and explains the missing pricing/billing evidence. No fixed spend estimate is claimed.
- Supported scope, limitations and known failures: Ticket-only intake, intake followed by authorized booking, existing open-ticket reuse, earliest or exact times, clarification and real handoffs. Service credits support paid invoices with recorded SLA breaches, current policy limits, exact supervisor grants and pending approval requests. Copyable ticket-status and confirmed-appointment messages are supported, alone or explicitly combined with intake/booking. General billing questions, standalone approval-status queries, ticket updates, cancellation, rescheduling, stored drafts and message sending are unsupported. Mixed billing/service requests ask which workflow to handle first. The demo resets state per submission; persistent clarification remains incomplete. See [DESIGN.md](DESIGN.md) and [EVALS.md](EVALS.md) for specific failure modes and verification limits.
- Ten-minute demo plan: Show ticket-only intake and a combined service request, then ambiguous equipment, a safety handoff and a ticket retained after an unavailable booking time. Show a $75 credit and a $150 pending approval, then inspect the ledger, grant-consumption and exact-retry evidence.
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
AGENT_PORT=8020 MOCK_PORT=8021 docker compose -p northstar-billing up --build -d
```

Open http://localhost:8020. Health endpoints are http://localhost:8020/health and http://localhost:8021/health. Stop it with `docker compose -p northstar-billing down`.

Each submission starts fresh synthetic state at 8 April 2030, 14:30 IST. The four example lists cover Billing, Scheduling, Tickets and Messages. Selecting a button fills both Subject and Request and focuses Request. Send request remains a separate action. The layout uses four columns on desktop, two on tablet and one on narrow screens.

The [exact examples and expected effects](../evals/demo.json) use baseline account C001 without fixture patches or broader access. The default visit is T001 at 15:30 IST. Backend timestamps remain UTC. The over-total credit request asks for $600 against I001's $501 remaining balance. It receives clarification about a lower amount and creates neither credit nor approval; it is not an unpaid-invoice refusal.

Messages contain copyable text in the existing reply area. Named recipients must be registered and authorized for the site. No message is sent or stored. The combined booking-and-message example creates its own visit because no submission can retrieve a previous submission's booking. The archived [earlier wording checks](evidence/demo-wording-checks.json) retain their original failed trials and prompt scope.

## Review status

The user reviewed and authorized integration of billing PR #5 and copyable-message PR #4. The integrated offline checks cover both workflows; separate historical live evaluations do not validate the combined prompt. The current demo verification is summarized separately in [EVALS.md](EVALS.md#grouped-demo-examples-7-october-2026); it does not establish full assignment completion or general live reliability. Historical reports are committed in the [archive](evidence/README.md), including failures. New demo screenshots, raw reports and backend snapshots remain in the ignored local review directory `candidate-submission/evidence/demo-examples/`. See [integration verification](EVALS.md#billing-and-message-integration-7-october-2026).

`make check` exercises the 158 default authored scenarios and all sixteen exact demo requests offline. The demo variants are an opt-in `--suite demo` in the evaluation runner to avoid duplicating them in the default action suite. Run `make eval-offline` only when you need its separate JSON report. The live intake sample and repeat commands are recorded in [EVALS.md](EVALS.md).


The two credit examples request $75 and $150 against invoice I001. Under baseline policy, the first applies a credit and the second records a pending supervisor approval. The assistant cannot grant approval itself. Both examples use the same requests as the authored billing cases.

Run all authored workflows through the real HTTP handler with paid interpretation:

```sh
.tools/uv/bin/uv run --frozen python -m evals.run --http --interval 0 --out reports/current-http.json
.tools/uv/bin/uv run --frozen python -m evals.run --http --suite billing --interval 0 --out reports/billing-http.json
```

These commands start isolated local servers on ephemeral ports and clean up synthetic sessions. `--suite service` restricts the run to intake/scheduling; `--suite messages` selects message cases. Offline checks inject interpretation; they do not measure model understanding.
