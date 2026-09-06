import pytest
import uuid
from datetime import date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.user import User, UserRole
from src.models.fixed_asset import FixedAsset, FixedAssetDepreciation
from src.models.transaction import Transaction
from src.models.enums import AssetStatus, DepreciationMethod, TransactionType, WorkflowStatus
from src.schemas.fixed_asset import FixedAssetCreate, FixedAssetUpdate
from src.services.fixed_asset_service import FixedAssetService
from src.services.coa_seeder import seed_standard_coa
from src.services.accounting_period_service import AccountingPeriodService
from src.schemas.accounting_period import AccountingPeriodCreate, AccountingPeriodUpdate
from src.services.accounting_engine import AccountingEngine
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.pl_service import ProfitLossService
from src.core.exceptions import InvariantViolationException


def test_category_default_useful_life():
    assert FixedAssetService.get_category_default_useful_life("Laptop") == 48
    assert FixedAssetService.get_category_default_useful_life("Computer") == 48
    assert FixedAssetService.get_category_default_useful_life("Komputer") == 48
    assert FixedAssetService.get_category_default_useful_life("Office Equipment") == 48
    assert FixedAssetService.get_category_default_useful_life("Peralatan Proyek") == 48
    assert FixedAssetService.get_category_default_useful_life("Alat Berat") == 96
    assert FixedAssetService.get_category_default_useful_life("Heavy Equipment") == 96
    assert FixedAssetService.get_category_default_useful_life("Vehicle") == 96
    assert FixedAssetService.get_category_default_useful_life("Kendaraan") == 96
    assert FixedAssetService.get_category_default_useful_life("Building") == 240
    assert FixedAssetService.get_category_default_useful_life("Bangunan") == 240


def test_capitalization_guidance():
    # >= 5,000,000 and > 12 months -> FIXED_ASSET_CANDIDATE
    res1 = FixedAssetService.get_capitalization_guidance(Decimal("15000000.00"), benefit_months=36)
    assert res1.qualifies_as_fixed_asset is True
    assert res1.recommendation == "FIXED_ASSET_CANDIDATE"

    # < 5,000,000 -> EXPENSE_DEFAULT
    res2 = FixedAssetService.get_capitalization_guidance(Decimal("1200000.00"), benefit_months=24)
    assert res2.qualifies_as_fixed_asset is False
    assert res2.recommendation == "EXPENSE_DEFAULT"

    # >= 5,000,000 but <= 12 months -> REVIEW_REQUIRED
    res3 = FixedAssetService.get_capitalization_guidance(Decimal("8000000.00"), benefit_months=10)
    assert res3.qualifies_as_fixed_asset is False
    assert res3.recommendation == "REVIEW_REQUIRED"


def test_straight_line_formula_and_available_date():
    asset = FixedAsset(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        asset_code="AST-001",
        asset_name="Excavator Mini",
        asset_category="ALAT_BERAT",
        purchase_date=date(2026, 1, 1),
        available_for_use_date=date(2026, 3, 1),  # available in March
        purchase_cost=Decimal("96000000.00"),
        salvage_value=Decimal("0.00"),
        useful_life_months=96,
        accumulated_depreciation=Decimal("0.00"),
        status=AssetStatus.ACTIVE
    )
    service = FixedAssetService(None)

    # Monthly rate: 96,000,000 / 96 = 1,000,000 / month
    assert asset.monthly_depreciation_rate == Decimal("1000000.00")
    assert asset.depreciable_amount == Decimal("96000000.00")
    assert asset.net_book_value == Decimal("96000000.00")

    # Before available_for_use_date -> 0
    dep_feb = service.calculate_depreciation_amount(asset, date(2026, 2, 28))
    assert dep_feb == Decimal("0.00")

    # On/after available_for_use_date -> 1,000,000
    dep_mar = service.calculate_depreciation_amount(asset, date(2026, 3, 31))
    assert dep_mar == Decimal("1000000.00")

    # Near end of useful life (remaining < monthly rate)
    asset.accumulated_depreciation = Decimal("95500000.00")
    dep_end = service.calculate_depreciation_amount(asset, date(2034, 3, 31))
    assert dep_end == Decimal("500000.00"), "Must not depreciate beyond remaining depreciable amount"

    # Already fully depreciated
    asset.accumulated_depreciation = Decimal("96000000.00")
    dep_zero = service.calculate_depreciation_amount(asset, date(2034, 4, 30))
    assert dep_zero == Decimal("0.00")


