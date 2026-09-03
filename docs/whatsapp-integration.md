# WhatsApp integration — offline implementation and operations

Feature 007 keeps the approved boundary:

WhatsApp provider → WhatsApp adapter → `HermesApiClient` → authenticated SaaS API → Feature 005 intake / candidate review.

The adapter has no database, storage, journal, transaction-posting, or approval service dependency. SaaS API handlers own sender mappings, message audit records and clarification sessions. Original bytes and captions are persisted by the existing document intake service. Existing financial rules and frontend behavior are unchanged.

## Runtime configuration (no production activation)

The default `WHATSAPP_PROVIDER=mock` makes no Meta calls. Without explicitly configured webhook secrets and machine credentials, public requests fail closed. No live credentials are included in this repository.

| Setting | Purpose |
| --- | --- |
| `WHATSAPP_PROVIDER` | `mock` by default; `meta` only after explicit deployment approval |
| `WHATSAPP_VERIFY_TOKEN` | GET subscription verification secret |
| `WHATSAPP_WEBHOOK_APP_SECRET` | HMAC-SHA256 secret for raw POST bytes |
| `WHATSAPP_SAAS_URL` | HTTPS SaaS API base URL |
| `WHATSAPP_ADAPTER_TOKEN` | Least-privilege machine credential for sender resolution and rejection audit only |
| `WHATSAPP_TENANT_TOKENS` | JSON object of organization UUID to distinct tenant-bound machine secret |
| `WHATSAPP_ORG_MESSAGES_PER_MINUTE` | Organization limit, default 200; sender limit is always 20/minute |
| `WHATSAPP_API_TOKEN` | Future Meta bearer credential, redacted in settings representations |
| `WHATSAPP_PHONE_NUMBER_ID` | Future Meta sending number identifier |
| `WHATSAPP_GRAPH_VERSION` | Configurable Graph API version; approved baseline is `v26.0` |

Tenant credentials extend Hermes machine authentication without changing existing `HERMES_AGENT_TOKEN` / `HERMES_ORGANIZATION_ID` behavior. The external adapter credential cannot upload a document. Each tenant token maps server-side to exactly one organization; `X-Organization-ID` never selects its tenant. Duplicate token assignments fail closed. Supply secrets through encrypted deployment secret storage, not checked-in files; `SecretStr` redacts representations but is not itself encryption at rest.

The notification worker polls SaaS processing results every 10 seconds. It starts within the application lifespan and uses only HTTPS client operations. Unconfigured installations do not start external requests. A test can inject `app.state.whatsapp_service` with `MockWhatsAppProvider` and an ASGI-backed `HttpxHermesTransport` to exercise every API boundary without a network service.

## APIs

Public provider endpoints:

- `GET /api/v1/integrations/whatsapp/webhook`: subscription challenge; wrong token/mode → 403.
- `POST /api/v1/integrations/whatsapp/webhook`: raw-body HMAC required; wrong/missing signature → 401. Request body capped at 1 MiB. Unsupported/malformed payload → 422.

Administration:

- `GET/POST /api/v1/integrations/whatsapp/senders`
- `DELETE /api/v1/integrations/whatsapp/senders/{id}` soft-disables, never deletes history.

These require a signed, expiring user bearer JWT and an active ADMIN in the specified `X-Organization-ID`. Mapping another organization's user is rejected. The existing application JWT signing key must be securely configured before any deployment.

Internal authenticated Hermes channel operations (all POST under `/api/v1/hermes/whatsapp/`):

| Operation | Authority / behavior |
| --- | --- |
| `resolve` | Adapter credential; resolves an active sender and active SaaS user |
| `rejections/claim`, `rejections/finish` | Adapter credential; rejected contact audit only, no financial references |
| `messages/claim`, `messages/finish` | Tenant credential; durable idempotency and inbound/outbound audit |
| `documents/get` | Tenant credential plus sender permission; minimal document status only |
| `status` | Tenant credential plus PROJECT_MANAGER / FINANCE_MANAGER mapping |
| `clarifications/open` | Tenant credential; document must originate from that sender and remain in Review Queue; choices built by SaaS |
| `clarifications/reply` | Tenant and sender/session-bound; validates typed choice and candidate mutability |
| `clarifications/expire` | Tenant-scoped expiry after 24 hours |
| `notifications`, `notifications/claim`, `notifications/finish` | Tenant-scoped, idempotently claimed processing-result notices and prompts |

