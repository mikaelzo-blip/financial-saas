import uuid
import pytest
from sqlalchemy import select, exc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enums import (
    UserRole,
    AccountType,
    NormalBalance,
    CostCategory,
    ExpenseCategory,
    TransactionType,
    WorkflowStatus,
    ReviewFlag,
    ProjectStatus,
    BillingStatus,
    CollectionStatus,
    DocumentType,
)
from src.models.organization import Organization
from src.models.user import User
from src.models.counterparty import Counterparty
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.audit import AuditLog
from src.core.security import hash_password, verify_password, create_access_token, decode_access_token
from src.services.coa_seeder import (
    seed_standard_coa,
    seed_standard_payment_accounts,
    STANDARD_COA_DEFINITIONS,
    STANDARD_PAYMENT_ACCOUNTS,
)


@pytest.mark.asyncio
async def test_organization_creation_and_constraints(db_session: AsyncSession):
    """Test organization creation, defaults, and slug uniqueness."""
    org = Organization(
        slug="pt-kontraktor-utama",
        legal_name="PT Kontraktor Utama Indonesia",
        tax_id="01.234.567.8-901.000",
        default_payment_term_days=30,
        fiscal_year_start_month=1
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)

    assert org.id is not None
    assert org.slug == "pt-kontraktor-utama"
    assert org.default_payment_term_days == 30
    assert org.created_at is not None

    # Test duplicate slug constraint
    duplicate_org = Organization(
        slug="pt-kontraktor-utama",
        legal_name="Another Company"
    )
    db_session.add(duplicate_org)
    with pytest.raises(exc.IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_user_organization_relationship_and_roles(db_session: AsyncSession):
    """Test user creation, role assignment, and organization relationship."""
    org = Organization(slug="org-users-test", legal_name="Org Users Test")
    db_session.add(org)
    await db_session.commit()

    hashed_pw = hash_password("SecurePassword123!")
    user = User(
        organization_id=org.id,
        email="operator@kontraktor.co.id",
        full_name="Budi Santoso",
        password_hash=hashed_pw,
        role=UserRole.OPERATOR
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.role == UserRole.OPERATOR
    assert user.is_active is True
    assert user.organization_id == org.id

    # Test password verification
    assert verify_password("SecurePassword123!", user.password_hash) is True
    assert verify_password("WrongPassword", user.password_hash) is False
    assert user.password_hash != "SecurePassword123!"


def test_password_security_and_jwt():
    """Verify password hashing security and JWT token creation."""
    plain = "SuperSecret#2026"
    hashed = hash_password(plain)

    # Never plaintext
    assert hashed != plain
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongSecret", hashed) is False

    # Empty password check
    with pytest.raises(ValueError):
        hash_password("")

    # JWT generation and decode
    token = create_access_token(subject="user-uuid-123", claims={"role": "ADMIN"})
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-uuid-123"
    assert payload["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_counterparty_roles_and_json_fields(db_session: AsyncSession):
    """Test Counterparty model with customer/vendor roles and structured JSON metadata."""
    org = Organization(slug="org-counterparty-test", legal_name="Org Counterparty Test")
    db_session.add(org)
    await db_session.commit()

    # Vendor + Customer (Dual role)
    partner = Counterparty(
        organization_id=org.id,
        name="PT Semen Jaya & Kontraktor",
        is_customer=True,
        is_vendor=True,
        tax_id="02.999.888.7-111.000",
        contact_info={"phone": "021-5551234", "address": "Jakarta Pusat"},
        bank_accounts=[{"bank": "Mandiri", "account_number": "123000998877", "name": "PT Semen Jaya"}]
    )
    db_session.add(partner)
    await db_session.commit()
    await db_session.refresh(partner)

    assert partner.is_customer is True
    assert partner.is_vendor is True
    assert partner.contact_info["phone"] == "021-5551234"
    assert len(partner.bank_accounts) == 1
    assert partner.bank_accounts[0]["bank"] == "Mandiri"


@pytest.mark.asyncio
async def test_chart_of_accounts_no_balance_column(db_session: AsyncSession):
    """
    Test ChartOfAccount structure.
    CRITICAL: Confirms COA does NOT store balance columns.
    """
    org = Organization(slug="org-coa-test", legal_name="Org COA Test")
    db_session.add(org)
    await db_session.commit()

    coa = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Setara Kas"
    )
    db_session.add(coa)
    await db_session.commit()
    await db_session.refresh(coa)

    # Invariant check: ChartOfAccount must NOT have balance attribute
    assert not hasattr(coa, "balance")
    assert not hasattr(coa, "current_balance")
    assert not hasattr(coa, "running_balance")

    assert coa.account_code == "1101"
    assert coa.normal_balance == NormalBalance.DEBIT
    assert coa.account_type == AccountType.ASSET


@pytest.mark.asyncio
async def test_payment_account_mapping(db_session: AsyncSession):
    """Test operational PaymentAccount linked to parent COA account."""
    org = Organization(slug="org-pay-account-test", legal_name="Org Pay Account Test")
    db_session.add(org)
    await db_session.commit()

    coa = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Setara Kas"
    )
    db_session.add(coa)
    await db_session.commit()

    mandiri = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa.id,
        name="Bank Mandiri Operasional",
        bank_name="Mandiri",
        account_number="1234567890"
    )
    cash = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa.id,
        name="Kas Kecil Proyek",
        bank_name="Cash",
        account_number=None
    )
    db_session.add_all([mandiri, cash])
    await db_session.commit()

    # Query payment accounts under parent COA
    stmt = select(PaymentAccount).where(PaymentAccount.organization_id == org.id)
    result = await db_session.execute(stmt)
    accounts = result.scalars().all()
    assert len(accounts) == 2
    assert all(a.coa_account_id == coa.id for a in accounts)


