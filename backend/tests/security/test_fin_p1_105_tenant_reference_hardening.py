"""Security regression and characterization suite for FIN-P1-105.

Tenant Ownership Validation for Supplied Foreign UUID References.
CP1: Executable reproduction of all 7 confirmed vulnerable foreign-reference
fields + ProjectBudget defense-in-depth characterization + same-tenant positive
controls + fail-closed contract verification.

ZERO PRODUCTION CODE CHANGES IN CP1.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import io
import uuid
from typing import AsyncGenerator, Dict, Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.database import Base, get_db
from src.core.exceptions import EntityNotFoundException
from src.core.security import create_access_token, hash_password
from src.main import create_application
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.counterparty import Counterparty
from src.models.document import Document
from src.models.enums import (
    AssetStatus,
    CostCategory,
    DepreciationMethod,
    DocumentProcessingStatus,
    DocumentType,
    MovementDirection,
    MovementSourceType,
    ProjectStatus,
    ReconciliationStatus,
    SettlementType,
    StatementImportStatus,
    TransactionType,
    UserRole,
    WorkflowStatus,
)
from src.models.fixed_asset import FixedAsset
from src.models.journal import JournalEntry, JournalLine
from src.models.money_movement import MoneyMovement, Settlement, SettlementAllocation
from src.models.organization import Organization
from src.models.project import Project, ProjectBudget
from src.models.bank_reconciliation import (
    BankStatementImport,
    BankStatementLine,
    BankReconciliation,
)
from src.models.transaction import Transaction
from src.models.user import User
from src.schemas.project import ProjectCreate, ProjectUpdate, ProjectBudgetCreate
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.project_service import ProjectService


def make_auth_headers(org_id: uuid.UUID, user_id: uuid.UUID) -> Dict[str, str]:
    """Generate JWT authorization and tenant context headers matching AUTHZ-001."""
    token = create_access_token(str(user_id), {"organization_id": str(org_id)})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org_id),
        "X-User-ID": str(user_id),
    }


@pytest.fixture
async def tenant_hardening_env() -> AsyncGenerator[Dict[str, Any], None]:
    """Multi-tenant test environment establishing isolated Tenant A and Tenant B.

    Creates valid users across roles (ADMIN, MANAGER, OPERATOR, VIEWER) and
    entities (counterparties, projects, documents, transactions, movements,
    journals, and bank statement lines) for both tenants.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_application()

    async def override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    async with session_factory() as session:
        # 1. Organization A & Users
        org_a = Organization(
            id=uuid.uuid4(),
            slug="tenant-a-org",
            legal_name="Tenant A Corporation PT",
        )
        session.add(org_a)
        await session.flush()

        users_a = {}
        for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR, UserRole.VIEWER]:
            u = User(
                id=uuid.uuid4(),
                organization_id=org_a.id,
                email=f"{role.value.lower()}@tenant-a.local",
                full_name=f"Tenant A {role.value}",
                role=role,
                password_hash=hash_password("secret123"),
                is_active=True,
            )
            session.add(u)
            users_a[role] = u
        await session.flush()

        # Seed COA & Payment Accounts for Org A
        await seed_standard_coa(session, org_a.id)
        await seed_standard_payment_accounts(session, org_a.id)
        coa_a = await session.scalar(
            select(ChartOfAccount).where(ChartOfAccount.organization_id == org_a.id)
        )
        pay_acc_a = await session.scalar(
            select(PaymentAccount).where(PaymentAccount.organization_id == org_a.id)
        )
        assert coa_a is not None
        assert pay_acc_a is not None

        # Counterparties for Org A
        customer_a = Counterparty(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Tenant A Customer PT",
            is_customer=True,
            is_vendor=False,
        )
        vendor_a = Counterparty(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            name="Tenant A Vendor PT",
            is_customer=False,
            is_vendor=True,
        )
        session.add_all([customer_a, vendor_a])
        await session.flush()

        # Document for Org A
        doc_a = Document(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            document_code="DOC-A-001",
            document_type=DocumentType.VENDOR_INVOICE,
            file_name="invoice_a.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024,
            file_hash="hash_doc_a_unique",
            storage_path="/tmp/doc_a.pdf",
            source_channel="WEB",
            source_metadata={},
            raw_extraction={},
            processing_status=DocumentProcessingStatus.PROCESSED,
            confidence_scores={"overall": 0.95},
            created_by=users_a[UserRole.OPERATOR].id,
        )
        session.add(doc_a)

        # Project for Org A
        project_a = Project(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            project_code="PRJ-A-2026-001",
            project_name="Tenant A Project 1",
            customer_id=customer_a.id,
            original_contract_value=Decimal("50000000.00"),
            revised_contract_value=Decimal("50000000.00"),
            start_date=date(2026, 1, 1),
            project_status=ProjectStatus.ACTIVE,
            pic_user_id=users_a[UserRole.MANAGER].id,
        )
        session.add(project_a)

        # Transaction for Org A
        tx_a = Transaction(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            transaction_code="TX-A-2026-001",
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("5000000.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.APPROVED,
            counterparty_id=vendor_a.id,
            payment_account_id=pay_acc_a.id,
            description="Tenant A Bill Transaction",
        )
        session.add(tx_a)

        # Money Movement for Org A
        mm_a = MoneyMovement(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            movement_code="MM-A-2026-001",
            payment_account_id=pay_acc_a.id,
            direction=MovementDirection.OUT,
            amount=Decimal("5000000.00"),
            movement_date=date(2026, 1, 2),
            source_type=MovementSourceType.MANUAL,
            description="Tenant A Payment Movement",
        )
        session.add(mm_a)

        # Journal Entry & Line for Org A
        je_a = JournalEntry(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            entry_number="JE-A-2026-001",
            transaction_id=tx_a.id,
            posting_date=date(2026, 1, 2),
            description="Tenant A Journal Entry",
            total_debit=Decimal("5000000.00"),
            total_credit=Decimal("5000000.00"),
            is_balanced=True,
        )
        session.add(je_a)
        await session.flush()

        jl_a = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_a.id,
            line_number=1,
            account_id=coa_a.id,
            debit_amount=Decimal("5000000.00"),
            credit_amount=Decimal("0.00"),
        )
        jl_a_credit = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_a.id,
            line_number=2,
            account_id=coa_a.id,
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("5000000.00"),
        )
        session.add_all([jl_a, jl_a_credit])

        # Bank Statement Import & Line for Org A
        stmt_imp_a = BankStatementImport(
            id=uuid.uuid4(),
            organization_id=org_a.id,
            payment_account_id=pay_acc_a.id,
            file_hash="stmt_hash_a_unique",
            source_file="bank_a.csv",
            imported_at=datetime.now(timezone.utc),
            status=StatementImportStatus.COMPLETED,
        )
        session.add(stmt_imp_a)
        await session.flush()

        stmt_line_a = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_imp_a.id,
            organization_id=org_a.id,
            line_number=1,
            transaction_date=date(2026, 1, 2),
            description="Bank Outflow A",
            debit=Decimal("5000000.00"),
            credit=Decimal("0.00"),
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        session.add(stmt_line_a)

        # -----------------------------------------------------------------
        # 2. Organization B & Users (Foreign Tenant)
        # -----------------------------------------------------------------
        org_b = Organization(
            id=uuid.uuid4(),
            slug="tenant-b-org",
            legal_name="Tenant B Corporation PT",
        )
        session.add(org_b)
        await session.flush()

        users_b = {}
        for role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR, UserRole.VIEWER]:
            u = User(
                id=uuid.uuid4(),
                organization_id=org_b.id,
                email=f"{role.value.lower()}@tenant-b.local",
                full_name=f"Tenant B {role.value}",
                role=role,
                password_hash=hash_password("secret123"),
                is_active=True,
            )
            session.add(u)
            users_b[role] = u
        await session.flush()

        # Seed COA & Payment Accounts for Org B
        await seed_standard_coa(session, org_b.id)
        await seed_standard_payment_accounts(session, org_b.id)
        coa_b = await session.scalar(
            select(ChartOfAccount).where(ChartOfAccount.organization_id == org_b.id)
        )
        pay_acc_b = await session.scalar(
            select(PaymentAccount).where(PaymentAccount.organization_id == org_b.id)
        )
        assert coa_b is not None
        assert pay_acc_b is not None

        # Counterparties for Org B
        customer_b = Counterparty(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            name="Tenant B Customer PT",
            is_customer=True,
            is_vendor=False,
        )
        vendor_b = Counterparty(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            name="Tenant B Vendor PT",
            is_customer=False,
            is_vendor=True,
        )
        session.add_all([customer_b, vendor_b])
        await session.flush()

        # Document for Org B
        doc_b = Document(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            document_code="DOC-B-001",
            document_type=DocumentType.VENDOR_INVOICE,
            file_name="invoice_b.pdf",
            mime_type="application/pdf",
            file_size_bytes=2048,
            file_hash="hash_doc_b_unique",
            storage_path="/tmp/doc_b.pdf",
            source_channel="WEB",
            source_metadata={},
            raw_extraction={},
            processing_status=DocumentProcessingStatus.PROCESSED,
            confidence_scores={"overall": 0.98},
            created_by=users_b[UserRole.OPERATOR].id,
        )
        session.add(doc_b)

        # Project for Org B
        project_b = Project(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            project_code="PRJ-B-2026-001",
            project_name="Tenant B Project 1",
            customer_id=customer_b.id,
            original_contract_value=Decimal("75000000.00"),
            revised_contract_value=Decimal("75000000.00"),
            start_date=date(2026, 1, 1),
            project_status=ProjectStatus.ACTIVE,
            pic_user_id=users_b[UserRole.MANAGER].id,
        )
        session.add(project_b)

        # Transaction for Org B
        tx_b = Transaction(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            transaction_code="TX-B-2026-001",
            transaction_type=TransactionType.VENDOR_BILL,
            transaction_date=date(2026, 1, 1),
            amount=Decimal("5000000.00"),
            currency="IDR",
            workflow_status=WorkflowStatus.APPROVED,
            counterparty_id=vendor_b.id,
            payment_account_id=pay_acc_b.id,
            description="Tenant B Bill Transaction",
        )
        session.add(tx_b)

        # Money Movement for Org B
        mm_b = MoneyMovement(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            movement_code="MM-B-2026-001",
            payment_account_id=pay_acc_b.id,
            direction=MovementDirection.OUT,
            amount=Decimal("5000000.00"),
            movement_date=date(2026, 1, 2),
            source_type=MovementSourceType.MANUAL,
            description="Tenant B Payment Movement",
        )
        session.add(mm_b)

        # Journal Entry & Line for Org B
        je_b = JournalEntry(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            entry_number="JE-B-2026-001",
            transaction_id=tx_b.id,
            posting_date=date(2026, 1, 2),
            description="Tenant B Journal Entry",
            total_debit=Decimal("5000000.00"),
            total_credit=Decimal("5000000.00"),
            is_balanced=True,
        )
        session.add(je_b)
        await session.flush()

        jl_b = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_b.id,
            line_number=1,
            account_id=coa_b.id,
            debit_amount=Decimal("5000000.00"),
            credit_amount=Decimal("0.00"),
        )
        jl_b_credit = JournalLine(
            id=uuid.uuid4(),
            journal_entry_id=je_b.id,
            line_number=2,
            account_id=coa_b.id,
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("5000000.00"),
        )
        session.add_all([jl_b, jl_b_credit])

        # Bank Statement Import & Line for Org B
        stmt_imp_b = BankStatementImport(
            id=uuid.uuid4(),
            organization_id=org_b.id,
            payment_account_id=pay_acc_b.id,
            file_hash="stmt_hash_b_unique",
            source_file="bank_b.csv",
            imported_at=datetime.now(timezone.utc),
            status=StatementImportStatus.COMPLETED,
        )
        session.add(stmt_imp_b)
        await session.flush()

        stmt_line_b = BankStatementLine(
            id=uuid.uuid4(),
            import_id=stmt_imp_b.id,
            organization_id=org_b.id,
            line_number=1,
            transaction_date=date(2026, 1, 2),
            description="Bank Outflow B",
            debit=Decimal("5000000.00"),
            credit=Decimal("0.00"),
            reconciliation_status=ReconciliationStatus.UNMATCHED_BANK,
        )
        session.add(stmt_line_b)

        await session.commit()

        # Extract IDs and references
        data = {
            "session_factory": session_factory,
            "org_a": org_a,
            "org_b": org_b,
            "users_a": {r: u.id for r, u in users_a.items()},
            "users_b": {r: u.id for r, u in users_b.items()},
            "customer_a": customer_a,
            "customer_b": customer_b,
            "vendor_a": vendor_a,
            "vendor_b": vendor_b,
            "doc_a": doc_a,
            "doc_b": doc_b,
            "project_a": project_a,
            "project_b": project_b,
            "tx_a": tx_a,
            "tx_b": tx_b,
            "mm_a": mm_a,
            "mm_b": mm_b,
            "je_a": je_a,
            "je_b": je_b,
            "jl_a": jl_a,
            "jl_b": jl_b,
            "stmt_line_a": stmt_line_a,
            "stmt_line_b": stmt_line_b,
            "pay_acc_a": pay_acc_a,
            "pay_acc_b": pay_acc_b,
            "coa_a": coa_a,
            "coa_b": coa_b,
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        data["client"] = client
        yield data

    await engine.dispose()


# =============================================================================
# 1. Project.pic_user_id (Create & Update) — Field 1
# =============================================================================

async def test_project_create_same_tenant_pic_user_accepted(tenant_hardening_env):
    """Positive Control: Tenant A creates project supplying Tenant A PIC user."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.MANAGER])

    payload = {
        "project_name": "Tenant A New Project",
        "customer_id": str(env["customer_a"].id),
        "original_contract_value": "10000000.00",
        "start_date": "2026-03-01",
        "pic_user_id": str(env["users_a"][UserRole.OPERATOR]),
    }
    response = await client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["pic_user_id"] == str(env["users_a"][UserRole.OPERATOR])


async def test_project_create_cross_tenant_pic_user_rejected(tenant_hardening_env):
    """Tenant A cannot supply a Tenant B User UUID as Project.pic_user_id."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.MANAGER])

    payload = {
        "project_name": "Cross Tenant PIC Project",
        "customer_id": str(env["customer_a"].id),
        "original_contract_value": "10000000.00",
        "start_date": "2026-03-01",
        "pic_user_id": str(env["users_b"][UserRole.MANAGER]),  # Tenant B user
    }
    response = await client.post("/api/v1/projects", json=payload, headers=headers)

    # Future Invariant: fail-closed 404 NOT_FOUND
    assert response.status_code == 404
    error_body = response.json().get("error", {})
    assert error_body.get("code") == "NOT_FOUND"


async def test_project_create_nonexistent_pic_user_characterization(tenant_hardening_env):
    """A nonexistent project PIC returns the same not-found contract as a foreign PIC."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.MANAGER])
    nonexistent_id = uuid.uuid4()

    payload = {
        "project_name": "Nonexistent PIC Project",
        "customer_id": str(env["customer_a"].id),
        "original_contract_value": "10000000.00",
        "start_date": "2026-03-01",
        "pic_user_id": str(nonexistent_id),
    }
    response = await client.post("/api/v1/projects", json=payload, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_project_update_same_tenant_pic_user_accepted(tenant_hardening_env):
    """Positive Control: Tenant A updates project with valid Tenant A PIC user."""
    env = tenant_hardening_env
    session_factory = env["session_factory"]
    async with session_factory() as session:
        service = ProjectService(session)
        updated = await service.update_project(
            organization_id=env["org_a"].id,
            project_id=env["project_a"].id,
            data=ProjectUpdate(pic_user_id=env["users_a"][UserRole.OPERATOR]),
        )
        assert updated.pic_user_id == env["users_a"][UserRole.OPERATOR]


async def test_project_update_cross_tenant_pic_user_rejected(tenant_hardening_env):
    """Tenant A cannot assign a Tenant B User UUID as project PIC."""
    env = tenant_hardening_env
    session_factory = env["session_factory"]
    foreign_user_id = env["users_b"][UserRole.MANAGER]

    async with session_factory() as session:
        service = ProjectService(session)
        original_pic_user_id = (await service.get_project(env["org_a"].id, env["project_a"].id)).pic_user_id

        with pytest.raises(EntityNotFoundException):
            await service.update_project(
                organization_id=env["org_a"].id,
                project_id=env["project_a"].id,
                data=ProjectUpdate(pic_user_id=foreign_user_id),
            )

        unchanged = await service.get_project(env["org_a"].id, env["project_a"].id)
        assert unchanged.pic_user_id == original_pic_user_id


async def test_project_update_null_and_omitted_pic_user_accepted(tenant_hardening_env):
    """Nullability & Omission Controls: clearing PIC and omitting PIC."""
    env = tenant_hardening_env
    session_factory = env["session_factory"]

    async with session_factory() as session:
        service = ProjectService(session)
        original_pic_user_id = (await service.get_project(env["org_a"].id, env["project_a"].id)).pic_user_id

        p1 = await service.update_project(
            organization_id=env["org_a"].id,
            project_id=env["project_a"].id,
            data=ProjectUpdate(project_name="Renamed Project"),
        )
        assert p1.pic_user_id == original_pic_user_id
        assert p1.project_name == "Renamed Project"

        cleared = await service.update_project(
            organization_id=env["org_a"].id,
            project_id=env["project_a"].id,
            data=ProjectUpdate(pic_user_id=None),
        )
        assert cleared.pic_user_id is None


# =============================================================================
# 2. FixedAsset.vendor_id — Field 2
# =============================================================================

async def test_fixed_asset_create_same_tenant_vendor_accepted(tenant_hardening_env):
    """Positive Control: Tenant A creates fixed asset with valid Tenant A vendor."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "asset_code": "AST-A-001",
        "asset_name": "Excavator A",
        "asset_category": "EQUIPMENT",
        "purchase_date": "2026-01-10",
        "purchase_cost": "150000000.00",
        "salvage_value": "15000000.00",
        "useful_life_months": 48,
        "vendor_id": str(env["vendor_a"].id),
    }
    response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["vendor_id"] == str(env["vendor_a"].id)


