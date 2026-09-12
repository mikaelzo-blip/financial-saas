# Quickstart: Role Enforcement & Actor Attribution Testing

**Feature**: AUTHZ-001 (Reconciled Baseline)
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

### Run AUTHZ-001 CP1 Test Suite
```bash
cd backend
# Run characterization tests (all must pass green)
uv run pytest tests/security/test_authz001_role_enforcement.py -k "characterization" -v

# Run honest RED tests (must fail as RED on current baseline)
uv run pytest tests/security/test_authz001_role_enforcement.py -k "test_viewer_denied_on_vulnerable_routes" -v
```

### Run Existing Security Regressions
```bash
cd backend
uv run pytest tests/unit/test_security_accounting_hardening.py -v
uv run pytest tests/unit/test_jwt_security.py -v
```

### Run Full Backend Test Suite
```bash
cd backend
uv run pytest -q
```