@pytest.mark.asyncio
async def test_audit_log_append_behavior(db_session: AsyncSession):
    """Test append-only AuditLog record creation and snapshot storage."""
    org = Organization(slug="org-audit-test", legal_name="Org Audit Test")
    db_session.add(org)
    await db_session.commit()

    target_id = uuid.uuid4()
    audit_entry = AuditLog(
        organization_id=org.id,
        entity_name="projects",
        entity_id=target_id,
        action="STATE_CHANGE",
        old_values={"status": "PLANNED"},
        new_values={"status": "ACTIVE"},
        reason="Site mobilization started"
    )
    db_session.add(audit_entry)
    await db_session.commit()
    await db_session.refresh(audit_entry)

    assert audit_entry.id is not None
    assert audit_entry.action == "STATE_CHANGE"
    assert audit_entry.old_values["status"] == "PLANNED"
    assert audit_entry.new_values["status"] == "ACTIVE"
    assert audit_entry.reason == "Site mobilization started"
    assert audit_entry.timestamp is not None


@pytest.mark.asyncio
async def test_idempotent_coa_and_payment_account_seeders(db_session: AsyncSession):
    """Test deterministic and idempotent COA and Payment Account seeding."""
    org = Organization(slug="org-seeder-test", legal_name="Org Seeder Test")
    db_session.add(org)
    await db_session.commit()

    # First seeding pass
    created_coa, skipped_coa = await seed_standard_coa(db_session, org.id)
    await db_session.commit()

    assert created_coa == len(STANDARD_COA_DEFINITIONS)
    assert skipped_coa == 0

    # Verify COA counts and essential accounts
    stmt = select(ChartOfAccount).where(ChartOfAccount.organization_id == org.id)
    result = await db_session.execute(stmt)
    all_coa = result.scalars().all()
    assert len(all_coa) == len(STANDARD_COA_DEFINITIONS)

    coa_codes = {c.account_code for c in all_coa}
    assert "1101" in coa_codes  # Kas dan Bank
    assert "1201" in coa_codes  # Piutang Usaha
    assert "2101" in coa_codes  # Utang Usaha
    assert "5101" in coa_codes  # Harga Pokok Proyek

    # Seed payment accounts
    created_pa, skipped_pa = await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    assert created_pa == len(STANDARD_PAYMENT_ACCOUNTS)
    assert skipped_pa == 0

    # Second seeding pass (MUST be completely idempotent)
    created_coa_2, skipped_coa_2 = await seed_standard_coa(db_session, org.id)
    created_pa_2, skipped_pa_2 = await seed_standard_payment_accounts(db_session, org.id)
    await db_session.commit()

    assert created_coa_2 == 0
    assert skipped_coa_2 == len(STANDARD_COA_DEFINITIONS)
    assert created_pa_2 == 0
    assert skipped_pa_2 == len(STANDARD_PAYMENT_ACCOUNTS)


def test_domain_enums_integrity():
    """Verify all domain enums are present and conform to spec."""
    assert len(CostCategory) == 9
    assert CostCategory.MAT == "MAT"
    assert CostCategory.SUB == "SUB"
    assert CostCategory.OTH == "OTH"

    assert len(ExpenseCategory) == 9
    assert ExpenseCategory.SALARY == "SALARY"
    assert ExpenseCategory.DEPRECIATION == "DEPRECIATION"

    assert len(TransactionType) == 35
    assert TransactionType.DIRECT_PURCHASE == "DIRECT_PURCHASE"
    assert TransactionType.REVERSAL == "REVERSAL"
    assert TransactionType.JOURNAL_ADJUSTMENT == "JOURNAL_ADJUSTMENT"

    assert len(UserRole) == 4
    assert UserRole.ADMIN == "ADMIN"
    assert UserRole.MANAGER == "MANAGER"
    assert UserRole.OPERATOR == "OPERATOR"
    assert UserRole.VIEWER == "VIEWER"

    assert len(DocumentType) == 22
    assert DocumentType.UNKNOWN == "UNKNOWN"
    assert DocumentType.SPK == "SPK"
    assert DocumentType.BAST == "BAST"