Upload reuses `POST /api/v1/hermes/documents/upload` with a stable `wa-msg-<SHA256(wamid)>` idempotency key, `source_channel=WHATSAPP`, and validated JSON source metadata (`wamid`, `sender_phone`, `timestamp`, `caption`, `media_id`). Sender ownership is rechecked by SaaS. Feature 005 content-hash duplicates return the existing document, without changing its original metadata or scheduling extraction again.

## Review safety

`STATUS`, `RINGKASAN`, `STATUS PROYEK`, and `ANTREAN NOTA` return only permitted operational counts. `HELP` and unknown commands return safe help. There are no chat commands to approve, post, reverse, delete, or select debit/credit accounts.

Missing/ambiguous project extraction automatically generates a session with up to three active project choices and the document code. Further documents wait while that sender has a pending question. Numeric replies resolve only one active session; buttons include the session UUID. Expired or converted candidates cannot be changed.

The SaaS can also open `CONFIRM_AMOUNT` and `SELECT_CATEGORY` prompts. Amount confirmation is restricted to the exact extracted positive finite Decimal, not an arbitrary typed amount. Category choices come from the existing `CostCategory` enum, not COA accounts. All three question types append a `DocumentCorrection` and an audit event. They preserve `REVIEW_REQUIRED`, every review flag, source bytes, and approval requirements.

## Reliability and operational limits

- Database uniqueness on `(organization_id, wamid)` prevents concurrent webhook replay from processing twice; original message timestamps outside 24 hours or over five minutes in the future are discarded.
- Hermes retries transient transport/408/429/5xx failures at most three times with identical tenant credentials and idempotency keys. Authentication/validation failures are not retried.
- HTTPS media retrieval only accepts the configured provider's exact media host, rejects redirects, checks MIME signatures and the actual streamed byte count, and caps media at 25 MiB. No adapter-side files are written.
- Download failure records `DOWNLOAD_FAILED` and asks the user to resend. Exhausted SaaS retries record `FAILED` and send a safe resubmission notice.
- Unconfirmed outbound sends are recorded as failed attempts, without automatic POST retry (the provider might already have delivered them). Operators must reconcile failed/stuck message records before resubmission; this implementation is not a durable job-queue/crash-recovery system.
- The approved sliding-window limiter is in-process and bounded. Run a **single adapter worker**; distributed rate limiting is required before horizontal scaling. Unknown-sender notices have a bounded in-memory cache plus deterministic persistent audit IDs for restart-safe deduplication.
- To satisfy FR-020 without inventing a tenant, unknown-sender audit records have a nullable organization, guarded by a database check that permits only `UNREGISTERED_SENDER` records with no document/submission references. Tenant API queries never include these records. This narrow resolution follows the spec's all-message audit requirement over the data-model table's initially non-null organization assumption. Disabled known senders retain their organization in rejection audit.
- Throttled, previously claimed or expired events acknowledge HTTP 200 to prevent provider retry storms. Throttled known-sender events are recorded as rejected and emit at most one warning per window.

## Automated verification

Use the committed CI workflow as the authoritative command set. From `backend`:

```text
uv sync --locked --extra test
uv pip install --python .venv/bin/python pip==25.3
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/python -m alembic upgrade head --sql
```

On Windows replace `.venv/bin/python` with `.venv\Scripts\python.exe`.

From `frontend`: `npm ci`, `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`. From repository root: `bash .github/scripts/check-repository-safety.sh`.

`backend/tests/integration/test_whatsapp_quickstart.py` executes all six acceptance scenarios:

| Scenario | Verification |
| --- | --- |
| A | GET handshake returns the exact challenge |
| B | Registered photo intake preserves caption and WHATSAPP source |
| C | Concurrent replay creates one document, one download and one receipt |
| D | Unknown sender receives a safe notice; no document created |
| E | Numeric reply changes project only; session answered, no journal |
| F | Simultaneous tenant requests remain isolated; actual authorized document lookup succeeds and cross-tenant lookup returns 404 |

Additional tests execute the real Feature 005 pipeline with a scripted extraction provider, confirm transfer proof remains in review, exercise typed Decimal/category choices, verify no financial posting, enforce tenant and administrator permissions, and round-trip migration 010 in a disposable SQLite database. CI validates the complete PostgreSQL migration SQL chain; it does not run a live PostgreSQL migration.

## Future provider prerequisites — approval required

No real provider was activated or provisioned. Future activation requires a verified Meta Business/developer account, WABA, a dedicated authorized phone number, a supported Graph API version, a messaging/management access token, app secret, and a public HTTPS callback registration. Validate current provider permissions, media-host policy and message-template/conversation-window rules before deployment. Paid resources, real numbers and webhook registration require explicit approval. These are not prerequisites for the mock test suite.
