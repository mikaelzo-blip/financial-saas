# Project Status

- **Last reconciled**: 2026-10-08
- **Current branch**: `main` (remediation work happens on `hermes/T*` branches)
- **Main commit**: `4849ba0` (`docs(audit): add Gemini remediation task list and regression probe (#90)`)
- **Active work**: Audit Remediation Batch 2026-10-07 (T01–T17). Executed by **Hermes Coder**, orchestrated and audited by **Claude**.
- **Operating model**: Local-first. Local Baileys intake is supported while the Finance PC services are running; durable PC-off capture remains `DEFERRED_POST_RC1`.

## Baseline

- Slice 5 (Automatic Accounting Posting, PR #71) is complete. Merges since then on `main`: #72, #73, #74, #76, #77, #78, #79, #82, #84, #85, #88, #89, #90 (`git log faec99b..4849ba0`).
- The 2026-10-07 audit of `690e761` produced the task list in `docs/audit/2026-10-07-audit-remediation-tasks.md` and the probe `tools/audit/regression_probe.py`.
- Probe baseline on `4849ba0`: defects present for T03, T04, T05, T06, T07, T08, T09, T10, T11. Trial balance is balanced.

## Blockers

- **Backend CI is red on `main` for every PR** until T01 and T02 merge:
  - `pip-audit --strict` reports 25 vulnerabilities (`pyjwt` 2.13.0, `pypdf` 6.16.2, `urllib3` 2.7.0) → T02.
  - Two UAT tests hardcode 2026-09 dates and fail after 2026-10-01 → T01.

## Merge Gate (owner instruction for this batch)

A `[Txx]` PR is squash-merged only when GitHub CI is green **and** Claude has commented `Claude audit: APPROVE` on it. This overrides automatic squash merge for this batch.

## Remediation Queue

Progress source of truth: merged PRs titled `[Txx]` on `main`. Task PRs must not edit this file; the orchestrator updates it.

| Wave | Task | Summary | Depends on |
|---|---|---|---|
| 1 | T01 | Date-independent AR/AP UAT tests | — |
| 1 | T02 | Upgrade `pyjwt`, `pypdf`, `urllib3` | — |
| 2 | T03 | Reject review flags on posted/reversed transactions | T01, T02 |
| 2 | T04 | Forbid reversing a reversal | T01, T02 |
| 2 | T06 | Validate status before approve/post (no HTTP 500) | T01, T02 |
| 2 | T07 | Record `created_by`, audit transaction creation | T01, T02 |
| 2 | T08 | Audit accounting period lifecycle | T01, T02 |
| 2 | T09 | Subcontractor bills/payments in AP sub-ledger | T01, T02 |
| 2 | T11 | Block generic adjustments on control accounts | T01, T02 |
| 2 | T12 | Edge-relay signature verification, fail closed | T01, T02 |
| 2 | T13 | Upload validation for `/inbox/capture` | T01, T02 |
| 2 | T14 | Safe local config defaults (`DEBUG`, `SECRET_KEY`, SQL echo) | T01, T02 |
| 2 | T15 | Org-scoped assertions in `test_scenario_j` | T01, T02 |
| 2 | T16 | Block invoice reversal while retention releases exist | T01, T02 |
| 2 | T17 | Block depreciation reversal until register sync exists | T01, T02 |
| 3 | T05 | Unique reversal per transaction (migration 030) | T04, T16, T17 (same `reversal_service.py`) |
| 3 | T10 | Vendor bill number unique per vendor (migration 031) | T05, T09 |

T01 and T02 ship as one PR. At most 3 `[Txx]` PRs may be open at the same time. Wave 3 is strictly sequential.

## Pending Owner Decisions

D1–D9 in `docs/audit/2026-10-07-audit-remediation-tasks.md` (maker/checker, currency, payment account requirement, fixed-asset disposal, year-end close, opening AR/AP, soft-void reversals, DB-level immutability, advances). These are out of scope for Hermes until the owner decides.

## Next Action

Hermes Coder: implement **T01 and T02 together** on branch `hermes/T01-T02-unblock-ci` (two commits, one PR titled `[T01+T02]`), because either PR alone stays red on the other's failure. After CI finishes, comment `Siap audit Claude: T01+T02` on the PR and wait for the audit verdict before merging.
