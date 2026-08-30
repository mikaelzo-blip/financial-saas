# Quickstart: Hermes Automation Integration

1. Set `HERMES_AGENT_TOKEN` and `HERMES_ORGANIZATION_ID` only in deployment secrets. Do not put either value in source or a queued job payload.
2. Instantiate `HermesApiClient` with an HTTPS base URL, runtime token supplier, and transport implementation.
3. Submit original evidence using `submit_document` with one stable idempotency key per logical source document.
4. Read the returned SaaS processing/review status. A review-required outcome remains pending for ordinary SaaS review.
5. Never invoke database services, document storage, approval, posting, or journal endpoints from Hermes.

Run local verification from `backend/`:

```powershell
python -m pytest tests/unit/test_hermes_auth.py tests/integration/test_hermes_api.py -q
python -m alembic upgrade head --sql
```
