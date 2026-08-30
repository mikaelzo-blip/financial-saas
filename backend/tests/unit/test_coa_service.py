import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.enums import AccountType, NormalBalance
from src.models.coa import ChartOfAccount, PaymentAccount
from src.schemas.coa import ChartOfAccountCreate, PaymentAccountCreate
from src.services.coa_service import COAService, PaymentAccountService
from src.core.exceptions import EntityNotFoundException, DuplicateEntityException, InvariantViolationException


@pytest.mark.asyncio
async def test_coa_service_create_and_validation(db_session: AsyncSession):
    """Test COA creation, normal balance validation, and duplicate prevention."""
    org = Organization(slug="org-coa-svc-test", legal_name="Org COA Service Test")
    db_session.add(org)
    await db_session.flush()

    coa_service = COAService(db_session)

    # 1. Create valid account
    dto = ChartOfAccountCreate(
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Setara Kas"
    )
    account = await coa_service.create_account(org.id, dto)
    await db_session.commit()

    assert account.id is not None
    assert account.account_code == "1101"
    assert account.normal_balance == NormalBalance.DEBIT

    # 2. Prevent duplicate account_code in same organization
    with pytest.raises(DuplicateEntityException):
        await coa_service.create_account(org.id, dto)

    # 3. Allow same account_code in different organization
    org2 = Organization(slug="org2-coa-svc-test", legal_name="Org 2 COA Service Test")
    db_session.add(org2)
    await db_session.flush()
    account2 = await coa_service.create_account(org2.id, dto)
    assert account2.id != account.id


@pytest.mark.asyncio
async def test_payment_account_service_mapping_and_validation(db_session: AsyncSession):
    """Test operational payment accounts must map to valid parent COA account."""
    org = Organization(slug="org-pa-svc-test", legal_name="Org PA Service Test")
    db_session.add(org)
    await db_session.flush()

    coa_service = COAService(db_session)
    pa_service = PaymentAccountService(db_session)

    parent_coa = await coa_service.create_account(
        org.id,
        ChartOfAccountCreate(
            account_code="1101",
            account_name="Kas dan Bank",
            account_type=AccountType.ASSET,
            normal_balance=NormalBalance.DEBIT,
            report_group="Kas & Setara Kas"
        )
    )
    await db_session.commit()

    # 1. Create valid payment account
    pa_dto = PaymentAccountCreate(
        coa_account_id=parent_coa.id,
        name="Bank Mandiri Giro",
        bank_name="Mandiri",
        account_number="1234567890"
    )
    pa = await pa_service.create_payment_account(org.id, pa_dto)
    await db_session.commit()

    assert pa.id is not None
    assert pa.coa_account_id == parent_coa.id
    assert pa.name == "Bank Mandiri Giro"

    # 2. Reject non-existent parent COA
    invalid_pa_dto = PaymentAccountCreate(
        coa_account_id=uuid.uuid4(),
        name="Invalid Account",
        bank_name="BCA"
    )
    with pytest.raises(EntityNotFoundException):
        await pa_service.create_payment_account(org.id, invalid_pa_dto)
