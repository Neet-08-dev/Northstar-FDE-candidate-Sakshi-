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