async def test_fixed_asset_create_cross_tenant_vendor_rejected(tenant_hardening_env):
    """Tenant A cannot create an asset with a Tenant B vendor reference."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "asset_code": "AST-A-RED-VEND",
        "asset_name": "Foreign Vendor Asset",
        "asset_category": "EQUIPMENT",
        "purchase_date": "2026-01-10",
        "purchase_cost": "150000000.00",
        "salvage_value": "15000000.00",
        "useful_life_months": 48,
        "vendor_id": str(env["vendor_b"].id),  # Tenant B vendor
    }
    response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)

    assert response.status_code == 404
    error_body = response.json().get("error", {})
    assert error_body.get("code") == "NOT_FOUND"

    async with env["session_factory"]() as session:
        assert not await session.scalar(
            select(FixedAsset).where(FixedAsset.asset_code == payload["asset_code"])
        )


async def test_fixed_asset_create_mixed_tenant_references_are_atomic(tenant_hardening_env):
    """A valid reference cannot permit persistence when the other reference is foreign."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payloads = [
        {
            "asset_code": "AST-A-MIXED-DOC",
            "asset_name": "Valid Vendor Foreign Document",
            "asset_category": "EQUIPMENT",
            "purchase_date": "2026-01-10",
            "purchase_cost": "50000000.00",
            "salvage_value": "5000000.00",
            "useful_life_months": 24,
            "vendor_id": str(env["vendor_a"].id),
            "document_id": str(env["doc_b"].id),
        },
        {
            "asset_code": "AST-A-MIXED-VENDOR",
            "asset_name": "Foreign Vendor Valid Document",
            "asset_category": "EQUIPMENT",
            "purchase_date": "2026-01-10",
            "purchase_cost": "50000000.00",
            "salvage_value": "5000000.00",
            "useful_life_months": 24,
            "vendor_id": str(env["vendor_b"].id),
            "document_id": str(env["doc_a"].id),
        },
    ]

    for payload in payloads:
        response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    async with env["session_factory"]() as session:
        result = await session.execute(
            select(FixedAsset).where(FixedAsset.asset_code.in_([item["asset_code"] for item in payloads]))
        )
        assert list(result.scalars()) == []


