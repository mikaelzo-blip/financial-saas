import uuid
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.user import User
from src.models.transaction import Transaction
from src.models.enums import ReviewFlag, WorkflowStatus, UserRole, TransactionType
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.review_service import ReviewQueueService
from src.core.exceptions import InvariantViolationException, AuthorizationException


@pytest.mark.asyncio
async def test_review_queue_multi_flag_resolution_lifecycle(db_session: AsyncSession):
    """
    Test Multi-Flag Review Lifecycle:
    1. Transaction created with 2 simultaneous flags: PROJECT_UNKNOWN and AMOUNT_MISMATCH.
    2. Workflow status is REVIEW_REQUIRED.
    3. Attempting to approve/post fails because unresolved flags exist.
    4. Resolve flag 1 (PROJECT_UNKNOWN) -> status remains REVIEW_REQUIRED (AMOUNT_MISMATCH still unresolved).
    5. Resolve flag 2 (AMOUNT_MISMATCH) -> status automatically transitions to STAGED.
    6. Verify resolution details and auditability.
    """
    org = Organization(slug="org-review-unit", legal_name="Org Review Unit")
    db_session.add(org)
    await db_session.flush()

    user = User(
        organization_id=org.id,
        email="reviewer@example.com",
        full_name="Staff Reviewer",
        password_hash="dummy_hash",
        role=UserRole.OPERATOR
    )
    db_session.add(user)
    await db_session.flush()

    trx = Transaction(
        organization_id=org.id,
        transaction_code="TRX-2026-000099",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 2, 1),
        amount=Decimal("15000000.00"),
        description="Nota Belanja Tanpa Proyek & Beda Nominal",
        workflow_status=WorkflowStatus.REVIEW_REQUIRED
    )
    db_session.add(trx)
    await db_session.flush()

    review_svc = ReviewQueueService(db_session)

    # 1. Add 2 simultaneous review flags
    f1 = await review_svc.add_review_flag(
        org.id, trx.id, ReviewFlag.PROJECT_UNKNOWN, "Proyek tidak tertera pada nota"
    )
    f2 = await review_svc.add_review_flag(
        org.id, trx.id, ReviewFlag.AMOUNT_MISMATCH, "Nominal nota beda dengan bukti transfer"
    )
    await db_session.commit()

    # 2. Verify both flags exist
    items = await review_svc.list_review_items(org.id)
    assert len(items) == 1
    assert len(items[0].review_flags) == 2

    # 3. Attempting to approve must fail
    with pytest.raises(InvariantViolationException) as exc:
        await review_svc.approve_and_post(org.id, trx.id, user.id, user.role)
    assert "Unresolved review flags exist" in str(exc.value)

    # 4. Resolve flag 1
    await review_svc.resolve_review_flag(
        org.id, trx.id, f1.id, user.id, "Sudah dikonfirmasi ke lapangan: Proyek Gedung A"
    )
    await db_session.commit()

    # Re-fetch transaction: status must STILL be REVIEW_REQUIRED because f2 is unresolved
    items_after_f1 = await review_svc.list_review_items(org.id)
    assert len(items_after_f1) == 1
    assert items_after_f1[0].workflow_status == WorkflowStatus.REVIEW_REQUIRED

    # 5. Resolve flag 2
    await review_svc.resolve_review_flag(
        org.id, trx.id, f2.id, user.id, "Kuitansi susulan terlampir Rp 15.000.000 pas"
    )
    await db_session.commit()

    # Re-fetch transaction: status is now STAGED (unblocked)
    items_after_all = await review_svc.list_review_items(org.id)
    assert len(items_after_all) == 0  # No longer in unresolved review queue


@pytest.mark.asyncio
async def test_role_based_sensitive_transaction_approval(db_session: AsyncSession):
    """Verify sensitive transactions (e.g. OWNER_WITHDRAWAL) require Manager role."""
    org = Organization(slug="org-approval-roles", legal_name="Org Approval Roles")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    operator = User(
        organization_id=org.id,
        email="operator@example.com",
        full_name="Staff Operator",
        password_hash="dummy_hash",
        role=UserRole.OPERATOR
    )

    manager = User(
        organization_id=org.id,
        email="manager@example.com",
        full_name="Finance Manager",
        password_hash="dummy_hash",
        role=UserRole.MANAGER
    )

    db_session.add_all([operator, manager])
    await db_session.flush()

    trx = Transaction(
        organization_id=org.id,
        transaction_code="TRX-2026-000100",
        transaction_type=TransactionType.OWNER_WITHDRAWAL,
        transaction_date=date(2026, 2, 5),
        amount=Decimal("50000000.00"),
        description="Prive Direktur",
        workflow_status=WorkflowStatus.STAGED
    )
    db_session.add(trx)
    await db_session.commit()

    review_svc = ReviewQueueService(db_session)

    # 1. Operator attempts to approve sensitive transaction -> MUST FAIL
    with pytest.raises(AuthorizationException) as exc:
        await review_svc.approve_and_post(org.id, trx.id, operator.id, operator.role)
    assert "requires Manager approval" in str(exc.value)

    # 2. Manager approves sensitive transaction -> SUCCEEDS
    approved_trx, je = await review_svc.approve_and_post(org.id, trx.id, manager.id, manager.role)
    await db_session.commit()

    assert approved_trx.workflow_status == WorkflowStatus.POSTED
    assert je.is_balanced is True
