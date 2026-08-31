# Production Operations Runbook

This runbook defines safe procedures. It does not authorize production deployment, destructive database work, paid services, real WhatsApp registration, DNS changes, credential rotation, or external AI data egress.

## Approval boundaries

Explicit user approval is required before any real production deployment, production data deletion, destructive/irreversible migration, paid resource purchase, external AI financial-data egress, real WhatsApp number registration, DNS change, production credential rotation, or irreversible infrastructure modification.

## Environment and secrets

Production/staging startup fails unless:

- `ENVIRONMENT` is explicit and `DEBUG=false`;
- `SECRET_KEY` is unique and at least 32 characters;
- async and sync PostgreSQL URLs contain real least-privilege credentials;
- `BACKEND_CORS_ORIGINS` is an explicit HTTPS origin allowlist;
- `STORAGE_DIR` is an absolute durable mount;
- provider secrets come from the deployment secret store, never files or logs.

Keep development, staging, and production databases, storage, secrets, domains, and provider accounts separate.

## Business initialization

Run after migrations against an empty authorized database:

```text
python -m src.cli.bootstrap --slug COMPANY --legal-name "Legal Company Name" --admin-email owner@example.com --admin-name "Initial Admin"
```

The command prompts for the password, creates the organization/admin atomically, and seeds standard COA/payment accounts. A duplicate organization or admin fails. Then the admin configures real bank/payment accounts, customers, vendors, projects, sender mappings, and users through authenticated workflows. Never seed financial balances directly; opening balances require authorized posted transactions.

## Deployment sequence

1. Obtain deployment approval and record change owner/window.
2. Verify immutable artifact revision and CI success.
3. Create and verify database and document-storage backups.
4. Deploy to staging with production-equivalent configuration.
5. Run migrations, `/health`, `/ready`, login, tenant isolation, document upload/hash, review, posting, reversal, AR/AP, balance-sheet, and export smoke tests.
6. Obtain UAT sign-off.
7. Put production writes in the approved maintenance state if migration requires it.
8. Run `alembic upgrade head`; save logs and resulting revision.
9. Deploy the same verified artifact. Confirm `/health` and `/ready` before traffic.
10. Run non-mutating integrity diagnostics, then controlled smoke tests.
11. Monitor errors, latency, database pool, storage, audit events, and financial integrity.

## Rollback

Application rollback uses the previous immutable artifact. Do not blindly downgrade a database. If a migration is additive and its reviewed downgrade is proven against a restored copy, the operator may use it only under an approved change. Otherwise restore the pre-migration backup into a new database and repoint after validation. Never delete posted financial history to recover.

## PostgreSQL backup

Use the platform-managed encrypted snapshot plus a logical custom-format backup. Example shape; supply credentials through the secret store:

```text
pg_dump --format=custom --no-owner --no-privileges --file financial-saas-YYYYMMDD-HHMM.dump "$SYNC_DATABASE_URL"
pg_restore --list financial-saas-YYYYMMDD-HHMM.dump
```

Record checksum, PostgreSQL version, application revision, Alembic revision, size, timestamp, storage location, encryption, and retention class. Never place dumps in the repository.

## Restore test

At least quarterly and before risky migrations:

1. Provision an isolated empty PostgreSQL database.
2. Restore with `pg_restore --clean --if-exists --no-owner` only against that isolated target.
3. Run `alembic current`, application `/ready`, tenant-isolation tests, journal debit/credit reconciliation, trial balance, balance sheet equation, AR/AP reconciliation, and document-reference reconciliation.
4. Verify document storage from the matching snapshot and sample SHA-256 hashes.
5. Destroy the isolated test resource only under its approved lifecycle.
6. Record duration and evidence. Target RPO/RTO must be approved by the business owner; until then readiness remains PARTIAL.

## Document storage backup and recovery

Use versioned, encrypted, tenant-isolated durable storage. Snapshot storage consistently with the database. Recovery must restore original bytes and paths, then recompute sampled SHA-256 hashes and verify every restored database reference resolves. Local single-host filesystem storage is not acceptable as the only production copy.

## Incident and troubleshooting

- `/health` failure: process/runtime issue; rollback application if newly introduced.
- `/ready` failure: check database reachability, credentials, pool exhaustion, and migration revision. Do not route traffic.
- `INTEGRITY_ERROR`: stop report certification/export and posting investigation; never add a balancing plug.
- Review backlog: inspect source documents and flags; never bulk bypass approval.
- Storage/hash mismatch: quarantine affected documents, preserve evidence, restore from versioned backup, and audit every access.
- Suspected credential exposure: stop affected integration and request explicit rotation approval.
- WhatsApp failure: retain idempotency keys and audit records; do not replay non-idempotent outbound messages blindly.
- AI provider failure: keep mock/deterministic fallback; never enable external egress as an incident workaround.

Structured request logs contain correlation ID, method, route path, status, and duration only. Do not log bodies, query strings, authorization headers, documents, prompts, or financial values.

## UAT checklist

- [ ] Initial admin can log in; invalid credentials fail.
- [ ] Operator/manager/admin permissions match policy.
- [ ] Forged tenant/user headers cannot cross tenants.
- [ ] Document original bytes and SHA-256 remain stable.
- [ ] Ambiguous transfer proof remains in Review Queue.
- [ ] Posting produces balanced journals.
- [ ] Posted records are immutable; reversal/correction works.
- [ ] AR/AP reconcile to GL.
- [ ] Assets = Liabilities + Equity.
- [ ] Project profit and cash position remain distinct.
- [ ] Backup restore evidence passes.
- [ ] Operations owner signs acceptance.

## Audit retention

Audit and source-document retention requires an approved legal/accounting policy. Until approved, do not purge. Restrict access by role and tenant, archive immutably, record export/access, and test restoration. Define retention duration, legal hold, deletion approval, and evidence format before production.

## WhatsApp production prerequisites

Requires explicit approval, verified Meta business/WABA, dedicated number, supported Graph API version, public HTTPS callback, app secret, least-privilege tokens, template/window policy review, sandbox acceptance, and operator ownership. Keep `WHATSAPP_PROVIDER=mock` until approved.

## AI production prerequisites

External AI activation requires explicit approval for provider, contract/DPA, allowed data fields, residency, retention, redaction, model/version, timeout, spend budget, token limits, audit, and fallback. Sending real financial data externally is separately approval-bound. Keep mock/deterministic operation until approved.
