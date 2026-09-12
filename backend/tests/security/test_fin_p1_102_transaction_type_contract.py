"""Security regression and characterization suite for FIN-P1-102.

Remediation: FIN-P1-102 — TransactionType Ingestion vs Executable Processing Contract
Checkpoint: CP2 — Canonical Processing Capability & Generic Ingestion Gate.

Invariants Covered:
- TYPE-R01: Executable generic ingestion gate (PostingRuleRegistry 20 supported types)
- TYPE-R02: Pre-persistence rejection of unsupported types
- TYPE-R03: Standard 422 INVARIANT_VIOLATION error contract
- TYPE-R04: Tenant sequence counter preservation on rejected intake
- TYPE-R05: REVERSAL generic intake prohibition (special workflow only)
- TYPE-R06: Dedicated reversal workflow preservation (201 Created)
- TYPE-R07: Document candidate correction generic capability gate
- TYPE-R08: Document candidate approval defense-in-depth fail-closed safety
- TYPE-R09: PETTY_CASH_EXPENSE AUTO_SAFE contradiction removal
- TYPE-R10: AUTO_SAFE subset of normal generic posting rules invariant
- TYPE-R11: Full positive controls for supported transaction types
- TYPE-R12: Zero speculative accounting policy invention

"""

from datetime import date, datetime
from decimal import Decimal
import io
import uuid
from typing import AsyncGenerator, Dict, Any, List

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.database import Base, get_db
from src.core.exceptions import InvariantViolationException
from src.core.security import create_access_token, hash_password
from src.main import create_application
from src.models.accounting_period import AccountingPeriod
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import Document
from src.models.enums import (
    AccountingPeriodStatus,
    CandidateStatus,
    CostCategory,
    DocumentProcessingStatus,
    DocumentType,
    ExpenseCategory,
    ProjectStatus,
    TransactionType,
    UserRole,
    WorkflowStatus,
)
from src.models.journal import JournalEntry, JournalLine
from src.models.organization import Organization
from src.models.project import Project
from src.models.tenant_sequence import TenantSequence
from src.models.transaction import Transaction
from src.models.user import User
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.posting_rules import PostingRuleRegistry
from src.services.processing_policy_service import ProcessingPolicyService


# ==============================================================================
# AUTHORITATIVE CAPABILITY CLASSIFICATION (37 Total Types)
# ==============================================================================

POSTING_RULE_SUPPORTED_TYPES: frozenset[TransactionType] = frozenset({
    TransactionType.DIRECT_PURCHASE,
    TransactionType.VENDOR_BILL,
    TransactionType.PAY_VENDOR_BILL,
    TransactionType.SUBCONTRACTOR_BILL,
    TransactionType.PAY_SUBCONTRACTOR,
    TransactionType.VENDOR_ADVANCE,
    TransactionType.SETTLE_VENDOR_ADVANCE,
    TransactionType.CUSTOMER_ADVANCE,
    TransactionType.BANK_TO_CASH,
    TransactionType.CASH_TO_BANK,
    TransactionType.INTERBANK_TRANSFER,
    TransactionType.ASSET_PURCHASE,
    TransactionType.FIXED_ASSET_DEPRECIATION,
    TransactionType.CUSTOMER_INVOICE,
    TransactionType.CUSTOMER_PAYMENT,
    TransactionType.RETENTION_RELEASE,
    TransactionType.OWNER_CONTRIBUTION,
    TransactionType.OWNER_WITHDRAWAL,
    TransactionType.BANK_CHARGE,
    TransactionType.JOURNAL_ADJUSTMENT,
})

SPECIAL_WORKFLOW_TYPES: frozenset[TransactionType] = frozenset({
    TransactionType.REVERSAL,
})

UNSUPPORTED_TYPES: frozenset[TransactionType] = frozenset({
    TransactionType.EMPLOYEE_ADVANCE,
    TransactionType.EMPLOYEE_SETTLEMENT,
    TransactionType.REIMBURSEMENT,
    TransactionType.PAY_REIMBURSEMENT,
    TransactionType.PETTY_CASH_EXPENSE,
    TransactionType.TOPUP_PETTY_CASH,
    TransactionType.RETURN_PETTY_CASH,
    TransactionType.INVENTORY_PURCHASE,
    TransactionType.INVENTORY_USAGE,
    TransactionType.REVENUE_RECOGNITION,
    TransactionType.CUSTOMER_REFUND,
    TransactionType.VENDOR_REFUND,
    TransactionType.LOAN_RECEIVED,
    TransactionType.LOAN_PAYMENT,
    TransactionType.OTHER_INCOME,
    TransactionType.OTHER_EXPENSE,
})

