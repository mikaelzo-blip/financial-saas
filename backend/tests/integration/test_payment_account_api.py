import uuid

import pytest

from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import AccountType, NormalBalance
from src.models.organization import Organization


@pytest.mark.asyncio
async def test_payment_account_api_persists_authoritative_identity_and_coa_mapping(client, db_session):
    organization = Organization(slug="uat-payment-account", legal_name="UAT Payment Account")
    db_session.add(organization)
    await db_session.flush()
    coa = ChartOfAccount(
        organization_id=organization.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Current Assets",
    )
    db_session.add(coa)
    await db_session.commit()

    response = await client.post(
        "/api/v1/payment-accounts",
        headers={"X-Organization-ID": str(organization.id)},
        json={
            "coa_account_id": str(coa.id),
            "name": "Bank BCA",
            "bank_name": "BCA",
            "account_number": "1234567890",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Bank BCA"
    assert body["coa_account_id"] == str(coa.id)
    assert body["coa_account_code"] == "1101"
    assert body["coa_account_name"] == "Kas dan Bank"
    assert body["account_type"] == "ASSET"
    assert body["is_active"] is True

    stored = await db_session.get(PaymentAccount, uuid.UUID(body["id"]))
    assert stored is not None
    assert stored.organization_id == organization.id
    assert stored.coa_account_id == coa.id
    assert stored.name == "Bank BCA"


@pytest.mark.asyncio
async def test_payment_account_listing_is_tenant_scoped(client, db_session):
    org_a = Organization(slug="payment-a", legal_name="Payment A")
    org_b = Organization(slug="payment-b", legal_name="Payment B")
    db_session.add_all([org_a, org_b])
    await db_session.flush()
    coa_a = ChartOfAccount(
        organization_id=org_a.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Current Assets",
    )
    coa_b = ChartOfAccount(
        organization_id=org_b.id,
        account_code="1101",
        account_name="Kas dan Bank",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Current Assets",
    )
    db_session.add_all([coa_a, coa_b])
    await db_session.flush()
    db_session.add_all([
        PaymentAccount(organization_id=org_a.id, coa_account_id=coa_a.id, name="Kas A"),
        PaymentAccount(organization_id=org_b.id, coa_account_id=coa_b.id, name="Kas B"),
    ])
    await db_session.commit()

    response = await client.get(
        "/api/v1/payment-accounts",
        headers={"X-Organization-ID": str(org_a.id)},
    )
    assert response.status_code == 200, response.text
    assert [account["name"] for account in response.json()] == ["Kas A"]
