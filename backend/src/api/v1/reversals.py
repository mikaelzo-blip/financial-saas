import uuid
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.models.audit import AuditLog
from src.schemas.transaction import TransactionResponse
from src.services.reversal_service import ReversalService

router = APIRouter(tags=["Reversals & Audit"])


class ReversalRequest(BaseModel):
    reason: str = Field(min_length=5, description="Reason for reversing the posted transaction")


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    entity_name: str
    entity_id: uuid.UUID
    action: str
    old_values: dict
    new_values: dict
    reason: Optional[str] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post(
    "/transactions/{transaction_id}/reverse",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reverse a Posted Transaction"
)
async def reverse_transaction(
    transaction_id: uuid.UUID,
    data: ReversalRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    service = ReversalService(db)
    rev_trx, _ = await service.reverse_transaction(
        organization_id=org_id,
        original_transaction_id=transaction_id,
        reason=data.reason
    )
    await db.commit()
    return rev_trx


@router.get(
    "/audit-logs",
    response_model=List[AuditLogResponse],
    summary="List Audit Trail Logs"
)
async def list_audit_logs(
    entity_name: Optional[str] = Query(None),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db)
):
    filters = [AuditLog.organization_id == org_id]
    if entity_name:
        filters.append(AuditLog.entity_name == entity_name)

    stmt = select(AuditLog).where(and_(*filters)).order_by(AuditLog.timestamp.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())
