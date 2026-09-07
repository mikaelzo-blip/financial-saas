from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.models.user import User
from src.models.enums import UserRole
from src.models.whatsapp import WhatsAppSenderMapping
from scripts.export_whatsapp_allowlist import get_active_sender_phones


async def test_exports_only_active_canonical_sender_phones(db_session: AsyncSession):
    organization = Organization(legal_name="Startup Test", slug="startup-test")
    db_session.add(organization)
    await db_session.flush()
    user = User(
        organization_id=organization.id,
        email="startup@example.test",
        full_name="Startup Test",
        password_hash="not-used",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add_all(
        [
            WhatsAppSenderMapping(
                organization_id=organization.id,
                user_id=user.id,
                phone_number="+628111111111",
                display_name="Active",
                role_in_org="OPERATOR",
                is_active=True,
            ),
            WhatsAppSenderMapping(
                organization_id=organization.id,
                user_id=user.id,
                phone_number="+628222222222",
                display_name="Inactive",
                role_in_org="OPERATOR",
                is_active=False,
            ),
            WhatsAppSenderMapping(
                organization_id=organization.id,
                user_id=user.id,
                phone_number="invalid",
                display_name="Malformed",
                role_in_org="OPERATOR",
                is_active=True,
            ),
        ]
    )
    await db_session.flush()

    assert await get_active_sender_phones(db_session) == ["628111111111"]
