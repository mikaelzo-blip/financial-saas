# Quickstart: Role Enforcement & Actor Attribution Testing

**Feature**: AUTHZ-001 & AUTH-002  
**Specification**: [spec.md](spec.md)  
**Tasks**: [tasks.md](tasks.md)  

---

## 1. Prerequisites

Ensure dependencies are installed and the Python environment is active:

```bash
cd backend
# Run test suite via uv or project python
uv run pytest -k "security" -v
```

---

## 2. Running Checkpoint Verification

### Run AUTHZ-001 Regression Suite
```bash
cd backend
uv run pytest tests/security/test_authz001_role_enforcement.py -v
```

### Run Existing Security Hardening Regressions
```bash
cd backend
uv run pytest tests/security/test_security_accounting_hardening.py -v
uv run pytest tests/security/test_accounting_period_guards.py -v
uv run pytest tests/security/test_ai_isolation.py -v
uv run pytest tests/security/test_production_readiness.py -v
```

### Run Full Backend Test Suite
```bash
cd backend
uv run pytest -v
```

### Run Frontend Gates
```bash
cd frontend
npm test
npx oxlint
npx tsc -b
npm run build
```

---

## 3. Manual Role Enforcement Verification via Curl

### Login as VIEWER
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "viewer@example.com", "password": "password123"}'
# Capture access_token from response
```

### Attempt Mutation as VIEWER (Must Return 403 Forbidden)
```bash
curl -X POST http://localhost:8000/api/v1/transactions \
  -H "Authorization: Bearer <VIEWER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"transaction_type": "DIRECT_PURCHASE", "amount": "100.00", "transaction_date": "2026-09-12", "description": "Unauthorized attempt"}'
# Response must be: HTTP 403 Forbidden
```

### Attempt Identity Spoofing with `X-User-ID` Header (Must Be Ignored or Rejected)
```bash
curl -X POST http://localhost:8000/api/v1/documents/<DOC_ID>/corrections \
  -H "Authorization: Bearer <VIEWER_TOKEN>" \
  -H "X-User-ID: <ADMIN_USER_UUID>" \
  -H "Content-Type: application/json" \
  -d '{"changes": {"description": "Hacked"}}'
# Response must be: HTTP 403 Forbidden
```
