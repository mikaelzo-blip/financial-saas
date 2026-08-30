from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.enums import ProjectStatus, TransactionType, CostCategory, WorkflowStatus
from src.schemas.transaction import TransactionCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.services.accounting_engine import AccountingEngine
from src.services.reversal_service import ReversalService
from src.services.balance_service import BalanceService


@pytest.mark.asyncio
async def test_three_step_correction_pattern(db_session: AsyncSession):
    """
    Test 3-Step Correction Flow:
    1. Step 1 (Original): Post Direct Purchase for Rp 50.000.000 (Incorrectly recorded)
    2. Step 2 (Reversal): Reverse original transaction -> Offsets trial balance back to 0 net effect.
    3. Step 3 (Correcting): Post correct transaction for Rp 40.000.000.
    4. Verify final Net Balance matches exactly the Correcting transaction (Rp 40.000.000).
    5. Verify Audit Trail and Relationships.
    """
    org = Organization(slug="org-reversal-flow", legal_name="Org Reversal Flow")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    customer = Counterparty(organization_id=org.id, name="PT Pemberi Tugas", is_customer=True)
    db_session.add(customer)
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-2026-401",
        project_name="Pabrik Semen",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add(project)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    engine = AccountingEngine(db_session)
    rev_svc = ReversalService(db_session)
    balance_svc = BalanceService(db_session)

    # Initial Capital: Rp 100.000.000
    t_cap = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.OWNER_CONTRIBUTION,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("100000000.00"),
            description="Setoran Modal Awal"
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_cap.id)
    await db_session.commit()

    # Step 1: Post Incorrect Original Transaction: Rp 50.000.000
    t_orig = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("50000000.00"),
            description="Pembelian Salah Nominal (Rp 50jt padahal 40jt)",
            project_id=project.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_orig.id)
    await db_session.commit()

    tb1 = await balance_svc.get_trial_balance(org.id)
    b1 = {r["account_code"]: r["net_balance"] for r in tb1["accounts"]}
    assert b1["5101"] == Decimal("50000000.00")
    assert b1["1101"] == Decimal("50000000.00")  # 100M - 50M

    # Step 2: Reversal Transaction: Inverts the original transaction
    rev_trx, rev_je = await rev_svc.reverse_transaction(
        organization_id=org.id,
        original_transaction_id=t_orig.id,
        reason="Koreksi salah input nominal (seharusnya Rp 40jt)"
    )
    await db_session.commit()

    assert rev_trx.workflow_status == WorkflowStatus.POSTED
    assert rev_trx.reversal_of_id == t_orig.id

    # Check Trial Balance after Reversal: Net project expense is back to 0.00, Cash back to 100M
    tb2 = await balance_svc.get_trial_balance(org.id)
    b2 = {r["account_code"]: r["net_balance"] for r in tb2["accounts"]}
    assert b2["5101"] == Decimal("0.00")
    assert b2["1101"] == Decimal("100000000.00")

    # Step 3: Correcting Transaction: Rp 40.000.000
    t_corr = await trx_svc.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("40000000.00"),
            description="Pembelian Benar (Koreksi dari TRX sebelumnya)",
            project_id=project.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()
    await engine.post_transaction(org.id, t_corr.id)
    await db_session.commit()

    # Final Balance Verification:
    tb3 = await balance_svc.get_trial_balance(org.id)
    b3 = {r["account_code"]: r["net_balance"] for r in tb3["accounts"]}
    assert b3["5101"] == Decimal("40000000.00")   # Exactly correct expense
    assert b3["1101"] == Decimal("60000000.00")   # Cash 100M - 40M
    assert b3["3101"] == Decimal("100000000.00")  # Modal
