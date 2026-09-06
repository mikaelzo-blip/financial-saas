---
name: financial-saas-orchestrator
description: Procedural Hermes workflow for this tenant-isolated financial SaaS repository.
---

# Financial SaaS Orchestrator

1. Read `PROJECT_STATUS.md` first. Then read only the active feature's `spec.md`, clarifications, `plan.md`, `data-model.md`, `contracts/`, and `tasks.md` needed for the current action. Do not reread the entire repository when the status and active artifacts are sufficient.
2. Resolve requirements in the authority order in `AGENTS.md`, beginning with `.specify/memory/constitution.md` and the product concept. Preserve approved accounting, audit, security, tenancy, and document rules.
3. Use the Hermes Spec Kit integration and global `speckit-*` skills in this lifecycle: research -> specify -> clarify -> plan -> tasks -> analyze -> implement -> tests -> review.
4. Work on `hermes/*` branches. Use small checkpoint commits. Never mix setup work with an active business-feature implementation.
5. Before delivery, run applicable backend/frontend tests, lint, type checks, builds, migration validation, dependency checks, diff checks, and Spec Kit analysis. Never weaken tests or introduce synthetic accounting entries.
6. Push only after the checkpoint passes, open a PR, and rely on GitHub CI as an independent gate. Squash merge only when tasks are complete, CI and all quality gates pass, the PR is mergeable, and there are zero Critical/High findings or financial/tenant/security violations. Synchronize `main` afterward.
7. Update `PROJECT_STATUS.md` concisely with main commit, completed/current feature, branch, checkpoint, tests, CI, blockers, and next action. Never record secrets or verbose logs.
8. The approved runtime is Hermes -> `http://127.0.0.1:20200/v1` -> AutoRouter -> 9Router/providers. Check connectivity only; AutoRouter and 9Router are intentionally manually started, not Windows autorun services.
9. Stop for production deployment, destructive production database actions, paid services, credential changes, real WhatsApp provisioning, external AI egress of real financial data, or irreversible infrastructure actions. After this skill is merged, the production worktree `C:\Projects\financial-saas-hermes` must be trusted before use.

## Supporting Engineering Skills Routing Policy (ECC Integration)

ECC (affaan-m/ECC) is a supporting engineering layer. It does NOT replace `financial-saas-orchestrator`, Spec Kit, the Constitution, `AGENTS.md`, or repository architecture.

When routing development workflows:

- **NEW FEATURE**:
  Spec Kit (`speckit-specify` -> `speckit-clarify` -> `speckit-plan` -> `speckit-tasks` -> `speckit-analyze`)
  -> ECC `intent-driven-development` when useful for acceptance criteria
  -> ECC `tdd-workflow` / `test-driven-development`
  -> implementation
  -> ECC `verification-loop`
  -> review
- **BUG FIX**:
  `systematic-debugging` / root-cause analysis
  -> ECC `tdd-workflow`
  -> fix implementation
  -> ECC `verification-loop`
- **SECURITY / FINANCIAL / AUTH / WHATSAPP**:
  Use best available security/review skills (e.g. `security-review`, `production-audit`)
  while strictly enforcing Financial SaaS hard invariants.
- **RELEASE / PR**:
  ECC `delivery-gate` / `git-workflow` where useful
  -> repository tests & safety checks
  -> independent review
  -> PR
  -> GitHub CI

### Conflict Precedence Order
1. `.specify/memory/constitution.md`
2. Financial SaaS `AGENTS.md`
3. `financial-saas-orchestrator`
4. Active Spec Kit specification (`specs/`)
5. Approved Financial SaaS architecture
6. ECC rules/skills
7. Generic Hermes/native conventions

If an ECC generic rule conflicts with accounting, tenancy, security, human-review, or project requirements, Financial SaaS rules WIN. Never bypass tenant isolation, double-entry equality, the Review Queue hard-stop, human approval, or auditability.

Authoritative details remain in `AGENTS.md`, `.specify/memory/constitution.md`, the product concept, and active feature artifacts; do not duplicate them here.
