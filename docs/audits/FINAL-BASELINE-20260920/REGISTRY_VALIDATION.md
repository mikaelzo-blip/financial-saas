# Registry Validation Report: Cross-Journey Integrity Audit

- **Audit Run ID:** `FINAL-BASELINE-20260920`
- **Target File:** `docs/workflows/WORKFLOW_REGISTRY.yaml`
- **Git Commit SHA:** `26ab5affee58` (`26ab5af`)
- **Date:** 20 September 2026
- **Status:** Validated with Reconciled Schema Inconsistencies

---

## 1. Structural & Syntax Validation

| Check Item | Requirement | Result | Evidence / Notes |
| :--- | :--- | :--- | :--- |
| **YAML Syntax** | Valid, parseable YAML | PASS | Successfully parsed by `yaml.safe_load()` |
| **Schema Version** | Present and integer | PASS | `schema_version: 1` |
| **Unique Journey IDs** | Exactly 8 distinct journeys | PASS | 8 journeys: `J1_document_to_journal` through `J8_whatsapp_to_web_review` |
| **Unique Finding IDs** | Distinct `WF-xxx` format | PASS | 19 distinct finding IDs (`WF-001` through `WF-019`) |
| **Valid Statuses** | In defined status enum | PASS | All statuses belong to {`PASS_WITH_FRICTION`, `FULLY_VERIFIED`, `PARTIAL`} |
| **Last Verified SHA** | Present on every journey | PASS | Every journey references `26ab5af` / `26ab5affee58` |
| **Run IDs Present** | Valid audit run reference | PASS | All 8 journeys have valid run IDs matching audit records |
| **Audit History** | Preserved without truncation | PASS | 7 chronological historical audit runs recorded |

---

## 2. Inconsistency & Contradiction Analysis

### A. Journey Findings vs. Global Findings Discrepancy
- **Observation:** Finding `WF-019` (*Duplicate /api/v1 URL prefix in inboxApi breaks WhatsApp Inbox page*) was registered in root `findings` and documented in `audit_history` for run `E2E-TEST-20260920-1505`, but was omitted from the `findings:` list under `journeys.J8_whatsapp_to_web_review`.
- **Classification:** Registry Metadata Inconsistency (Non-fatal, documentation gap).
- **Resolution:** Reconciled in Phase 18 by linking `WF-019` to `journeys.J8_whatsapp_to_web_review.findings`.

### B. Artifact Directory Reference for Baseline Runs J1 & J2
- **Observation:** `J1_document_to_journal` and `J2_duplicate_document_protection` reference `last_verified_run: E2E-TEST-20260920-1139`. However, the physical audit directory `docs/audits/E2E-TEST-20260920-1139/` does not exist on disk.
- **Evidence Location:** The physical artifacts for this run are preserved in `dogfood-output/`:
  - `dogfood-output/Financial_SaaS_Active_Workflow_Audit_Report.pdf`
  - `dogfood-output/Backend_Trace_Reconciliation_Report.pdf`
  - `dogfood-output/screenshots/01-14.png`
- **Classification:** Path Reference Convention (Artifacts exist in legacy preservation folder).

### C. J8 Transport vs. Workflow Status Consistency
- **Check:** Ensure no contradiction between transport status and workflow status.
- **Result:** Consistent. Because real external WhatsApp cellular/Meta network transport was not exercised, transport was marked `NOT_VERIFIED` (`INTERNAL_INGESTION_ONLY`), and J8 status was restricted to `PARTIAL` rather than `FULLY_VERIFIED`.

### D. J5 Bank Reconciliation URL Blocker vs. Status Consistency
- **Check:** Ensure blocked UI is reflected accurately in status.
- **Result:** Consistent. J5 is marked `PARTIAL` because `browser_workflow` is blocked by URL prefix defect `WF-009` and undo/unmatch is unsupported (`WF-010`).

---

## 3. Scope Boundary Enforcement

Every claim in `WORKFLOW_REGISTRY.yaml` has been audited against the scope principle:
- No journey claim is classified as `APPLICATION-WIDE` without full repository-wide verification.
- J1, J3, J4, J6, J7 claims are explicitly restricted to `JOURNEY-SCOPED`.
- Known limitations are transparently documented on all journeys.
