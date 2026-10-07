# AI development-tool build log

This is a checkpoint record for the scheduling implementation. It summarizes sanitized development evidence rather than private transcripts or model reasoning.

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
