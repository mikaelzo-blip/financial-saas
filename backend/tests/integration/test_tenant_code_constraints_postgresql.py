from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import (
    AccountType,
    AssetStatus,
    DepreciationMethod,
    MovementDirection,
    MovementSourceType,
    NormalBalance,
    SettlementType,
)
from src.models.fixed_asset import FixedAsset
from src.models.inbox import DocumentSession
from src.models.money_movement import MoneyMovement, Settlement

pytestmark = pytest.mark.postgresql


async def create_payment_accounts(
    session: AsyncSession,
    organization_ids: tuple[UUID, UUID],
) -> tuple[UUID, UUID]:
    accounts: list[PaymentAccount] = []
    for organization_id, suffix in zip(organization_ids, ("A", "B")):
        cash = ChartOfAccount(
            organization_id=organization_id,
            account_code=f"1101-{suffix}",
            account_name=f"Feature 012 cash {suffix}",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="CURRENT_ASSET",
        )
        session.add(cash)
        await session.flush()
        account = PaymentAccount(
            organization_id=organization_id,
            coa_account_id=cash.id,
            name=f"Feature 012 bank {suffix}",
        )
        session.add(account)
        accounts.append(account)
    await session.flush()
    return accounts[0].id, accounts[1].id


async def insert_money_movement(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    payment_account_id: UUID,
    movement_code: str,
) -> None:
    async with session_factory() as session:
        session.add(
            MoneyMovement(
                organization_id=organization_id,
                movement_code=movement_code,
                payment_account_id=payment_account_id,
                direction=MovementDirection.IN,
                amount=Decimal("100.00"),
                movement_date=date(2026, 9, 10),
                source_type=MovementSourceType.MANUAL,
            )
        )
        await session.commit()


async def insert_settlement(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    payment_account_id: UUID,
    movement_code: str,
    settlement_code: str,
) -> None:
    async with session_factory() as session:
        movement = MoneyMovement(
            organization_id=organization_id,
            movement_code=movement_code,
            payment_account_id=payment_account_id,
            direction=MovementDirection.IN,
            amount=Decimal("100.00"),
            movement_date=date(2026, 9, 10),
            source_type=MovementSourceType.MANUAL,
        )
        session.add(movement)
        await session.flush()
        session.add(
            Settlement(
                organization_id=organization_id,
                settlement_code=settlement_code,
                money_movement_id=movement.id,
                settlement_type=SettlementType.DIRECT_EXPENSE,
                amount=Decimal("100.00"),
            )
        )
        await session.commit()


async def insert_fixed_asset(
    session_factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    asset_code: str,
    suffix: str,
) -> None:
    async with session_factory() as session:
        asset_account = ChartOfAccount(
            organization_id=organization_id,
            account_code=f"1501-{suffix}",
            account_name=f"Feature 012 asset {suffix}",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="FIXED_ASSET",
        )
        depreciation_account = ChartOfAccount(
            organization_id=organization_id,
            account_code=f"1502-{suffix}",
            account_name=f"Feature 012 accumulated depreciation {suffix}",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.CREDIT,
            report_group="FIXED_ASSET",
        )
        session.add_all([asset_account, depreciation_account])
        await session.flush()
        session.add(
            FixedAsset(
                organization_id=organization_id,
                asset_code=asset_code,
                asset_name=f"Feature 012 asset {suffix}",
                asset_category="EQUIPMENT",
                purchase_date=date(2026, 9, 10),
                purchase_cost=Decimal("1000.00"),
                salvage_value=Decimal("0.00"),
                useful_life_months=12,
                depreciation_method=DepreciationMethod.STRAIGHT_LINE,
                status=AssetStatus.ACTIVE,
                asset_account_id=asset_account.id,
                depreciation_account_id=depreciation_account.id,
            )
        )
        await session.commit()