async def test_fixed_asset_create_null_vendor_accepted(tenant_hardening_env):
    """Nullability Control: Fixed asset created without vendor_id (None)."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "asset_code": "AST-A-NULL-VEND",
        "asset_name": "No Vendor Asset",
        "asset_category": "EQUIPMENT",
        "purchase_date": "2026-01-10",
        "purchase_cost": "150000000.00",
        "salvage_value": "15000000.00",
        "useful_life_months": 48,
        "vendor_id": None,
    }
    response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["vendor_id"] is None


async def test_fixed_asset_create_nonexistent_vendor_characterization(tenant_hardening_env):
    """Nonexistent UUID Control: Fixed asset created with random UUID vendor_id."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "asset_code": "AST-A-NONEXIST-VEND",
        "asset_name": "Nonexistent Vendor Asset",
        "asset_category": "EQUIPMENT",
        "purchase_date": "2026-01-10",
        "purchase_cost": "150000000.00",
        "salvage_value": "15000000.00",
        "useful_life_months": 48,
        "vendor_id": str(uuid.uuid4()),
    }
    response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 3. FixedAsset.document_id — Field 3
# =============================================================================

async def test_fixed_asset_create_same_tenant_document_accepted(tenant_hardening_env):
    """Positive Control: Tenant A creates fixed asset with valid Tenant A document."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "asset_code": "AST-A-DOC-VALID",
        "asset_name": "Documented Asset A",
        "asset_category": "EQUIPMENT",
        "purchase_date": "2026-01-10",
        "purchase_cost": "50000000.00",
        "salvage_value": "5000000.00",
        "useful_life_months": 24,
        "document_id": str(env["doc_a"].id),
    }
    response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["document_id"] == str(env["doc_a"].id)


async def test_fixed_asset_create_cross_tenant_document_rejected(tenant_hardening_env):
    """Tenant A cannot create an asset with a Tenant B document reference."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "asset_code": "AST-A-RED-DOC",
        "asset_name": "Foreign Document Asset",
        "asset_category": "EQUIPMENT",
        "purchase_date": "2026-01-10",
        "purchase_cost": "50000000.00",
        "salvage_value": "5000000.00",
        "useful_life_months": 24,
        "document_id": str(env["doc_b"].id),  # Tenant B document
    }
    response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)

    assert response.status_code == 404
    error_body = response.json().get("error", {})
    assert error_body.get("code") == "NOT_FOUND"

    async with env["session_factory"]() as session:
        assert not await session.scalar(
            select(FixedAsset).where(FixedAsset.asset_code == payload["asset_code"])
        )


