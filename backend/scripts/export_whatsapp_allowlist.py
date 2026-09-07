"""Print the active canonical WhatsApp sender allowlist for local startup."""

import asyncio
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.models.whatsapp import WhatsAppSenderMapping

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")


async def get_active_sender_phones(session: AsyncSession) -> list[str]:
    phones = (
        await session.scalars(
            select(WhatsAppSenderMapping.phone_number)
            .where(WhatsAppSenderMapping.is_active.is_(True))
            .order_by(WhatsAppSenderMapping.phone_number)
        )
    ).all()
    return [phone[1:] for phone in phones if _E164.fullmatch(phone)]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        print(",".join(await get_active_sender_phones(session)))


if __name__ == "__main__":
    asyncio.run(main())
