from sqlalchemy import select

from tests.integration.test_whatsapp_intake_flow import wa, send
from src.models import WhatsAppSenderMapping


async def test_status_is_tenant_scoped_and_role_checked(wa, db_session):
    await send(wa)
    await send(wa, wamid="wamid.status-alpha", text="STATUS")
    assert "Dokumen: 1" in wa["provider"].outbound[-1].body_text
    await send(wa, phone=wa["phones"][1], wamid="wamid.status-beta", text="RINGKASAN")
    assert "Dokumen: 0" in wa["provider"].outbound[-1].body_text
    mapping = await db_session.scalar(select(WhatsAppSenderMapping).where(WhatsAppSenderMapping.phone_number == wa["phones"][0]))
    mapping.role_in_org = "OPERATOR"
    await db_session.commit()
    response = await wa["client"].post("/api/v1/hermes/whatsapp/status", headers={"Authorization": "Bearer test-tenant-0"}, json={"phone_number": wa["phones"][0]})
    assert response.status_code == 403
