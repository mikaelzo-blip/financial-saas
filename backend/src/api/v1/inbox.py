import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.api.deps import get_current_org_id
from src.api.auth import require_application_user, require_roles
from src.models.enums import InboxMessageStatus, SessionMatchStatus, UserRole
from src.models.user import User
from src.schemas.inbox import (
    InboxMessageResponse,
    RemoteInboxPayload,
    DocumentSessionResponse
)
from src.services.remote_inbox_service import RemoteInboxService
from src.services.deferred_analysis_service import DeferredAnalysisService

router = APIRouter()


@router.post(
    "/capture",
    response_model=InboxMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Remote Relay Capture Ingestion"
)
async def capture_remote_message(
    payload: RemoteInboxPayload,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db)
):
    service = RemoteInboxService(db)
    msg = await service.ingest_remote_capture(org_id, payload)
    return msg


@router.post(
    "/sync",
    response_model=List[InboxMessageResponse],
    summary="Local Sync Worker Backlog Pull"
)
async def sync_backlog(
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db)
):
    service = RemoteInboxService(db)
    return await service.sync_backlog(org_id)


@router.get(
    "/messages",
    response_model=List[InboxMessageResponse],
    summary="List Raw Synced WhatsApp Inbox Messages"
)
async def list_inbox_messages(
    status_filter: Optional[InboxMessageStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    org_id: uuid.UUID = Depends(get_current_org_id),
    _user=Depends(require_application_user),
    db: AsyncSession = Depends(get_db)
):
    service = RemoteInboxService(db)
    return await service.list_inbox_messages(
        organization_id=org_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset
    )


@router.get(
    "/sessions",
    response_model=List[DocumentSessionResponse],
    summary="List Document Sessions for Deferred Analysis"
)
async def list_document_sessions(
    status_filter: Optional[SessionMatchStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    org_id: uuid.UUID = Depends(get_current_org_id),
    _user=Depends(require_application_user),
    db: AsyncSession = Depends(get_db)
):
    service = RemoteInboxService(db)
    return await service.list_sessions(
        organization_id=org_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset
    )


@router.get(
    "/sessions/{session_id}",
    response_model=DocumentSessionResponse,
    summary="Get Document Session Details"
)
async def get_document_session(
    session_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    _user=Depends(require_application_user),
    db: AsyncSession = Depends(get_db)
):
    service = RemoteInboxService(db)
    return await service.get_session(organization_id=org_id, session_id=session_id)


@router.post(
    "/sessions/{session_id}/analyze",
    response_model=DocumentSessionResponse,
    summary="Run Deferred Analysis On A Session"
)
async def analyze_document_session(
    session_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.OPERATOR)),
    db: AsyncSession = Depends(get_db)
):
    service = DeferredAnalysisService(db)
    doc_session, _ = await service.analyze_session(organization_id=org_id, session_id=session_id)
    await db.commit()
    return doc_session

