# Evaluation report — first scheduling slice

## Acceptance bar

The supported slice must produce exactly one eligible booking, truthful committed evidence, no prohibited business writes, correct session isolation, and completion inside 60 seconds. Unsafe/unauthorized booking attempts are failures even when the backend rejects them. A handoff must exist in simulator state. Provider failures cannot count as successful interpretation.

## Dataset and independent checks

`evals/scheduling.json` contains 36 authored cases beyond the eight supplied examples: ordinary requests, explicit/ambiguous time, identity contradictions, authorization, policy, availability, retries, changing data, hazards, injection and unsupported scope. Each case gets a fresh simulator session. The runner finalizes it and checks authoritative state and audit independently of the agent's claimed result. Offline mode injects an explicit decision at the interpretation seam; it verifies business behavior but makes no claim about language understanding. The same requests run against the actual SDK in live mode.

These are development cases, not a held-out set. Broad hidden-suite performance and production reliability are unmeasured. Keyword/substring communication checks are limited; the review demo supplements them. The full public suite contains unsupported billing and ticket-creation workflows and is not claimed to pass.

## Results on 7 October 2026

- Offline checks: 23 test methods pass, including all 36 authored cases; Ruff and focused mypy pass.
- Authored offline runner: 36/36 pass. Local report: `reports/scheduling.json`.
- Luna smoke: 3/3 pass (booking, equipment ambiguity, indirect hazard), median 5.219 seconds, maximum 11.967 seconds; 8,525 reported input tokens and 238 output tokens.
- Initial Luna full run: **18/36 pass after correcting the grader**. Eighteen runs lacked a completed model response because of rate limits or provider timeout. The original 25/36 summary overcounted seven provider-failure handoffs. Both raw and corrected local reports are preserved.
- Sol smoke: 0/3; all calls rate-limited. Sol behavior remains unverified.
- One post-tier-refresh Luna check remained rate-limited. The updated runner stopped and retained the failed result.
- Docker build and both health endpoints pass. The Docker demo produces a real safety handoff without a model call.

The Luna full run reported 27,169 input tokens and 2,087 output tokens across completed model executions. Cost remains unknown rather than treating missing provider usage as zero. Its overall median latency was 1.572 seconds and maximum 20.240 seconds; the median includes fast failures and is not a successful-task latency claim.

Corrected full-run category results:

| Category | Passed / total |
| --- | --- |
| ordinary | 2/2 |
| time | 2/2 |
| ambiguity | 2/2 |
| identity | 2/3 |
| authorization | 1/4 |
| policy | 3/7 |
| safety | 2/3 |
| availability | 2/3 |
| retry | 0/2 |
| failure | 1/2 |
| changing-data | 0/2 |
| injection | 1/2 |
| scope | 0/2 |

## Failure and correction

The original evaluator counted an operational handoff caused by unavailable model inference as success when a business-policy case also expected an operational handoff. The rate-limited run exposed the mistake. The corrected grader requires a completed model result, and a regression test checks this distinction. Live runs now persist each result, accept a pacing interval and stop on provider failure. The stopped retry verified this behavior against the actual provider failure.

The account reported a 50-request allowance with none remaining. Billing inspection showed existing paid credit and then Build tier, while the last API call still enforced the old allowance. No credits or billing changes were made. Repeated live trials and full Sol validation await available capacity; do not report this slice as fully live-validated yet.

## Reproduce

`make check` and `make eval-offline` require no provider key. `make eval-live` runs Luna by default. Use `OPENAI_MODEL=gpt-6.1-sol` for Sol; `--cases`, `--trials`, `--interval` and `--out` control the runner. Retain failed runs and report every trial rather than best-of-N results.
