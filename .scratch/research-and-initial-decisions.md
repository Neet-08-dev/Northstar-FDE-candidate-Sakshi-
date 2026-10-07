# Northstar: research and initial decisions

Updated 7 October 2026. Architecture agreed; agent implementation pending.

## Decision

Build one bounded decision agent between incoming requests and the existing Northstar tools. Use **Python + OpenAI Agents SDK + an OpenAI API key**. API usage is separate from the Codex subscription. No subscription sign-in integration is planned.

The SDK owns the model/tool iteration loop. Our code owns business correctness. Start with direct function wrappers; no separate MCP server or multi-agent hierarchy is needed initially.

## Responsibility and rationale

| AI | Deterministic Python |
| --- | --- |
| Interpret varied language, extract candidate details, investigate ambiguity, select safe tools, draft replies. Language and investigation paths vary. | Enforce identity, tenant/role, live policy, eligibility, exact approvals, money/time validation, idempotency, retries, conflicts, and execution budgets. These rules must hold regardless of model behavior. |

Expose a small, typed tool surface with mandatory checks inside action implementations. Construct final status and evidence from confirmed backend results. Missing authority or eligibility must block mutations; ambiguous requests may require clarification or a real handoff.

## Research conclusion

The Agents SDK saves orchestration work while fitting the existing Python service. Cursor SDK is viable but adds coding-runtime restrictions and integration checks. Plain Python would require maintaining the agent loop ourselves. Decisions API is an optional classifier, not necessary for the initial agent.

Sources: [Agents SDK runner](https://developers.openai.com/api/docs/guides/agents/running-agents), [Cursor Python SDK](https://cursor.com/docs/sdk/python), [Decisions API](https://developers.openai.com/api/docs/guides/decisions). Detailed comparison: [earlier research](../docs/AGENT_APPROACH_RESEARCH.md). **This note supersedes its undecided runtime recommendation and proposed framework comparison.** Product facts should be rechecked when integrating.

The assignment permits this choice: [README](../README.md), [brief](../candidate-brief.md). Preserve the [API contract](../docs/API.md); do not access fixtures directly at runtime.

## Proposed checkpoints

1. Define supported scenarios, acceptance criteria, and module boundaries.
2. Build reliable backend access and deterministic business actions.
3. Connect one SDK agent and verify a complete workflow.
4. Evaluate normal, ambiguous, risky, failure, and retry scenarios; retain regressions.
5. Finish demo, required submission documents, and reproducible setup.

Organize by responsibility: orchestration, business rules/actions, backend access, and evaluation. Exact module names remain open. Provide coding agents with a short repository guide, explicit boundaries, and repeatable setup/check commands. Keep fast deterministic checks separate from live model evaluations.

Next decisions: first vertical slice, model, budget, dependency versions, and evaluation cases. No API key has been configured or verified in this work.
