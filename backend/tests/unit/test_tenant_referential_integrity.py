import uuid
from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.organization import Organization
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.document import Document, TransactionDocumentLink
from src.models.coa import PaymentAccount
from src.models.enums import (
    TransactionType,
    WorkflowStatus,
    CostCategory,
    DocumentType,
    DocumentProcessingStatus,
    DocumentSourceChannel,
)
from src.schemas.transaction import TransactionCreate, TransactionAllocationInput
from src.services.coa_seeder import seed_standard_coa, seed_standard_payment_accounts
from src.services.transaction_service import TransactionService
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


@pytest.mark.asyncio
async def test_cross_tenant_counterparty_blocked(db_session: AsyncSession):
    org_a = Organization(slug="org-a-tenant", legal_name="Org A")
    org_b = Organization(slug="org-b-tenant", legal_name="Org B")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    # Counterparty belongs to Org B
    vendor_b = Counterparty(organization_id=org_b.id, name="Vendor Org B", is_vendor=True)
    db_session.add(vendor_b)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    with pytest.raises(EntityNotFoundException):
        await trx_svc.create_transaction(
            organization_id=org_a.id,
            data=TransactionCreate(
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=date(2026, 3, 1),
                amount=Decimal("100000.00"),
                description="Cross-tenant counterparty",
                counterparty_id=vendor_b.id,
            )
        )


@pytest.mark.asyncio
async def test_cross_tenant_payment_account_blocked(db_session: AsyncSession):
    org_a = Organization(slug="org-pa-a", legal_name="Org PA A")
    org_b = Organization(slug="org-pa-b", legal_name="Org PA B")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    await seed_standard_coa(db_session, org_b.id)
    await seed_standard_payment_accounts(db_session, org_b.id)
    await db_session.commit()

    pa_b = await db_session.scalar(
        select(PaymentAccount).where(PaymentAccount.organization_id == org_b.id)
    )

    trx_svc = TransactionService(db_session)
    with pytest.raises(EntityNotFoundException):
        await trx_svc.create_transaction(
            organization_id=org_a.id,
            data=TransactionCreate(
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=date(2026, 3, 1),
                amount=Decimal("100000.00"),
                description="Cross-tenant payment account",
                payment_account_id=pa_b.id,
            )
        )


@pytest.mark.asyncio
async def test_cross_tenant_project_blocked(db_session: AsyncSession):
    org_a = Organization(slug="org-proj-a", legal_name="Org Proj A")
    org_b = Organization(slug="org-proj-b", legal_name="Org Proj B")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    customer_b = Counterparty(organization_id=org_b.id, name="Customer B", is_customer=True)
    db_session.add(customer_b)
    await db_session.flush()

    proj_b = Project(
        organization_id=org_b.id,
        project_code="PRJ-B-001",
        project_name="Gudang B",
        customer_id=customer_b.id,
        start_date=date(2026, 1, 1),
    )
    db_session.add(proj_b)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    with pytest.raises(EntityNotFoundException):
        await trx_svc.create_transaction(
            organization_id=org_a.id,
            data=TransactionCreate(
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=date(2026, 3, 1),
                amount=Decimal("500000.00"),
                description="Cross-tenant project",
                project_id=proj_b.id,
                cost_category=CostCategory.MAT,
            )
        )


@pytest.mark.asyncio
async def test_cross_tenant_document_blocked(db_session: AsyncSession):
    org_a = Organization(slug="org-doc-a", legal_name="Org Doc A")
    org_b = Organization(slug="org-doc-b", legal_name="Org Doc B")
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    doc_b = Document(
        organization_id=org_b.id,
        document_code="DOC-2026-000001",
        file_name="receipt.jpg",
        storage_path="storage/receipt.jpg",
        file_hash="1234567890abcdef" * 4,
        mime_type="image/jpeg",
        file_size_bytes=1024,
        document_type=DocumentType.RECEIPT,
        processing_status=DocumentProcessingStatus.UPLOADED,
        source_channel=DocumentSourceChannel.WEB,
    )

    db_session.add(doc_b)
    await db_session.commit()

    trx_svc = TransactionService(db_session)
    with pytest.raises(EntityNotFoundException):
        await trx_svc.create_transaction(
            organization_id=org_a.id,
            data=TransactionCreate(
                transaction_type=TransactionType.DIRECT_PURCHASE,
                transaction_date=date(2026, 3, 1),
                amount=Decimal("250000.00"),
                description="Cross-tenant doc link",
                document_ids=[doc_b.id],
            )
        )
