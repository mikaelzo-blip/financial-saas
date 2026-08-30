import uuid
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit import AuditLog


class AuditService:
    """
    Append-only audit trail service logging financial state transitions and sensitive actions.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        organization_id: uuid.UUID,
        entity_name: str,
        entity_id: uuid.UUID,
        action: str,
        actor_id: Optional[uuid.UUID] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None
    ) -> AuditLog:
        entry = AuditLog(
            organization_id=organization_id,
            entity_name=entity_name,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            old_values=old_values or {},
            new_values=new_values or {},
            reason=reason
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
