import io
import uuid
from decimal import Decimal
from datetime import date
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.project import Project
from src.models.enums import (
    AccountType,
    NormalBalance,
    ProjectStatus,
    TransactionType,
    WorkflowStatus,
    CostCategory,
    DocumentType,
    ReviewFlag,
)
from src.schemas.transaction import TransactionCreate, TransactionAllocationInput
from src.services.transaction_service import TransactionService
from src.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_transaction_intake_single_project(db_session: AsyncSession):
    """Test capturing single-project transaction and verifying sequential code & allocation."""
    org = Organization(slug="org-trx-single", legal_name="Org Trx Single")
    db_session.add(org)
    await db_session.flush()

    vendor = Counterparty(organization_id=org.id, name="Toko Bangunan Sejahtera", is_vendor=True)
    coa = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Setara Kas"
    )
    db_session.add_all([vendor, coa])
    await db_session.flush()

    pa = PaymentAccount(
        organization_id=org.id,
        coa_account_id=coa.id,
        name="Kas Operasional",
        bank_name="Cash"
    )
    project = Project(
        organization_id=org.id,
        project_code="PRJ-2026-001",
        project_name="Renovasi Kantor",
        customer_id=vendor.id,
        start_date=date(2026, 1, 1),
        project_status=ProjectStatus.ACTIVE
    )
    db_session.add_all([pa, project])
    await db_session.commit()

    trx_service = TransactionService(db_session)

    # 1. Create direct purchase transaction
    create_dto = TransactionCreate(
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=date(2026, 2, 1),
        amount=Decimal("4500000.00"),
        counterparty_id=vendor.id,
        payment_account_id=pa.id,
        description="Pembelian Semen & Pasir",
        project_id=project.id,
        cost_category=CostCategory.MAT
    )
    trx = await trx_service.create_transaction(org.id, create_dto)
    await db_session.commit()

    year = date.today().year
    assert trx.transaction_code == f"TRX-{year}-000001"
    assert trx.workflow_status == WorkflowStatus.STAGED
    assert trx.amount == Decimal("4500000.00")
    assert len(trx.allocations) == 1
    assert trx.allocations[0].project_id == project.id
    assert trx.allocations[0].cost_category == CostCategory.MAT
    assert trx.allocations[0].amount == Decimal("4500000.00")


@pytest.mark.asyncio
async def test_transaction_split_allocation_and_heuristic_duplicate(db_session: AsyncSession):
    """Test multi-project split allocation and heuristic duplicate detection flag."""
    org = Organization(slug="org-trx-split", legal_name="Org Trx Split")
    db_session.add(org)
    await db_session.flush()

    vendor = Counterparty(organization_id=org.id, name="PT Distributor Baja", is_vendor=True)
    coa = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Setara Kas"
    )
    db_session.add_all([vendor, coa])
    await db_session.flush()

    pa = PaymentAccount(organization_id=org.id, coa_account_id=coa.id, name="Mandiri", bank_name="Mandiri")
    p1 = Project(organization_id=org.id, project_code="PRJ-2026-001", project_name="Proyek A", customer_id=vendor.id, start_date=date(2026, 1, 1), project_status=ProjectStatus.ACTIVE)
    p2 = Project(organization_id=org.id, project_code="PRJ-2026-002", project_name="Proyek B", customer_id=vendor.id, start_date=date(2026, 1, 1), project_status=ProjectStatus.ACTIVE)
    db_session.add_all([pa, p1, p2])
    await db_session.commit()

    trx_service = TransactionService(db_session)

    # First transaction: split Rp 10.000.000 (Rp 6.000.000 to P1, Rp 4.000.000 to P2)
    t1 = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 2, 10),
            amount=Decimal("10000000.00"),
            counterparty_id=vendor.id,
            payment_account_id=pa.id,
            description="Baja batch 1",
            allocations=[
                TransactionAllocationInput(project_id=p1.id, cost_category=CostCategory.MAT, amount=Decimal("6000000.00")),
                TransactionAllocationInput(project_id=p2.id, cost_category=CostCategory.MAT, amount=Decimal("4000000.00")),
            ]
        )
    )
    await db_session.commit()
    assert t1.workflow_status == WorkflowStatus.STAGED
    assert len(t1.allocations) == 2

    # Second transaction: same date, same amount, same vendor, same payment account -> MUST BE FLAGGED
    t2 = await trx_service.create_transaction(
        org.id,
        TransactionCreate(
            transaction_type=TransactionType.DIRECT_PURCHASE,
            transaction_date=date(2026, 2, 10),
            amount=Decimal("10000000.00"),
            counterparty_id=vendor.id,
            payment_account_id=pa.id,
            description="Baja batch 2 suspected dupe",
            project_id=p1.id,
            cost_category=CostCategory.MAT
        )
    )
    await db_session.commit()

    assert t2.workflow_status == WorkflowStatus.REVIEW_REQUIRED
    assert len(t2.review_flags) == 1
    assert t2.review_flags[0].flag == ReviewFlag.DUPLICATE_SUSPECTED


@pytest.mark.asyncio
async def test_transaction_rest_api_capture_and_query(client: AsyncClient, db_session: AsyncSession):
    """Test REST API capture endpoint /api/v1/transactions with document attachment."""
    org = Organization(slug="org-trx-api", legal_name="Org Trx API")
    db_session.add(org)
    await db_session.flush()

    vendor = Counterparty(organization_id=org.id, name="PT Supplier API", is_vendor=True)
    coa = ChartOfAccount(
        organization_id=org.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Setara Kas"
    )
    db_session.add_all([vendor, coa])
    await db_session.flush()

    pa = PaymentAccount(organization_id=org.id, coa_account_id=coa.id, name="Kas Besar", bank_name="Cash")
    db_session.add(pa)
    await db_session.commit()

    # Upload document first
    doc_service = DocumentService(db_session)
    doc = await doc_service.ingest_document(
        org.id,
        io.BytesIO(b"%PDF-1.4\nNOTA-BELANJA-KONTRAKTOR"),
        "nota.pdf",
        "application/pdf",
        DocumentType.RECEIPT
    )
    await db_session.commit()

    # POST /api/v1/transactions
    payload = {
        "transaction_type": "DIRECT_PURCHASE",
        "transaction_date": "2026-03-01",
        "amount": 2500000.00,
        "counterparty_id": str(vendor.id),
        "payment_account_id": str(pa.id),
        "description": "Pembelian Alat Ukur Proyek",
        "cost_category": "EQP",
        "document_ids": [str(doc.id)]
    }

    response = await client.post(
        "/api/v1/transactions",
        json=payload,
        headers={"X-Organization-ID": str(org.id)}
    )
    assert response.status_code == 201
    trx_data = response.json()
    assert trx_data["transaction_type"] == "DIRECT_PURCHASE"
    assert Decimal(str(trx_data["amount"])) == Decimal("2500000.00")
    trx_id = trx_data["id"]

    # GET /api/v1/transactions/{id}
    get_resp = await client.get(
        f"/api/v1/transactions/{trx_id}",
        headers={"X-Organization-ID": str(org.id)}
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == trx_id
