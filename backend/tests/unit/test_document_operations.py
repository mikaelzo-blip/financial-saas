import uuid
from datetime import datetime, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select

from src.models.organization import Organization
from src.models.user import User
from src.models.document import Document, ProjectDocumentLink
from src.models.project import Project
from src.models.counterparty import Counterparty
from src.models.transaction import Transaction
from src.models.background_job import BackgroundJob
from src.models.enums import (
    DocumentType,
    DocumentProcessingStatus,
    ReviewFlag,
    UserRole,
    TransactionType,
    WorkflowStatus,
)


@pytest.fixture
async def setup_ops_data(db_session):
    # Tenant A
    org_a = Organization(id=uuid.uuid4(), slug="org-a", legal_name="Organization A")
    user_a = User(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        email="operator@orga.test",
        full_name="Operator A",
        password_hash="pwd",
        role=UserRole.OPERATOR,
    )
    db_session.add_all([org_a, user_a])

    # Tenant B
    org_b = Organization(id=uuid.uuid4(), slug="org-b", legal_name="Organization B")
    user_b = User(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        email="operator@orgb.test",
        full_name="Operator B",
        password_hash="pwd",
        role=UserRole.OPERATOR,
    )
    db_session.add_all([org_b, user_b])
    await db_session.flush()

    # Project and Counterparties in Tenant A
    cust_a = Counterparty(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        is_customer=True,
        name="Owner Property",
    )
    cp_a = Counterparty(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        is_vendor=True,
        name="PT Semen Nusantara",
    )
    db_session.add_all([cust_a, cp_a])
    await db_session.flush()

    proj_a = Project(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        project_code="PRJ-001",
        project_name="Tower Construction",
        customer_id=cust_a.id,
        start_date=datetime.now().date(),
        original_contract_value=Decimal("100000000.00"),
    )
    db_session.add(proj_a)

    # Converted transaction for a posted document in Tenant A
    trx_a = Transaction(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        transaction_code="TRX-2026-000001",
        transaction_type=TransactionType.DIRECT_PURCHASE,
        transaction_date=datetime.now().date(),
        amount=Decimal("2500000.00"),
        description="Posted material invoice",
        workflow_status=WorkflowStatus.POSTED,
    )
    db_session.add(trx_a)
    await db_session.flush()

    # Documents in Tenant A
    # 1. Received / Uploaded
    doc_new = Document(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        document_code="DOC-2026-000001",
        document_type=DocumentType.RECEIPT,
        file_name="receipt_01.pdf",
        mime_type="application/pdf",
        file_size_bytes=10240,
        file_hash="hash01",
        storage_path="org-a/receipt_01.pdf",
        source_channel="WEB",
        processing_status=DocumentProcessingStatus.UPLOADED,
    )
    # 2. Queued
    doc_queued = Document(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        document_code="DOC-2026-000002",
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="invoice_vendor_1.pdf",
        mime_type="application/pdf",
        file_size_bytes=20480,
        file_hash="hash02",
        storage_path="org-a/invoice_vendor_1.pdf",
        source_channel="WHATSAPP",
        processing_status=DocumentProcessingStatus.QUEUED,
        created_at=datetime.now() - timedelta(minutes=25),
    )
    # 3. Processing (Extracting)
    doc_processing = Document(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        document_code="DOC-2026-000003",
        document_type=DocumentType.SURAT_JALAN,
        file_name="surat_jalan_1.pdf",
        mime_type="application/pdf",
        file_size_bytes=15000,
        file_hash="hash03",
        storage_path="org-a/surat_jalan_1.pdf",
        source_channel="WEB",
        processing_status=DocumentProcessingStatus.EXTRACTING,
        created_at=datetime.now() - timedelta(minutes=5),
    )
    # 4. Review Required with flags
    doc_review = Document(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        document_code="DOC-2026-000004",
        document_type=DocumentType.VENDOR_INVOICE,
        file_name="invoice_ambiguous.pdf",
        mime_type="application/pdf",
        file_size_bytes=30000,
        file_hash="hash04",
        storage_path="org-a/invoice_ambiguous.pdf",
        source_channel="WEB",
        processing_status=DocumentProcessingStatus.REVIEW_REQUIRED,
        review_flags=[ReviewFlag.AMBIGUOUS_MATCH.value, ReviewFlag.PROJECT_UNKNOWN.value],
        candidate_transaction={"counterparty_id": str(cp_a.id), "amount": "1500000.00"},
        extracted_data={"invoice_number": "INV-999", "counterparty_name": "PT Semen Nusantara"},
    )
    # 5. Ready to Post
    doc_ready = Document(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        document_code="DOC-2026-000005",
        document_type=DocumentType.RECEIPT,
        file_name="ready_to_post.pdf",
        mime_type="application/pdf",
        file_size_bytes=40000,
        file_hash="hash05",
        storage_path="org-a/ready_to_post.pdf",
        source_channel="API",
        processing_status=DocumentProcessingStatus.READY_TO_POST,
        candidate_transaction={"amount": "2500000.00", "project_id": str(proj_a.id)},
    )
    # 6. Posted with converted transaction
    doc_posted = Document(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        document_code="DOC-2026-000006",
        document_type=DocumentType.RECEIPT,
        file_name="posted_material.pdf",
        mime_type="application/pdf",
        file_size_bytes=50000,
        file_hash="hash06",
        storage_path="org-a/posted_material.pdf",
        source_channel="WEB",
        processing_status=DocumentProcessingStatus.POSTED,
        converted_transaction_id=trx_a.id,
        candidate_transaction={"amount": "2500000.00"},
    )
    # 7. Failed with safe error
    doc_failed = Document(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        document_code="DOC-2026-000007",
        document_type=DocumentType.RECEIPT,
        file_name="corrupt.pdf",
        mime_type="application/pdf",
        file_size_bytes=2000,
        file_hash="hash07",
        storage_path="org-a/corrupt.pdf",
        source_channel="WEB",
        processing_status=DocumentProcessingStatus.FAILED,
        processing_attempts=3,
        failure_code="OCR_CORRUPT_PAYLOAD",
        failure_message="File header signature corrupt or invalid format.",
    )

    # Document in Tenant B (cross-tenant data)
    doc_b = Document(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        document_code="DOC-2026-000099",
        document_type=DocumentType.RECEIPT,
        file_name="doc_tenant_b.pdf",
        mime_type="application/pdf",
        file_size_bytes=8000,
        file_hash="hash99",
        storage_path="org-b/doc_tenant_b.pdf",
        source_channel="WEB",
        processing_status=DocumentProcessingStatus.REVIEW_REQUIRED,
        review_flags=[ReviewFlag.DUPLICATE_SUSPECTED.value],
    )

    db_session.add_all([
        doc_new, doc_queued, doc_processing, doc_review, doc_ready, doc_posted, doc_failed, doc_b
    ])
    await db_session.flush()

    # Link doc_ready to project
    link = ProjectDocumentLink(project_id=proj_a.id, document_id=doc_ready.id)
    db_session.add(link)

    # Jobs in Tenant A
    # Pending job
    job_pending = BackgroundJob(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        job_type="DOCUMENT_PROCESS",
        idempotency_key=f"DOCUMENT_PROCESS:{doc_queued.id}",
        payload={"document_id": str(doc_queued.id)},
        status="PENDING",
        attempt_count=1,
        max_attempts=3,
        created_at=datetime.now() - timedelta(minutes=20),
    )
    # Failed job
    job_failed = BackgroundJob(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        job_type="DOCUMENT_PROCESS",
        idempotency_key=f"DOCUMENT_PROCESS:{doc_failed.id}",
        payload={"document_id": str(doc_failed.id)},
        status="FAILED",
        attempt_count=3,
        max_attempts=3,
        last_error="Corrupt payload in file parser.",
        created_at=datetime.now() - timedelta(hours=1),
    )
    # Job in Tenant B
    job_b = BackgroundJob(
        id=uuid.uuid4(),
        organization_id=org_b.id,
        job_type="DOCUMENT_PROCESS",
        idempotency_key=f"DOCUMENT_PROCESS:{doc_b.id}",
        payload={"document_id": str(doc_b.id)},
        status="FAILED",
        attempt_count=3,
        max_attempts=3,
        last_error="Secret key missing for org B: key_xyz123",
    )
    db_session.add_all([job_pending, job_failed, job_b])
    await db_session.flush()

    return {
        "org_a": org_a,
        "user_a": user_a,
        "org_b": org_b,
        "user_b": user_b,
        "doc_new": doc_new,
        "doc_queued": doc_queued,
        "doc_processing": doc_processing,
        "doc_review": doc_review,
        "doc_ready": doc_ready,
        "doc_posted": doc_posted,
        "doc_failed": doc_failed,
        "doc_b": doc_b,
        "proj_a": proj_a,
        "cp_a": cp_a,
        "trx_a": trx_a,
    }


