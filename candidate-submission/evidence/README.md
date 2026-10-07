# Saved evaluation evidence

The three summary JSON files reference committed reports in `runs/`. Every `report` or `source_file` path is relative to the JSON file containing it. The adjacent `report_sha256` or `source_sha256` identifies the exact report bytes, including whitespace. A matching hash establishes file identity, not the validity of an evaluation.

These are existing development reports, including failed trials. Packaging them did not run new evaluations or alter results. The files were checked for configured secrets and credential fields; their existing reduced audit format needed no redaction, so the original bytes and recorded hashes are preserved. Demo report hashes were added during packaging.

Reports retain responses, checks, usage, ordered tool names and commit/error flags. Later reports also retain interpreted decisions; demo wording reports include the exact requests and expectations. They do not retain full backend snapshots or tool arguments. The runner checked those during execution and deleted the synthetic sessions afterward. Historical state checks and exact argument replay cannot be independently recomputed from these saved reports. A fresh run produces new evidence and may produce different model results.

The intake HTTP demo smoke is already embedded in `intake-evaluations.json`. It remains a response-only check without a retained backend snapshot. It is not an additional runner report in this archive.

Scratch output stays ignored under the repository's top-level `reports/` directory. Only reports referenced by the committed summaries are archived here. The summaries retain their historical prompt and implementation caveats; no runner-attested Git revision is added retroactively.

## Scheduling checkpoint

- [luna-final.json](runs/luna-final.json)
- [sol-final.json](runs/sol-final.json)
- [sol-risky-repeats.json](runs/sol-risky-repeats.json)

## Intake verification

- [intake-luna-diagnosis.json](runs/intake-luna-diagnosis.json)
- [intake-luna-time-regression.json](runs/intake-luna-time-regression.json)
- [intake-luna.json](runs/intake-luna.json)
- [intake-sol-repeats.json](runs/intake-sol-repeats.json)
- [intake-sol.json](runs/intake-sol.json)

## Demo wording checks

- [demo-wording-luna-booking.json](runs/demo-wording-luna-booking.json)
- [demo-wording-luna-followup.json](runs/demo-wording-luna-followup.json)
- [demo-wording-luna-initial.json](runs/demo-wording-luna-initial.json)
- [demo-wording-luna-revised.json](runs/demo-wording-luna-revised.json)