async def test_fixed_asset_create_null_document_accepted(tenant_hardening_env):
    """Nullability Control: Fixed asset created without document_id (None)."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "asset_code": "AST-A-NULL-DOC",
        "asset_name": "No Doc Asset",
        "asset_category": "EQUIPMENT",
        "purchase_date": "2026-01-10",
        "purchase_cost": "50000000.00",
        "salvage_value": "5000000.00",
        "useful_life_months": 24,
        "document_id": None,
    }
    response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["document_id"] is None


async def test_fixed_asset_create_nonexistent_document_characterization(tenant_hardening_env):
    """Nonexistent UUID Control: Fixed asset created with random UUID document_id."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "asset_code": "AST-A-NONEXIST-DOC",
        "asset_name": "Nonexistent Doc Asset",
        "asset_category": "EQUIPMENT",
        "purchase_date": "2026-01-10",
        "purchase_cost": "50000000.00",
        "salvage_value": "5000000.00",
        "useful_life_months": 24,
        "document_id": str(uuid.uuid4()),
    }
    response = await client.post("/api/v1/fixed-assets", json=payload, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 4. Settlement.transaction_id & Multi-Settlement Atomicity — Field 4
# =============================================================================

async def test_money_movement_create_same_tenant_settlement_transaction_accepted(tenant_hardening_env):
    """Positive Control: Tenant A creates money movement settlement linking Tenant A transaction."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "payment_account_id": str(env["pay_acc_a"].id),
        "direction": "OUT",
        "amount": "2000000.00",
        "movement_date": "2026-01-15",
        "source_type": "MANUAL",
        "description": "Valid Same Tenant Settlement",
        "settlements": [
            {
                "amount": "2000000.00",
                "settlement_type": "INVOICE_PAYMENT",
                "transaction_id": str(env["tx_a"].id),
            }
        ],
    }
    response = await client.post("/api/v1/money-movements", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert len(body["settlements"]) == 1
    assert body["settlements"][0]["transaction_id"] == str(env["tx_a"].id)


async def test_money_movement_create_cross_tenant_settlement_transaction_rejected(tenant_hardening_env):
    """Tenant A cannot link a settlement to Tenant B transaction."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "payment_account_id": str(env["pay_acc_a"].id),
        "direction": "OUT",
        "amount": "2000000.00",
        "movement_date": "2026-01-15",
        "source_type": "MANUAL",
        "description": "Cross Tenant Settlement Attempt",
        "settlements": [
            {
                "amount": "2000000.00",
                "settlement_type": "INVOICE_PAYMENT",
                "transaction_id": str(env["tx_b"].id),  # Tenant B transaction
            }
        ],
    }
    response = await client.post("/api/v1/money-movements", json=payload, headers=headers)

    assert response.status_code == 404
    error_body = response.json().get("error", {})
    assert error_body.get("code") == "NOT_FOUND"

    async with env["session_factory"]() as session:
        assert not (await session.scalars(
            select(MoneyMovement).where(MoneyMovement.description == payload["description"])
        )).all()
        assert not (await session.scalars(
            select(Settlement).where(Settlement.transaction_id == env["tx_b"].id)
        )).all()
        assert not (await session.scalars(select(SettlementAllocation))).all()


