# Submission

- **Candidate identifier:** Sakshi.
- **Repository and exact commit:** [Northstar repository](https://github.com/Neet-08-dev/Northstar-FDE-candidate-Sakshi-), branch `staging` after this work merges. A commit cannot contain its own hash, so the exact SHA is given with the submission link; `git rev-parse HEAD` on that checkout shows it. Evaluation reports record prompt hashes, not Git SHAs.
- **Actual time spent:** about 7 to 8 hours in total, as estimated by the candidate. This is an estimate, not a measured duration.
- **Start command and health check:** `make setup`, put `OPENAI_API_KEY` in ignored `.env`, then `make dev` (or `docker compose up --build -d`). Demo: http://localhost:8000. Health: http://localhost:8000/health and http://localhost:8001/health.
- **Model/provider, settings and environment variable names (no values):** OpenAI Responses through the OpenAI Agents SDK. The service model is fixed in code to `gpt-6-luna` at high reasoning effort, with a 40-second provider timeout and provider retries disabled. Three agents: a safety screen (3,200 output tokens, one turn) runs in parallel with the interpreter (6,400 output tokens, eight turns, read-only scoped lookups), and an independent write check (2,400 output tokens, one turn) runs before the first business write. Only the evaluation runner can switch models (`--model gpt-6.1-sol`, low effort). Environment: `OPENAI_API_KEY`; `ADMIN_TOKEN` only for the local demo; `AGENT_PORT` and `MOCK_PORT` for Docker host ports. Environment values override `.env`.
- **Run public and authored evals:** `make check` runs lint, formatting, types and 71 offline tests, including all 196 authored scenarios and the sixteen demo examples. `make eval-live` runs the authored suite on Luna; add `--http` to `python -m evals.run` to go through the real `/process` handler, or `--suite demo` for the demo examples. `make public-evals` runs the eight published cases against running local services. `python -m evals.write_check_probe` tests the write check alone. See [EVALS.md](EVALS.md#submission-verification-8-october-2026) for results and exact commands.
- **Expected costs and required access:** Offline checks need no key. Live runs need an OpenAI key with `gpt-6-luna` access. A typical request uses about 5,000 to 6,000 input and 400 output tokens across the agents, roughly $0.001 at unverified third-party list prices ($0.10/M input, $0.50/M output); the responses report `cost_usd: null` because no verified price or invoice is available. A full live run of every authored case and demo example (207 requests on PR #12 code) used 1.10M input and 0.07M output tokens, about $0.15 at those prices. Docker is needed for the container demo.
- **Supported scope, limitations and known failures:** Ticket intake (record only, or record and book), booking on an existing ticket at the earliest slot or an exact time, slot options for missing or vague times, status answers for tickets, visits and credit eligibility, service credits within the live policy limit, supervisor-approval requests above it, exact grants, and copyable ticket-status and appointment messages. Safety hazards, unsupported work (cancel, reschedule, general billing questions, sending messages) and failures get a recorded human handoff. Times without a zone use the site's recorded timezone (UTC for every fixture site). `/process` is single-request; the demo keeps up to four earlier turns per conversation. Known weaknesses: hazard recognition and time reading depend on the model, so a provider outage becomes a human handoff; interpretation misses still occur on some wordings (listed in EVALS.md); the write check approved a wrong follow-up credit amount in 1 of 4 repeated probes, which also needs an interpreter error to matter; there is no transaction across eligibility reads and writes. See [DESIGN.md](DESIGN.md) and [EVALS.md](EVALS.md).
- **Ten-minute demo plan:** see [below](#ten-minute-demo-plan).
- **Relevant files and any interface/image changes:** [Design](DESIGN.md), [evaluation report](EVALS.md), [build log](AI_BUILD_LOG.md), [submission evidence](evidence/submission-evaluations.json), [runtime prompts](../starter/prompts/), [authored cases](../evals/) and [tests](../tests/). Runtime modules: `starter/orchestration.py` (interpretation, safety screen, write check, response), `starter/actions.py` (business rules and writes), `starter/backend.py` (scoped transport and exact retries). `starter/index.html`, `service_desk.js` and `service_desk.css` are the demo dashboard. The `/process` contract in `docs/API.md` is unchanged; `/demo`, `/demo/customers` and `/demo/end` are local demo routes. The Docker image installs locked dependencies and enables Python's fault handler.

POST `/process` accepts the per-request API URL and session token from [docs/API.md](../docs/API.md), and the hiring team's injected backend stays authoritative. The processing path never reads fixture files or needs administrative access. Remove `ADMIN_TOKEN` from the agent's environment to disable the demo routes during grading. Credentials are excluded from Git and the Docker build context.

## Local setup and demo

```sh
make setup
make check
make dev
```

`make setup` uses an installed `uv` or bootstraps a pinned copy into `.tools/`. `.python-version` selects Python 3.12 and `uv.lock` pins dependencies. Put the key in ignored `.env`. `make dev` stops its child services on exit. With Docker instead: `docker compose up --build -d`; set `AGENT_PORT`/`MOCK_PORT` to use other host ports.

Each conversation starts fresh synthetic state at 8 April 2030, 9:00 AM UTC. The header's customer picker chooses which of the eighteen synthetic customers owns the session (default Aster Foods, C001); `/demo` accepts only a known `customer_id`, and request text cannot change identity. A collapsible records card lists that customer's tickets, invoices, sites, equipment and contacts.

Sixteen examples, grouped as Visits, Tickets, Credits, Safety and Messages, read like requests from a site or finance lead. Selecting one fills Subject and Request; Send request makes a real call. For another customer, examples swap in that customer's own ticket, invoice, site, equipment and contact; four examples that need Aster Foods records keep their text and are labelled, which shows access scoping. Five examples start a conversation and show a suggested follow-up reply. Follow-ups continue the same synthetic session until New conversation.

Each response has a collapsed **Run details** box: outcome, customer, conversation turn, round-trip time, model and tokens, cost (unknown without verified pricing), the cited evidence, any message recipient, and the exact `/demo` response with a copy button. Messages appear once as subject and body with copy buttons; nothing is sent or stored.

## Ten-minute demo plan

| Time | Show | Point |
| --- | --- | --- |
| 0:00–1:00 | Header, customer picker, records card | Synthetic clock and data; identity comes from the session, not the text |
| 1:00–3:00 | Tickets › Ask for an update, then the two suggested follow-ups | Status from live records; "Yes please" books through the write check; the copyable confirmation. Open Run details: tokens, evidence, raw JSON |
| 3:00–4:00 | Visits › Visit tomorrow morning, then "10 AM tomorrow works" | Vague time gives verified slots; nothing is booked until the user chooses |
| 4:00–5:00 | Visits › Time that's taken, then Cancel a visit | Nearest open slots without silently booking; unsupported work gets a named handoff |
| 5:00–6:30 | Safety › Smoke from a unit, then Noise, not a hazard | Safety queue and guidance; a negated hazard books on the existing ticket without a duplicate |
| 6:30–8:00 | Credits › Are we owed a credit? then "Let's go with $75."; Larger credit; Another company's invoice | Eligibility facts, a credit within the limit, a pending supervisor approval, and a claimed-authority request blocked without disclosing the invoice |
| 8:00–9:00 | Tickets › Which unit?; switch to Birch Logistics and rerun a credit | Options instead of guessing; the same example refused for an unpaid invoice |
| 9:00–10:00 | EVALS.md submission table and known weaknesses | 212/212 latest live results, 8/8 published cases, what is still model-dependent |

## Review status

Earlier slices reached `staging` through pull requests the user reviewed and merged. This branch's changes and live runs are summarized in [EVALS.md](EVALS.md#submission-verification-8-october-2026). Historical reports, including failures, are committed in the [evidence archive](evidence/README.md).
