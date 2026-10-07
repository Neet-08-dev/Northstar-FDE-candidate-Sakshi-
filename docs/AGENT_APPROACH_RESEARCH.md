# Northstar agent approach research

Researched 7 October 2026. Recommendation only; no runtime selected, dependencies installed, or paid model calls made. Product facts below come from official documentation; suitability and development-effort judgments are engineering inferences, not measured benchmarks. Account access remains unverified.

## Working recommendation

Start with Python orchestration, structured language interpretation, deterministic business workflows, and evidence-backed outcomes. Allow a bounded model-directed investigation loop where variable record discovery earns its complexity. Keep the same permission and execution modules regardless of the model/runtime.

Shortlist direct model calls and the OpenAI Agents SDK for the default implementation; evaluate Cursor local Python SDK if using the existing plan is a priority. Pydantic AI is a credible alternative Python framework. Choose one after a small comparable experiment, rather than implementing all options. Decisions is an optional classifier, not the whole runtime.

The assignment's existing tool transport, business simulator, schemas, eight public cases, and Docker shell substantially reduce the implementation needed. Preserve per-request credentials, live policy/time, synchronous completion, the default 60-second deadline, and the 128-attempt session limit. See [runtime contract](API.md), [brief](../candidate-brief.md), and [tool schemas](../northstar/schema.py).

## Verified product facts

### OpenAI Decisions

