# AI development-tool build log

This records scheduling, intake and billing development. It summarizes sanitized evidence rather than private transcripts or model reasoning. Historical checkpoints below retain their original scope; the billing entry describes the current local branch.

## Local billing implementation, 7 October 2026

The user approved the service-credit workflow, asking for missing amounts, asking before reducing a request to the available balance, automatically requesting necessary supervisor approval, and clarifying mixed billing/service requests before writes. They authorized offline and paid end-to-end verification in this chat and a local commit for review. The isolated branch is `codex/billing-approvals`, based on staging `e61a9510635d67be8bb2ce80924c1168bc099582` after PR #2 merged. No publication or merge is part of this work.

Codebase Design kept one credit workflow behind the existing action interface. Python owns invoice/ticket relationships, integer-cent amounts, role and tenant checks, paid status, authoritative SLA breach, remaining balance, current limits and exact supervisor grants. The model interprets intent and resolves descriptions. Operation-key construction moved from backend.py to actions.py, matching repository ownership rules. Transport still freezes complete requests for retries. No runtime module, agent hierarchy or subagent was added.

The initial implementation left equipment-to-ticket lookup to the model. A five-case Luna HTTP sample passed four cases and safely asked for clarification on the named-equipment case. Two diagnostic trials reproduced intermittency: one passed, one failed. Scoped lookup traces showed the failed trial searching tickets by the equipment label instead of its asset ID. Python now follows the verified asset ID to a unique ticket and invoice; the model only resolves the equipment description. Three consecutive HTTP regression trials passed. This is a concrete benefit of concentrating relationship rules inside the action module rather than relying on repeated model searches.

The first full live suite passed 105/105 authored cases. The published Docker suite then passed 6/8. One failure was a clarification reply that omitted the expected site term. The other exposed an ordering mistake: a request for an outside-account invoice with no amount asked for an amount before checking access. Neither failure attempted a financial write. The reply now names the relevant site; explicit invoice/ticket identity survives a missing amount, and Python checks access before asking for that amount. A new authored regression checks the missing-amount cross-tenant case. Final results and every retained development failure are in EVALS.md.

The next Luna sweep passed 105/106, with an unnecessary amount clarification when a real amount appeared alongside a pasted approval ID. The second published sweep passed 7/8; an explicit S2 request without symptoms asked for an issue description. Prompt refinements distinguish digits in identifiers from amounts and preserve an explicit severity with a factual summary. These refinements passed three Luna trials each for the pasted-ID and explicit-severity cases, but the outside-account missing-amount case still passed only one of three. No unauthorized write occurred. Sol passed all nine corresponding repeated trials. The reviewed default was changed to Sol, with Luna retained as an optional development override. The failed Luna trials are retained rather than folded into a passing aggregate. This is a bounded model-selection decision, not proof of general model superiority.

The existing-ticket scheduling prerequisite was also confirmed in the staging code: recovery could omit the verified ticket ID. Actions now retains that ID for handoffs, including outer timeout recovery. The existing persistent-outage scenario asserts the stored escalation's ticket linkage. A grader regression deliberately supplies an unlinked escalation and verifies rejection. Billing timeout recovery also checks the actual billing queue and ticket ID.

Other checks exercise fresh policy after interpretation, exact integer types, actual HTTP handling, approval consumption, pending-request reuse, invoice balance changes, and no forbidden attempts. A test-fixture mistake initially indexed simulator sessions by session ID rather than its internal token key; the policy-refresh test failed with no pending request. The fixture access was corrected without changing runtime code, and the test now demonstrates that a lowered live limit causes approval rather than credit.

The demo gained two customer credit examples and displays credit/approval receipts. Docker builds and health checks use isolated ports 8020/8021. Browser checks exercised both example buttons, a confirmed $75 credit, and a pending $150 approval that explicitly says no credit was applied. The demo deletes synthetic sessions, so these UI observations supplement the independent state/audit checks. No secrets, provider billing changes or real financial transactions are involved. Implementation elapsed time is not a measured total assessment-work duration.

## Tools and workflow

Codex implemented the agreed Python/OpenAI Agents SDK approach in an isolated Git worktree. Codebase Design informed module interfaces; Writing for Agents informed repository and runtime instructions. Git and Docker supported local integration. Ruff, focused mypy, unittest and the authored evaluation runner provided verification. Luna was used for fast live development and Sol for the recorded final scheduling runs.