async def test_money_movement_create_null_settlement_transaction_accepted(tenant_hardening_env):
    """Nullability Control: Settlement created without transaction_id (None)."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "payment_account_id": str(env["pay_acc_a"].id),
        "direction": "OUT",
        "amount": "1000000.00",
        "movement_date": "2026-01-15",
        "source_type": "MANUAL",
        "description": "Null Transaction Settlement",
        "settlements": [
            {
                "amount": "1000000.00",
                "settlement_type": "INVOICE_PAYMENT",
                "transaction_id": None,
            }
        ],
    }
    response = await client.post("/api/v1/money-movements", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["settlements"][0]["transaction_id"] is None


async def test_money_movement_create_mixed_settlement_atomicity_rejected(tenant_hardening_env):
    """A valid settlement cannot allow a foreign settlement in the same request."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "payment_account_id": str(env["pay_acc_a"].id),
        "direction": "OUT",
        "amount": "3000000.00",
        "movement_date": "2026-01-15",
        "source_type": "MANUAL",
        "description": "Mixed Multi-Settlement Atomicity Probe",
        "settlements": [
            {
                "amount": "1500000.00",
                "settlement_type": "INVOICE_PAYMENT",
                "transaction_id": str(env["tx_a"].id),  # Valid Tenant A
            },
            {
                "amount": "1500000.00",
                "settlement_type": "INVOICE_PAYMENT",
                "transaction_id": str(env["tx_b"].id),  # Foreign Tenant B
            },
        ],
    }
    response = await client.post("/api/v1/money-movements", json=payload, headers=headers)

    assert response.status_code == 404

    async with env["session_factory"]() as session:
        assert not (await session.scalars(
            select(MoneyMovement).where(MoneyMovement.description == payload["description"])
        )).all()
        assert not (await session.scalars(
            select(Settlement).where(Settlement.transaction_id.in_([env["tx_a"].id, env["tx_b"].id]))
        )).all()
        assert not (await session.scalars(select(SettlementAllocation))).all()


