# Working in this repository

Implement behind `starter.agent.process`; keep each request's injected tool URL
and session token authoritative. Runtime business data comes from scoped tools.
Fixture and admin access belongs exclusively to local demo/test administration.

Before changing request handling or actions, read `docs/API.md` and
`docs/DATA_DICTIONARY.md`. For policy behavior, inspect `knowledge/` as reference;
production decisions use the current policy returned by the tool backend.

Keep business checks and operation identity in `starter/actions.py`, transport
and exact retries in `starter/backend.py`, and SDK interpretation in
`starter/orchestration.py`. The runtime instruction source is
`starter/prompts/assistant.md`; edit it when interpretation behavior changes.

Use `make help` for setup and verification commands. `make check` runs offline.
Live evaluation consumes API credit and must be invoked explicitly. Keep secrets
in ignored local configuration, and report only sanitized outcomes and usage.

For behavior changes, verify observable outcomes and actual backend effects.
Include a failure or adversarial case for the changed rule. Completion requires
passing applicable offline checks, an honest report of live checks performed,
and any remaining unsupported behavior. Update the submission build log with
consequential mistakes and their regression checks. Keep changes local unless
publishing is explicitly requested.
