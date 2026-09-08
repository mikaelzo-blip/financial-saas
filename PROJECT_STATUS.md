# Project Status

- **Last reconciled**: 2026-09-08
- **Current origin/main baseline**: `a367de8` (PR #52 merged)
- **Current branch**: `hermes/governance-cleanup`
- **Active work**: Repository governance and disposable-artifact cleanup before creating the isolated Hermes Coder profile.
- **Active Spec Kit feature**: None. The stale local pointer to completed feature 005 must not be used to select work.
- **Completed baseline**: Product features 001-010, production-readiness work, document-intelligence UAT, RC1 remediation, PRD UX v3.0 checkpoints, and storage-path remediation are merged through PR #52. Detailed historical evidence remains in `specs/`, Git history, and the retained trackers.
- **Operating model**: Local-first. Local Baileys intake is supported while the Finance PC services are running; durable PC-off capture remains `DEFERRED_POST_RC1`.
- **Current verification**: 393 backend tests passed and 3 skipped; 66 frontend tests and 6 Node bridge/contract tests passed; frontend lint completed with pre-existing warnings; typecheck and production build passed; backend dependency and complete offline migration-chain validation passed; diff and repository-safety checks passed.
- **Protected local data**: Both `backend/storage` and `backend/backend/storage` contain ignored source-document files. Do not delete or merge either tree until database references and SHA-256 hashes are reconciled.
- **Known accounting follow-up**: `FIXED_ASSET_DEPRECIATION` still posts debit account `6105` although the authoritative concept assigns depreciation to `6108`. The existing `6108` regression test exercises `DIRECT_PURCHASE`, not the fixed-asset depreciation transaction path. Fix in a separate focused feature.
- **Current cleanup checkpoint**: Governance terminology, authority, routing, state-source normalization, and disposable-artifact cleanup are implemented and verified locally.
- **Blockers**: None within the cleanup. The Hermes Coder profile must not perform autonomous development until this governance cleanup is reviewed and merged.
- **Local cleanup checkpoint**: Committed as `chore(governance): prepare repository for Hermes Coder` on `hermes/governance-cleanup`.
- **Delivery state**: Local commit complete. Push/PR awaits explicit confirmation that the configured `origin` remote is an approved destination.
- **Next action**: Push `hermes/governance-cleanup`, run PR/CI review, merge the verified cleanup, then create the new Hermes Coder profile.