async def test_money_movement_create_nonexistent_transaction_characterization(tenant_hardening_env):
    """Nonexistent UUID Control: Money movement settlement with random UUID transaction_id."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "payment_account_id": str(env["pay_acc_a"].id),
        "direction": "OUT",
        "amount": "1000000.00",
        "movement_date": "2026-01-15",
        "source_type": "MANUAL",
        "description": "Nonexistent Transaction Settlement",
        "settlements": [
            {
                "amount": "1000000.00",
                "settlement_type": "INVOICE_PAYMENT",
                "transaction_id": str(uuid.uuid4()),
            }
        ],
    }
    response = await client.post("/api/v1/money-movements", json=payload, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 5. BankReconciliation.journal_line_id — Field 5
# =============================================================================

async def test_bank_reconciliation_match_same_tenant_journal_line_accepted(tenant_hardening_env):
    """Positive Control: Tenant A reconciles statement line against valid Tenant A JournalLine."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "5000000.00",
        "journal_line_id": str(env["jl_a"].id),
        "notes": "Same Tenant Journal Line Reconciled",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json().get("message") == "Reconciliation match created"


async def test_bank_reconciliation_match_cross_tenant_journal_line_rejected(tenant_hardening_env):
    """Tenant A cannot reconcile against Tenant B journal line."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "5000000.00",
        "journal_line_id": str(env["jl_b"].id),  # Tenant B journal line
        "notes": "Cross Tenant Journal Line Match Attempt",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)

    assert response.status_code == 404
    error_body = response.json().get("error", {})
    assert error_body.get("code") == "NOT_FOUND"

    async with env["session_factory"]() as session:
        statement_line = await session.get(BankStatementLine, env["stmt_line_a"].id)
        assert statement_line.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK
        assert not await session.scalar(
            select(BankReconciliation).where(BankReconciliation.statement_line_id == env["stmt_line_a"].id)
        )


async def test_bank_reconciliation_match_nonexistent_journal_line_characterization(tenant_hardening_env):
    """Nonexistent UUID Control: Bank reconciliation with random UUID journal_line_id."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "1000000.00",
        "journal_line_id": str(uuid.uuid4()),
        "notes": "Nonexistent JL match",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 6. BankReconciliation.money_movement_id — Field 6
# =============================================================================

async def test_bank_reconciliation_match_same_tenant_money_movement_accepted(tenant_hardening_env):
    """Positive Control: Tenant A reconciles statement line against valid Tenant A MoneyMovement."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "5000000.00",
        "money_movement_id": str(env["mm_a"].id),
        "notes": "Same Tenant MM Reconciled",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json().get("message") == "Reconciliation match created"


async def test_bank_reconciliation_match_cross_tenant_money_movement_rejected(tenant_hardening_env):
    """Tenant A cannot reconcile against Tenant B money movement."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "5000000.00",
        "money_movement_id": str(env["mm_b"].id),  # Tenant B money movement
        "notes": "Cross Tenant MM Match Attempt",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)

    assert response.status_code == 404
    error_body = response.json().get("error", {})
    assert error_body.get("code") == "NOT_FOUND"

    async with env["session_factory"]() as session:
        statement_line = await session.get(BankStatementLine, env["stmt_line_a"].id)
        assert statement_line.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK
        assert not await session.scalar(
            select(BankReconciliation).where(BankReconciliation.statement_line_id == env["stmt_line_a"].id)
        )


async def test_bank_reconciliation_match_nonexistent_money_movement_characterization(tenant_hardening_env):
    """Nonexistent UUID Control: Bank reconciliation with random UUID money_movement_id."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "1000000.00",
        "money_movement_id": str(uuid.uuid4()),
        "notes": "Nonexistent MM match",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 7. BankReconciliation.transaction_id — Field 7
# =============================================================================

async def test_bank_reconciliation_match_same_tenant_transaction_accepted(tenant_hardening_env):
    """Positive Control: Tenant A reconciles statement line against valid Tenant A Transaction."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "5000000.00",
        "transaction_id": str(env["tx_a"].id),
        "notes": "Same Tenant TX Reconciled",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json().get("message") == "Reconciliation match created"


async def test_bank_reconciliation_match_cross_tenant_transaction_rejected(tenant_hardening_env):
    """Tenant A cannot reconcile against Tenant B transaction."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "5000000.00",
        "transaction_id": str(env["tx_b"].id),  # Tenant B transaction
        "notes": "Cross Tenant TX Match Attempt",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)

    assert response.status_code == 404
    error_body = response.json().get("error", {})
    assert error_body.get("code") == "NOT_FOUND"

    async with env["session_factory"]() as session:
        statement_line = await session.get(BankStatementLine, env["stmt_line_a"].id)
        assert statement_line.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK
        assert not await session.scalar(
            select(BankReconciliation).where(BankReconciliation.statement_line_id == env["stmt_line_a"].id)
        )


async def test_bank_reconciliation_match_nonexistent_transaction_characterization(tenant_hardening_env):
    """Nonexistent UUID Control: Bank reconciliation with random UUID transaction_id."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "1000000.00",
        "transaction_id": str(uuid.uuid4()),
        "notes": "Nonexistent TX match",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# =============================================================================
