"""Security tests for AUTHZ-001: Role enforcement & actor attribution hardening.

CP1: Honest RED tests for vulnerable routes + PASS characterization for protected behavior.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import io
import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.v1 import bank_reconciliation as bank_reconciliation_api
from src.api.v1 import counterparties as counterparties_api
from src.api.v1 import documents as documents_api
from src.api.v1 import inbox as inbox_api
from src.api.v1 import money_movements as money_movements_api
from src.api.v1 import projects as projects_api
from src.api.v1 import reference_data as reference_data_api
from src.api.v1 import review as review_api
from src.api.v1 import transactions as transactions_api
from src.core.database import Base, get_db
from src.core.security import create_access_token, hash_password
from src.main import create_application
from src.models.accounting_period import AccountingPeriod
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import Document
from src.models.enums import (
    AccountingPeriodStatus,
    CandidateStatus,
    DocumentProcessingStatus,
    DocumentType,
    ProjectStatus,
    UserRole,
)
from src.models.organization import Organization
from src.models.project import Project
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.document_service import DocumentService
from src.api.auth import require_roles


@pytest.fixture
async def security_test_env(tmp_path):
    """Isolated in-memory SQLite database and test application with real auth stack."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_application()

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    # Seed organization and users
    async with session_factory() as session:
        org = Organization(slug="sec-test-org", legal_name="Security Test Org Ltd")
        session.add(org)
        await session.flush()

        users = {}
        for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR, UserRole.VIEWER]:
            u = User(
                organization_id=org.id,
                email=f"{role.value.lower()}@security-test.local",
                full_name=f"{role.value} User",
                role=role,
                password_hash=hash_password("secret123"),
                is_active=True,
            )
            session.add(u)
            users[role] = u
        await session.flush()

        await seed_standard_coa(session, org.id)
        await seed_standard_payment_accounts(session, org.id)
        coa_account_id = await session.scalar(
            select(ChartOfAccount.id).where(ChartOfAccount.organization_id == org.id)
        )
        payment_account_id = await session.scalar(
            select(PaymentAccount.id).where(PaymentAccount.organization_id == org.id)
        )
        assert coa_account_id is not None
        assert payment_account_id is not None

        # Seed counterparty & project
        customer = Counterparty(
            organization_id=org.id,
            name="Test Hardening Customer",
            is_customer=True,
            is_vendor=False,
        )
        session.add(customer)
        await session.flush()

        project = Project(
            organization_id=org.id,
            project_code="PRJ-001",
            project_name="Test Hardening Project",
            customer_id=customer.id,
            original_contract_value=Decimal("50000000.00"),
            start_date=date(2026, 1, 1),
            project_status=ProjectStatus.ACTIVE,
        )
        session.add(project)

        # Seed accounting period
        period = AccountingPeriod(
            organization_id=org.id,
            period_name="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            status=AccountingPeriodStatus.OPEN,
        )
        session.add(period)

        # Seed document awaiting review without writing outside the test sandbox.
        document_service = DocumentService(session)
        document_service.storage.base_dir = tmp_path
        doc = await document_service.ingest_document(
            org.id,
            io.BytesIO(b"%PDF-1.4\ntest"),
            "review_doc.pdf",
            "application/pdf",
            DocumentType.TRANSFER_PROOF,
            created_by=users[UserRole.OPERATOR].id,
        )
        doc.candidate_transaction = {
            "id": str(doc.id),
            "status": CandidateStatus.REVIEW_REQUIRED.value,
            "proposed_transaction_type": "VENDOR_BILL",
            "amount": "1000.00",
            "transaction_date": "2026-01-01",
        }
        doc.review_flags = ["OCR_LOW_CONFIDENCE"]
        doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED

        other_org = Organization(slug="sec-test-other-org", legal_name="Security Test Other Org Ltd")
        session.add(other_org)
        await session.flush()
        other_manager = User(
            organization_id=other_org.id,
            email="other-manager@security-test.local",
            full_name="Other Manager",
            role=UserRole.MANAGER,
            password_hash=hash_password("secret123"),
            is_active=True,
        )
        session.add_all([other_org, other_manager])

        await session.commit()
        org_id = org.id
        users_map = {r: u.id for r, u in users.items()}
        customer_id = customer.id
        project_id = project.id
        period_id = period.id
        doc_id = doc.id
        other_org_id = other_org.id
        other_manager_id = other_manager.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "app": app,
            "client": client,
            "org_id": org_id,
            "users": users_map,
            "customer_id": customer_id,
            "project_id": project_id,
            "period_id": period_id,
            "doc_id": doc_id,
            "coa_account_id": coa_account_id,
            "payment_account_id": payment_account_id,
            "other_org_id": other_org_id,
            "other_manager_id": other_manager_id,
            "session_factory": session_factory,
        }

    await engine.dispose()