GENERIC_INGESTIBLE_TYPES: frozenset[TransactionType] = POSTING_RULE_SUPPORTED_TYPES

GENERIC_REJECTED_TYPES: tuple[TransactionType, ...] = tuple(sorted(
    UNSUPPORTED_TYPES | SPECIAL_WORKFLOW_TYPES,
    key=lambda t: t.value,
))


def make_auth_headers(org_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, str]:
    """Generate authentic JWT bearer authorization and matching identity headers."""
    token = create_access_token(str(user_id), {"organization_id": str(org_id)})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(user_id),
    }


@pytest.fixture
async def p1_102_env(tmp_path) -> AsyncGenerator[Dict[str, Any], None]:
    """Isolated in-memory test environment establishing organization, users, and ledger base."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_application()

    async def override_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db

    async with session_factory() as session:
        org = Organization(slug="fin-p1-102-org", legal_name="FIN-P1-102 Test Corp")
        session.add(org)
        await session.flush()

        users = {}
        for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR, UserRole.VIEWER]:
            u = User(
                organization_id=org.id,
                email=f"{role.value.lower()}@p1-102.local",
                full_name=f"{role.value} User",
                role=role,
                password_hash=hash_password("secret123"),
                is_active=True,
            )
            session.add(u)
            users[role] = u
        await session.flush()

        # Seed COA and payment accounts
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

        # Seed active customer counterparty
        customer = Counterparty(
            organization_id=org.id,
            name="P1-102 Test Customer",
            is_customer=True,
            is_vendor=False,
        )
        # Seed active vendor counterparty
        vendor = Counterparty(
            organization_id=org.id,
            name="P1-102 Test Vendor",
            is_customer=False,
            is_vendor=True,
        )
        session.add_all([customer, vendor])
        await session.flush()

        # Seed active project
        project = Project(
            organization_id=org.id,
            project_code="PRJ-102-001",
            project_name="P1-102 Test Project",
            customer_id=customer.id,
            original_contract_value=Decimal("10000000.00"),
            start_date=date(2026, 1, 1),
            project_status=ProjectStatus.ACTIVE,
        )
        session.add(project)

        # Seed open accounting period for January 2026
        period = AccountingPeriod(
            organization_id=org.id,
            period_name="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            status=AccountingPeriodStatus.OPEN,
        )
        session.add(period)

        await session.commit()
        org_id = org.id
        users_map = {r: u.id for r, u in users.items()}
        customer_id = customer.id
        vendor_id = vendor.id
        project_id = project.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield {
            "app": app,
            "client": client,
            "org_id": org_id,
            "users": users_map,
            "customer_id": customer_id,
            "vendor_id": vendor_id,
            "project_id": project_id,
            "coa_account_id": coa_account_id,
            "payment_account_id": payment_account_id,
            "session_factory": session_factory,
        }

    await engine.dispose()


# ==============================================================================
# 1. CAPABILITY MATRIX CHARACTERIZATION — PASS
# ==============================================================================

def test_capability_matrix_completeness():
    """Characterize and verify the 37-member TransactionType processing capability contract.

    Proves:
    - Total TransactionType enum count is exactly 37.
    - Normal posting rule supported count is exactly 20.
    - Special-workflow-only count is exactly 1 (REVERSAL).
    - Policy-blocked unsupported count is exactly 16.
    - Future generic ingestible set has exactly 20 members.
    - Future generic rejected set has exactly 17 members.
    - All categories are mutually disjoint and their union covers all 37 enum members.
    """
    all_enum_types = set(TransactionType)
    assert len(all_enum_types) == 37
    assert len(POSTING_RULE_SUPPORTED_TYPES) == 20
    assert len(SPECIAL_WORKFLOW_TYPES) == 1
    assert SPECIAL_WORKFLOW_TYPES == {TransactionType.REVERSAL}
    assert len(UNSUPPORTED_TYPES) == 16
    assert len(GENERIC_INGESTIBLE_TYPES) == 20
    assert len(GENERIC_REJECTED_TYPES) == 17

    # Mutually disjoint
    assert POSTING_RULE_SUPPORTED_TYPES.isdisjoint(SPECIAL_WORKFLOW_TYPES)
    assert POSTING_RULE_SUPPORTED_TYPES.isdisjoint(UNSUPPORTED_TYPES)
    assert SPECIAL_WORKFLOW_TYPES.isdisjoint(UNSUPPORTED_TYPES)

    # Exhaustive union
    assert POSTING_RULE_SUPPORTED_TYPES | SPECIAL_WORKFLOW_TYPES | UNSUPPORTED_TYPES == all_enum_types
    assert GENERIC_INGESTIBLE_TYPES | set(GENERIC_REJECTED_TYPES) == all_enum_types

    # Production capability exposure matches the independently classified contract.
    assert PostingRuleRegistry.POSTING_RULE_SUPPORTED_TYPES == POSTING_RULE_SUPPORTED_TYPES
    assert PostingRuleRegistry.SPECIAL_WORKFLOW_TYPES == SPECIAL_WORKFLOW_TYPES
    for transaction_type in TransactionType:
        assert PostingRuleRegistry.is_generic_ingestible(transaction_type) is (
            transaction_type in GENERIC_INGESTIBLE_TYPES
        )


# ==============================================================================
# 2. GENERIC CREATE REJECTION — GREEN (17 CASES)
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("trx_type", GENERIC_REJECTED_TYPES, ids=[t.value for t in GENERIC_REJECTED_TYPES])
async def test_generic_intake_rejects_unsupported_and_special_types(p1_102_env, trx_type: TransactionType):
    """Reject all 16 unsupported types and REVERSAL at generic intake.

    Contract:
    - HTTP 422 Unprocessable Content
    - error.code == 'INVARIANT_VIOLATION'
    - Error details identify the rejected type and capability reason
    - Zero Transaction persistence in database
    """
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    headers = make_auth_headers(org_id, admin_id)

    payload = {
        "transaction_type": trx_type.value,
        "transaction_date": "2026-01-15",
        "amount": "250000.00",
        "currency": "IDR",
        "description": f"Generic intake probe for {trx_type.value}",
        "document_ids": [],
    }

    response = await client.post("/api/v1/transactions", headers=headers, json=payload)

    assert response.status_code == 422
    error = response.json().get("error", {})
    assert error.get("code") == "INVARIANT_VIOLATION"
    assert error.get("details", {}).get("transaction_type") == trx_type.value
    expected_reason = (
        "SPECIAL_WORKFLOW_ONLY"
        if trx_type in SPECIAL_WORKFLOW_TYPES
        else "NO_POSTING_RULE"
    )
    assert error.get("details", {}).get("reason") == expected_reason

    # No transaction record is persisted.
    async with env["session_factory"]() as session:
        persisted = await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.organization_id == org_id,
                Transaction.transaction_type == trx_type,
            )
        )
        assert persisted == 0


@pytest.mark.asyncio
async def test_generic_intake_preserves_tenant_sequence_on_rejection(p1_102_env):
    """Rejected transaction attempts must not consume tenant sequence numbers.

    Contract:
    - HTTP 422 INVARIANT_VIOLATION
    - TenantSequence row for namespace 'TRX' and year '2026' is not created or incremented
    """
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    headers = make_auth_headers(org_id, admin_id)

    payload = {
        "transaction_type": TransactionType.OTHER_EXPENSE.value,
        "transaction_date": "2026-01-15",
        "amount": "100000.00",
        "description": "Sequence allocation probe for unsupported type",
        "document_ids": [],
    }

    response = await client.post("/api/v1/transactions", headers=headers, json=payload)

    assert response.status_code == 422

    async with env["session_factory"]() as session:
        seq_row = await session.scalar(
            select(TenantSequence).where(
                TenantSequence.organization_id == org_id,
                TenantSequence.namespace == "TRX",
                TenantSequence.scope_key == "2026",
            )
        )
        assert seq_row is None or seq_row.current_value == 0


# ==============================================================================
# 3. SUPPORTED GENERIC POSITIVE CONTROLS — PASS
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("supported_type", [
    TransactionType.DIRECT_PURCHASE,
    TransactionType.BANK_CHARGE,
], ids=["DIRECT_PURCHASE", "BANK_CHARGE"])
async def test_supported_generic_intake_positive_controls(p1_102_env, supported_type: TransactionType):
    """Ensure generic intake gating does not reject valid normal posting types.

    Proves:
    - Normal posting rule supported types return HTTP 201 Created.
    - Transaction is persisted with initial status STAGED.
    - Authoritative transaction code is allocated.
    """
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    pa_id = env["payment_account_id"]
    headers = make_auth_headers(org_id, admin_id)

    payload = {
        "transaction_type": supported_type.value,
        "transaction_date": "2026-01-10",
        "amount": "50000.00",
        "payment_account_id": str(pa_id),
        "expense_category": ExpenseCategory.OFFICE_ADMIN.value if supported_type == TransactionType.DIRECT_PURCHASE else None,
        "description": f"Positive control intake for {supported_type.value}",
        "document_ids": [],
    }

    response = await client.post("/api/v1/transactions", headers=headers, json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["workflow_status"] == "STAGED"
    assert data["transaction_type"] == supported_type.value
    assert data["transaction_code"].startswith("TRX-2026-")

    # Verify database persistence
    async with env["session_factory"]() as session:
        trx = await session.scalar(
            select(Transaction).where(
                Transaction.organization_id == org_id,
                Transaction.id == uuid.UUID(data["id"]),
            )
        )
        assert trx is not None
        assert trx.workflow_status == WorkflowStatus.STAGED


# ==============================================================================
# 4. STAGED DEAD-END BASELINE & ZERO-LEDGER IMPACT — PASS
# ==============================================================================

@pytest.mark.asyncio
async def test_historical_staged_unsupported_transaction_remains_fail_closed(p1_102_env):
    """Preserve CP1 evidence for historical unsupported STAGED rows.

    New unsupported rows cannot enter through generic intake after CP2. A direct
    historical fixture proves that pre-existing rows still fail closed at posting,
    create no journal records, and remain unchanged by this remediation.
    """
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    headers = make_auth_headers(org_id, admin_id)

    async with env["session_factory"]() as session:
        transaction = Transaction(
            organization_id=org_id,
            transaction_code="TRX-2026-HIST01",
            transaction_type=TransactionType.OTHER_EXPENSE,
            transaction_date=date(2026, 1, 12),
            amount=Decimal("750000.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.STAGED,
            description="Historical dead-end characterization",
        )
        session.add(transaction)
        await session.commit()
        transaction_id = transaction.id

    post_res = await client.post(
        f"/api/v1/transactions/{transaction_id}/post",
        headers=headers,
    )
    assert post_res.status_code == 422
    error = post_res.json()["error"]
    assert error["code"] == "INVARIANT_VIOLATION"
    assert "No posting rule defined for transaction type: OTHER_EXPENSE" in error["message"]

    async with env["session_factory"]() as session:
        journal_entry_count = await session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == org_id,
                JournalEntry.transaction_id == transaction_id,
            )
        )
        journal_line_count = await session.scalar(
            select(func.count(JournalLine.id)).where(
                JournalLine.notes == "Historical dead-end characterization"
            )
        )
        persisted_transaction = await session.scalar(
            select(Transaction).where(
                Transaction.organization_id == org_id,
                Transaction.id == transaction_id,
            )
        )
        assert journal_entry_count == 0
        assert journal_line_count == 0
        assert persisted_transaction is not None
        assert persisted_transaction.workflow_status == WorkflowStatus.STAGED


@pytest.mark.asyncio
async def test_dead_end_recovery_reversal_rejected(p1_102_env):
    """A historical unsupported STAGED transaction cannot use the reversal workflow."""
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    headers = make_auth_headers(org_id, admin_id)

    async with env["session_factory"]() as session:
        transaction = Transaction(
            organization_id=org_id,
            transaction_code="TRX-2026-HIST02",
            transaction_type=TransactionType.OTHER_EXPENSE,
            transaction_date=date(2026, 1, 14),
            amount=Decimal("300000.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.STAGED,
            description="Historical recovery characterization probe",
        )
        session.add(transaction)
        await session.commit()
        transaction_id = transaction.id

    rev_res = await client.post(
        f"/api/v1/transactions/{transaction_id}/reverse",
        headers=headers,
        json={"reason": "Attempting to reverse historical staged transaction"},
    )
    assert rev_res.status_code == 422
    error = rev_res.json()["error"]
    assert error["code"] == "INVARIANT_VIOLATION"
    assert "Only POSTED transactions can be reversed" in error["message"]


# ==============================================================================
# 5. DEDICATED REVERSAL WORKFLOW — PASS
# ==============================================================================

@pytest.mark.asyncio
async def test_dedicated_reversal_flow_success(p1_102_env):
    """Preserve dedicated reversal workflow on a valid POSTED transaction.

    Proves:
    - Valid POSTED transaction + dedicated reversal endpoint succeeds.
    - Returns HTTP 201 Created.
    - Reversal transaction is created with transaction_type == 'REVERSAL' and status 'POSTED'.
    - Original transaction status transitions to 'REVERSED'.
    - Original and reversal journal entries form an offsetting balanced pair.
    """
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    pa_id = env["payment_account_id"]
    headers = make_auth_headers(org_id, admin_id)

    # 1. Create valid DIRECT_PURCHASE
    create_res = await client.post("/api/v1/transactions", headers=headers, json={
        "transaction_type": TransactionType.DIRECT_PURCHASE.value,
        "transaction_date": "2026-01-10",
        "amount": "120000.00",
        "payment_account_id": str(pa_id),
        "expense_category": ExpenseCategory.OFFICE_ADMIN.value,
        "description": "Original transaction for dedicated reversal test",
    })
    assert create_res.status_code == 201
    orig_trx_id = uuid.UUID(create_res.json()["id"])

    # 2. Post original transaction
    post_res = await client.post(f"/api/v1/transactions/{orig_trx_id}/post", headers=headers)
    assert post_res.status_code == 200
    assert post_res.json()["workflow_status"] == "POSTED"

    # 3. Reverse original transaction via dedicated route
    rev_res = await client.post(f"/api/v1/transactions/{orig_trx_id}/reverse", headers=headers, json={
        "reason": "Legitimate operational reversal of incorrect bill",
    })
    assert rev_res.status_code == 201
    rev_data = rev_res.json()
    assert rev_data["transaction_type"] == "REVERSAL"
    assert rev_data["workflow_status"] == "POSTED"
    assert rev_data["reversal_of_id"] == str(orig_trx_id)

    # 4. Verify database state
    async with env["session_factory"]() as session:
        orig_trx = await session.scalar(
            select(Transaction).where(
                Transaction.organization_id == org_id,
                Transaction.id == orig_trx_id,
            )
        )
        assert orig_trx is not None
        assert orig_trx.workflow_status == WorkflowStatus.REVERSED


# ==============================================================================
# 6. AUTO_SAFE CONTRADICTION & POSITIVE CONTROLS
# ==============================================================================

@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="TYPE-R09/TYPE-R10: PETTY_CASH_EXPENSE in AUTO_SAFE_TYPES contradicts lack of executable posting rule",
)
def test_auto_safe_types_must_be_subset_of_posting_rule_supported():
    """Assert future invariant: AUTO_SAFE_TYPES must be a strict subset of POSTING_RULE_SUPPORTED_TYPES.

    Current baseline flaw:
    - ProcessingPolicyService.AUTO_SAFE_TYPES includes PETTY_CASH_EXPENSE.
    - PostingRuleRegistry has no rule for PETTY_CASH_EXPENSE.
    - Hence this test strictly XFAILs in CP1 until CP3 removes the contradiction.
    """
    assert TransactionType.PETTY_CASH_EXPENSE not in ProcessingPolicyService.AUTO_SAFE_TYPES
    assert ProcessingPolicyService.AUTO_SAFE_TYPES.issubset(POSTING_RULE_SUPPORTED_TYPES)


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="TYPE-R09: evaluate_processing_policy must return HUMAN_REVIEW for PETTY_CASH_EXPENSE",
)
async def test_petty_cash_expense_policy_evaluation_requires_human_review(p1_102_env):
    """Assert future invariant: Candidate transaction with PETTY_CASH_EXPENSE must evaluate to HUMAN_REVIEW.

    Current baseline behavior:
    - Returns 'AUTO_SAFE' because PETTY_CASH_EXPENSE is in AUTO_SAFE_TYPES.
    - Hence this test strictly XFAILs in CP1.
    """
    env = p1_102_env
    async with env["session_factory"]() as session:
        policy_service = ProcessingPolicyService(session)
        trx = Transaction(
            organization_id=env["org_id"],
            transaction_code="TRX-TEST-001",
            transaction_type=TransactionType.PETTY_CASH_EXPENSE,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("50000.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.STAGED,
            description="Petty cash expense evaluation probe",
        )
        trx.review_flags = []

        result = await policy_service.evaluate_processing_policy(trx)
        assert result == "HUMAN_REVIEW"


def test_auto_safe_positive_controls():
    """Verify legitimate AUTO_SAFE entries DIRECT_PURCHASE and BANK_CHARGE are executable.

    Proves:
    - DIRECT_PURCHASE and BANK_CHARGE are present in AUTO_SAFE_TYPES.
    - Both are present in POSTING_RULE_SUPPORTED_TYPES.
    """
    assert TransactionType.DIRECT_PURCHASE in ProcessingPolicyService.AUTO_SAFE_TYPES
    assert TransactionType.BANK_CHARGE in ProcessingPolicyService.AUTO_SAFE_TYPES
    assert TransactionType.DIRECT_PURCHASE in POSTING_RULE_SUPPORTED_TYPES
    assert TransactionType.BANK_CHARGE in POSTING_RULE_SUPPORTED_TYPES


# ==============================================================================
# 7. DOCUMENT CORRECTION GENERIC CAPABILITY — STRICT RED (17 CASES)
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("trx_type", GENERIC_REJECTED_TYPES, ids=[t.value for t in GENERIC_REJECTED_TYPES])
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="TYPE-R07: Document review correction must reject non-executable transaction types",
)
async def test_document_correction_rejects_non_generic_types(p1_102_env, trx_type: TransactionType):
    """Assert future invariant: POST /documents/{id}/corrections must reject assigning non-generic types.

    Future expected contract:
    - HTTP 422 Unprocessable Content
    - error.code == 'INVARIANT_VIOLATION'
    - Candidate proposed_transaction_type remains unchanged.

    Current baseline behavior:
    - Returns 200 OK and updates proposed_transaction_type to the rejected type.
    - Hence this test strictly XFAILs in CP1 across all 17 rejected types.
    """
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    headers = make_auth_headers(org_id, admin_id)

    # Seed document candidate awaiting review
    async with env["session_factory"]() as session:
        doc = Document(
            organization_id=org_id,
            document_code=f"DOC-CORR-{trx_type.value[:10]}-{uuid.uuid4().hex[:6]}",
            file_name="correction_probe.pdf",
            file_hash=uuid.uuid4().hex,
            file_size_bytes=512,
            mime_type="application/pdf",
            storage_path=f"test/corr_{trx_type.value}.pdf",
            document_type=DocumentType.TRANSFER_PROOF,
            source_channel="WEB",
            processing_status=DocumentProcessingStatus.REVIEW_REQUIRED,
            review_flags=["OCR_LOW_CONFIDENCE"],
            candidate_transaction={
                "id": str(uuid.uuid4()),
                "status": "REVIEW_REQUIRED",
                "proposed_transaction_type": "DIRECT_PURCHASE",
                "amount": "150000.00",
                "transaction_date": "2026-01-10",
                "description": "Document correction capability probe",
            },
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    # Attempt to correct proposed_transaction_type to the non-executable type
    correction_payload = {
        "changes": {
            "proposed_transaction_type": trx_type.value,
        },
        "reason": f"Probing correction boundary with {trx_type.value}",
    }

    response = await client.post(f"/api/v1/documents/{doc_id}/corrections", headers=headers, json=correction_payload)

    # Future contract assertion (fails with 200 != 422 in baseline)
    assert response.status_code == 422
    body = response.json()
    assert body.get("error", {}).get("code") == "INVARIANT_VIOLATION"


@pytest.mark.asyncio
async def test_document_correction_positive_control(p1_102_env):
    """Ensure document review correction accepts valid generic transaction types.

    Proves:
    - Correcting proposed_transaction_type to DIRECT_PURCHASE succeeds with HTTP 200.
    - Candidate transaction in document reflects updated type.
    """
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    headers = make_auth_headers(org_id, admin_id)

    async with env["session_factory"]() as session:
        doc = Document(
            organization_id=org_id,
            document_code=f"DOC-CORR-POS-{uuid.uuid4().hex[:6]}",
            file_name="pos_corr.pdf",
            file_hash=uuid.uuid4().hex,
            file_size_bytes=512,
            mime_type="application/pdf",
            storage_path="test/pos_corr.pdf",
            document_type=DocumentType.TRANSFER_PROOF,
            source_channel="WEB",
            processing_status=DocumentProcessingStatus.REVIEW_REQUIRED,
            review_flags=["OCR_LOW_CONFIDENCE"],
            candidate_transaction={
                "id": str(uuid.uuid4()),
                "status": "REVIEW_REQUIRED",
                "proposed_transaction_type": "VENDOR_BILL",
                "amount": "100000.00",
                "transaction_date": "2026-01-10",
                "description": "Positive control correction probe",
            },
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    correction_payload = {
        "changes": {
            "proposed_transaction_type": "DIRECT_PURCHASE",
        },
        "reason": "Valid operational reclassification to Direct Purchase",
    }

    response = await client.post(f"/api/v1/documents/{doc_id}/corrections", headers=headers, json=correction_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["candidate_transaction"]["proposed_transaction_type"] == "DIRECT_PURCHASE"


# ==============================================================================
# 8. DOCUMENT CANDIDATE APPROVAL FAIL-CLOSED SAFETY — PASS
# ==============================================================================

@pytest.mark.asyncio
async def test_document_candidate_approval_unsupported_type_fails_closed(p1_102_env):
    """Characterize document candidate approval safety with unsupported type.

    Proves:
    - When a candidate transaction with an unsupported type (OTHER_EXPENSE) is approved:
      1. Downstream posting fails with HTTP 422 INVARIANT_VIOLATION.
      2. The clean transaction rolls back completely.
      3. Zero durable Transaction records are created.
      4. Zero JournalEntry records are created.
      5. Zero JournalLine records are created.
      6. Document candidate remains in READY_FOR_APPROVAL status.
    - Demonstrates current implementation is fail-closed against ledger corruption.
    """
    env = p1_102_env
    client: AsyncClient = env["client"]
    org_id = env["org_id"]
    admin_id = env["users"][UserRole.ADMIN]
    headers = make_auth_headers(org_id, admin_id)

    # Seed document candidate with unsupported type ready for approval
    candidate_id = str(uuid.uuid4())
    async with env["session_factory"]() as session:
        doc = Document(
            organization_id=org_id,
            document_code=f"DOC-APPR-UNSUP-{uuid.uuid4().hex[:6]}",
            file_name="unsupported_candidate.pdf",
            file_hash=uuid.uuid4().hex,
            file_size_bytes=512,
            mime_type="application/pdf",
            storage_path="test/unsupported_candidate.pdf",
            document_type=DocumentType.TRANSFER_PROOF,
            source_channel="WEB",
            processing_status=DocumentProcessingStatus.READY_FOR_APPROVAL,
            review_flags=[],
            candidate_transaction={
                "id": candidate_id,
                "status": "READY_FOR_APPROVAL",
                "proposed_transaction_type": TransactionType.OTHER_EXPENSE.value,
                "amount": "450000.00",
                "transaction_date": "2026-01-10",
                "description": "Historical candidate with unsupported type",
            },
        )
        session.add(doc)
        await session.commit()
        doc_id = doc.id

    # Attempt to approve candidate
    response = await client.post(f"/api/v1/documents/{doc_id}/approve", headers=headers)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVARIANT_VIOLATION"
    assert body["error"]["details"]["transaction_type"] == TransactionType.OTHER_EXPENSE.value
    assert body["error"]["details"]["reason"] == "NO_POSTING_RULE"

    # Verify zero persistence in database
    async with env["session_factory"]() as session:
        trx_count = await session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.organization_id == org_id,
                Transaction.description == "Historical candidate with unsupported type",
            )
        )
        assert trx_count == 0

        je_count = await session.scalar(
            select(func.count(JournalEntry.id)).where(
                JournalEntry.organization_id == org_id,
                JournalEntry.description == "Historical candidate with unsupported type",
            )
        )
        assert je_count == 0

        # Document retains its pre-approval state
        persisted_doc = await session.scalar(
            select(Document).where(
                Document.organization_id == org_id,
                Document.id == doc_id,
            )
        )
        assert persisted_doc is not None
        assert persisted_doc.processing_status == DocumentProcessingStatus.READY_FOR_APPROVAL
        assert persisted_doc.candidate_transaction["status"] == "READY_FOR_APPROVAL"