Decisions is a public beta at `/v1/decisions`, currently supporting `gpt-6-luna`. It returns predicates, choices, and scores. Arbitrary structured extraction and tool-call arguments belong to Responses. Published pricing is $0.10 per million input tokens, with regional/long-context qualifications; the advertised speedup is not a Northstar benchmark. [Official guide](https://developers.openai.com/api/docs/guides/decisions).

Application judgment: potentially useful for routing and hazard screening. It adds another dependency and often another call because we still need IDs, amounts, and time extraction. Benchmark it only when it replaces work or meaningfully improves hazard recall/latency. A classification probability never establishes identity, credit eligibility, or permission. Include mixed/unknown cases rather than forcing every request into one workflow. Do not average away a safety incident through a severity score.

### Responses and OpenAI Agents SDK

Responses function calling lets the model request a function; our application executes it and returns the result for continuation. [Function calling](https://developers.openai.com/api/docs/guides/function-calling). Structured Outputs supplies schema-constrained output for extraction; semantic correctness still requires our validation and handling of refusals/failures. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

The Agents SDK supports Python and TypeScript application-owned integration. [SDK overview](https://developers.openai.com/api/docs/guides/agents/sdk). Its runner handles model/tool iterations and specialist handoffs. [Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents). Input, output, and tool guardrails have different scopes; approval pauses are separately supported. [Guardrails](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals).

Application judgment: use direct calls when interpretation plus ordinary workflows suffice; use the SDK if repeated investigative tool selection is valuable. Neither supplies Northstar's authorization rules. Put mandatory preconditions inside action wrappers and fail before calling the simulator. An SDK approval pause is not a Northstar supervisor grant: create the actual pending approval record and return the appropriate response.

OpenAI also has a distinct managed Agents API with durable sessions and managed orchestration. [Managed Agents](https://developers.openai.com/api/docs/guides/agents-api/overview). Application judgment: extra lifecycle integration offers little initial benefit for a short request that must finish before evaluation finalization. Local application function handlers can still reach local tools; hosted execution does not automatically see our Docker network.

### Cursor SDK

`cursor-sdk` supports Python, local custom functions, tool restrictions, cancellation, and usage reporting. Custom tools/restrictions are local-only; custom output schemas are not validated. Disabling `mcp` also removes custom tools; disabling `task` prevents subagents. [Python SDK](https://cursor.com/docs/sdk/python).

User-key SDK runs bill to the user's plan and share request pools/pricing with IDE/cloud usage. Custom tools skip interactive approval. TypeScript documents account-gated, local-only `systemPrompt` replacement; equivalent Python support was not established by the inspected Python page. [TypeScript SDK](https://cursor.com/docs/sdk/typescript).

Python uses a bundled bridge embedding the TypeScript runtime. [Bridge](https://cursor.com/docs/sdk/bridge).

Application judgment: a legitimate contender, with additional integration checks. Test the exact tool allowlist and disable ambient filesystem/shell/web/subagent capabilities. Use a fresh agent per Northstar request and a workspace without fixtures or secrets. Inspect output handling, cancellation, usage, and Linux-container startup. Do not assume a subscription gives unlimited usage or that evaluators can reuse personal authentication. Confirm reproducible credential configuration and the available fixed model before selection.

## Patterns other teams document

These are published engineering patterns and reference implementations, not proof that any framework passes Northstar.

* Anthropic distinguishes predefined workflows from model-directed agents and describes customer support with retrieval and programmatic actions. Its guidance favors adding complexity only when it improves measured outcomes. [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).
* LangGraph's email-support walkthrough separates classification, retrieval, actions, and human input using explicit state transitions. [Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph). Useful if we later need durable, long-lived review; for this assignment return a clarification or committed handoff rather than waiting indefinitely.
* Pydantic AI's bank-support example combines injected customer/database context, typed results, and tools. [Bank support](https://pydantic.dev/docs/ai/examples/conversational-agents/bank-support/). Tool schemas can derive from typed functions and docstrings. [Function tools](https://pydantic.dev/docs/ai/tools-toolsets/tools/). Borrow the context separation, but validate claims against actual actions: a returned flag alone does not prove that a card, ticket, or payment record changed.

## Option tradeoffs for this repository

| Approach | Benefit | Work or risk we retain | Initial fit |
| --- | --- | --- | --- |
| Plain Python workflows plus structured LLM calls | Small dependency surface; visible control flow; easy deterministic regression checks | Implement provider failure handling and any needed investigation loop | Leading baseline |
| OpenAI Agents SDK | Ready runner and tool integration | Business policy, execution reliability, deadlines, evidence, SDK behavior | Leading choice for adaptive investigation |
| Cursor local Python SDK | Existing plan may be economically useful; supplied agent loop | Constrain coding defaults; verify bridge/container/account capabilities | Worth a bounded trial |
| Pydantic AI | Python types, context injection, function tools | Framework learning and the same business correctness work | Good alternative if preferred by implementer |
| LangGraph | Explicit transitions and resumable state | Graph/checkpoint setup and learning overhead | Reconsider for long-lived workflows |
| Managed/cloud coding harness | Managed agent lifecycle | Connectivity, lifecycle, capability restrictions and latency | Defer unless experiments show a benefit |

“Fastest” means time to independently verified behavior, not time to the first model response. No framework removes the policy and evaluation work.

## AI versus deterministic responsibility

| Decision | Owner | Reason |
| --- | --- | --- |
| Meaning of varied language; multiple intents | AI proposes structured interpretation | Semantics and paraphrases vary |
| IDs, money, and date expressions | AI extracts candidates; code validates/resolves | Interpretation is uncertain; cents and UTC must be exact |
| Which records to investigate next | Code for known paths; bounded AI loop for ambiguity | Adaptability can help search, while limiting access and work |
| Actor, tenant, delegated role | Code using trusted context | User prose cannot establish authority |
| Coverage, active asset, ticket state, credit eligibility | Code using current authoritative records/policy | Explicit rules need consistent enforcement |
| Exact approval binding, expiry and remaining balance | Code | These are checkable conditions, not judgments of plausibility |
| Hazard recognition | Early deterministic signals plus semantic AI screening | Neither keyword matching nor a classifier alone establishes complete recall |
| Response to a detected hazard or live safety hold | Code | Required handoff and action restrictions must be enforced |
| Idempotency, retries, conflicts, budgets | Code | Correctness depends on operation identity and state |
| Clarification and handoff wording | AI may draft from a constrained outcome | Language generation helps usability |
| Status, committed IDs, amounts, times, evidence | Code from observed results | Prevent invented actions and commitments |

Unknown authorization/eligibility means no mutation. Unclear language means clarification or appropriate handoff. Model unavailability must have bounded degraded behavior; it must not silently turn into optimistic authorization. The system is hybrid: deterministic enforcement does not make semantic interpretation deterministic.

## Suggested loop and tools

1. Construct request-local dependencies from the trusted envelope; fetch context and policy.
2. Screen hazards early, before ordinary investigation or actions. Unverified actors cannot retrieve customer records; provide the appropriate real handoff without disclosure.
3. Interpret into a typed request with supported intent(s), candidate references, constraints, and unresolved details.
4. Run the workflow's required reads. Permit additional model-requested reads only through scoped, allowlisted wrappers.
5. Resolve identity and contradictions; ask a targeted question if action would require guessing.
6. Apply deterministic action preconditions immediately before execution.
7. Execute one logical write with an application-owned key. Replay identical arguments after uncertain success. Re-read/replan for a conflict rather than replaying stale state. Bound all attempts.
8. Build an outcome from confirmed tool results and validate the final response. Finish all writes before returning.

Use the supplied schemas as the contract reference, adapting explicitly to each provider's schema restrictions. Do not blindly forward model-generated arguments. Keep URL, token, idempotency keys, and trusted versions outside model-controlled inputs. Log local rejections as well as remote tool attempts.

The model-facing interface can be narrower than the twelve backend tools. For example, `handle_credit_request(invoice_id, amount_cents, reason)` can hide authoritative reads, eligibility, grant checking, approval-request creation, and safe credit execution. It returns a typed outcome such as credited, approval pending, blocked, or failed. This is a deep module because it concentrates business behavior and verification behind a small interface. Clarification must remain possible; a wrapper must never guess missing intent.

No standalone MCP server is necessary initially. Direct function wrappers fit the existing transport. Reconsider MCP only when sharing tools across independent clients earns the extra setup.

## Small experiment before committing

Timebox the comparison; do not build six complete integrations. Use identical deterministic workflows and fixtures, and compare a direct structured interpretation baseline with one SDK contender. If Cursor plan usage is the main constraint, prioritize Cursor as that contender. Add a Decisions classifier experiment separately only if routing/screening is the uncertainty we need to resolve.

Use eight representative cases: eligible scheduling; ambiguous site; eligible small credit; over-limit approval; cross-tenant attempt; indirect hazard; prompt injection in retrieved text; timeout after committed write. Repeat risky cases with fresh sessions, preserve every result, and retain other cases for final held-out evaluation.

Measure end-to-end correctness, forbidden remote attempts and locally rejected proposals, duplicates, truthful evidence, cold/warm latency, tool attempts, token usage/cost, and engineering time. The default task budget is 60 seconds; aim below it with explicit headroom for retries/handoffs. A proposed internal 45-second p95 target is an experiment target, not an assignment requirement or statistically strong claim from a tiny sample.

Inspect failures independently through finalized simulator state and audit, not the agent's explanation. Log concise decision reasons, policy version and record references, not private chain-of-thought. Pin package versions and the selected available model. Record unavailable cost data honestly.

For development speed, establish setup/check/eval commands and agent instructions first, then complete one workflow with its independent assertions. Reuse its request context, execution, and outcome modules across the next workflows. Use coding assistants for small changes with observable acceptance criteria; keep their development credentials separate from the submitted runtime.

The experiment still needs live account access and actual runs. No latency, reliability, spending, or account-entitlement result is claimed by this research.