def make_auth_headers(org_id: uuid.UUID, user_id: uuid.UUID) -> dict:
    """Generate authentic JWT bearer authorization and matching identity headers."""
    token = create_access_token(str(user_id), {"organization_id": str(org_id)})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(user_id),
    }


# Characterization tests cover protections already present in the live baseline.

@pytest.mark.asyncio
async def test_characterization_jwt_user_id_mismatch_returns_403(security_test_env):
    """Proves that spoofing an Admin X-User-ID with a Viewer JWT returns 403 User mismatch."""
    env = security_test_env
    viewer_id = env["users"][UserRole.VIEWER]
    admin_id = env["users"][UserRole.ADMIN]
    org_id = env["org_id"]

    token = create_access_token(str(viewer_id), {"organization_id": str(org_id)})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(admin_id),  # Spoofed Admin ID
    }

    resp = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/corrections",
        headers=headers,
        json={"changes": {"amount": "1500.00"}, "reason": "spoofed test"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "User mismatch"


@pytest.mark.asyncio
async def test_characterization_jwt_org_id_mismatch_returns_403(security_test_env):
    """Proves that spoofing X-Organization-ID mismatching JWT returns 403 Organization mismatch."""
    env = security_test_env
    viewer_id = env["users"][UserRole.VIEWER]
    org_id = env["org_id"]

    token = create_access_token(str(viewer_id), {"organization_id": str(org_id)})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(uuid.uuid4()),  # Spoofed Org ID
        "X-User-ID": str(viewer_id),
    }

    resp = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/corrections",
        headers=headers,
        json={"changes": {"amount": "1500.00"}, "reason": "spoofed org test"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Organization mismatch"


@pytest.mark.asyncio
async def test_characterization_missing_or_invalid_jwt_returns_401(security_test_env):
    """Proves that requests lacking valid JWT credentials fail closed with 401."""
    env = security_test_env
    # Missing token
    resp1 = await env["client"].get("/api/v1/counterparties")
    assert resp1.status_code == 401

    # Tampered / Invalid token
    resp2 = await env["client"].get(
        "/api/v1/counterparties",
        headers={"Authorization": "Bearer invalid.token.payload"},
    )
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_characterization_document_correction_viewer_denied_403(security_test_env):
    """Proves POST /documents/{id}/corrections denies VIEWER with 403 via require_reviewer."""
    env = security_test_env
    headers = make_auth_headers(env["org_id"], env["users"][UserRole.VIEWER])

    resp = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/corrections",
        headers=headers,
        json={"changes": {"amount": "2000.00"}, "reason": "viewer attempt"},
    )
    assert resp.status_code == 403
    assert "review permission required" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_characterization_document_rejection_viewer_denied_403(security_test_env):
    """Proves POST /documents/{id}/reject denies VIEWER with 403 via require_reviewer."""
    env = security_test_env
    headers = make_auth_headers(env["org_id"], env["users"][UserRole.VIEWER])

    resp = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/reject",
        headers=headers,
        json={"reason": "viewer reject attempt"},
    )
    assert resp.status_code == 403
    assert "review permission required" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_characterization_accounting_period_create_viewer_denied_403(security_test_env):
    """Proves POST /periods denies VIEWER with 403 via in-body role check."""
    env = security_test_env
    headers = make_auth_headers(env["org_id"], env["users"][UserRole.VIEWER])

    resp = await env["client"].post(
        "/api/v1/periods",
        headers=headers,
        json={"period_name": "2026-02", "start_date": "2026-02-01", "end_date": "2026-02-28"},
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data.get("error", {}).get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_characterization_accounting_period_status_update_viewer_denied_403(security_test_env):
    """Proves PATCH /periods/{id}/status denies VIEWER with 403 via in-body role check."""
    env = security_test_env
    headers = make_auth_headers(env["org_id"], env["users"][UserRole.VIEWER])

    resp = await env["client"].patch(
        f"/api/v1/periods/{env['period_id']}/status",
        headers=headers,
        json={"status": "CLOSED"},
    )
    assert resp.status_code == 403
    data = resp.json()
    assert data.get("error", {}).get("code") == "FORBIDDEN"


@pytest.mark.asyncio
async def test_characterization_cross_tenant_document_rejection_returns_404(security_test_env):
    """Proves a manager cannot reject a document owned by another tenant."""
    env = security_test_env
    headers = make_auth_headers(env["other_org_id"], env["other_manager_id"])

    response = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/reject",
        headers=headers,
        json={"reason": "cross-tenant attempt"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_characterization_require_roles_fallback_unreachable_in_normal_traffic(security_test_env):
    """Proves header fallback in require_roles is unreachable in normal mounted traffic."""
    env = security_test_env
    admin_id = env["users"][UserRole.ADMIN]
    org_id = env["org_id"]

    # Request with Admin headers but NO JWT to a require_roles endpoint (e.g. POST /transactions/{id}/post)
    resp = await env["client"].post(
        f"/api/v1/transactions/{uuid.uuid4()}/post",
        headers={
            "X-Organization-ID": str(org_id),
            "X-User-ID": str(admin_id),
        },
    )
    # Blocked by require_application_user with 401, NOT looked up via header fallback!
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authenticated user required"


@pytest.mark.asyncio
async def test_require_roles_rejects_headers_without_verified_principal(security_test_env):
    """Headers cannot reconstruct a principal when the verified dependency yields none."""
    checker = require_roles(UserRole.ADMIN)

    with pytest.raises(HTTPException) as error:
        await checker(current_user=None)

    assert error.value.status_code == 401
    assert error.value.detail == "Authenticated user required"


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.MANAGER])
async def test_document_correction_audit_actor_is_verified_jwt_principal(security_test_env, role, monkeypatch):
    env = security_test_env
    actor_id = env["users"][role]
    captured_actor_ids = []

    async def capture_audit_actor(_self, _org_id, _entity_name, _entity_id, _action, actor_id, **_kwargs):
        captured_actor_ids.append(actor_id)

    monkeypatch.setattr(documents_api.AuditService, "log_event", capture_audit_actor)
    headers = make_auth_headers(env["org_id"], actor_id)
    headers.pop("X-User-ID")
    response = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/corrections",
        headers=headers,
        json={"changes": {"amount": "1500.00"}, "reason": "verified actor test"},
    )

    assert response.status_code == 200, response.text
    assert captured_actor_ids == [actor_id]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.MANAGER])
