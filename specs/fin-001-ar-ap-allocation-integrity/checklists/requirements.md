# FIN-001 Requirements and Traceability Checklist

## Specification Quality

- [x] CHK001 The defect is reproduced against disposable PostgreSQL with independent sessions and a synchronization barrier.
- [x] CHK002 Scope explicitly excludes production implementation, schema/migration, historical data, accounting mappings, debit/credit rules, push, and merge for this checkpoint.
- [x] CHK003 Source locking, payment locking, lock order, transaction owner, conflict policy, retry bound, and response behavior are explicit.
- [x] CHK004 Multi-source ordering describes exactly how reverse input order avoids a lock cycle.
- [x] CHK005 PostgreSQL—not SQLite—is required for concurrency proof.
- [x] CHK006 The migration decision is explicit and evidence-based.
- [x] CHK007 CI silent-skip risk and required fail-closed remediation are specified.

## Requirement Traceability

| Requirement | Implementation checkpoint | Authoritative test / acceptance gate | Status |
|---|---|---|---|
| FIN-001-R01 AR source protection | CP2 | Two-session AR barrier + N=50 total `<= collectible`; CP2 gate | Planned |
| FIN-001-R02 AP source protection | CP2 | Two-session AP barrier + N=50 total `<= bill`; CP2 gate | Planned |
| FIN-001-R03 source locks in transaction | CP2 | SQL/behavior assertion that balance is read after `FOR UPDATE`; CP2 gate | Planned |
| FIN-001-R04 tenant isolation | CP1/CP2 | Cross-tenant source UUID fails closed with zero effects; CP2 gate | Planned |
| FIN-001-R05 deterministic multi-source order | CP2 | Reversed-order independent-session no-deadlock test; CP2 gate | Planned |
| FIN-001-R06 full rollback | CP1/CP3 | Forced post-allocation failure has zero partial graph; CP3 gate | Planned |
| FIN-001-R07 at-most-once retry effects | CP3 | Controlled transient conflict/retry counts one graph; CP3 gate | Planned |
| FIN-001-R08 sequential compatibility | CP2/CP4 | Existing AR/AP sequential safety suites green; CP4 gate | Planned |
| FIN-001-R09 accounting policy unchanged | CP2/CP4 | Diff review + existing journal balance tests; CP4 gate | Planned |
| FIN-001-R10 historical records unchanged | CP4 | Diff/schema/data review; no migration; CP4 gate | Planned |
| FIN-001-R11 PostgreSQL evidence mandatory | CP1/CP4 | Independent sessions/barriers, migrated disposable DB, no SQLite substitution; CP4 gate | Planned |
| FIN-001-R12 CI fails closed | CP1/CP4 | Dedicated helper rejects missing/unsafe URL; required CI PostgreSQL job rejects missing/unreachable URL and reports zero skip | CP1 helper verified; CI job planned |
| FIN-001-R13 endpoint characterization | CP1 | Real same-tenant customer/vendor HTTP requests remain serialized at Feature-012 `TRX` allocation before allocation service entry | CP1 verified |
| FIN-001-R14 no incidental-correctness reliance | CP2 | Direct independent-session service REDs remain executable until authoritative source/payment locking plus fresh aggregate validation is implemented | CP1 verified; CP2 planned |

**TOTAL REQUIREMENTS: 14**
**MAPPED: 14**
**COVERAGE: 100%**

## Constitution and Scope Check

- [x] Derived AR/AP balances remain authoritative and are not independently maintained.
- [x] Double-entry, deterministic mapping, and cash/economic classification are unchanged.
- [x] Posted history is not rewritten; corrections remain outside FIN-001.
- [x] Tenant isolation is an acceptance condition, not an assumed property.
- [x] Monetary authority remains Decimal/NUMERIC.
- [x] No protected storage, credential, production database, paid service, or external AI egress is in scope.

## Readiness Decision

- [x] Current defect has evidence.
- [x] Smallest correct design is selected.
- [x] Migration is not needed.
- [x] RED PostgreSQL plan is actionable.
- [x] No unresolved accounting policy decision blocks implementation.
- [x] CI PostgreSQL gate is a required CP1/CP4 work item.
