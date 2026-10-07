# AI development-tool build log — scheduling slice

Codex implemented the agreed Python/OpenAI Agents SDK design in an isolated worktree from origin/main. Codebase Design informed the action/process/transport interfaces; Writing for Agents informed AGENTS.md and the runtime instructions. No subagents or code-review workflow were used. Changes remain local.

The model initially proposed several file-level abstractions. Applying the depth/deletion tests reduced this to three meaningful modules, with response formatting kept internal. Dependencies are injected for controlled tests, while real HTTP integration uses the supplied simulator.

Verification uses Ruff, focused mypy, the original contract tests and 36 authored state/audit scenarios. A small Luna smoke run successfully booked a visit, asked for equipment clarification and recognized an indirectly described hazard. Docker was built and run independently of the pre-existing checkout's containers.

Consequential mistake: the first live grader accepted an operations handoff caused by provider failure in cases expecting an operations handoff for a business-policy reason. The larger run hit provider rate limits, exposing this false positive. The grader now requires completed model execution for model-backed cases, persists intermediate results and stops on provider failure. A regression test prevents treating unknown model usage as a successful model run. Raw earlier reports remain local; their aggregate is corrected in EVALS.md.

The account initially reported a 50-request allowance. Chrome inspection confirmed existing paid credits and a subsequently displayed Build tier. No credits were purchased, auto-reload enabled, or spending limits changed by Codex. Provider access is verified through actual calls, not inferred from the billing UI.

This log records observed work and failures; no quantified productivity comparison or final deployment reliability is claimed. Total assessment time, held-out evaluation and full Sol validation remain final-submission tasks.

After the user replaced the local key, the live demo booked successfully. A live development run exposed two interpretation mistakes: asking identity clarification for an explicit outside-account ID and for a policy incompatibility. The runtime instructions now preserve explicit booking intent and leave eligibility/access decisions to Python. Three Luna outside-account regression trials passed, followed by unchanged-prompt full suites (36/36 each on Luna and Sol) and twelve additional risky Sol trials (12/12). All offline checks still pass. The demo was rebuilt with the verified prompt, using the new ignored local configuration.

User-facing dates now use Asia/Kolkata (IST), including confirmations, existing visits and alternative slots. The dashboard explains the assessment’s fixed 2030 clock; synthetic records and UTC storage remain unchanged. All 24 offline tests pass, including IST date rollover, no-write alternatives and existing-visit replies. Two live Luna requests on the refreshed Docker demo confirmed an IST booking and an unavailable-slot alternative. The earlier full Luna/Sol evaluations precede the added prompt definition of IST; they were not rerun for this display change.