@pytest.mark.asyncio
async def test_fixed_asset_posting_and_ledger_invariants(db_session: AsyncSession):
    """
    Integration test:
    1. Create asset via FixedAssetService
    2. Depreciate asset
    3. Assert JournalEntry: Dr 6105, Cr 1502, Total Dr == Total Cr
    4. Assert duplicate depreciation in same month is blocked
    5. Assert balance sheet and P&L reflect depreciation without discrepancy
    """
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        slug=f"asset-test-{uuid.uuid4().hex[:6]}",
        legal_name="PT Aset UAT Konstruksi"
    )
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org_id)

    user = User(
        id=uuid.uuid4(),
        organization_id=org_id,
        email=f"fa.{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        full_name="Asset Admin",
        role=UserRole.ADMIN
    )
    db_session.add(user)
    await db_session.flush()

    service = FixedAssetService(db_session)

    # 1. Create Fixed Asset (Laptop: 24,000,000 / 24 months = 1,000,000 / month)
    asset_data = FixedAssetCreate(
        asset_code="AST-LPT-001",
        asset_name="Laptop Engineer",
        asset_category="COMPUTER",
        purchase_date=date(2026, 1, 10),
        available_for_use_date=date(2026, 1, 15),
        purchase_cost=Decimal("24000000.00"),
        salvage_value=Decimal("0.00"),
        useful_life_months=24
    )
    asset = await service.create_asset(org_id, asset_data, actor_id=user.id)
    assert asset.asset_code == "AST-LPT-001"
    assert asset.net_book_value == Decimal("24000000.00")
    assert asset.status == AssetStatus.ACTIVE

    # 2. Run Depreciation for Jan 2026
    dep_res = await service.depreciate_asset(
        organization_id=org_id,
        asset_id=asset.id,
        period_date=date(2026, 1, 31),
        actor_id=user.id,
        actor_role=user.role
    )
    assert dep_res.depreciation_amount == Decimal("1000000.00")
    assert dep_res.accumulated_depreciation == Decimal("1000000.00")
    assert dep_res.net_book_value == Decimal("23000000.00")
    assert dep_res.journal_entry_number is not None

    # 3. Assert duplicate depreciation in same month is blocked
    with pytest.raises(InvariantViolationException) as exc_dup:
        await service.depreciate_asset(
            organization_id=org_id,
            asset_id=asset.id,
            period_date=date(2026, 1, 31),
            actor_id=user.id,
            actor_role=user.role
        )
    assert "sudah disusutkan" in str(exc_dup.value)

    # 4. Check P&L: Beban Penyusutan (6105) must show 1,000,000
    pnl = await ProfitLossService.get_profit_and_loss(
        session=db_session,
        organization_id=org_id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31)
    )
    assert pnl.operating_expenses_section.subtotal == Decimal("1000000.00")
    assert pnl.net_profit == Decimal("-1000000.00")

    # 5. Check Balance Sheet:
    # Akumulasi Penyusutan (1502) is contra-asset: -1,000,000
    # Fixed Assets subtotal: -1,000,000
    # Equity: Net loss (-1,000,000)
    # Total Assets (-1M) == Total Liab (0) + Total Equity (-1M) -> Balanced!
    bs = await BalanceSheetService.get_balance_sheet(
        session=db_session,
        organization_id=org_id,
        as_of_date=date(2026, 1, 31)
    )
    assert bs.total_assets == Decimal("-1000000.00")
    assert bs.total_liabilities == Decimal("0.00")
    assert bs.total_equity == Decimal("-1000000.00")
    assert bs.is_balanced is True