The user chose the scope, authentication approach and models, tested the demo, and reviewed the draft PR. Work delegated to Codex included implementation, setup, evaluation, documentation and requested Git operations. No subagents or code-review workflow were used. The user explicitly reserved code review and merging for themselves.

The candidate estimates 10 to 20 minutes of planning and about 30 minutes of review per slice, or 40 to 50 minutes combined. Implementation/testing time and the complete assessment total remain unrecorded. Commit timestamps and elapsed model-call time are insufficient substitutes. Changes through `071a6f2` were published in [draft PR #1](https://github.com/Neet-08-dev/Northstar-FDE-candidate-Sakshi-/pull/1). The later template corrections are a local documentation follow-up pending review.

## Evidence of judgment

These instructions are summaries of the user's requests, not verbatim transcripts.

| Instruction | What Codex produced | Verification | Kept or changed |
| --- | --- | --- | --- |
| Build the first scheduling scenario with the agreed SDK/API-key approach and verify the module design. | A typed interpretation step, deterministic scheduling actions, scoped transport and local demo. | Offline checks exercised backend state, unsafe write prevention, failures and retries; live model runs exercised interpretation. | Kept three modules with distinct responsibilities. Response formatting remained internal rather than becoming a separate abstraction. |
| Verify behavior, including unauthorized and policy-incompatible requests. | An initial prompt that sometimes treated an explicit outside-account ticket or incompatible policy as identity ambiguity. | A Luna development run passed 34/36 cases. State/audit checks exposed the wrong statuses and missing policy handoff. | Changed instructions to preserve explicit intent and let Python check eligibility. Cross-tenant regression trials passed 3/3; subsequent fixed-prompt Luna and Sol suites each passed 36/36. |
| Display times in IST and explain the future date. | A shared IST formatter, revised demo explanation and an IST definition in the runtime prompt. | Offline checks covered booking instants, date rollover, existing visits and unavailable alternatives. Two live Luna requests exercised an exact IST booking and a suggested alternative. | Kept the assessment's fixed 2030 clock and UTC storage. Converted user-facing times and disclosed that full model suites preceded the prompt change. |

## Most consequential AI-generated mistake

The original live grader could count an operations handoff caused by provider failure as a passing case when the expected business outcome was also an operations handoff. A larger run hit provider limits and exposed this false positive. Its reported 25/36 was corrected to 18/36 after regrading the preserved results.

The grader now requires completed model execution for model-backed cases. It saves intermediate results and stops on provider failure. `test_provider_failure_cannot_pass_handoff_case` guards against treating missing model usage as successful interpretation. Deterministic early exits remain valid when no model call is needed. The corrected result is retained in [EVALS.md](EVALS.md); the earlier run is not a comparable reliability baseline.

A separate documentation mistake replaced supplied template headings and left requested sections unanswered. The user caught this during PR review. This follow-up restores the exact headings, checks coverage against the original templates, separates proposed controls from implemented behavior and adds sanitized evaluation evidence. Template preservation was checked for this update; no permanent documentation-check tool is claimed.

## Productivity and limits

Observed output includes the runnable workflow, setup, tests, evaluation runner and demo. No controlled comparison measured human time saved, so neither a percentage improvement nor a numerical productivity estimate is claimed.

The work remained with one coding agent; there was no subagent delegation to stop. Codex performed bounded verification, while the user retained decisions about scope, review and merging. Provider failures paused useful live evaluation until the user replaced the local key. Existing balance funded subsequent calls; Codex did not buy credits or change billing settings. Account details are unnecessary to explain the engineering correction.

All reported evaluations use authored development cases. They do not establish held-out performance, production throughput or general language reliability. The full Luna/Sol runs used the prompt before the IST definition; later checks had narrower scope. [EVALS.md](EVALS.md) records those revisions and limits. Future workflow implementation and a final submission-wide validation remain outstanding.

## Local intake implementation, 7 October 2026

The user approved ticket-only intake and intake followed by booking, permission to create a necessary ticket for an unambiguous technician request, and retention of confirmed tickets when booking cannot finish. They requested local implementation and verification before any new draft PR. At the user's request, the verified intake changes are committed locally and remain unpushed on `codex/scheduling-workflow`; PR #1 was not updated for intake. The concurrent documentation correction at `13c2154` was preserved.

Codebase Design kept the existing three runtime modules. Private service checks are shared inside Actions, while scheduling retains its slot and technician rules. Backend transport required no changes. Writing for Agents guided the intake and time instructions. No subagents or code-review workflow were used.

The verification budget was ten new/adapted behavior cases, reusing the existing scenario runner rather than creating another set of helper tests. Final offline verification passes all 24 test methods and 45 scenarios. The first type check caught a missing optional-record annotation; it was corrected before execution tests.

A consequential live failure occurred in Luna's partial-completion case: the request supplied an exact IST time, but the assistant recorded the ticket and asked for time again. The grader rejected the reply because it omitted the real available alternative. The original report did not capture the interpreted Decision, so its exact erroneous field could not be established. Diagnosing Bugs guided a targeted rerun and decision capture; that rerun passed, confirming intermittency. The prompt now explicitly preserves exact times for intake with booking. Three Luna regression trials passed, followed by the final-prompt Sol sample at 10/10 and four further Sol repeats at 4/4. All runs, including the initial failure, are retained in EVALS.md and the intake evidence.

The runner used 28 live trials, four more than planned for the observed failure. No full 45-case model suite was run. The Docker demo was rebuilt for the final prompt and both services passed health checks. The UI includes ticket-only and combined intake examples. No billing settings or credentials were changed.

A final Luna HTTP demo smoke resolved the named annex equipment without IDs and created the correct ticket without booking. This was one additional live request beyond the 28 runner trials. Its response and checks are saved in the intake evidence.

The original Contract checks CI workflow still ran bare Python after SDK dependencies were introduced. Both push and pull-request jobs failed while importing pydantic and dotenv; the newer Offline checks workflow passed. A clean copy of commit `13c2154` reproduced both import errors. The local workflow fix installs the locked environment and runs unittest through uv. All 24 test methods and `docker compose config --quiet` passed in that clean copy. This prevents existing developer environments from hiding missing CI setup; verification uses a clean checkout rather than adding a test that merely inspects workflow text.

## Customer demo wording follow-up

On `codex/ticket-intake` in its dedicated worktree, the six demo examples were rewritten as customer requests. Each button now fills a relevant subject and message, the default follows up on an existing ticket, and the submit button says "Send request". Internal site/asset IDs and eligibility jargon were removed from the examples. One normal customer ticket reference remains in the follow-up.

Live verification exposed identity ambiguity in three proposed messages and an issue-category clarification in a revised follow-up. Rather than claim those drafts worked, the checks retained every failure. The final examples use registered equipment/site names where necessary and an existing ticket reference for the general follow-up. All six final messages passed their targeted state/audit checks across eleven total trials; no runtime prompt or business-rule changes were made. This is a bounded demo improvement, not a fix for arbitrary natural-language record resolution. EVALS.md records the scope and evidence. Offline checks pass, and browser checks verified subject/body population for every button. The changes are committed locally for user review; nothing was pushed.

## Evidence report packaging correction

PR review exposed that committed evidence referenced reports available only in ignored local worktrees. The summaries retained outcomes, but reviewers could not inspect the referenced source files. The selected reports now live in `evidence/runs/`, including failed trials. JSON references resolve relative to their containing file, existing source hashes are preserved, and demo report hashes are included. The archive documents that the runner did not save full backend snapshots or tool arguments; making reports accessible does not recover that missing historical state.

Packaging checks cover JSON parsing, reference resolution, report hashes, consistency with the saved outcomes, and configured-secret/credential checks. Verification passed for all 12 archived reports, 25 hashed references and 123 preserved trial outcomes. `make check` also passed lint, formatting, mypy and all 24 test methods, including the 45 scenarios. This correction adds no behavior tests or paid evaluation runs.

## Billing report archive and staging rebase

At the user's request, draft PR #5 was rebased onto staging `4abf967`, which includes the report-packaging correction from PR #6. The rebase completed without conflicts. Billing's 11 referenced source reports now live under `evidence/runs/` with relative `report` links in the billing summary. Original report bytes and hashes are unchanged, including all 370 authored and published-suite outcomes and the failed trials. Historical runtime and prompt hashes still match; no runner-attested revision was invented for old runs.

Packaging checks passed for JSON parsing, configured secrets and credential fields, all 11 billing source hashes, outcome consistency, and all 36 hashed references across the four summaries. `make check` passed lint, formatting, mypy and all 29 test methods, including the 107 scenarios. The archive distinguishes billing's retained scoped read lookup arguments from missing write arguments and full backend snapshots. The top-level scratch `reports/` directory remains ignored. No new paid evaluation was run for this rebase and evidence-only update.
