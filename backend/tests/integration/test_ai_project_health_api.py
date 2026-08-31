from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select
from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.receivable import CustomerInvoice, CustomerPaymentAllocation
from src.models.journal import JournalLine
from src.models.transaction import Transaction
from src.models.enums import CostCategory
from tests.integration.test_ai_executive_summary_api import insight_identity


async def project_fixture(db, slug='project-a'):
    org, user, headers = await insight_identity(db, slug, Decimal('50000000'), Decimal('200000000'))
    customer = Counterparty(organization_id=org.id, name='Customer '+slug, is_customer=True)
    db.add(customer)
    await db.flush()
    project = Project(organization_id=org.id, project_code='P-'+slug, project_name='Project '+slug, customer_id=customer.id, start_date=date(2026,1,1), original_contract_value=Decimal('300000000'), revised_contract_value=Decimal('300000000'))
    db.add(project)
    await db.flush()
    invoice = CustomerInvoice(organization_id=org.id, customer_id=customer.id, project_id=project.id, invoice_code='INV-'+slug, invoice_date=date(2026,1,1), due_date=date(2026,2,1), total_amount=Decimal('300000000'))
    db.add(invoice)
    await db.flush()
    payment = await db.scalar(select(Transaction).where(Transaction.organization_id == org.id, Transaction.transaction_code == slug+'-REVENUE'))
    db.add(CustomerPaymentAllocation(invoice_id=invoice.id, payment_transaction_id=payment.id, allocated_amount=Decimal('50000000')))
    from src.models.journal import JournalEntry
    lines = (await db.scalars(select(JournalLine).join(JournalEntry).where(JournalEntry.organization_id == org.id))).all()
    for line in lines:
        line.project_id = project.id
        line.cost_category = CostCategory.MAT
    await db.commit()
    return org, user, headers, project


@pytest.mark.asyncio
async def test_project_api_profit_cash_and_nine_cost_categories(client, db_session):
    _, _, headers, project = await project_fixture(db_session)
    response = await client.get(f'/api/v1/insights/projects/{project.id}', headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body['factual_metrics']['project_profit']) == Decimal('100000000')
    assert Decimal(body['factual_metrics']['project_cash_position']) == Decimal('-150000000')
    assert body['headline'] == 'Laba positif, posisi kas defisit'
    assert len([k for k in body['factual_metrics'] if k.startswith('cost_')]) == 9
    assert body['factual_metrics']['total_budget'] is None