@pytest.mark.asyncio
async def test_operational_summary_and_queue_health(db_session, setup_ops_data):
    from src.services.document_operations_service import DocumentOperationsService

    service = DocumentOperationsService(db_session)
    summary = await service.get_summary(setup_ops_data["org_a"].id)

    # 1. Summary status counts
    assert summary.status_counts["received"] == 1  # doc_new
    assert summary.status_counts["queued"] == 1  # doc_queued
    assert summary.status_counts["processing"] == 1  # doc_processing
    assert summary.status_counts["review_required"] == 1  # doc_review
    assert summary.status_counts["ready_to_post"] == 1  # doc_ready
    assert summary.status_counts["posted"] == 1  # doc_posted
    assert summary.status_counts["failed"] == 1  # doc_failed
    assert summary.status_counts["total"] == 7

    # 2. Review flags
    assert summary.flag_counts["AMBIGUOUS_MATCH"] == 1
    assert summary.flag_counts["PROJECT_UNKNOWN"] == 1
    # Org B flag must NOT be in Org A summary
    assert summary.flag_counts["DUPLICATE_SUSPECTED"] == 0

    # 3. Queue metrics
    assert summary.queue_health.pending_count == 1
    assert summary.queue_health.failed_count == 1
    assert summary.queue_health.retrying_count == 1  # job_pending has attempt_count=1
    assert summary.queue_health.near_max_attempts_count == 1  # job_failed has attempt_count=3 >= max-1
    assert summary.queue_health.oldest_pending_seconds is not None
    assert summary.queue_health.oldest_pending_seconds >= 1000

    # 4. Actionable counts
    assert summary.actionable_counts["needs_review"] == 1
    assert summary.actionable_counts["ready_to_post"] == 1
    assert summary.actionable_counts["failed"] == 1
    assert summary.actionable_counts["retrying"] == 1