async def test_document_rejection_audit_actor_is_verified_jwt_principal(security_test_env, role, monkeypatch):
    env = security_test_env
    actor_id = env["users"][role]
    captured_actor_ids = []

    async def capture_audit_actor(_self, _org_id, _entity_name, _entity_id, _action, actor_id, **_kwargs):
        captured_actor_ids.append(actor_id)

    monkeypatch.setattr(documents_api.AuditService, "log_event", capture_audit_actor)
    headers = make_auth_headers(env["org_id"], actor_id)
    headers.pop("X-User-ID")
    response = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/reject",
        headers=headers,
        json={"reason": "verified actor test"},
    )

    assert response.status_code == 200, response.text
    assert captured_actor_ids == [actor_id]


@pytest.mark.asyncio
async def test_valid_jwt_without_user_header_uses_jwt_principal(security_test_env):
    env = security_test_env
    actor_id = env["users"][UserRole.MANAGER]
    headers = make_auth_headers(env["org_id"], actor_id)
    headers.pop("X-User-ID")
    response = await env["client"].get("/api/v1/documents/review-queue", headers=headers)

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_role_header_cannot_elevate_viewer(security_test_env):
    env = security_test_env
    headers = make_auth_headers(env["org_id"], env["users"][UserRole.VIEWER])
    headers["X-Role"] = UserRole.ADMIN.value
    response = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/reject",
        headers=headers,
        json={"reason": "role header spoof"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("path, payload", [
    ("corrections", {"changes": {"amount": "1500.00"}, "reason": "operator attempt"}),
    ("reject", {"reason": "operator attempt"}),
])
async def test_document_review_operator_remains_denied(security_test_env, path, payload):
    env = security_test_env
    response = await env["client"].post(
        f"/api/v1/documents/{env['doc_id']}/{path}",
        headers=make_auth_headers(env["org_id"], env["users"][UserRole.OPERATOR]),
        json=payload,
    )

    assert response.status_code == 403
    assert "review permission required" in response.json()["detail"].lower()


MUTATION_CASES = [
    ("create_transaction", "POST", "/api/v1/transactions", transactions_api.TransactionService, "create_transaction", True),
    ("create_project", "POST", "/api/v1/projects", projects_api.ProjectService, "create_project", True),
    ("update_project_status", "PATCH", "/api/v1/projects/{project_id}/status", projects_api.ProjectService, "update_project_status", True),
    ("set_project_budget", "POST", "/api/v1/projects/{project_id}/budgets", projects_api.ProjectService, "add_or_update_project_budget", True),
    ("create_counterparty", "POST", "/api/v1/counterparties", counterparties_api, "Counterparty", False),
    ("create_coa", "POST", "/api/v1/coa", reference_data_api.COAService, "create_account", True),
    ("create_payment_account", "POST", "/api/v1/payment-accounts", reference_data_api.PaymentAccountService, "create_payment_account", True),
    ("create_money_movement", "POST", "/api/v1/money-movements", money_movements_api.MoneyMovementService, "create_money_movement", True),
    ("upload_bank_statement", "POST", "/api/v1/bank-reconciliation/imports", bank_reconciliation_api.BankReconciliationService, "import_statement", True),
    ("auto_match_statement", "POST", "/api/v1/bank-reconciliation/imports/{import_id}/auto-match", bank_reconciliation_api.BankReconciliationService, "auto_match_statement", True),
    ("manual_reconcile", "POST", "/api/v1/bank-reconciliation/reconcile", bank_reconciliation_api.BankReconciliationService, "match_manual", True),
    ("upload_document", "POST", "/api/v1/documents/upload", documents_api.DocumentService, "ingest_document", True),
    ("retry_document", "POST", "/api/v1/documents/{doc_id}/retry", documents_api.DocumentService, "get_document", True),
    ("add_review_flag", "POST", "/api/v1/transactions/{transaction_id}/review-flags", review_api.ReviewQueueService, "add_review_flag", True),
    ("inbox_capture", "POST", "/api/v1/inbox/capture", inbox_api.RemoteInboxService, "ingest_remote_capture", True),
    ("inbox_sync", "POST", "/api/v1/inbox/sync", inbox_api.RemoteInboxService, "sync_backlog", True),
    ("inbox_analyze_session", "POST", "/api/v1/inbox/sessions/{session_id}/analyze", inbox_api.DeferredAnalysisService, "analyze_session", True),
]


def mutation_request(case_name: str, env: dict) -> dict:
    payment_account_id = str(env["payment_account_id"])
    coa_account_id = str(env["coa_account_id"])

    requests = {
        "create_transaction": {"json": {"transaction_type": "OTHER_EXPENSE", "transaction_date": "2026-01-02", "amount": "100.00", "description": "Authorization boundary probe", "document_ids": []}},
        "create_project": {"json": {"project_name": "Authorization Boundary Project", "customer_id": str(env["customer_id"]), "start_date": "2026-01-02", "original_contract_value": "100.00"}},
        "update_project_status": {"json": {"status": "ON_HOLD"}},
        "set_project_budget": {"json": {"cost_category": "MAT", "budget_amount": "100.00"}},
        "create_counterparty": {"json": {"name": "Authorization Boundary Counterparty", "is_vendor": True}},
        "create_coa": {"json": {"account_code": "9999", "account_name": "Authorization Boundary Account", "account_type": "EXPENSE", "normal_balance": "DEBIT", "report_group": "Other Expense"}},
        "create_payment_account": {"json": {"coa_account_id": coa_account_id, "name": "Authorization Boundary Account", "bank_name": "Test Bank", "account_number": "000001"}},
        "create_money_movement": {"json": {"payment_account_id": payment_account_id, "direction": "OUT", "amount": "100.00", "movement_date": "2026-01-02", "source_type": "MANUAL", "settlements": []}},
        "upload_bank_statement": {"data": {"payment_account_id": payment_account_id}, "files": {"file": ("statement.csv", b"date,description,amount\\n2026-01-02,Test,100.00\\n", "text/csv")}},
        "auto_match_statement": {},
        "manual_reconcile": {"json": {"statement_line_id": str(uuid.uuid4()), "matched_amount": "100.00"}},
        "upload_document": {"data": {"document_type": "TRANSFER_PROOF", "source_channel": "WEB", "process": "false"}, "files": {"file": ("boundary.pdf", b"%PDF-1.4\\nprobe", "application/pdf")}},
        "retry_document": {},
        "add_review_flag": {"json": {"flag": "OCR_LOW_CONFIDENCE", "message": "Authorization boundary probe", "severity": "WARNING"}},
        "inbox_capture": {"json": {"external_message_id": "authz-boundary-001", "sender_phone": "+628000000001", "received_at": datetime(2026, 1, 2, tzinfo=timezone.utc).isoformat()}},
        "inbox_sync": {},
        "inbox_analyze_session": {},
    }
    return requests[case_name]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_name,method,path_template,patch_target,patch_attribute,is_async_boundary",
    MUTATION_CASES,
    ids=[case[0] for case in MUTATION_CASES],
)
async def test_viewer_denied_before_reaching_vulnerable_mutation_boundary(
    security_test_env,
    monkeypatch,
    case_name,
    method,
    path_template,
    patch_target,
    patch_attribute,
    is_async_boundary,
):
    """Requires a role denial before a schema-valid request can reach mutation code."""
    env = security_test_env

    mutation_boundary_reached = False

    if is_async_boundary:
        async def mutation_boundary(*args, **kwargs):
            nonlocal mutation_boundary_reached
            mutation_boundary_reached = True
            raise HTTPException(status_code=418, detail=f"{case_name} mutation boundary reached")
    else:
        def mutation_boundary(*args, **kwargs):
            nonlocal mutation_boundary_reached
            mutation_boundary_reached = True
            raise HTTPException(status_code=418, detail=f"{case_name} mutation boundary reached")

    monkeypatch.setattr(patch_target, patch_attribute, mutation_boundary)
    path = path_template.format(
        project_id=env["project_id"],
        doc_id=env["doc_id"],
        import_id=uuid.uuid4(),
        transaction_id=uuid.uuid4(),
        session_id=uuid.uuid4(),
    )
    response = await env["client"].request(
        method,
        path,
        headers=make_auth_headers(env["org_id"], env["users"][UserRole.VIEWER]),
        **mutation_request(case_name, env),
    )

    assert not mutation_boundary_reached, f"{case_name}: mutation boundary reached before VIEWER was denied"
    assert response.status_code == 403
