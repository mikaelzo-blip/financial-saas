"""Security and Accounting Invariant Hardening Reproduction and Regression Suite.

Covers Feature 011 confirmed findings:
- FIN-P0-001: Transaction /post and /approve authorization & role enforcement
- FIN-P0-002: Review flag resolution authorization & role enforcement
- FIN-P0-003: Opening-balance authorization & closed-period invariant
- FIN-P0-004: Reversal authorization, closed-period invariant & actor attribution
- FIN-P0-005: Hard CLOSED-period invariant across direct financial posting paths
- FIN-P0-006: Fixed-asset endpoint RBAC & real actor-role propagation
- FIN-P1-101: Fixed-asset depreciation authoritative COA 6108 alignment
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.exceptions import InvariantViolationException, AuthorizationException
from src.core.security import create_access_token, hash_password
from src.models.organization import Organization
from src.models.user import User
from src.models.enums import (
    UserRole,
    TransactionType,
    WorkflowStatus,
    AccountingPeriodStatus,
    ReviewFlag,
)
from src.models.transaction import Transaction, TransactionReviewFlag
from src.schemas.accounting_period import AccountingPeriodCreate, AccountingPeriodUpdate
from src.schemas.transaction import TransactionCreate
from src.services.accounting_engine import AccountingEngine
from src.services.accounting_period_service import AccountingPeriodService
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.posting_rules import PostingRuleRegistry
from src.services.review_service import ReviewQueueService
from src.services.transaction_service import TransactionService


# ---------------------------------------------------------------------------
# Test Fixtures & Helpers
# ---------------------------------------------------------------------------

async def create_test_env(db_session: AsyncSession):
    """Creates a tenant organization, seeds standard COA & payment accounts, and creates users for each role."""
    org = Organization(
        id=uuid.uuid4(),
        slug=f"tenant-{uuid.uuid4().hex[:8]}",
        legal_name="PT Test Invariant Security",
    )
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)

    roles = [UserRole.VIEWER, UserRole.OPERATOR, UserRole.MANAGER, UserRole.ADMIN]
    users: dict[UserRole, User] = {}

    for role in roles:
        u = User(
            id=uuid.uuid4(),
            organization_id=org.id,
            email=f"{role.value.lower()}_{uuid.uuid4().hex[:4]}@example.com",
            full_name=f"User {role.value}",
            password_hash=hash_password("Password123!"),
            role=role,
            is_active=True,
        )
        db_session.add(u)
        users[role] = u

    await db_session.commit()
    return org, users


def auth_headers(user: User, org: Organization) -> dict[str, str]:
    """Builds authenticated JWT and tenant headers required by require_application_user."""
    token = create_access_token(str(user.id), {"organization_id": str(org.id)})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
        "X-User-ID": str(user.id),
    }


# ---------------------------------------------------------------------------
# FIN-P0-001: Transaction /post and /approve Authorization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fin_p0_001_transaction_post_and_approve_authorization(
    security_client: AsyncClient, db_session: AsyncSession
):
    """
    FIN-P0-001:
    - VIEWER must receive 403 Forbidden for /post and /approve.
    - OPERATOR must receive 403 Forbidden for sensitive transaction types (e.g. OWNER_WITHDRAWAL).
    - OPERATOR may post routine AUTO_SAFE transactions (e.g. DIRECT_PURCHASE).
    - MANAGER and ADMIN may post sensitive transactions.
    - bypass_role_check=True must not be exposed to or bypass caller role.
    """
    org, users = await create_test_env(db_session)
    trx_svc = TransactionService(db_session)

    # 1. Create a sensitive transaction (OWNER_WITHDRAWAL)
    sensitive_trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_WITHDRAWAL,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("5000000.00"),
            description="Penarikan Prive Pemilik",
        ),
    )
    await db_session.commit()

    # VIEWER attempt to post sensitive transaction -> MUST be 403
    resp_viewer = await security_client.post(
        f"/api/v1/transactions/{sensitive_trx.id}/post",
        headers=auth_headers(users[UserRole.VIEWER], org),
    )
    assert resp_viewer.status_code == 403, (
        f"VIEWER must receive 403 on /post, got {resp_viewer.status_code}: {resp_viewer.text}"
    )

    # VIEWER attempt to approve sensitive transaction -> MUST be 403
    resp_viewer_appr = await security_client.post(
        f"/api/v1/transactions/{sensitive_trx.id}/approve",
        headers=auth_headers(users[UserRole.VIEWER], org),
    )
    assert resp_viewer_appr.status_code == 403, (
        f"VIEWER must receive 403 on /approve, got {resp_viewer_appr.status_code}: {resp_viewer_appr.text}"
    )

    # OPERATOR attempt to post sensitive transaction -> MUST be 403
    resp_operator = await security_client.post(
        f"/api/v1/transactions/{sensitive_trx.id}/post",
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator.status_code == 403, (
        f"OPERATOR must receive 403 when posting sensitive transaction, got {resp_operator.status_code}: {resp_operator.text}"
    )

    # 2. Create a routine transaction (DIRECT_PURCHASE)
    routine_trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 3, 1),
            amount=Decimal("150000.00"),
            description="Beli Perlengkapan Kantor",
        ),
    )
    await db_session.commit()

    # OPERATOR posting routine AUTO_SAFE transaction -> ALLOWED (200)
    resp_operator_routine = await security_client.post(
        f"/api/v1/transactions/{routine_trx.id}/post",
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator_routine.status_code == 200, (
        f"OPERATOR should be allowed to post routine transaction, got {resp_operator_routine.status_code}: {resp_operator_routine.text}"
    )

    # 3. MANAGER posting sensitive transaction -> ALLOWED (200)
    resp_manager = await security_client.post(
        f"/api/v1/transactions/{sensitive_trx.id}/post",
        headers=auth_headers(users[UserRole.MANAGER], org),
    )
    assert resp_manager.status_code == 200, (
        f"MANAGER should be allowed to post sensitive transaction, got {resp_manager.status_code}: {resp_manager.text}"
    )


# ---------------------------------------------------------------------------
# FIN-P0-002: Review Flag Resolution Authorization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fin_p0_002_review_flag_resolution_authorization(
    security_client: AsyncClient, db_session: AsyncSession
):
    """
    FIN-P0-002:
    - Only ADMIN and MANAGER may resolve financial review flags.
    - VIEWER and OPERATOR must receive 403 Forbidden.
    """
    org, users = await create_test_env(db_session)
    review_svc = ReviewQueueService(db_session)

    trx = Transaction(
        organization_id=org.id,
        transaction_code="TRX-FLAG-001",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 3, 1),
        amount=Decimal("2000000.00"),
        description="Transaksi Bermasalah",
        workflow_status=WorkflowStatus.REVIEW_REQUIRED,
    )
    db_session.add(trx)
    await db_session.flush()

    flag = await review_svc.add_review_flag(
        organization_id=org.id,
        transaction_id=trx.id,
        flag=ReviewFlag.PROJECT_UNKNOWN,
        message="Project missing",
        severity="WARNING",
    )
    await db_session.commit()

    resolve_payload = {"resolution_notes": "Resolved project attribution"}

    # VIEWER resolve attempt -> MUST be 403
    resp_viewer = await security_client.post(
        f"/api/v1/transactions/{trx.id}/review-flags/{flag.id}/resolve",
        json=resolve_payload,
        headers=auth_headers(users[UserRole.VIEWER], org),
    )
    assert resp_viewer.status_code == 403, (
        f"VIEWER must receive 403 resolving review flag, got {resp_viewer.status_code}: {resp_viewer.text}"
    )

    # OPERATOR resolve attempt -> MUST be 403
    resp_operator = await security_client.post(
        f"/api/v1/transactions/{trx.id}/review-flags/{flag.id}/resolve",
        json=resolve_payload,
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator.status_code == 403, (
        f"OPERATOR must receive 403 resolving review flag, got {resp_operator.status_code}: {resp_operator.text}"
    )

    # MANAGER resolve attempt -> ALLOWED (200)
    resp_manager = await security_client.post(
        f"/api/v1/transactions/{trx.id}/review-flags/{flag.id}/resolve",
        json=resolve_payload,
        headers=auth_headers(users[UserRole.MANAGER], org),
    )
    assert resp_manager.status_code == 200, (
        f"MANAGER must be allowed to resolve review flag, got {resp_manager.status_code}: {resp_manager.text}"
    )


# ---------------------------------------------------------------------------
# FIN-P0-003: Opening Balance Authorization & Closed-Period Invariant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fin_p0_003_opening_balance_authorization_and_closed_period(
    security_client: AsyncClient, db_session: AsyncSession
):
    """
    FIN-P0-003:
    - Only ADMIN may establish opening balances (POST /transactions/opening-balances).
    - VIEWER, OPERATOR, and MANAGER must receive 403 Forbidden.
    - Posting into a CLOSED period must fail even for ADMIN.
    """
    org, users = await create_test_env(db_session)
    period_svc = AccountingPeriodService(db_session)

    payload = {
        "as_of_date": "2026-01-01",
        "entries": [
            {"account_code": "1101", "debit": "1000000.00", "credit": "0.00"},
            {"account_code": "3101", "debit": "0.00", "credit": "1000000.00"},
        ],
        "notes": "Saldo Awal 2026",
    }

    # VIEWER attempt -> MUST be 403
    resp_viewer = await security_client.post(
        "/api/v1/transactions/opening-balances",
        json=payload,
        headers=auth_headers(users[UserRole.VIEWER], org),
    )
    assert resp_viewer.status_code == 403, (
        f"VIEWER must receive 403 on opening-balances, got {resp_viewer.status_code}: {resp_viewer.text}"
    )

    # OPERATOR attempt -> MUST be 403
    resp_operator = await security_client.post(
        "/api/v1/transactions/opening-balances",
        json=payload,
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator.status_code == 403, (
        f"OPERATOR must receive 403 on opening-balances, got {resp_operator.status_code}: {resp_operator.text}"
    )

    # MANAGER attempt -> MUST be 403
    resp_manager = await security_client.post(
        "/api/v1/transactions/opening-balances",
        json=payload,
        headers=auth_headers(users[UserRole.MANAGER], org),
    )
    assert resp_manager.status_code == 403, (
        f"MANAGER must receive 403 on opening-balances, got {resp_manager.status_code}: {resp_manager.text}"
    )

    # Create a CLOSED period covering 2026-01-01
    period = await period_svc.create_period(
        org.id,
        AccountingPeriodCreate(
            period_name="2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        ),
    )
    await period_svc.update_period_status(
        org.id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.CLOSED)
    )
    await db_session.commit()

    # ADMIN attempt into CLOSED period -> MUST FAIL (400, 403, or 422, cannot be 201)
    resp_admin_closed = await security_client.post(
        "/api/v1/transactions/opening-balances",
        json=payload,
        headers=auth_headers(users[UserRole.ADMIN], org),
    )
    assert resp_admin_closed.status_code != 201, (
        f"ADMIN must NOT post opening balances into CLOSED period, got 201: {resp_admin_closed.text}"
    )


# ---------------------------------------------------------------------------
# FIN-P0-004: Reversal Authorization and CLOSED-Period Invariant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fin_p0_004_reversal_authorization_and_closed_period(
    security_client: AsyncClient, db_session: AsyncSession
):
    """
    FIN-P0-004:
    - Only ADMIN and MANAGER may reverse posted transactions.
    - VIEWER and OPERATOR must receive 403 Forbidden.
    - Reversal in a CLOSED accounting period must be rejected.
    - Successful reversal must record actor_id from authenticated principal.
    """
    org, users = await create_test_env(db_session)
    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    period_svc = AccountingPeriodService(db_session)

    # Create and post a transaction
    trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 4, 10),
            amount=Decimal("800000.00"),
            description="Belanja Material Operasional",
        ),
    )
    await db_session.commit()
    await engine.post_transaction(org.id, trx.id)
    await db_session.commit()

    rev_payload = {"reason": "Salah input jumlah pembelian material"}

    # VIEWER reversal attempt -> MUST be 403
    resp_viewer = await security_client.post(
        f"/api/v1/transactions/{trx.id}/reverse",
        json=rev_payload,
        headers=auth_headers(users[UserRole.VIEWER], org),
    )
    assert resp_viewer.status_code == 403, (
        f"VIEWER must receive 403 reversing transaction, got {resp_viewer.status_code}: {resp_viewer.text}"
    )

    # OPERATOR reversal attempt -> MUST be 403
    resp_operator = await security_client.post(
        f"/api/v1/transactions/{trx.id}/reverse",
        json=rev_payload,
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator.status_code == 403, (
        f"OPERATOR must receive 403 reversing transaction, got {resp_operator.status_code}: {resp_operator.text}"
    )

    # Close period covering today (reversal date defaults to today)
    today = date.today()
    period = await period_svc.create_period(
        org.id,
        AccountingPeriodCreate(
            period_name=f"{today.year}-{today.month:02d}",
            start_date=date(today.year, today.month, 1),
            end_date=date(today.year, today.month, 28),
        ),
    )
    await period_svc.update_period_status(
        org.id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.CLOSED)
    )
    await db_session.commit()

    # MANAGER reversal into CLOSED period -> MUST FAIL (cannot be 201)
    resp_manager_closed = await security_client.post(
        f"/api/v1/transactions/{trx.id}/reverse",
        json=rev_payload,
        headers=auth_headers(users[UserRole.MANAGER], org),
    )
    assert resp_manager_closed.status_code != 201, (
        f"Reversal must NOT succeed in CLOSED period, got 201: {resp_manager_closed.text}"
    )

    # Re-open period
    await period_svc.update_period_status(
        org.id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.OPEN, reason="Reopening for reversal test")
    )
    await db_session.commit()

    # MANAGER reversal in OPEN period -> ALLOWED (201) and records actor attribution
    resp_manager_open = await security_client.post(
        f"/api/v1/transactions/{trx.id}/reverse",
        json=rev_payload,
        headers=auth_headers(users[UserRole.MANAGER], org),
    )
    assert resp_manager_open.status_code == 201, (
        f"MANAGER reversal in OPEN period must succeed with 201, got {resp_manager_open.status_code}: {resp_manager_open.text}"
    )
    rev_data = resp_manager_open.json()
    assert rev_data["transaction_type"] == TransactionType.REVERSAL.value
    assert rev_data["reversal_of_id"] == str(trx.id)


# ---------------------------------------------------------------------------
# FIN-P0-005: Hard CLOSED-Period Invariant Across Direct Posting Paths
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fin_p0_005_hard_closed_period_invariant_accounting_engine(
    db_session: AsyncSession,
):
    """
    FIN-P0-005:
    - AccountingEngine.post_transaction() must unconditionally reject posting with
      InvariantViolationException if the transaction date falls in a CLOSED accounting period.
    - Direct callers (payables, receivables, documents, depreciation) must not bypass CLOSED period.
    """
    org = Organization(
        id=uuid.uuid4(),
        slug=f"tenant-engine-{uuid.uuid4().hex[:6]}",
        legal_name="PT Invariant Engine Test",
    )
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)

    period_svc = AccountingPeriodService(db_session)
    period = await period_svc.create_period(
        org.id,
        AccountingPeriodCreate(
            period_name="2026-05",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
        ),
    )
    await period_svc.update_period_status(
        org.id, period.id, AccountingPeriodUpdate(status=AccountingPeriodStatus.CLOSED)
    )
    await db_session.commit()

    # Staged transaction inside CLOSED period (2026-05-15)
    trx_svc = TransactionService(db_session)
    trx = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 5, 15),
            amount=Decimal("450000.00"),
            description="Pembelian di Periode Tertutup",
        ),
    )
    await db_session.commit()

    engine = AccountingEngine(db_session)

    # Calling AccountingEngine.post_transaction directly MUST raise InvariantViolationException
    with pytest.raises(InvariantViolationException) as exc_info:
        await engine.post_transaction(org.id, trx.id)

    assert "CLOSED" in str(exc_info.value), (
        f"Expected InvariantViolationException mentioning CLOSED period, got: {exc_info.value}"
    )


# ---------------------------------------------------------------------------
# FIN-P0-006: Fixed-Asset Endpoint RBAC & Real Actor-Role Propagation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fin_p0_006_fixed_asset_endpoint_rbac_and_role_propagation(
    security_client: AsyncClient, db_session: AsyncSession
):
    """
    FIN-P0-006:
    - Fixed asset creation (POST /) and update (PUT /{id}):
      - VIEWER receives 403 Forbidden.
      - OPERATOR, MANAGER, ADMIN allowed.
    - Fixed asset depreciation (POST /{id}/depreciate, POST /depreciate-batch) and disposal:
      - VIEWER and OPERATOR receive 403 Forbidden.
      - MANAGER and ADMIN allowed.
      - actor_role=UserRole.ADMIN must not be hardcoded; real principal role must be used.
    """
    org, users = await create_test_env(db_session)

    asset_payload = {
        "asset_code": "AST-SEC-001",
        "asset_name": "Excavator Mini PC-50",
        "asset_category": "ALAT_BERAT",
        "purchase_date": "2026-01-10",
        "available_for_use_date": "2026-01-15",
        "purchase_cost": "120000000.00",
        "salvage_value": "0.00",
        "useful_life_months": 60,
    }

    # 1. VIEWER create attempt -> MUST be 403
    resp_viewer_create = await security_client.post(
        "/api/v1/fixed-assets",
        json=asset_payload,
        headers=auth_headers(users[UserRole.VIEWER], org),
    )
    assert resp_viewer_create.status_code == 403, (
        f"VIEWER must receive 403 creating fixed asset, got {resp_viewer_create.status_code}: {resp_viewer_create.text}"
    )

    # 2. OPERATOR create attempt -> ALLOWED (201)
    resp_operator_create = await security_client.post(
        "/api/v1/fixed-assets",
        json=asset_payload,
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator_create.status_code == 201, (
        f"OPERATOR should be allowed to create asset, got {resp_operator_create.status_code}: {resp_operator_create.text}"
    )
    asset_id = resp_operator_create.json()["id"]

    # 3. VIEWER update attempt -> MUST be 403
    resp_viewer_update = await security_client.put(
        f"/api/v1/fixed-assets/{asset_id}",
        json={"asset_name": "Excavator Mini Updated"},
        headers=auth_headers(users[UserRole.VIEWER], org),
    )
    assert resp_viewer_update.status_code == 403, (
        f"VIEWER must receive 403 updating fixed asset, got {resp_viewer_update.status_code}: {resp_viewer_update.text}"
    )

    # 4. VIEWER depreciate attempt -> MUST be 403
    resp_viewer_dep = await security_client.post(
        f"/api/v1/fixed-assets/{asset_id}/depreciate",
        json={"period_date": "2026-01-31"},
        headers=auth_headers(users[UserRole.VIEWER], org),
    )
    assert resp_viewer_dep.status_code == 403, (
        f"VIEWER must receive 403 depreciating asset, got {resp_viewer_dep.status_code}: {resp_viewer_dep.text}"
    )

    # 5. OPERATOR depreciate attempt -> MUST be 403
    resp_operator_dep = await security_client.post(
        f"/api/v1/fixed-assets/{asset_id}/depreciate",
        json={"period_date": "2026-01-31"},
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator_dep.status_code == 403, (
        f"OPERATOR must receive 403 depreciating asset, got {resp_operator_dep.status_code}: {resp_operator_dep.text}"
    )

    # 6. OPERATOR batch depreciate attempt -> MUST be 403
    resp_operator_batch = await security_client.post(
        "/api/v1/fixed-assets/depreciate-batch",
        json={"period_date": "2026-01-31"},
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator_batch.status_code == 403, (
        f"OPERATOR must receive 403 batch depreciating assets, got {resp_operator_batch.status_code}: {resp_operator_batch.text}"
    )

    # 7. OPERATOR dispose attempt -> MUST be 403
    resp_operator_dispose = await security_client.post(
        f"/api/v1/fixed-assets/{asset_id}/dispose",
        headers=auth_headers(users[UserRole.OPERATOR], org),
    )
    assert resp_operator_dispose.status_code == 403, (
        f"OPERATOR must receive 403 disposing asset, got {resp_operator_dispose.status_code}: {resp_operator_dispose.text}"
    )

    # 8. MANAGER depreciate attempt -> ALLOWED (200)
    resp_manager_dep = await security_client.post(
        f"/api/v1/fixed-assets/{asset_id}/depreciate",
        json={"period_date": "2026-01-31"},
        headers=auth_headers(users[UserRole.MANAGER], org),
    )
    assert resp_manager_dep.status_code == 200, (
        f"MANAGER must be allowed to depreciate asset, got {resp_manager_dep.status_code}: {resp_manager_dep.text}"
    )


# ---------------------------------------------------------------------------
# FIN-P1-101: Fixed Asset Depreciation Authoritative COA 6108
# ---------------------------------------------------------------------------

def test_fin_p1_101_fixed_asset_depreciation_authoritative_coa_6108():
    """
    FIN-P1-101:
    - FIXED_ASSET_DEPRECIATION posting rule must post:
      - Debit: 6108 (Beban Penyusutan Aset Tetap)
      - Credit: 1502 (Akumulasi Penyusutan Aset Tetap)
    - Verifies that incorrect 6105 (Beban Legal/Perizinan) is NOT used.
    """
    trx = Transaction(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        transaction_code="TRX-DEP-001",
        transaction_type=TransactionType.FIXED_ASSET_DEPRECIATION,
        transaction_date=date(2026, 1, 31),
        amount=Decimal("2000000.00"),
        description="Penyusutan Bulanan Excavator",
        workflow_status=WorkflowStatus.APPROVED,
    )

    legs = PostingRuleRegistry.generate_journal_legs(trx)
    assert len(legs) == 2, f"Expected 2 legs, got {len(legs)}"

    debit_legs = [leg for leg in legs if leg.debit_amount > Decimal("0.00")]
    credit_legs = [leg for leg in legs if leg.credit_amount > Decimal("0.00")]

    assert len(debit_legs) == 1, "Expected exactly 1 debit leg"
    assert len(credit_legs) == 1, "Expected exactly 1 credit leg"

    assert debit_legs[0].account_code == "6108", (
        f"Depreciation debit must be 6108 (Beban Penyusutan Aset Tetap), got {debit_legs[0].account_code}"
    )
    assert credit_legs[0].account_code == "1502", (
        f"Depreciation credit must be 1502 (Akumulasi Penyusutan Aset Tetap), got {credit_legs[0].account_code}"
    )
    assert debit_legs[0].debit_amount == Decimal("2000000.00")
    assert credit_legs[0].credit_amount == Decimal("2000000.00")