@pytest.mark.asyncio
async def test_cross_tenant_isolation(db_session, setup_ops_data):
    from src.services.document_operations_service import DocumentOperationsService

    service = DocumentOperationsService(db_session)
    summary_b = await service.get_summary(setup_ops_data["org_b"].id)

    # Org B only has 1 document and 1 failed job
    assert summary_b.status_counts["total"] == 1
    assert summary_b.status_counts["review_required"] == 1
    assert summary_b.flag_counts["DUPLICATE_SUSPECTED"] == 1
    assert summary_b.flag_counts["AMBIGUOUS_MATCH"] == 0
    assert summary_b.queue_health.failed_count == 1
    assert summary_b.queue_health.pending_count == 0

    # List documents for Org B
    list_b = await service.list_operational_documents(setup_ops_data["org_b"].id)
    assert list_b.total == 1
    assert list_b.items[0].document_code == "DOC-2026-000099"


@pytest.mark.asyncio
async def test_operational_list_filtering_pagination_search(db_session, setup_ops_data):
    from src.services.document_operations_service import DocumentOperationsService

    service = DocumentOperationsService(db_session)
    org_id = setup_ops_data["org_a"].id

    # Filter by status: READY_TO_POST
    res_ready = await service.list_operational_documents(
        org_id, processing_status=DocumentProcessingStatus.READY_TO_POST
    )
    assert res_ready.total == 1
    assert res_ready.items[0].document_code == "DOC-2026-000005"
    assert res_ready.items[0].can_post is True
    assert res_ready.items[0].project_name == "Tower Construction"

    # Filter by source: WHATSAPP
    res_wa = await service.list_operational_documents(org_id, source_channel="WHATSAPP")
    assert res_wa.total == 1
    assert res_wa.items[0].document_code == "DOC-2026-000002"

    # Filter by review flag: AMBIGUOUS_MATCH
    res_flag = await service.list_operational_documents(org_id, review_flag="AMBIGUOUS_MATCH")
    assert res_flag.total == 1
    assert res_flag.items[0].document_code == "DOC-2026-000004"
    assert res_flag.items[0].counterparty_name == "PT Semen Nusantara"

    # Search by code
    res_search = await service.list_operational_documents(org_id, search="000007")
    assert res_search.total == 1
    assert res_search.items[0].document_code == "DOC-2026-000007"
    assert res_search.items[0].failure_code == "OCR_CORRUPT_PAYLOAD"
    assert res_search.items[0].can_retry is True

    # Search by filename
    res_search_fn = await service.list_operational_documents(org_id, search="posted_material")
    assert res_search_fn.total == 1
    assert res_search_fn.items[0].document_code == "DOC-2026-000006"
    assert res_search_fn.items[0].converted_transaction_code == "TRX-2026-000001"

    # Pagination
    res_page = await service.list_operational_documents(org_id, page=1, limit=3)
    assert res_page.total == 7
    assert len(res_page.items) == 3
    assert res_page.pages == 3

    # Project filter
    res_proj = await service.list_operational_documents(
        org_id, project_id=setup_ops_data["proj_a"].id
    )
    assert res_proj.total == 1
    assert res_proj.items[0].document_code == "DOC-2026-000005"

    # Counterparty filter
    res_cp = await service.list_operational_documents(
        org_id, counterparty_id=setup_ops_data["cp_a"].id
    )
    assert res_cp.total == 1
    assert res_cp.items[0].document_code == "DOC-2026-000004"

    # Sorting
    res_sort_asc = await service.list_operational_documents(
        org_id, sort_by="document_code", sort_dir="asc", limit=10
    )
    codes = [item.document_code for item in res_sort_asc.items]
    assert codes == sorted(codes)

    res_sort_desc = await service.list_operational_documents(
        org_id, sort_by="document_code", sort_dir="desc", limit=10
    )
    codes_desc = [item.document_code for item in res_sort_desc.items]
    assert codes_desc == sorted(codes, reverse=True)


