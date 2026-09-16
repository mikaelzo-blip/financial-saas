import math
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import select, func, and_, or_, String, cast
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document, ProjectDocumentLink
from src.models.project import Project
from src.models.counterparty import Counterparty
from src.models.background_job import BackgroundJob
from src.models.enums import DocumentType, DocumentProcessingStatus, ReviewFlag
from src.schemas.document_operations import (
    SafeJobFailure,
    QueueHealth,
    DocumentOperationsSummaryResponse,
    DocumentOperationalItem,
    DocumentOperationalListResponse,
)


def format_age_display(seconds: int) -> str:
    """Formats duration in seconds into a concise human-readable string."""
    if seconds < 60:
        return f"{seconds}d" if seconds == 0 else f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_minutes = minutes % 60
    if hours < 24:
        return f"{hours}j {rem_minutes}m" if rem_minutes > 0 else f"{hours}j"
    days = hours // 24
    rem_hours = hours % 24
    return f"{days}h {rem_hours}j" if rem_hours > 0 else f"{days}h"


def sanitize_error_message(error: Optional[str]) -> Optional[str]:
    """Strips stack traces, sensitive paths, and credentials from error text."""
    if not error:
        return None
    # Truncate at first stack traceback marker
    lines = error.strip().splitlines()
    safe_lines: List[str] = []
    for line in lines:
        if "Traceback (most recent call last):" in line or line.strip().startswith('File "'):
            break
        # Redact database URL credentials
        cleaned = re.sub(r"[a-zA-Z0-9+_-]+://[^:\s]+:[^@\s]+@[^\s]+", "[DATABASE_URL_REDACTED]", line)
        # Redact Bearer and authorization tokens
        cleaned = re.sub(r"(Bearer\s+|authorization:\s*Bearer\s+)\S+", r"\g<1>[REDACTED]", cleaned, flags=re.IGNORECASE)
        # Redact key=value or key: value credential assignments
        cleaned = re.sub(r"(password|secret|token|api[_-]?key)\s*[:=]\s*\S+", r"\g<1>=[REDACTED]", cleaned, flags=re.IGNORECASE)
        # Redact common standalone credential patterns
        cleaned = re.sub(r"(key[_-]?[a-zA-Z0-9]{8,}|token[_-]?[a-zA-Z0-9]{8,}|secret[_-]?[a-zA-Z0-9]{6,}|password[_-]?[a-zA-Z0-9]{6,})", "[REDACTED]", cleaned, flags=re.IGNORECASE)
        # Redact Windows absolute file paths
        cleaned = re.sub(r"[A-Za-z]:\\[^:\s\n\r]+", "[PATH]", cleaned)
        # Redact Unix absolute private paths
        cleaned = re.sub(r"/(?:Users|home|root|tmp|var|etc|opt)/[^\s\n\r]+", "[PATH]", cleaned)
        safe_lines.append(cleaned)
    msg = " ".join(safe_lines).strip()
    return msg[:200] if len(msg) > 200 else msg or "An unknown processing error occurred."


class DocumentOperationsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_summary(self, organization_id: uuid.UUID) -> DocumentOperationsSummaryResponse:
        """Aggregates tenant-scoped document status counts, review flags, and queue health."""
        # 1. Document status counts
        stmt = (
            select(Document.processing_status, func.count(Document.id))
            .where(Document.organization_id == organization_id)
            .group_by(Document.processing_status)
        )
        status_rows = (await self.session.execute(stmt)).all()
        raw_status_map = {row[0]: row[1] for row in status_rows}

        received = (
            raw_status_map.get(DocumentProcessingStatus.UPLOADED, 0)
            + raw_status_map.get(DocumentProcessingStatus.HASHED, 0)
        )
        queued = raw_status_map.get(DocumentProcessingStatus.QUEUED, 0)
        processing = (
            raw_status_map.get(DocumentProcessingStatus.EXTRACTING, 0)
            + raw_status_map.get(DocumentProcessingStatus.EXTRACTED, 0)
            + raw_status_map.get(DocumentProcessingStatus.MATCHING, 0)
        )
        review_required = raw_status_map.get(DocumentProcessingStatus.REVIEW_REQUIRED, 0)
        ready_for_approval = raw_status_map.get(DocumentProcessingStatus.READY_FOR_APPROVAL, 0)
        ready_to_post = raw_status_map.get(DocumentProcessingStatus.READY_TO_POST, 0)
        posted = raw_status_map.get(DocumentProcessingStatus.POSTED, 0)
        rejected = raw_status_map.get(DocumentProcessingStatus.REJECTED, 0)
        failed = raw_status_map.get(DocumentProcessingStatus.FAILED, 0)
        total_docs = sum(raw_status_map.values())

        status_counts = {
            "received": received,
            "queued": queued,
            "processing": processing,
            "review_required": review_required,
            "ready_for_approval": ready_for_approval,
            "ready_to_post": ready_to_post,
            "posted": posted,
            "rejected": rejected,
            "failed": failed,
            "total": total_docs,
        }

        # 2. Review flag counts across documents for this organization
        flags_stmt = (
            select(Document.review_flags)
            .where(
                and_(
                    Document.organization_id == organization_id,
                    Document.review_flags.isnot(None),
                )
            )
        )
        flag_rows = (await self.session.execute(flags_stmt)).scalars().all()
        flag_counts: Dict[str, int] = {flag.value: 0 for flag in ReviewFlag}
        for flags in flag_rows:
            if isinstance(flags, list):
                for f in flags:
                    if f in flag_counts:
                        flag_counts[f] += 1

        # 3. Queue operational metrics from BackgroundJob
        job_stmt = (
            select(BackgroundJob.status, func.count(BackgroundJob.id))
            .where(BackgroundJob.organization_id == organization_id)
            .group_by(BackgroundJob.status)
        )
        job_rows = (await self.session.execute(job_stmt)).all()
        raw_job_map = {row[0]: row[1] for row in job_rows}

        retrying_stmt = (
            select(func.count(BackgroundJob.id))
            .where(
                and_(
                    BackgroundJob.organization_id == organization_id,
                    BackgroundJob.attempt_count > 0,
                    BackgroundJob.status.in_(["PENDING", "RUNNING"]),
                )
            )
        )
        retrying_count = (await self.session.scalar(retrying_stmt)) or 0

        oldest_pending_stmt = (
            select(func.min(BackgroundJob.created_at))
            .where(
                and_(
                    BackgroundJob.organization_id == organization_id,
                    BackgroundJob.status == "PENDING",
                )
            )
        )
        oldest_pending_dt = await self.session.scalar(oldest_pending_stmt)
        now_dt = datetime.now(timezone.utc) if oldest_pending_dt and oldest_pending_dt.tzinfo else datetime.now()
        oldest_pending_seconds = int((now_dt - oldest_pending_dt).total_seconds()) if oldest_pending_dt else None

        oldest_running_stmt = (
            select(func.min(BackgroundJob.created_at))
            .where(
                and_(
                    BackgroundJob.organization_id == organization_id,
                    BackgroundJob.status == "RUNNING",
                )
            )
        )
        oldest_running_dt = await self.session.scalar(oldest_running_stmt)
        now_dt_running = datetime.now(timezone.utc) if oldest_running_dt and oldest_running_dt.tzinfo else datetime.now()
        oldest_running_seconds = int((now_dt_running - oldest_running_dt).total_seconds()) if oldest_running_dt else None

        near_max_stmt = (
            select(func.count(BackgroundJob.id))
            .where(
                and_(
                    BackgroundJob.organization_id == organization_id,
                    BackgroundJob.attempt_count >= (BackgroundJob.max_attempts - 1),
                    BackgroundJob.status.in_(["PENDING", "RUNNING", "FAILED"]),
                )
            )
        )
        near_max_count = (await self.session.scalar(near_max_stmt)) or 0

        latest_failure_stmt = (
            select(BackgroundJob)
            .where(
                and_(
                    BackgroundJob.organization_id == organization_id,
                    BackgroundJob.status == "FAILED",
                )
            )
            .order_by(BackgroundJob.created_at.desc())
            .limit(1)
        )
        latest_failed_job = await self.session.scalar(latest_failure_stmt)
        safe_latest_failure: Optional[SafeJobFailure] = None
        if latest_failed_job:
            safe_latest_failure = SafeJobFailure(
                job_type=latest_failed_job.job_type,
                failure_message=sanitize_error_message(latest_failed_job.last_error),
                attempt_count=latest_failed_job.attempt_count,
                failed_at=latest_failed_job.completed_at or latest_failed_job.created_at,
            )

        queue_health = QueueHealth(
            pending_count=raw_job_map.get("PENDING", 0),
            running_count=raw_job_map.get("RUNNING", 0),
            failed_count=raw_job_map.get("FAILED", 0),
            completed_count=raw_job_map.get("COMPLETED", 0),
            retrying_count=retrying_count,
            oldest_pending_seconds=oldest_pending_seconds,
            oldest_running_seconds=oldest_running_seconds,
            near_max_attempts_count=near_max_count,
            latest_failure=safe_latest_failure,
        )

        # 4. Actionable counts prioritising human operator workflows
        actionable_counts = {
            "needs_review": review_required + ready_for_approval,
            "ready_to_post": ready_to_post,
            "failed": failed,
            "retrying": retrying_count,
            "queued": queued,
            "processing": processing,
            "posted": posted,
        }

        return DocumentOperationsSummaryResponse(
            status_counts=status_counts,
            flag_counts=flag_counts,
            integrity_flags=flag_counts,
            queue_health=queue_health,
            actionable_counts=actionable_counts,
        )

    async def list_operational_documents(
        self,
        organization_id: uuid.UUID,
        processing_status: Optional[DocumentProcessingStatus] = None,
        action_filter: Optional[str] = None,
        source_channel: Optional[str] = None,
        document_type: Optional[DocumentType] = None,
        review_flag: Optional[str] = None,
        project_id: Optional[uuid.UUID] = None,
        counterparty_id: Optional[uuid.UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        failed_or_retrying: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
        page: int = 1,
        limit: int = 20,
    ) -> DocumentOperationalListResponse:
        """Returns paginated, filterable operational document worklist without N+1 query overhead."""
        filters = [Document.organization_id == organization_id]

        if processing_status:
            filters.append(Document.processing_status == processing_status)

        if action_filter:
            action = action_filter.upper()
            if action == "NEEDS_REVIEW":
                filters.append(
                    Document.processing_status.in_([
                        DocumentProcessingStatus.REVIEW_REQUIRED,
                        DocumentProcessingStatus.READY_FOR_APPROVAL,
                    ])
                )
            elif action == "READY_TO_POST":
                filters.append(Document.processing_status == DocumentProcessingStatus.READY_TO_POST)
            elif action == "POSTED":
                filters.append(Document.processing_status == DocumentProcessingStatus.POSTED)
            elif action == "FAILED":
                filters.append(Document.processing_status == DocumentProcessingStatus.FAILED)
            elif action == "QUEUED":
                filters.append(Document.processing_status == DocumentProcessingStatus.QUEUED)
            elif action == "PROCESSING":
                filters.append(
                    Document.processing_status.in_([
                        DocumentProcessingStatus.EXTRACTING,
                        DocumentProcessingStatus.EXTRACTED,
                        DocumentProcessingStatus.MATCHING,
                    ])
                )
            elif action == "RETRYING":
                filters.append(Document.processing_attempts > 0)

        if source_channel:
            filters.append(Document.source_channel == source_channel)

        if document_type:
            filters.append(Document.document_type == document_type)

        if failed_or_retrying:
            filters.append(
                or_(
                    Document.processing_status == DocumentProcessingStatus.FAILED,
                    Document.processing_attempts > 0,
                )
            )

        if review_flag:
            # Match review flag string within JSON column
            filters.append(cast(Document.review_flags, String).contains(review_flag))

        if project_id:
            # Match project linked via ProjectDocumentLink
            filters.append(
                Document.id.in_(
                    select(ProjectDocumentLink.document_id).where(
                        ProjectDocumentLink.project_id == project_id
                    )
                )
            )

        if counterparty_id:
            # Match counterparty reference within candidate transaction
            filters.append(cast(Document.candidate_transaction, String).contains(str(counterparty_id)))

        if date_from:
            filters.append(Document.created_at >= date_from)

        if date_to:
            filters.append(Document.created_at <= date_to)

        if search:
            clean_search = f"%{search.strip()}%"
            filters.append(
                or_(
                    Document.document_code.ilike(clean_search),
                    Document.file_name.ilike(clean_search),
                    cast(Document.extracted_data, String).ilike(clean_search),
                )
            )

        # Total count query
        count_stmt = select(func.count(Document.id)).where(and_(*filters))
        total = (await self.session.scalar(count_stmt)) or 0

        # Deterministic sorting
        sort_column = Document.created_at
        if sort_by == "document_code":
            sort_column = Document.document_code
        elif sort_by == "status":
            sort_column = Document.processing_status
        elif sort_by == "file_name":
            sort_column = Document.file_name

        order_clause = sort_column.asc() if sort_dir.lower() == "asc" else sort_column.desc()

        # Paginated fetch with joined converted transaction
        offset = max(0, (page - 1) * limit)
        list_stmt = (
            select(Document)
            .options(joinedload(Document.converted_transaction))
            .where(and_(*filters))
            .order_by(order_clause, Document.id.desc())
            .offset(offset)
            .limit(limit)
        )
        docs = (await self.session.execute(list_stmt)).scalars().unique().all()

        if not docs:
            pages = max(1, math.ceil(total / limit)) if total > 0 else 1
            return DocumentOperationalListResponse(
                items=[],
                total=total,
                page=page,
                limit=limit,
                pages=pages,
            )

        doc_ids = [d.id for d in docs]

        # Batch lookup 1: Project Document Links
        proj_link_stmt = (
            select(ProjectDocumentLink.document_id, Project.id, Project.project_code, Project.project_name)
            .join(Project, Project.id == ProjectDocumentLink.project_id)
            .where(
                and_(
                    ProjectDocumentLink.document_id.in_(doc_ids),
                    Project.organization_id == organization_id,
                )
            )
        )
        proj_link_rows = (await self.session.execute(proj_link_stmt)).all()
        doc_project_map: Dict[uuid.UUID, Dict[str, Any]] = {}
        for r in proj_link_rows:
            doc_project_map[r[0]] = {"id": r[1], "code": r[2], "name": r[3]}

        # Collect any candidate project IDs not linked in table
        candidate_proj_ids: Set[uuid.UUID] = set()
        candidate_cp_ids: Set[uuid.UUID] = set()
        for d in docs:
            cand = d.candidate_transaction or {}
            p_id = cand.get("project_id")
            if p_id and d.id not in doc_project_map:
                try:
                    candidate_proj_ids.add(uuid.UUID(str(p_id)))
                except (ValueError, TypeError):
                    pass
            c_id = cand.get("counterparty_id")
            if c_id:
                try:
                    candidate_cp_ids.add(uuid.UUID(str(c_id)))
                except (ValueError, TypeError):
                    pass

        # Batch lookup 2: Additional projects from candidate_transaction
        if candidate_proj_ids:
            proj_stmt = select(Project.id, Project.project_code, Project.project_name).where(
                and_(Project.id.in_(candidate_proj_ids), Project.organization_id == organization_id)
            )
            for r in (await self.session.execute(proj_stmt)).all():
                for d in docs:
                    if d.id not in doc_project_map and (d.candidate_transaction or {}).get("project_id") == str(r[0]):
                        doc_project_map[d.id] = {"id": r[0], "code": r[1], "name": r[2]}

        # Batch lookup 3: Counterparties from candidate_transaction
        counterparty_map: Dict[uuid.UUID, str] = {}
        if candidate_cp_ids:
            cp_stmt = select(Counterparty.id, Counterparty.name).where(
                and_(Counterparty.id.in_(candidate_cp_ids), Counterparty.organization_id == organization_id)
            )
            for r in (await self.session.execute(cp_stmt)).all():
                counterparty_map[r[0]] = r[1]

        # Batch lookup 4: Background jobs for these documents
        idempotency_keys = [f"DOCUMENT_PROCESS:{d.id}" for d in docs] + [f"DOCUMENT_POST:{d.id}" for d in docs]
        job_stmt = (
            select(BackgroundJob.idempotency_key, BackgroundJob.status)
            .where(
                and_(
                    BackgroundJob.organization_id == organization_id,
                    BackgroundJob.idempotency_key.in_(idempotency_keys),
                )
            )
        )
        job_rows = (await self.session.execute(job_stmt)).all()
        job_status_map: Dict[str, str] = {r[0]: r[1] for r in job_rows}

        now = datetime.now(timezone.utc)
        items: List[DocumentOperationalItem] = []
        for d in docs:
            # Derived age
            doc_created = d.created_at
            now_calc = now if doc_created.tzinfo else datetime.now()
            age_seconds = max(0, int((now_calc - doc_created).total_seconds()))
            age_disp = format_age_display(age_seconds)

            # Stuck detection based on operational thresholds
            is_stuck = False
            if d.processing_status == DocumentProcessingStatus.QUEUED and age_seconds > 900:  # > 15m
                is_stuck = True
            elif (
                d.processing_status in (DocumentProcessingStatus.EXTRACTING, DocumentProcessingStatus.MATCHING)
                and age_seconds > 600  # > 10m
            ):
                is_stuck = True

            # Candidate & extracted data
            cand = d.candidate_transaction or {}
            ext = d.extracted_data or {}

            # Amount
            amount_val: Optional[Decimal] = None
            raw_amt = cand.get("amount") or ext.get("total_amount")
            if raw_amt is not None:
                try:
                    amount_val = Decimal(str(raw_amt))
                except Exception:
                    amount_val = None

            # Counterparty
            cp_id: Optional[uuid.UUID] = None
            cp_name: Optional[str] = None
            raw_cp_id = cand.get("counterparty_id")
            if raw_cp_id:
                try:
                    cp_id = uuid.UUID(str(raw_cp_id))
                    cp_name = counterparty_map.get(cp_id)
                except (ValueError, TypeError):
                    pass
            if not cp_name:
                cp_name = ext.get("counterparty_name")

            # Project
            proj_data = doc_project_map.get(d.id, {})
            p_id = proj_data.get("id")
            p_code = proj_data.get("code")
            p_name = proj_data.get("name")

            # Converted transaction linkage
            conv_id = d.converted_transaction_id
            conv_code = d.converted_transaction.transaction_code if d.converted_transaction else None

            # Posting job status
            post_job_status = job_status_map.get(f"DOCUMENT_POST:{d.id}")

            # Actions permitted for this state
            can_review = d.processing_status in (
                DocumentProcessingStatus.REVIEW_REQUIRED,
                DocumentProcessingStatus.READY_FOR_APPROVAL,
            )
            can_retry = d.processing_status in (
                DocumentProcessingStatus.FAILED,
                DocumentProcessingStatus.REVIEW_REQUIRED,
            )
            can_post = d.processing_status == DocumentProcessingStatus.READY_TO_POST

            items.append(
                DocumentOperationalItem(
                    id=d.id,
                    organization_id=d.organization_id,
                    document_code=d.document_code,
                    file_name=d.file_name,
                    file_hash=d.file_hash,
                    file_size_bytes=d.file_size_bytes,
                    source_channel=d.source_channel,
                    document_type=d.document_type,
                    received_at=d.created_at,
                    updated_at=d.updated_at,
                    processing_status=d.processing_status,
                    review_flags=d.review_flags or [],
                    counterparty_name=cp_name,
                    counterparty_id=cp_id,
                    project_name=p_name,
                    project_code=p_code,
                    project_id=p_id,
                    amount=amount_val,
                    currency=ext.get("currency") or "IDR",
                    processing_attempts=d.processing_attempts,
                    failure_code=d.failure_code,
                    failure_message=sanitize_error_message(d.failure_message),
                    age_seconds=age_seconds,
                    age_display=age_disp,
                    is_stuck=is_stuck,
                    converted_transaction_id=conv_id,
                    converted_transaction_code=conv_code,
                    posting_job_status=post_job_status,
                    can_review=can_review,
                    can_retry=can_retry,
                    can_post=can_post,
                )
            )

        pages = max(1, math.ceil(total / limit)) if total > 0 else 1
        return DocumentOperationalListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
            pages=pages,
            total_pages=pages,
        )