# 8. Bank Mixed-Reference Atomicity
# =============================================================================

async def test_bank_reconciliation_mixed_reference_atomicity_rejected(tenant_hardening_env):
    """A valid bank reference cannot allow a foreign reference in the same request."""
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.OPERATOR])

    payload = {
        "statement_line_id": str(env["stmt_line_a"].id),
        "matched_amount": "5000000.00",
        "money_movement_id": str(env["mm_a"].id),  # Valid Tenant A
        "transaction_id": str(env["tx_b"].id),     # Foreign Tenant B
        "notes": "Mixed Reference Bank Reconciliation Probe",
    }
    response = await client.post("/api/v1/bank-reconciliation/reconcile", json=payload, headers=headers)

    assert response.status_code == 404

    async with env["session_factory"]() as session:
        statement_line = await session.get(BankStatementLine, env["stmt_line_a"].id)
        assert statement_line.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK
        assert not await session.scalar(
            select(BankReconciliation).where(BankReconciliation.statement_line_id == env["stmt_line_a"].id)
        )


# =============================================================================
# 9. Project Budget Defense-in-Depth Characterization (Not an API Vulnerability)
# =============================================================================

async def test_project_budget_api_protection_rejects_cross_tenant_project(tenant_hardening_env):
    """Characterization: API route already enforces tenant boundary on project_id.

    Calling GET /projects/{project_b.id}/budgets or POST /projects/{project_b.id}/budgets
    with Tenant A credentials returns 404 NOT_FOUND because api/v1/projects.py calls
    await service.get_project(org_id, project_id).
    This confirms ProjectBudget is NOT an active API vulnerability.
    """
    env = tenant_hardening_env
    client = env["client"]
    headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.MANAGER])
    foreign_proj_id = env["project_b"].id

    # 1. GET budgets for foreign project
    res_get = await client.get(f"/api/v1/projects/{foreign_proj_id}/budgets", headers=headers)
    assert res_get.status_code == 404

    # 2. POST budget for foreign project
    budget_payload = {
        "cost_category": CostCategory.MAT.value,
        "budget_amount": "25000000.00",
        "notes": "Cross Tenant Budget Attempt",
    }
    res_post = await client.post(
        f"/api/v1/projects/{foreign_proj_id}/budgets",
        json=budget_payload,
        headers=headers,
    )
    assert res_post.status_code == 404


async def test_project_budget_service_defense_in_depth_rejects_cross_tenant_project(tenant_hardening_env):
    """Direct service calls reject a foreign project before listing or creating budgets."""
    env = tenant_hardening_env
    session_factory = env["session_factory"]
    foreign_proj_id = env["project_b"].id

    async with session_factory() as session:
        service = ProjectService(session)

        with pytest.raises(EntityNotFoundException):
            await service.get_project_budgets(env["org_a"].id, foreign_proj_id)

        with pytest.raises(EntityNotFoundException):
            await service.add_or_update_project_budget(
                env["org_a"].id,
                foreign_proj_id,
                ProjectBudgetCreate(
                    cost_category=CostCategory.EQP,
                    budget_amount=Decimal("15000000.00"),
                    notes="Service-level direct add",
                ),
            )

        assert not await session.scalar(
            select(ProjectBudget).where(ProjectBudget.project_id == foreign_proj_id)
        )


async def test_project_budget_service_same_tenant_calls_succeed(tenant_hardening_env):
    """Direct same-tenant budget calls remain available after service hardening."""
    env = tenant_hardening_env
    session_factory = env["session_factory"]

    async with session_factory() as session:
        service = ProjectService(session)
        budget = await service.add_or_update_project_budget(
            env["org_a"].id,
            env["project_a"].id,
            ProjectBudgetCreate(
                cost_category=CostCategory.EQP,
                budget_amount=Decimal("15000000.00"),
                notes="Same-tenant service add",
            ),
        )
        assert budget.project_id == env["project_a"].id
        budgets = await service.get_project_budgets(env["org_a"].id, env["project_a"].id)
        assert [item.id for item in budgets] == [budget.id]


# =============================================================================
# 10. AUTHZ-001 Role Enforcement Regression
# =============================================================================

async def test_authz001_viewer_denied_before_tenant_reference_processing(tenant_hardening_env):
    """AUTHZ-001 Invariant: VIEWER role is denied with 403 Forbidden at the perimeter.

    Confirms perimeter authorization remains intact and cannot be bypassed.
    """
    env = tenant_hardening_env
    client = env["client"]
    viewer_headers = make_auth_headers(env["org_a"].id, env["users_a"][UserRole.VIEWER])

    # 1. Project Create
    res_proj = await client.post(
        "/api/v1/projects",
        json={
            "project_name": "Viewer Project",
            "customer_id": str(env["customer_a"].id),
            "original_contract_value": "1000000.00",
            "start_date": "2026-03-01",
        },
        headers=viewer_headers,
    )
    assert res_proj.status_code == 403

    # 2. Fixed Asset Create
    res_asset = await client.post(
        "/api/v1/fixed-assets",
        json={
            "asset_code": "AST-VIEWER",
            "asset_name": "Viewer Asset",
            "asset_category": "EQUIPMENT",
            "purchase_date": "2026-01-10",
            "purchase_cost": "1000000.00",
        },
        headers=viewer_headers,
    )
    assert res_asset.status_code == 403

    # 3. Money Movement Create
    res_mm = await client.post(
        "/api/v1/money-movements",
        json={
            "payment_account_id": str(env["pay_acc_a"].id),
            "direction": "OUT",
            "amount": "1000000.00",
            "movement_date": "2026-01-15",
            "source_type": "MANUAL",
        },
        headers=viewer_headers,
    )
    assert res_mm.status_code == 403

    # 4. Bank Reconciliation Match
    res_recon = await client.post(
        "/api/v1/bank-reconciliation/reconcile",
        json={
            "statement_line_id": str(env["stmt_line_a"].id),
            "matched_amount": "1000000.00",
        },
        headers=viewer_headers,
    )
    assert res_recon.status_code == 403