@pytest.mark.asyncio
async def test_operational_endpoints_api(authenticated_client, setup_ops_data):
    org_id = str(setup_ops_data["org_a"].id)
    user_id = str(setup_ops_data["user_a"].id)
    headers = {
        "X-Organization-ID": org_id,
        "X-User-ID": user_id,
    }

    # 1. Summary endpoint
    res = await authenticated_client.get("/api/v1/operations/documents/summary", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status_counts"]["total"] == 7
    assert data["actionable_counts"]["ready_to_post"] == 1
    assert data["queue_health"]["pending_count"] == 1

    # 2. List endpoint
    res = await authenticated_client.get(
        "/api/v1/operations/documents?limit=5&page=1", headers=headers
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total"] == 7
    assert len(data["items"]) == 5
    assert data["page"] == 1

    # 3. Action filter: NEEDS_REVIEW
    res = await authenticated_client.get(
        "/api/v1/operations/documents?action_filter=NEEDS_REVIEW", headers=headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["processing_status"] == "REVIEW_REQUIRED"


def test_failure_message_sanitization():
    from src.services.document_operations_service import sanitize_error_message

    # 1. Password redaction
    assert "secretpass123" not in sanitize_error_message("Failed: password=secretpass123 at host")
    assert "password=[REDACTED]" in sanitize_error_message("Failed: password=secretpass123 at host")

    # 2. Secret redaction
    assert "topsecretval456" not in sanitize_error_message("Failed: secret=topsecretval456")
    assert "secret=[REDACTED]" in sanitize_error_message("Failed: secret=topsecretval456")

    # 3. Token redaction
    assert "tok_abc123456789" not in sanitize_error_message("Failed: token=tok_abc123456789")
    assert "token=[REDACTED]" in sanitize_error_message("Failed: token=tok_abc123456789")

    # 4. Bearer / Authorization header
    bearer_msg = sanitize_error_message("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
    assert "eyJhbGci" not in bearer_msg
    assert "[REDACTED]" in bearer_msg

    # 5. Database URL credentials
    db_msg = sanitize_error_message("Connection error: postgresql://admin:secret123@localhost:5432/db")
    assert "secret123" not in db_msg
    assert "[DATABASE_URL_REDACTED]" in db_msg

    # 6. Windows absolute file paths
    win_msg = sanitize_error_message("Path error at C:\\Users\\Admin\\AppData\\Local\\file.txt: not found")
    assert "C:\\Users" not in win_msg
    assert "[PATH]" in win_msg

    # 7. Unix absolute private paths
    unix_msg = sanitize_error_message("Path error at /home/ubuntu/app/secrets.env: unreadable")
    assert "/home/ubuntu" not in unix_msg
    assert "[PATH]" in unix_msg

    # 8. Traceback content truncation
    tb_msg = sanitize_error_message(
        "Traceback (most recent call last):\n  File \"app.py\", line 10\nValueError: secret"
    )
    assert "Traceback" not in tb_msg
    assert "app.py" not in tb_msg