async def test_movement_code_cross_tenant_duplicate_is_allowed_after_feature_012(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    async with pg_session_factory() as session:
        payment_accounts = await create_payment_accounts(session, test_organizations)
        await session.commit()

    code = "MM-2026-000001"
    await insert_money_movement(
        pg_session_factory, test_organizations[0], payment_accounts[0], code
    )
    await insert_money_movement(
        pg_session_factory, test_organizations[1], payment_accounts[1], code
    )


async def test_movement_code_same_tenant_duplicate_remains_rejected(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    async with pg_session_factory() as session:
        payment_accounts = await create_payment_accounts(session, test_organizations)
        await session.commit()
    code = "MM-2026-000001"
    await insert_money_movement(
        pg_session_factory, test_organizations[0], payment_accounts[0], code
    )
    async with pg_session_factory() as session:
        session.add(
            MoneyMovement(
                organization_id=test_organizations[0],
                movement_code=code,
                payment_account_id=payment_accounts[0],
                direction=MovementDirection.IN,
                amount=Decimal("100.00"),
                movement_date=date(2026, 9, 10),
                source_type=MovementSourceType.MANUAL,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_settlement_code_cross_tenant_duplicate_is_allowed_after_feature_012(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    async with pg_session_factory() as session:
        payment_accounts = await create_payment_accounts(session, test_organizations)
        await session.commit()
    code = "SET-000001"
    await insert_settlement(
        pg_session_factory, test_organizations[0], payment_accounts[0], "MM-2026-000001", code
    )
    await insert_settlement(
        pg_session_factory, test_organizations[1], payment_accounts[1], "MM-2026-000002", code
    )


async def test_settlement_code_same_tenant_duplicate_remains_rejected(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    async with pg_session_factory() as session:
        payment_accounts = await create_payment_accounts(session, test_organizations)
        await session.commit()
    code = "SET-000001"
    await insert_settlement(
        pg_session_factory, test_organizations[0], payment_accounts[0], "MM-2026-000001", code
    )
    async with pg_session_factory() as session:
        movement = await session.scalar(
            select(MoneyMovement).where(
                MoneyMovement.organization_id == test_organizations[0],
                MoneyMovement.movement_code == "MM-2026-000001",
            )
        )
        assert movement is not None
        session.add(
            Settlement(
                organization_id=test_organizations[0],
                settlement_code=code,
                money_movement_id=movement.id,
                settlement_type=SettlementType.DIRECT_EXPENSE,
                amount=Decimal("100.00"),
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_asset_code_cross_tenant_duplicate_is_allowed_after_feature_012(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    await insert_fixed_asset(pg_session_factory, test_organizations[0], "AST-001", "A")
    await insert_fixed_asset(pg_session_factory, test_organizations[1], "AST-001", "B")


async def test_asset_code_same_tenant_duplicate_remains_rejected(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    await insert_fixed_asset(pg_session_factory, test_organizations[0], "AST-001", "A")
    async with pg_session_factory() as session:
        session.add(
            FixedAsset(
                organization_id=test_organizations[0],
                asset_code="AST-001",
                asset_name="Feature 012 duplicate asset",
                asset_category="EQUIPMENT",
                purchase_date=date(2026, 9, 10),
                purchase_cost=Decimal("1000.00"),
                salvage_value=Decimal("0.00"),
                useful_life_months=12,
                depreciation_method=DepreciationMethod.STRAIGHT_LINE,
                status=AssetStatus.ACTIVE,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_document_session_code_remains_globally_unique(
    pg_session_factory: async_sessionmaker[AsyncSession],
    test_organizations: tuple[UUID, UUID],
) -> None:
    code = "SESS-F012-GLOBAL-001"
    async with pg_session_factory() as session:
        session.add(DocumentSession(organization_id=test_organizations[0], session_code=code))
        await session.commit()
    async with pg_session_factory() as session:
        session.add(DocumentSession(organization_id=test_organizations[1], session_code=code))
        with pytest.raises(IntegrityError):
            await session.commit()
