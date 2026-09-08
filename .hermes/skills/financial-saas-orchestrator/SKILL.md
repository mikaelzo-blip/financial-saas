---
name: financial-saas-orchestrator
description: Procedural Hermes workflow for this tenant-isolated financial SaaS repository.
---

# Financial SaaS Orchestrator

1. Read `PROJECT_STATUS.md`, then reconcile it with the actual Git branch, worktree status, and `origin/main` commit. Git wins for operational state. If status is stale, correct it before selecting implementation work.
2. Resolve requirements exclusively in the authority order defined by `AGENTS.md`. Do not maintain a second precedence list in this skill. Preserve approved accounting, audit, security, tenancy, and document rules.
3. For a new feature, use the Hermes Spec Kit integration and global `speckit-*` skills in this lifecycle: research -> specify -> clarify -> plan -> tasks -> analyze -> implement -> tests -> review. For a contained bug, reproduce and specify the failing behavior before the smallest tested fix.
4. Hermes Coder is the single development orchestrator. Spec Kit owns canonical requirements and planning artifacts. Supporting skills provide methods or reviews only; they do not create competing PRDs, plans, task lists, or authority orders.
5. Work on `hermes/*` branches. Use small checkpoint commits. Never mix profile/setup work with an active business-feature implementation.
6. Prefer Hermes native planning, TDD, systematic-debugging, review, simplification, Git, and PR skills. Load a specialist only when its distinct capability is relevant. Installed does not mean automatically active.
7. Before delivery, run applicable backend/frontend tests, lint, type checks, builds, migration validation, dependency checks, diff checks, and Spec Kit analysis. Never weaken tests or introduce synthetic accounting entries.
8. Push only after the checkpoint passes, open a PR, and rely on GitHub CI as an independent gate. Squash merge only when tasks are complete, CI and all quality gates pass, the PR is mergeable, and there are zero Critical/High findings or financial/tenant/security violations. Synchronize `main` afterward.
9. Update only `PROJECT_STATUS.md` for current operational state. Keep it concise: baseline commit, active work, branch, checkpoint, verification, blockers, and next action. Never create a parallel current-state file or record secrets and verbose logs.
10. The approved Hermes Coder model runtime is Hermes -> `http://127.0.0.1:20200/v1` -> AutoRouter -> 9Router/providers. Check connectivity only; AutoRouter and 9Router are intentionally manually started, not Windows autorun services.
11. Stop for production deployment, destructive production database actions, paid services, credential changes, real WhatsApp provisioning, external AI egress of real financial data, or irreversible infrastructure actions.

## Supporting Engineering Skills Routing Policy

The Hermes Coder profile follows a minimal, native-first skill stack. Third-party suites such as ECC are not core workflow orchestrators. An individually inspected specialist skill MAY be used when it adds a distinct capability, but it does not replace this skill, Spec Kit, the Constitution, `AGENTS.md`, or repository architecture.

When routing development workflows:

- **NEW FEATURE**:
  Spec Kit (`speckit-specify` -> `speckit-clarify` -> `speckit-plan` -> `speckit-tasks` -> `speckit-analyze`)
  -> native TDD where practical
  -> implementation
  -> native verification and review
- **BUG FIX**:
  native `systematic-debugging` / root-cause analysis
  -> regression test
  -> fix implementation
  -> verification
- **SECURITY / FINANCIAL / AUTH / WHATSAPP**:
  Use an inspected specialist security/review skill when useful
  while strictly enforcing Financial SaaS hard invariants.
- **RELEASE / PR**:
  repository tests and safety checks
  -> independent review
  -> PR
  -> GitHub CI

Authoritative details remain in `AGENTS.md`, `.specify/memory/constitution.md`, the product concept, and active feature artifacts; do not duplicate them here.
