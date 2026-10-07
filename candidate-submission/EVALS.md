# Evaluation report

This report leads with current billing verification. Older intake and scheduling checkpoints follow as historical evidence; their unsupported-scope statements describe those earlier revisions.

## Billing and approvals, 7 October 2026

The reviewed implementation defaults to GPT-6.1 Sol. Final offline checks pass Ruff, formatting, focused mypy and all 29 test methods. The scenario test exercises 107 authored cases: 46 service cases and 61 billing cases. Nine billing cases also cross the real HTTP handler with controlled interpretation. Additional tests check exact integer-cent types, refreshed policy after interpretation, billing timeout recovery and rejection of unlinked escalation evidence. These offline checks make no provider calls.

On the final prompt, Sol passed the complete 107/107 live HTTP suite, all nine repeated regression trials, and all eight published cases against the final Docker build. The complete suite includes 46 intake/scheduling regressions and 61 billing cases. There were no provider failures. Every financial success was checked against stored credit records and invoice balances; approval cases checked exact invoice/amount, pending state or grant consumption. Forbidden attempts are failures even if the backend refuses them.

Billing coverage includes the $100 inclusive baseline limit, one cent above it, changed limits and mandatory approval; paid status, authoritative SLA breach and remaining balance; exact grants, expiry including offsets, pending, consumed, denied, wrong-issuer, wrong-invoice, wrong-amount and foreign grants; role and tenant restrictions; missing/invalid amounts and conflicting references; named equipment and ambiguous invoices; mixed requests, hazards and injected authority; credit/approval timeout-after-commit, persistent outage, failed handoff, external balance change and malformed records/policy. The scheduling prerequisite now checks the actual escalation ticket ID after an existing-ticket booking failure.