@pytest.mark.asyncio
async def test_fixed_asset_batch_depreciation_and_period_guards(db_session: AsyncSession):
    """
    Test batch depreciation and period guard controls:
    1. Create two assets available at different times
    2. Run batch depreciation
    3. Block depreciation in CLOSED period
    """
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        slug=f"asset-batch-{uuid.uuid4().hex[:6]}",
        legal_name="PT Batch Aset"
    )
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org_id)

    user = User(
        id=uuid.uuid4(),
        organization_id=org_id,
        email=f"batch.{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        full_name="Batch Officer",
        role=UserRole.ADMIN
    )
    db_session.add(user)
    await db_session.flush()

    service = FixedAssetService(db_session)

    # Asset 1: Ready in Jan (48,000,000 / 48m = 1,000,000/m)
    a1 = await service.create_asset(
        org_id,
        FixedAssetCreate(
            asset_code="AST-B1",
            asset_name="Server Kantor",
            asset_category="COMPUTER",
            purchase_date=date(2026, 1, 1),
            available_for_use_date=date(2026, 1, 5),
            purchase_cost=Decimal("48000000.00"),
            useful_life_months=48
        ),
        actor_id=user.id
    )

    # Asset 2: Ready only in Feb (96,000,000 / 96m = 1,000,000/m)
    a2 = await service.create_asset(
        org_id,
        FixedAssetCreate(
            asset_code="AST-B2",
            asset_name="Pickup Operasional",
            asset_category="VEHICLE",
            purchase_date=date(2026, 1, 10),
            available_for_use_date=date(2026, 2, 1),
            purchase_cost=Decimal("96000000.00"),
            useful_life_months=96
        ),
        actor_id=user.id
    )

    # Batch run for Jan 2026: only Asset 1 should be depreciated
    batch_jan = await service.depreciate_batch(
        organization_id=org_id,
        period_date=date(2026, 1, 31),
        actor_id=user.id,
        actor_role=user.role
    )
    assert batch_jan.total_assets_processed == 1
    assert batch_jan.total_depreciation_amount == Decimal("1000000.00")
    assert batch_jan.results[0].asset_code == "AST-B1"

    # Batch run for Feb 2026: both assets should be depreciated
    batch_feb = await service.depreciate_batch(
        organization_id=org_id,
        period_date=date(2026, 2, 28),
        actor_id=user.id,
        actor_role=user.role
    )
    assert batch_feb.total_assets_processed == 2
    assert batch_feb.total_depreciation_amount == Decimal("2000000.00")

    # Accounting Period Guard: Close period March 2026
    period_srv = AccountingPeriodService(db_session)
    p_mar = await period_srv.create_period(
        org_id,
        AccountingPeriodCreate(
            period_name="2026-03",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31)
        )
    )
    from src.models.enums import AccountingPeriodStatus
    await period_srv.update_period_status(
        org_id,
        p_mar.id,
        AccountingPeriodUpdate(status=AccountingPeriodStatus.CLOSED),
        actor_id=user.id
    )

    # Attempting to depreciate in closed March period must fail
    with pytest.raises(InvariantViolationException) as exc_closed:
        await service.depreciate_asset(
            organization_id=org_id,
            asset_id=a1.id,
            period_date=date(2026, 3, 31),
            actor_id=user.id,
            actor_role=user.role
        )
    assert "DITUTUP" in str(exc_closed.value)


@pytest.mark.asyncio
async def test_fixed_asset_purchase_and_disposal(db_session: AsyncSession):
    """
    Test recording asset purchase and subsequent asset disposal:
    1. Post ASSET_PURCHASE: Dr 1501, Cr 1101
    2. Dispose asset
    3. Assert status transitions to DISPOSED and cannot be depreciated
    """
    org_id = uuid.uuid4()
    org = Organization(
        id=org_id,
        slug=f"asset-disp-{uuid.uuid4().hex[:6]}",
        legal_name="PT Asset Disposal"
    )
    db_session.add(org)
    await db_session.flush()
    await seed_standard_coa(db_session, org_id)

    user = User(
        id=uuid.uuid4(),
        organization_id=org_id,
        email=f"disp.{uuid.uuid4().hex[:6]}@test.com",
        password_hash="hash",
        full_name="Disposal Officer",
        role=UserRole.ADMIN
    )
    db_session.add(user)
    await db_session.flush()

    service = FixedAssetService(db_session)

    # 1. Purchase Transaction: Dr 1501, Cr 1101
    tx = Transaction(
        id=uuid.uuid4(),
        organization_id=org_id,
        transaction_code="PUR-AST-001",
        transaction_type=TransactionType.ASSET_PURCHASE,
        transaction_date=date(2026, 1, 1),
        amount=Decimal("50000000.00"),
        description="Pembelian Mobil Pick Up Bekas",
        workflow_status=WorkflowStatus.APPROVED
    )
    db_session.add(tx)
    await db_session.flush()

    engine = AccountingEngine(db_session)
    journal = await engine.post_transaction(org_id, tx.id, actor_id=user.id)
    assert journal.total_debit == Decimal("50000000.00")
    assert journal.total_credit == Decimal("50000000.00")

    # 2. Register asset in fixed_assets
    asset = await service.create_asset(
        org_id,
        FixedAssetCreate(
            asset_code="AST-PKP-01",
            asset_name="Mobil Pick Up Bekas",
            asset_category="VEHICLE",
            purchase_date=date(2026, 1, 1),
            purchase_cost=Decimal("50000000.00"),
            useful_life_months=48
        ),
        actor_id=user.id
    )

    # 3. Dispose asset
    disposed = await service.dispose_asset(
        organization_id=org_id,
        asset_id=asset.id,
        disposal_date=date(2026, 2, 1),
        actor_id=user.id
    )
    assert disposed.status == AssetStatus.DISPOSED

    # Cannot depreciate disposed asset
    with pytest.raises(InvariantViolationException) as exc_disp:
        await service.depreciate_asset(
            organization_id=org_id,
            asset_id=asset.id,
            period_date=date(2026, 2, 28),
            actor_id=user.id,
            actor_role=user.role
        )
    assert "DISPOSED" in str(exc_disp.value)
