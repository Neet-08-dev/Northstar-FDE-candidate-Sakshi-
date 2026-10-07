# Submission

This is the integrated intake, scheduling, service-credit and copyable-message implementation. The selected A service desk presents sixteen demo requests, real outcomes and copyable messages. Natural dates use request-scoped time and default to IST. See [current verification](EVALS.md#service-desk-a-and-natural-time-7-october-2026); historical evaluation revisions and original submission fields remain below.

- Candidate identifier: Sakshi.
- Repository and exact commit: [Northstar repository](https://github.com/Neet-08-dev/Northstar-FDE-candidate-Sakshi-). This local UI integration starts at freshly fetched staging `118e5fad654ecc49c6fa8e94ec52e9c3e973efd2`, including safety/visit fixes and evaluation documentation. Branch `codex/northstar-ui-integration` is reserved for human review before publication. Use `git rev-parse HEAD` for the exact checkout revision. Historical evaluations retain their original revisions and hashes.
- Actual time spent: The candidate estimates 10 to 20 minutes of planning and about 30 minutes of review per slice, or 40 to 50 minutes combined. This excludes implementation/testing time and is not a measured total assessment duration. The complete total remains unrecorded.
- Start command and health check: Run `make setup`, configure ignored `.env`, then `make dev`. The default demo is http://localhost:8000; health checks are http://localhost:8000/health and http://localhost:8001/health. The isolated review dashboard uses ports 8070/8071 and the Docker command below.
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
AGENT_PORT=8070 MOCK_PORT=8071 docker compose -p northstar-ui-integration up --build -d mock-api agent
```

Open http://localhost:8070. Health endpoints are http://localhost:8070/health and http://localhost:8071/health. Stop this review project with `docker compose -p northstar-ui-integration down`.

Each submission starts fresh synthetic state at 8 April 2030, 2:30 PM IST. Examples cover Visits, Tickets, Credits, Safety and Messages with one category open at a time. Selecting fills Subject and Request, clears any old response and focuses Request. Send request performs a separate real submission. Desktop uses an example rail beside the composer and response; mobile stacks them and collapses example browsing after selection.

The [exact examples and expected effects](../evals/demo.json) use baseline account C001 without fixture patches or broader access. All sixteen scenarios match the current buttons, including ticket intake and additional failure cases. The default visit is T001 at 3:30 PM IST. "8 april 7:30 PM" uses 2030 and IST without extra date-format controls. Backend timestamps remain UTC. Missing or unavailable times ask for clarification without silently booking an alternative.

Messages appear once in subject/body previews with keyboard-accessible copy buttons. Named recipients must be registered and authorized for the site. No message is sent or stored. The combined booking-and-message example creates its own visit because no submission can retrieve a previous submission's booking. Replies render headings, paragraphs, bold, lists, quotations, code and HTTP(S) links. HTML and unsafe link schemes stay inert. The archived [earlier wording checks](evidence/demo-wording-checks.json) retain their original failed trials and prompt scope.

## Review status

The user reviewed and authorized integration of billing PR #5 and copyable-message PR #4. The integrated offline checks cover both workflows; separate historical live evaluations do not validate the combined prompt. The current demo verification is summarized separately in [EVALS.md](EVALS.md#grouped-demo-examples-7-october-2026); it does not establish full assignment completion or general live reliability. Historical reports are committed in the [archive](evidence/README.md), including failures. New demo screenshots, raw reports and backend snapshots remain in the ignored local review directory `candidate-submission/evidence/demo-examples/`. See [integration verification](EVALS.md#billing-and-message-integration-7-october-2026).

`make check` exercises 169 default authored scenarios and all sixteen current exact demo requests offline, plus natural-time and HTTP regressions. The sixteen demo scenarios are an opt-in `--suite demo` in the evaluation runner. Run `make eval-offline` only when you need its separate JSON report. The current-prompt six-case Sol HTTP sample passed; historical live samples still retain their original narrower scope. The live intake sample and repeat commands are recorded in [EVALS.md](EVALS.md).


The two credit examples request $75 and $150 against invoice I001. Under baseline policy, the first applies a credit and the second records a pending supervisor approval. The assistant cannot grant approval itself. Both examples use the same requests as the authored billing cases.

Run all authored workflows through the real HTTP handler with paid interpretation:

```sh
.tools/uv/bin/uv run --frozen python -m evals.run --http --interval 0 --out reports/current-http.json
.tools/uv/bin/uv run --frozen python -m evals.run --http --suite billing --interval 0 --out reports/billing-http.json
```

These commands start isolated local servers on ephemeral ports and clean up synthetic sessions. `--suite service` restricts the run to intake/scheduling; `--suite messages` selects message cases. Offline checks inject interpretation; they do not measure model understanding.