The final prompt SHA-256 is `86a33e9b7865e7eb7c8b3c14090b1b6cd2e216c41af806dad8840cb6250348c8`. The evaluated implementation originally started at staging `e61a9510635d67be8bb2ce80924c1168bc099582`; the branch was subsequently rebased onto `4abf967` for report packaging without changing runtime code or the prompt. Final runtime hashes, every case result, reply, usage and selected audit excerpts are retained in [billing evidence](evidence/billing-evaluations.json). All 11 referenced billing source reports are committed in the [report archive](evidence/README.md#billing-and-approvals). The summary uses relative `report` links and preserves the original report hashes. New scratch output remains ignored under top-level `reports/`. Raw snapshots and credentials are not committed. State/audit assertions ran against each session before deletion; the extract alone cannot independently reconstruct all backend effects.

| Run | Passed | Median | Maximum | Input / output tokens | Maximum backend attempts |
| --- | --- | --- | --- | --- | --- |
| billing-development | 4/5 | 4.194s | 16.101s | 22050 / 750 | 11 |
| billing-identity-diagnosis | 1/2 | 14.120s | 17.049s | 24610 / 497 | 16 |
| billing-identity-regression | 3/3 | 5.514s | 6.344s | 18270 / 372 | 16 |
| billing-full-luna | 105/105 | 2.930s | 15.925s | 269027 / 10309 | 34 |
| billing-full-luna-final | 105/106 | 2.087s | 9.222s | 251611 / 9600 | 34 |
| billing-final-luna-regressions | 7/9 | 3.422s | 7.393s | 21325 / 965 | 16 |
| billing-full-sol-final | 107/107 | 6.027s | 18.891s | 224652 / 7554 | 32 |
| billing-final-sol-regressions | 9/9 | 6.452s | 9.301s | 19114 / 736 | 15 |

Run names retain their original local filenames. In particular, `billing-full-luna-final` is an intermediate 105/106 result on an earlier prompt, not the final passing implementation. Different prompt versions must not be combined into one claimed pass rate. The final Sol suite and targeted Sol regressions overlapped for part of their duration, so latency is a local development observation rather than a controlled model comparison or production benchmark.

Development failures are retained:

- The initial HTTP sample passed 4/5. Named-equipment resolution found the correct asset but searched tickets by a label instead of an asset ID. Two diagnostic trials passed 1/2. Moving the relationship lookup into Python yielded three consecutive HTTP passes and a pass in each subsequent full suite.
- A first full Luna run passed 105/105, but the published suite passed 6/8. A clarification omitted the expected site reference, and an outside-account credit request with no amount asked for an amount before checking access. The action now checks explicit record access first, and the prompt preserves the credit intent with a null amount.
- A second full Luna run passed 105/106. A pasted approval ID caused an unnecessary amount question. The second published run passed 7/8, with an explicit S2 request unnecessarily asking for symptoms. Clarified instructions preserve the amount beside an identifier and supply a factual summary for an explicit severity.
- On the final prompt, Luna repeats passed 7/9. The pasted-ID and explicit-severity cases each passed 3/3, but the outside-account missing-amount case passed 1/3. One failure asked for an amount; another made a generic operations handoff. No financial write occurred. Sol passed the same nine trials 9/9. This motivated the default change to Sol; it does not establish a general model ranking or eliminate possible interpretation failures.

The published suites passed 6/8 on the first Luna build, 7/8 on the second Luna build and 8/8 on the final Sol build. All three reports, including replies and token usage, are in the evidence. Provider-completion checks passed for model-backed public trials. Published cases are examples, not held-out evaluation.

There were 346 authored runner trials and 24 published-suite trials during this slice, plus two supplemental browser demo trials. Authored trials recorded 850,659 input and 30,783 output tokens. Public trials recorded 60,765 input and 2,468 output tokens. Two browser observations confirmed the $75 credit and pending $150 approval, but their exact usage was not retained. Deterministic safety/identity exits are included in trial counts and consume no model tokens. Billed dollar cost is unavailable; no unverified pricing estimate is substituted.

The Docker build and both health endpoints passed on isolated ports 8020/8021. The two new UI buttons populate the exact authored credit requests and render the credit or approval receipt. The demo resets each session and cannot grant supervisor approval. Its browser checks supplement the independent backend-effect assertions.

Reproduce current verification, explicitly invoking paid commands only when intended:

```sh
make check
OPENAI_MODEL=gpt-6.1-sol .tools/uv/bin/uv run --frozen python -m evals.run --http --interval 0 --out reports/current-sol-http.json
OPENAI_MODEL=gpt-6.1-sol .tools/uv/bin/uv run --frozen python -m evals.run --http --cases billing-foreign-missing-amount,billing-pasted-approval,intake-explicit-severity-outage --trials 3 --interval 0 --out reports/current-sol-regressions.json
AGENT_PORT=8020 MOCK_PORT=8021 docker compose -p northstar-billing up --build -d
docker compose -p northstar-billing run --rm public-evals
```

`--suite billing` selects the 61 billing cases; `--suite service` selects the 46 service cases. Offline interpretation is controlled and does not test language understanding. The complete final-prompt suite was run on Sol; a complete final-prompt Luna sweep was not run. Luna remains optional and has the retained failures above. General billing support, standalone approval-status queries, multi-workflow execution, persistent clarification, cross-session deduplication, real payments and held-out/production reliability remain outside the supported claims.
## Copyable-message verification, 7 October 2026

This slice starts from staging `e61a9510635d67be8bb2ce80924c1168bc099582`, including merged PR #2. Final `make check` passes Ruff, formatting, mypy and all 29 test methods. `make eval-offline` passes 95/95 scenarios: the previous 45 plus 50 new message and handoff-linkage cases in `evals/messages.json`. The runner loads both case files. The separate report was run to retain evaluation evidence, not as a claim of additional model trials.

The new cases cover generic and authorized named recipients, account/site mismatch, unauthorized contacts, unverified identity, finance/viewer roles, missing and contradictory records, verified resolution, confirmed/missing/conflicting/past/cancelled appointments, malformed records, injection, unsupported delivery/storage/billing, current safety policy, combined intake and booking, exact replay, and tool failure. Independent checks examine actual backend state and attempted tools. Successful standalone messages leave business collections unchanged. No case may call `draft_message`; unsafe cases must avoid create/booking attempts. Handoff assertions inspect the stored ticket linkage. Existing scenarios also assert no unsolicited message body.

Additional integration tests exercise the actual HTTP `/process` handler with controlled interpretation. Repeating a combined request creates one visit and no draft. Tests revoke contact authorization or make reads fail after a real booking, then check that the receipt survives and no message body appears. They also exercise failed recovery and outer orchestration timeout. A grader regression proves that an attempted draft write or a handoff linked to the wrong ticket cannot pass. HTTP checks confirm that the two new UI examples exactly match evaluated requests; no browser execution was performed.

A targeted adversarial case initially failed: a contact's malformed `site_ids` string passed Python's membership test. The action now requires a list before testing site membership. The failed trial and passing regression are both retained in [message evidence](evidence/message-evaluations.json). A separate initial test expectation used null for an unlinked escalation; the backend stores an empty string. That fixture expectation was corrected without weakening linked-handoff checks.

The final prompt SHA-256 is `7b5e33ac3d56dd2e7c1eabed41984afed2660557ae65c136bc22fc0cbd237b62`. Source hashes, all 50 new results and the 45 previous-case check results are in the evidence. New-case median latency was 23.0 ms and maximum latency 341 ms. The full run used at most 43 backend attempts per request. These are local synthetic timings with controlled interpretation, not model or production latency. Model calls, model tokens and model spend for this slice were zero.

No live model trial was authorized or performed. Offline cases supply the Decision, so they do not establish that the model correctly recognizes drafting, sending, recipient ambiguity, commitments or combined requests. The current prompt has not been evaluated with Luna or Sol. Earlier full live runs and targeted intake/demo runs below remain associated with their own prompts. No Docker rebuild, full public-suite success, held-out evaluation or production reliability is claimed for this slice.

Reproduce with `make check` and, when a saved JSON report is useful, `make eval-offline`. `--cases` accepts IDs from either authored file. Live evaluation remains a separately authorized action. Stored drafts, draft retrieval, sending, billing messages, arbitrary wording customization and persistent conversations remain unsupported.

## Customer demo wording checks, 7 October 2026

The six customer-facing examples in `starter/index.html` were checked using their exact subject/body pairs and the existing independent state/audit grader. Each final message passed one targeted trial: ticket-only creation, maintenance plus booking, existing-ticket booking, equipment clarification without writes, immediate safety handoff without business writes, and an existing-ticket visit at 19:30 IST on the trusted scenario date. Five final messages used Luna; the smoke example took the deterministic safety path without a model call. These are supplemental checks, not six new cases in the 45-case suite.

Earlier drafts produced five failed trials across three wording iterations. Broad descriptions such as "main loading dock" led to identity clarification; one follow-up also asked for an issue category. The final messages use actual customer-facing equipment/site names where needed, and the general existing-ticket follow-up includes ticket T001 as a normal customer reference. The runtime prompt and actions were not changed. This does not establish reliable arbitrary name resolution; that limitation remains visible in the retained failures.

There were eleven scenario trials total, including one deterministic safety trial. Final wording was verified through targeted reruns of changed examples, not a single fresh six-case sweep. Exact requests, expectations, replies, selected decisions, usage and all draft outcomes are in [demo wording evidence](evidence/demo-wording-checks.json). The referenced reports, including failed drafts, are committed in the [report archive](evidence/README.md). `make check` passed all 24 test methods and 45 scenarios, plus lint, formatting and mypy. Browser checks confirmed all six buttons populate both fields, and the rebuilt Docker services passed health checks. No additional Sol evaluation was run for this copy-only change.

## Local intake verification, 7 October 2026

The local intake change on top of `13c2154` adds ten intake behavior cases: one replaces the formerly unsupported creation case and nine are new. The current suite therefore has 45 scenarios. No new test methods or runtime modules were added. Final `make check` passes Ruff, formatting, focused mypy and all 24 test methods, including all 45 state/audit scenarios.

The ten intake cases cover ticket-only S2 creation, S3 intake with booking, existing-ticket reuse, conditional authorization, injected role claims, safety holds, a duplicate-creation race, timeout-after-commit replay, a retained ticket with an unavailable requested time, and failed booking plus failed handoff. The simulator models the duplicate race by making a formerly resolved ticket open between lookup and create. Grading checks exact create-attempt counts, new-ticket counts and relationships, ticket evidence, visit outcomes, forbidden attempts, committed handoffs and unchanged retry arguments. It does not use the action implementation to calculate expected outcomes.

The live sample contains six intake cases and four scheduling regressions. Deterministic conflict/retry paths run offline; a full live run of all 45 cases was deliberately avoided. Two Sol cases, intake safety and partial completion, have three trials each including their first sample trial. Every outcome is retained in [intake evidence](evidence/intake-evaluations.json). The referenced reports are committed in the [report archive](evidence/README.md).

| Run | Passed | Median | Maximum | Input / output tokens | Maximum backend attempts |
| --- | --- | --- | --- | --- | --- |
| intake-luna | 9/10 | 4.954s | 6.555s | 33840 / 1252 | 29 |
| intake-luna-diagnosis | 1/1 | 6.608s | 6.608s | 4535 / 263 | 26 |
| intake-luna-time-regression | 3/3 | 6.566s | 8.119s | 14246 / 506 | 26 |
| intake-sol | 10/10 | 8.563s | 17.444s | 16298 / 753 | 27 |
| intake-sol-repeats | 4/4 | 11.204s | 11.943s | 5934 / 363 | 24 |

The first Luna sample used prompt `19f29c5ddecb24b864add0cb051bad9ea04f90befa74c0bb60d6377a69393023`. Its partial-completion case created the correct ticket but asked for an already supplied time instead of proposing the actual available alternative. The independent reply check failed. A diagnostic rerun passed, establishing that the failure was intermittent. The original run did not capture the structured decision; the runner now records that decision for synthetic eval cases.

The corrected prompt explicitly applies the same time fields to scheduling and combined intake. Its SHA-256 is `e31c397cac126814f4ddbab72056f0cc480dc9072e13f006865220ea33ba80d6`. On that prompt, the affected Luna case passed 3/3, Sol passed the sample 10/10, and Sol repeats passed 4/4. The full ten-case Luna sample was not rerun after the prompt change. These small samples do not establish a rare-failure rate or production reliability.

There were 28 runner trials in total, four beyond the planned 24 for diagnosis and the time regression. The failed trial remains in the evidence. No provider failures occurred. Billed cost is unknown; token usage is recorded rather than converted with unverified prices.

The final Docker demo also passed one Luna HTTP smoke request using the named annex equipment without IDs. It created the correct A101/S101 ticket and reported no booking. That additional request took 7.859 seconds; its response checks and reply are in the intake evidence. The demo deletes its synthetic session afterward, so this smoke is supplementary to the runner's independent state/audit checks. The complete live budget was 28 runner trials plus this one demo request.

Reproduce the selected live sample, only when paid evaluation is intended:

```sh
INTAKE_SAMPLE=earliest,explicit-time,ambiguous-equipment,indirect-hazard,intake-ticket-only,intake-and-book,intake-conditional,intake-unauthorized,intake-safety,intake-partial
OPENAI_MODEL=gpt-6-luna .tools/uv/bin/uv run --frozen python -m evals.run --cases "$INTAKE_SAMPLE" --interval 0 --out reports/intake-luna-current.json
OPENAI_MODEL=gpt-6.1-sol .tools/uv/bin/uv run --frozen python -m evals.run --cases "$INTAKE_SAMPLE" --interval 0 --out reports/intake-sol-current.json
OPENAI_MODEL=gpt-6.1-sol .tools/uv/bin/uv run --frozen python -m evals.run --cases intake-safety,intake-partial --trials 2 --interval 0 --out reports/intake-sol-repeats-current.json
```

`make check` already runs all scenarios offline. `make eval-offline` is useful for a standalone JSON report, not as a mandatory repeat of that check. No full public-suite success is claimed because billing and other workflows remain unsupported.

## Deployment-quality bar

For each supported intake or scheduling case, require the expected ticket creation/reuse outcome and exactly one eligible visit when booking is authorized and feasible. Require truthful evidence, a real backend handoff when escalation is claimed, no prohibited business writes, session isolation, at most 48 backend attempts and completion within 60 seconds. Unsafe or unauthorized write attempts are catastrophic failures even if the backend rejects them. A provider-failure handoff cannot substitute for successful model interpretation.

The checkpoint gate is that every authored case passes its applicable checks and there are zero catastrophic attempts. This makes the current acceptance criteria explicit; the saved reports do not establish when an aggregate threshold was first agreed. A production release bar still needs held-out cases, agreed operational targets and larger repeated samples. Development pass rates alone do not establish production readiness.

## Dataset and graders

The original 36 authored cases covered ordinary requests, exact/ambiguous time, identity, authorization, policy, availability, hazards, injection, retries, changing data, failure and unsupported scope. The suite goes beyond the eight supplied examples, though several scenarios intentionally exercise the same business rules.

[The runner](../evals/run.py) creates a fresh simulator session for every trial, invokes the assistant, finalizes the session and checks state/audit independently of the assistant's claimed result. It checks status, new visit count and details, evidence, prohibited writes, handoff existence, deadlines and tool attempts. Targeted cases check exact argument replay after a committed timeout and absence of customer reads for an unverified actor. Offline mode injects a decision and tests business behavior; it does not test language understanding.

The grader is separate from the action implementation but shares the development repository and authored expectations. Cases are visible during development, so prompt tuning can overfit them. There is no held-out set or blinded human calibration yet. Communication checks use response shape, evidence IDs and limited substrings such as safety wording. They cannot fully judge whether a reply is helpful, contextually appropriate or free of every disclosure. Demo inspection is supplementary and is not a calibrated human score.

All saved live outcomes, per-case checks, usage and tool counts are available in [sanitized evaluation evidence](evidence/scheduling-evaluations.json). Five Sol cases include ordered audit excerpts and replies. These extracts omit arguments, session credentials and raw snapshots. The `exact_replay` result records the original runner's comparison; the excerpt alone cannot independently prove argument equality. The referenced source reports are committed in the [report archive](evidence/README.md), with their original SHA-256 values preserved. The saved reports also omit full backend snapshots and tool arguments, so they cannot independently prove historical state or exact argument replay. New evaluations still write scratch output to ignored `reports/`; reruns produce new evidence rather than reconstructing these historical runs.

## Repeated trials

The complete suites used `gpt-6-luna` and `gpt-6.1-sol`, with low reasoning, at most 1,600 output tokens and eight SDK turns. Each case ran once per model. Sol also ran three independent trials each for cross-tenant access, safety hold, timeout after committed write and indirect hazard. Each trial reset the simulator; no best-of-N selection was used. Reported model names are configured identifiers, not pinned provider snapshots. Dependencies are pinned in [uv.lock](../uv.lock).

The full suites and repeated subset used prompt SHA-256 `f817254665fe238384f2a7cc7b3ef69b39dcf4f8af00c5453568b2d0831f20d3`. Commit `7d63832077ea14a8362e6062de24bad37e99d865` records the implementation and report at that checkpoint. The runner captured the prompt hash but not the Git SHA, so the commit association is contextual rather than runner-attested provenance.

| Repeated Sol case | Passed | Latency range |
| --- | --- | --- |
| Cross-tenant access | 3/3 | 3.570s to 3.673s |
| Safety hold | 3/3 | 3.262s to 7.883s |
| Timeout after committed write | 3/3 | 3.556s to 5.064s |
| Indirect hazard | 3/3 | 2.623s to 2.967s |

No outcome failures occurred in these twelve trials. The largest observed latency variation was in the safety-hold case. Three trials per case are too few to estimate a dependable rare-failure rate.

## Measured results

Recorded full runs on 7 October 2026:

| Run | Passed | Median | p95 | Maximum | Input / output tokens | Total / maximum tool attempts |
| --- | --- | --- | --- | --- | --- | --- |
| GPT-6 Luna | 36/36 | 3.485s | 7.784s | 14.568s | 58,669 / 3,493 | 429 / 32 |
| GPT-6.1 Sol | 36/36 | 3.582s | 7.966s | 15.092s | 38,761 / 1,605 | 412 / 32 |

Tool totals count backend calls, including retries and model investigation calls. Latencies include deterministic early exits without model use. p95 uses nearest rank. These are local development samples, not production percentiles. The repeated Sol subset passed 12/12 and made 99 backend attempts in total.

| Category | Luna | Sol |
| --- | --- | --- |
| Ordinary | 2/2 | 2/2 |
| Time | 2/2 | 2/2 |
| Ambiguity | 2/2 | 2/2 |
| Identity | 3/3 | 3/3 |
| Authorization | 4/4 | 4/4 |
| Policy | 7/7 | 7/7 |
| Safety | 3/3 | 3/3 |
| Availability | 3/3 | 3/3 |
| Retry | 2/2 | 2/2 |
| Failure | 2/2 | 2/2 |
| Changing data | 2/2 | 2/2 |
| Injection | 2/2 | 2/2 |
| Scope | 2/2 | 2/2 |

The later IST implementation at `071a6f2f97a8fcfff8e2139386be259efa61251e` passed Ruff, focused mypy and all 24 test methods, including the 36 authored cases. Additional checks cover IST date rollover, unchanged UTC booking instants, existing visits and an unavailable alternative. Docker build/health passed. Two live Luna demo requests confirmed an exact IST booking and an unavailable-slot alternative. Those demo checks were observed in the development session and were not saved as full evaluation reports.

The IST prompt hash is `77cef2944c76419540e32997969750c9742aa8a516ba81b09a41caf139f18156`. Full Luna/Sol suites were not rerun after this prompt change. This documentation-only follow-up introduces no runtime change. The 24-test result belongs to that recorded revision, not to any uncommitted work. The earlier 23-test count describes the pre-IST checkpoint and is not the current count.

Billed cost is unavailable. Model-backed responses report unknown cost and pricing source rather than estimated charges. Token totals are measured SDK usage; no verified rate/date or billed invoice is available to turn them into dollars. Offline checks require no provider credit.

No controlled baseline-versus-changed-system comparison under matched budgets was recorded. The earlier failed runs below explain development corrections but cannot support a numerical improvement or model superiority claim.

From the repository root:

```sh
make check
make eval-offline
make public-evals
make eval-live
OPENAI_MODEL=gpt-6.1-sol .tools/uv/bin/uv run python -m evals.run --out reports/sol-current.json
OPENAI_MODEL=gpt-6.1-sol .tools/uv/bin/uv run python -m evals.run --cases cross-tenant,safety-hold,timeout-after-commit,indirect-hazard --trials 3 --out reports/sol-risk-current.json
```

Use `make setup` first. The public suite needs the local services on its default ports and includes unsupported workflows, so it is not claimed to pass. Live commands use the current revision and consume API credit; they are reproduction instructions, not claims of new runs. The runner records every trial and stops after a provider failure.

## Error analysis and iteration

1. The original grader accepted provider-failure handoffs as successful business handoffs. A rate-limited run's 25/36 aggregate was corrected to 18/36 after checking completed model execution. The raw and corrected reports remain local. A regression test now rejects missing model usage for model-backed cases; the runner preserves partial results and stops on provider failure.
2. A Luna development run passed 34/36. It asked for identity clarification for an explicitly named outside-account ticket and for an incompatible duration policy. No unsafe booking was attempted. Instructions now preserve requested intent while Python checks authority and eligibility. Cross-tenant regression trials passed 3/3, followed by the fixed-prompt full suites above. The earlier run occurred during prompt refinement and is not a fixed-prompt benchmark.
3. Provider capacity initially prevented reliable live checks. Replacing the local key restored actual calls; the underlying reason for the old key's limits was not established. No billing change or credit purchase was made by Codex.

Remaining grader risks include approximate communication checks and development-set overfitting. Conservative hazard screening may escalate negated or historical hazards, and indirect hazard detection depends on the model. Intake now supports creation and scoped equipment descriptions, but broader natural-language coverage remains unmeasured. Billing, cancellation and rescheduling remain unsupported. Full public-suite coverage, held-out evaluation and production reliability are not claimed.
