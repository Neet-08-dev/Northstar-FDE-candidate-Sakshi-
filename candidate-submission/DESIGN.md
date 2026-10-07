# Design

This document describes intake, scheduling and service credits. Billing builds on staging commit `e61a9510635d67be8bb2ce80924c1168bc099582`, which includes the merged intake PR. Proposed production rollout steps remain separate from implemented behavior.

## Workflow and success criteria

Northstar staff receive email and portal requests, then cross-reference customer accounts, equipment, open tickets and technician availability. Customers need a confirmed appointment or a clear next step. Dispatch staff need accurate bookings, and safety/operations staff need recorded handoffs when routine service cannot proceed.

The implemented workflow records or reuses a service ticket and, when requested, books a qualified one-hour visit. Existing-ticket scheduling remains supported. It accepts an explicitly authorized earliest slot or an exact date, time and timezone. It checks identity, coverage, safety and availability before booking. Unclear requests ask for clarification; hazards and unsupported work receive a handoff. See [the evaluation bar](EVALS.md#deployment-quality-bar) for measurable acceptance checks.

A ticket tracks the service problem; a visit tracks its appointment. A ticket ID is an optional customer shortcut. The interpreter can search scoped sites, assets and tickets to resolve descriptions without IDs. An unambiguous request to send a technician permits creating a missing ticket. A symptom report alone asks whether to record an issue or book a visit. Intake supports one asset per request and S2 interruptions or S3 nonurgent maintenance. Python maps the interpreted issue category to severity; hazards receive an immediate safety handoff. Existing-ticket severity and status are preserved.

The current assumptions are that the injected session establishes customer identity, the backend provides authoritative records, and scheduling permission comes from the request. The fixed 2030 scenario clock belongs to the assessment. Replies display IST while stored timestamps retain the UTC contract.

Questions for a real customer remain open:

- How do customers identify equipment, and which site labels or serial numbers are familiar to them?
- Does the agreed permission rule for technician requests fit the customer's operating process?
- Who owns each handoff queue, and what acknowledgment can we promise?
- What request volume, response target and escalation capacity must the service support?

## Architecture and AI choices

`starter.agent.process` accepts the existing HTTP contract. One OpenAI Agents SDK agent interprets the request and returns a typed decision. Python executes the business action and constructs the response from confirmed results.

| Module | Responsibility |
| --- | --- |
| `starter/orchestration.py` | Request validation, model interpretation, read-only investigation, execution budget and final response assembly. |
| `starter/actions.py` | Service and credit eligibility, supervisor approval checks, ticket reuse/creation, scheduling, stable operation identity, committed outcomes and handoffs. |
| `starter/backend.py` | Request-scoped HTTP transport, scoped record lookup, evidence references and exact retries. |

The model handles varied language and candidate record selection. Deterministic code owns authority, relationships, live policy, time validation and writes. Tests inject an interpreter or transport at these interfaces and inspect simulator state independently of the reply. Response formatting stays within the action module.

Python fits the supplied service. The Agents SDK provides the model/tool loop and structured output, avoiding a custom loop. A plain Python/OpenAI client implementation would reduce framework dependency but require that orchestration code. A coding-agent runtime would add capabilities this request-processing service does not need. No separate MCP server or multi-agent hierarchy is required for this slice. These are design tradeoffs, not comparative performance measurements.

Development trials used `gpt-6-luna`; `gpt-6.1-sol` is the default for the reviewed implementation and final validation. Repeated Luna failures on the outside-account, missing-amount case motivated this choice. Luna remains an explicit environment override. Both use Responses through the SDK with low reasoning. Exact settings and evaluation revisions are recorded in [EVALS.md](EVALS.md).

## Trust, authority and reliability

Each request's injected API URL and session token remain authoritative. Processing never reads local fixtures or requires an admin credential. The optional demo uses separate admin access to allocate synthetic sessions. Identity and scenario time come from trusted context; current policy governs actions. User requests and record notes cannot grant authority. Model investigation exposes selected record fields and excludes free-text notes.

Record lookup first searches within the scoped collection. Python checks customer relationships, role, active account/site/asset, ticket state, service coverage, safety clearance, site access and technician skill, region and availability. Current safety signals cause an immediate safety handoff. Indirect hazard interpretation also uses the model. Final evidence identifies records actually read or created.

Writes are serialized within each request. Retries replay the same complete arguments and idempotency key, with at most three attempts per call. A slot/version conflict permits one fresh investigation. Existing visits are reused; a different requested time requires confirmation rather than silently rescheduling. The backend handles booking conflicts, while this slice does not perform versioned ticket updates. Changes between policy/coverage reads and a booking remain a race partly controlled by backend checks.

Execution is bounded to eight SDK turns, 48 backend attempts and a 55-second processing budget. Recovery reserves five seconds and three attempts. Provider retries are disabled. Unresolved or uncertain processing creates an operations handoff when possible; a failed handoff returns an error. The assistant never claims an unconfirmed booking or repair completion.

General billing inquiries, standalone approval-status queries, existing-ticket severity/status updates, cancellation, rescheduling and message drafting are unsupported. They receive a human handoff. Service-credit requests and their approval workflow are supported as described below.

## Service credits and supervisor approval

The action interface remains `Actions.handle(Decision)`. A credit decision supplies candidate invoice, ticket or equipment identity and an exact integer-cent amount. A small interface hides scoped relationship lookup, role checks, ledger validation, current policy, approval discovery and financial writes. The model resolves descriptions through read-only scoped tools. Python follows equipment to a unique ticket and invoice, and asks when those relationships are ambiguous. Explicit conflicting references remain constraints. A credit request and a service request in the same message require clarification before either workflow runs.

The permitted session roles are customer, dispatcher, finance and supervisor. Viewers cannot request approval or issue credits; an unverified requester receives an identity handoff before customer reads. A paid invoice and the linked ticket's authoritative SLA breach are required even when a supervisor grant exists. Credits cannot exceed the remaining paid amount. Invalid ledger types, currencies, relationships or policy shapes receive a billing handoff. Requests over the available balance ask whether to use the smaller amount; they never silently change the request. No remaining amount means refusal. Missing or unsupported amounts require clarification, and requested non-USD credits are refused without conversion.

The action reads current policy again after interpretation. The structured limit and always-requires-approval flag determine whether a grant is needed. A grant must belong to the same customer, invoice and exact amount, have granted status, come from a supervisor, and expire strictly after the trusted clock. Consumed grants cannot be reused. Search discovers candidates; a fresh record read verifies them. Otherwise the action reuses an exact pending request or creates one and reports that no credit has been applied. A user claim, pasted ID or job title cannot grant authority. The assistant cannot approve its own request or transfer funds to a bank account.

Operation identity lives in `actions.py`; `backend.py` freezes the full request for exact retries. A committed credit or approval request followed by a timeout yields one stored effect and the same receipt on retry. The action does not submit a different amount or a replacement operation after an uncertain failure. Billing recovery uses the billing queue and preserves the verified ticket ID. The same verified-ID fallback fixes existing-ticket scheduling failures that previously lost escalation linkage.

The backend has no transaction spanning all eligibility reads, approval requests and writes. Atomic credit checks and grant consumption protect the final credit, but approval-request eligibility can change after the last read. There is no cross-session deduplication or persistent conversation state. The demo starts a fresh session for every submission; an approval cannot be granted through the assistant. Tests install grants through local administration only.

## Intake execution and partial completion

`Actions.handle(Decision)` remains the action interface. Intake adds an issue category, a bounded factual summary and an explicit ticket-only or ticket-and-booking mode. Shared private checks validate scoped identity, active records, coverage and safety before either workflow writes. Booking-specific policy, slots and technician checks remain in scheduling. Backend transport requires no change.

Intake reuses an open/in-progress ticket for the asset, or creates one using a stable operation key. A duplicate-creation conflict triggers one fresh scoped lookup and eligibility check. Multiple open tickets require reconciliation. Exact retry preserves both arguments and key after a lost response. Explicit inaccessible or resolved ticket references never authorize creating a replacement.

Creation and booking are separate writes. A confirmed ticket remains when booking needs clarification or fails, and its ID and evidence remain in the response and recovery handoff. Missing booking time does not prevent authorized intake. Requests conditioned on successful booking require clarification before writing because the backend has no transaction spanning both actions. A failed handoff returns error rather than claiming a completed escalation.

Authorization to create, issue classification and conditional-request recognition depend on interpretation. The action module independently enforces tenant, role, relationships and live eligibility. Coverage/safety changes between reads and creation remain a race because the backend does not atomically enforce all preconditions. No new top-level runtime modules were added.

## Observability and rollout

The service logs tool names, attempt counts, result codes, durations, request outcomes and usage. It omits credentials and raw prompts. SDK remote tracing and response storage are disabled. These logs are basic observability, not a complete distributed trace system. The evaluation runner records sanitized tool events and checks simulator state/audit. [EVALS.md](EVALS.md) separates measured latency and tokens from unavailable billed cost.

Only the synthetic local demo has been exercised. The following rollout is proposed, not implemented:

1. Complete the supported-scope checks against the exact release revision, including human inspection of clarification and safety replies.
2. Evaluate recorded, sanitized customer-like requests without production writes. Agree handoff ownership and response targets with operators.
3. Pilot a limited account group with human approval of bookings and alerts for uncertainty, provider failure and unexpected write attempts.
4. Expand only after the pilot meets agreed safety, correctness, latency and cost thresholds.

Current controls are process/container shutdown, model configuration and removal of `ADMIN_TOKEN` to disable the local demo route. There is no production write-disable switch, operator console or admission controller. A production pilot would require those controls. Rollback would stop new requests and redeploy a previously verified revision, then reconcile uncertain or committed visits with operations. Reverting code does not undo business writes. This rollback procedure has not been rehearsed in production.

Known limitations include false alarms for negated or historical hazard words, model dependence for indirect hazards, unsupported broad time windows and overnight access windows, and no transactional guarantee across all eligibility reads. The demo resets state per submission and is not a persistent customer conversation. See [the evaluation limits](EVALS.md#dataset-and-graders).

## Time spent and tradeoffs

The candidate estimates 10 to 20 minutes of planning and about 30 minutes of review per slice, or 40 to 50 minutes combined. This excludes implementation/testing time and is not a measured total assessment duration. The complete total remains unrecorded. Commit timestamps do not establish time worked. No time-saving estimate is claimed.

The implementation retains the same three modules and independent failure checks. General billing support, persistent clarification, production operator controls and held-out evaluation remain deferred. [AI_BUILD_LOG.md](AI_BUILD_LOG.md) records the development workflow and corrections.

At 800 requests/day, daily averages alone cannot size the system. A production design would need measured peak concurrency and provider capacity, admission control, explicit queue/deadline behavior, operator handoff capacity and transactional protection for eligibility changes. Load tests and verified pricing would be needed before making throughput or cost commitments. None of those production measurements has been performed.