# =============================================================================
# 11. Foreign vs Nonexistent Response Contract Uniformity
# =============================================================================

def test_foreign_vs_nonexistent_contract_structure():
    """Verify EntityNotFoundException produces uniform error shape preventing oracle leakage."""
    entity_name = "User"
    nonexistent_id = uuid.uuid4()
    exc = EntityNotFoundException(entity_name, nonexistent_id)

    assert exc.status_code == 404
    assert exc.error_code == "NOT_FOUND"
    assert exc.details == {"entity": entity_name, "identifier": str(nonexistent_id)}
    assert str(nonexistent_id) in exc.message


# =============================================================================
# 12. PostgreSQL Constraint Confirmation
# =============================================================================

@pytest.mark.asyncio
async def test_postgresql_cross_tenant_foreign_key_acceptance_confirmation():
    """Authoritative PostgreSQL confirmation: Relational FKs accept cross-tenant UUIDs.

    Demonstrates that on PostgreSQL, a global foreign key constraint (e.g.
    projects.pic_user_id -> users.id) is fully satisfied by another tenant's row,
    allowing cross-tenant corruption at the database layer unless application
    services enforce tenant boundaries.
    """
    import os
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    pg_url = os.environ.get(
        "LIVE_POSTGRES_URL",
        "postgresql+asyncpg://financial:financial_dev_2026@localhost:5432/financial_saas",
    )

    try:
        pg_engine = create_async_engine(pg_url, echo=False)
        async with pg_engine.connect() as conn:
            await conn.execute(select(1))
    except (DBAPIError, OSError) as err:
        pytest.skip(f"PostgreSQL service not available for live confirmation: {err}")
        return

    pg_session_factory = async_sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)

    org_a_id = uuid.uuid4()
    org_b_id = uuid.uuid4()
    user_b_id = uuid.uuid4()
    cust_a_id = uuid.uuid4()
    proj_a_id = uuid.uuid4()

    async with pg_session_factory() as session:
        try:
            # Create two isolated organizations
            org_a = Organization(id=org_a_id, slug=f"pg-org-a-{org_a_id.hex[:8]}", legal_name="PG Org A PT")
            org_b = Organization(id=org_b_id, slug=f"pg-org-b-{org_b_id.hex[:8]}", legal_name="PG Org B PT")
            session.add_all([org_a, org_b])
            await session.flush()

            # Create User in Org B
            user_b = User(
                id=user_b_id,
                organization_id=org_b_id,
                email=f"user-b-{user_b_id.hex[:8]}@tenant-b.local",
                full_name="User Tenant B",
                role=UserRole.MANAGER,
                password_hash=hash_password("secret123"),
                is_active=True,
            )
            session.add(user_b)

            # Create Customer in Org A
            cust_a = Counterparty(
                id=cust_a_id,
                organization_id=org_a_id,
                name="Customer A PT",
                is_customer=True,
                is_vendor=False,
            )
            session.add(cust_a)
            await session.flush()

            # Create Project in Org A supplying user_b (Tenant B) as pic_user_id
            # On PostgreSQL, the foreign key constraint references users(id) globally.
            # Without application-level organization_id check, PostgreSQL accepts this insertion.
            proj_a = Project(
                id=proj_a_id,
                organization_id=org_a_id,
                project_code=f"PRJ-PG-{proj_a_id.hex[:8]}",
                project_name="PG Cross Tenant Project",
                customer_id=cust_a_id,
                original_contract_value=Decimal("10000000.00"),
                revised_contract_value=Decimal("10000000.00"),
                start_date=date(2026, 1, 1),
                project_status=ProjectStatus.ACTIVE,
                pic_user_id=user_b_id,  # Foreign tenant user UUID
            )
            session.add(proj_a)
            await session.commit()

            # Verify the cross-tenant linkage was accepted by PostgreSQL
            saved_proj = await session.scalar(select(Project).where(Project.id == proj_a_id))
            assert saved_proj is not None
            assert saved_proj.organization_id == org_a_id
            assert saved_proj.pic_user_id == user_b_id, (
                "PostgreSQL accepted cross-tenant foreign reference at database constraint layer"
            )

        finally:
            # Clean up all created rows in foreign-key order
            await session.rollback()
            async with pg_session_factory() as cleanup_session:
                await cleanup_session.execute(
                    text("DELETE FROM projects WHERE id = :id"), {"id": proj_a_id}
                )
                await cleanup_session.execute(
                    text("DELETE FROM counterparties WHERE id = :id"), {"id": cust_a_id}
                )
                await cleanup_session.execute(
                    text("DELETE FROM users WHERE id = :id"), {"id": user_b_id}
                )
                await cleanup_session.execute(
                    text("DELETE FROM organizations WHERE id IN (:id_a, :id_b)"),
                    {"id_a": org_a_id, "id_b": org_b_id},
                )
                await cleanup_session.commit()
            await pg_engine.dispose()
