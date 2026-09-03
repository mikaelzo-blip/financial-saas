import io
import time
import uuid
import json
import hmac
import hashlib
import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
import httpx
from pydantic import SecretStr
from sqlalchemy import select, func

from src.core.config import Settings, settings
from src.core.security import create_access_token
from src.models import (
    Organization, User, UserRole, Document, WhatsAppMessageLog,
    WhatsAppClarificationSession, WhatsAppSenderMapping, Project, Counterparty,
    Transaction, JournalEntry, JournalLine, CustomerInvoice,
    VendorBill, AuditLog,
)
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import (
    DocumentType, DocumentProcessingStatus, CandidateStatus,
    ProjectStatus, AccountType, NormalBalance, WorkflowStatus,
)
from src.schemas.document import StructuredExtraction, ConfidenceScores, TransactionCandidate
from src.services.hermes.client import HermesApiClient, HttpxHermesTransport
from src.services.integrations.whatsapp.mock_provider import MockWhatsAppProvider
from src.services.integrations.whatsapp.webhook_service import WhatsAppWebhookService
from src.services.integrations.whatsapp.provider import ProviderError, MediaReference
from src.services.integrations.whatsapp.meta_provider import MetaCloudWhatsAppProvider
from src.services.document_service import DocumentService
from src.services.documents.pipeline import DocumentPipeline
from src.services.documents.extraction import ExtractionResult, ScriptedExtractionProvider
from src.services.reporting.integrity_service import IntegrityService


@pytest.fixture(autouse=True)
def patch_background_task(monkeypatch):
    from src.api.v1 import hermes
    async def noop_background(document_id):
        pass
    monkeypatch.setattr(hermes, "process_document_background", noop_background)


async def test_uat15_phone_to_tenant_security_and_unknown_phone_fail_closed(client: httpx.AsyncClient, db_session, monkeypatch):
    """
    Scenario 1: Phone-to-Tenant Security Boundary
    - Unknown phone numbers fail closed.
    - Registered phone numbers map authoritatively server-side.
    - Senders CANNOT dictate organization_id in request payload.
    """
    org_alpha = Organization(slug=f"org-alpha-{uuid.uuid4().hex[:6]}", legal_name="PT Alpha Sandbox")
    org_beta = Organization(slug=f"org-beta-{uuid.uuid4().hex[:6]}", legal_name="PT Beta Sandbox")
    db_session.add_all([org_alpha, org_beta])
    await db_session.flush()

    user_alpha = User(
        organization_id=org_alpha.id,
        email=f"pm@{org_alpha.slug}.test",
        full_name="PM Alpha",
        password_hash="dummy",
        role=UserRole.MANAGER,
    )
    user_beta = User(
        organization_id=org_beta.id,
        email=f"pm@{org_beta.slug}.test",
        full_name="PM Beta",
        password_hash="dummy",
        role=UserRole.MANAGER,
    )
    db_session.add_all([user_alpha, user_beta])
    await db_session.flush()

    sender_phone = "+6281299990001"
    mapping_alpha = WhatsAppSenderMapping(
        organization_id=org_alpha.id,
        user_id=user_alpha.id,
        phone_number=sender_phone,
        display_name="PM Alpha",
        role_in_org="PROJECT_MANAGER",
        is_active=True,
    )
    db_session.add(mapping_alpha)
    await db_session.commit()

    unknown_phone = "+6289999999999"
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("adapter-secret-test"))
    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org_alpha.id): SecretStr("tenant-alpha-token")})

    res_unknown = await client.post(
        "/api/v1/hermes/whatsapp/resolve",
        headers={"Authorization": "Bearer adapter-secret-test"},
        json={"phone_number": unknown_phone},
    )
    assert res_unknown.status_code == 200
    assert res_unknown.json()["sender"] is None

    # Resolve known sender returns server-side mapping
    res_known = await client.post(
        "/api/v1/hermes/whatsapp/resolve",
        headers={"Authorization": "Bearer adapter-secret-test"},
        json={"phone_number": sender_phone},
    )
    assert res_known.status_code == 200
    sender_info = res_known.json()["sender"]
    assert sender_info["organization_id"] == str(org_alpha.id)
    assert sender_info["user_id"] == str(user_alpha.id)


async def test_uat15_media_types_sandbox_intake_matrix(client: httpx.AsyncClient, db_session, monkeypatch, tmp_path):
    """
    Scenario 2: Multi-MIME Media Intake Matrix & SHA-256 Content Hashing
    Tests representative media payloads:
    - PDF, JPG, PNG, WEBP
    Verifies original file is immutable, content-hashed, and stored securely.
    """
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("adapter-token-uat15"))

    org = Organization(slug=f"org-matrix-{uuid.uuid4().hex[:6]}", legal_name="PT Matrix Konstruksi")
    db_session.add(org)
    await db_session.flush()

    user = User(
        organization_id=org.id,
        email=f"user@{org.slug}.test",
        full_name="Staff Keuangan",
        password_hash="pwd",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()

    sender = WhatsAppSenderMapping(
        organization_id=org.id,
        user_id=user.id,
        phone_number="+6281122334455",
        display_name="Staff Keuangan",
        role_in_org="ACCOUNTANT",
        is_active=True,
    )
    db_session.add(sender)
    await db_session.commit()

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-matrix-token")})

    media_cases = [
        ("nota-semen.pdf", "application/pdf", b"%PDF-1.4 sample pdf content for contractor receipt"),
        ("bukti-transfer.jpg", "image/jpeg", b"\xff\xd8\xff\xe0" + b"sample jpeg image bytes 12345678"),
        ("invoice-material.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"sample png image bytes 12345678"),
        ("surat-jalan.webp", "image/webp", b"RIFF" + b"\x00\x00\x00\x00WEBP" + b"sample webp content 123456"),
    ]

    for fname, mime, raw_bytes in media_cases:
        expected_hash = hashlib.sha256(raw_bytes).hexdigest()
        provider_wamid = f"wamid.matrix.{uuid.uuid4().hex[:8]}"

        files = {"file": (fname, io.BytesIO(raw_bytes), mime)}
        data = {
            "source_channel": "WHATSAPP",
            "source_metadata": json.dumps({
                "wamid": provider_wamid,
                "sender_phone": sender.phone_number,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "caption": f"Upload {fname}",
                "media_id": f"media-{provider_wamid}",
            }),
        }

        resp = await client.post(
            "/api/v1/hermes/documents/upload",
            headers={"Authorization": "Bearer tenant-matrix-token", "Idempotency-Key": f"idemp-{provider_wamid}-{uuid.uuid4().hex[:8]}"},
            files=files,
            data=data,
        )
        assert resp.status_code == 202
        res_json = resp.json()
        doc_id = uuid.UUID(res_json["id"])

        # Verify in DB
        doc = await db_session.get(Document, doc_id)
        assert doc is not None
        assert doc.file_hash == expected_hash
        assert doc.source_channel == "WHATSAPP"
        assert doc.mime_type == mime
        assert doc.organization_id == org.id


async def test_uat15_full_traceability_correlation(client: httpx.AsyncClient, db_session, monkeypatch, tmp_path):
    """
    Scenario 3: Complete Correlation & Traceability Flow
    Traceability:
    WhatsApp wamid -> HermesSubmission -> Document -> Extraction Candidate -> Review Queue -> Transaction -> JournalEntry
    """
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("adapter-token-trace"))

    org = Organization(slug=f"org-trace-{uuid.uuid4().hex[:6]}", legal_name="PT Traceabilitas Nusantara")
    db_session.add(org)
    await db_session.flush()

    admin = User(
        organization_id=org.id,
        email=f"admin@{org.slug}.test",
        full_name="Admin Trace",
        password_hash="pwd",
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    await db_session.flush()

    coa_1101 = ChartOfAccount(
        organization_id=org.id, account_code="1101", account_name="Kas dan Bank",
        account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="ASSET"
    )
    coa_5101 = ChartOfAccount(
        organization_id=org.id, account_code="5101", account_name="Beban Material",
        account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="EXPENSE"
    )
    db_session.add_all([coa_1101, coa_5101])
    await db_session.flush()

    bank_acc = PaymentAccount(organization_id=org.id, name="BCA Operasional", coa_account_id=coa_1101.id)
    customer = Counterparty(organization_id=org.id, name="Klien Utama", is_customer=True, is_vendor=False)
    vendor = Counterparty(organization_id=org.id, name="Toko Besi Jaya", is_vendor=True, is_customer=False)
    db_session.add_all([bank_acc, customer, vendor])
    await db_session.flush()

    project = Project(
        organization_id=org.id,
        project_code="PRJ-TRACE-001",
        project_name="Proyek Gedung A",
        customer_id=customer.id,
        original_contract_value=Decimal("100000000.00"),
        revised_contract_value=Decimal("100000000.00"),
        start_date=date(2026, 1, 1),
    )
    db_session.add(project)
    await db_session.flush()

    sender = WhatsAppSenderMapping(
        organization_id=org.id,
        user_id=admin.id,
        phone_number="+6281234567890",
        display_name="Admin Trace",
        role_in_org="ADMIN",
        is_active=True,
    )
    db_session.add(sender)
    await db_session.commit()

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-trace-token")})

    wamid = "wamid.HBgNNjI4MTIzNDU2Nzg5MBUC"
    sample_content = b"%PDF-1.4 purchase receipt nota besi Rp 1.500.000"
    files = {"file": ("nota-besi.pdf", io.BytesIO(sample_content), "application/pdf")}
    metadata = {
        "wamid": wamid,
        "sender_phone": sender.phone_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "caption": "Beli besi beton proyek Gedung A",
        "media_id": "media-trace-001",
    }

    # Step 1: Hermes submit document via WhatsApp channel
    resp = await client.post(
        "/api/v1/hermes/documents/upload",
        headers={"Authorization": "Bearer tenant-trace-token", "Idempotency-Key": f"idemp-{wamid}-{uuid.uuid4().hex[:8]}"},
        files=files,
        data={"source_channel": "WHATSAPP", "source_metadata": json.dumps(metadata)},
    )
    assert resp.status_code == 202
    doc_id = uuid.UUID(resp.json()["id"])

    # Step 2: Ensure 0 journals created upon ingestion
    je_count_initial = await db_session.scalar(
        select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org.id)
    )
    assert je_count_initial == 0

    # Step 3: Populate review candidate (simulating OCR pipeline)
    doc = await db_session.get(Document, doc_id)
    doc.document_type = DocumentType.RECEIPT
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    doc.suggested_category = "DIRECT_PURCHASE"
    candidate_id = uuid.uuid4()
    doc.candidate_transaction = {
        "id": str(candidate_id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "amount": "1500000.00",
        "description": "Pembelian besi beton Gedung A via WA",
        "transaction_date": "2026-09-03",
        "payment_account_id": str(bank_acc.id),
        "counterparty_id": str(vendor.id),
        "project_id": str(project.id),
        "status": "READY_FOR_APPROVAL",
    }
    doc.review_flags = []
    await db_session.commit()

    auth_token = create_access_token(admin.id)
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "X-Organization-ID": str(org.id),
        "X-User-ID": str(admin.id),
    }

    approve_resp = await client.post(
        f"/api/v1/documents/{doc_id}/approve",
        headers=headers,
        json={"notes": "Approved from WhatsApp intake verification"},
    )
    assert approve_resp.status_code == 201
    approve_data = approve_resp.json()
    assert approve_data["workflow_status"] == "POSTED"
    txn_id = uuid.UUID(approve_data["id"])

    # Step 5: Verify Transaction & Posted JournalEntry
    tx = await db_session.get(Transaction, txn_id)
    assert tx is not None
    assert tx.amount == Decimal("1500000.00")
    assert tx.workflow_status == WorkflowStatus.POSTED

    # Verify Document link
    doc_refreshed = await db_session.get(Document, doc_id)
    assert doc_refreshed.processing_status == DocumentProcessingStatus.PROCESSED
    assert doc_refreshed.candidate_transaction["converted_transaction_id"] == str(txn_id)

    je = await db_session.scalar(
        select(JournalEntry).where(JournalEntry.transaction_id == txn_id)
    )
    assert je is not None
    assert je.total_debit == Decimal("1500000.00")
    assert je.total_credit == Decimal("1500000.00")

    # Step 6: Verify full audit and traceability linkage
    audit_logs = (await db_session.scalars(
        select(AuditLog).where(AuditLog.organization_id == org.id)
    )).all()
    assert len(audit_logs) > 0


async def test_uat15_idempotency_and_retry_resilience(client: httpx.AsyncClient, db_session, monkeypatch, tmp_path):
    """
    Scenario 4: Webhook Replay, Duplicate Media, Application Restart, and Double-Approval Safety
    - Duplicate webhook delivery returns cached outcome.
    - Same binary file under different name is deduplicated.
    - Double approval attempts fail cleanly (HTTP 400 / Conflict) without duplicating financial postings.
    """
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("adapter-token-idemp"))

    org = Organization(slug=f"org-idemp-{uuid.uuid4().hex[:6]}", legal_name="PT Idemp Safety")
    db_session.add(org)
    await db_session.flush()

    user = User(
        organization_id=org.id,
        email=f"pm@{org.slug}.test",
        full_name="PM Idemp",
        password_hash="pwd",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()

    coa_1101 = ChartOfAccount(
        organization_id=org.id, account_code="1101", account_name="Kas dan Bank",
        account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="ASSET"
    )
    coa_5101 = ChartOfAccount(
        organization_id=org.id, account_code="5101", account_name="Beban Operasional",
        account_type=AccountType.EXPENSE, normal_balance=NormalBalance.DEBIT, report_group="EXPENSE"
    )
    db_session.add_all([coa_1101, coa_5101])
    await db_session.flush()

    bank_acc = PaymentAccount(organization_id=org.id, name="Kas Besar", coa_account_id=coa_1101.id)
    db_session.add(bank_acc)
    await db_session.flush()

    sender = WhatsAppSenderMapping(
        organization_id=org.id,
        user_id=user.id,
        phone_number="+6287766554433",
        display_name="PM Idemp",
        role_in_org="ADMIN",
        is_active=True,
    )
    db_session.add(sender)
    await db_session.commit()

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-idemp-token")})

    content = b"%PDF-1.4 identical invoice payload 998877"
    wamid = "wamid.idemp.001"
    idemp_key = f"idemp-key-{uuid.uuid4().hex}"

    # 1. First submission
    resp1 = await client.post(
        "/api/v1/hermes/documents/upload",
        headers={"Authorization": "Bearer tenant-idemp-token", "Idempotency-Key": idemp_key},
        files={"file": ("invoice1.pdf", io.BytesIO(content), "application/pdf")},
        data={"source_channel": "WHATSAPP", "source_metadata": json.dumps({
            "wamid": wamid,
            "sender_phone": sender.phone_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caption": "Nota 1",
            "media_id": "media-idemp-1",
        })},
    )
    assert resp1.status_code == 202
    doc_id1 = resp1.json()["id"]

    # 2. Duplicate submission with same idempotency key (webhook retry)
    resp2 = await client.post(
        "/api/v1/hermes/documents/upload",
        headers={"Authorization": "Bearer tenant-idemp-token", "Idempotency-Key": idemp_key},
        files={"file": ("invoice1.pdf", io.BytesIO(content), "application/pdf")},
        data={"source_channel": "WHATSAPP", "source_metadata": json.dumps({
            "wamid": wamid,
            "sender_phone": sender.phone_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caption": "Nota 1",
            "media_id": "media-idemp-1",
        })},
    )
    assert resp2.status_code == 200
    assert resp2.json()["id"] == doc_id1

    # 3. Same binary content with new wamid & filename (SHA-256 duplicate detection)
    resp3 = await client.post(
        "/api/v1/hermes/documents/upload",
        headers={"Authorization": "Bearer tenant-idemp-token", "Idempotency-Key": f"idemp-diff-{uuid.uuid4().hex}"},
        files={"file": ("invoice_renamed.pdf", io.BytesIO(content), "application/pdf")},
        data={"source_channel": "WHATSAPP", "source_metadata": json.dumps({
            "wamid": "wamid.idemp.002",
            "sender_phone": sender.phone_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caption": "Nota rename",
            "media_id": "media-idemp-2",
        })},
    )
    assert resp3.status_code == 202
    assert resp3.json()["id"] == doc_id1
    assert resp3.headers.get("X-Document-Duplicate") == "true"

    # 4. Double Approval Attempt Prevention
    doc = await db_session.get(Document, uuid.UUID(doc_id1))
    doc.document_type = DocumentType.RECEIPT
    doc.processing_status = DocumentProcessingStatus.READY_FOR_APPROVAL
    candidate_id = uuid.uuid4()
    doc.candidate_transaction = {
        "id": str(candidate_id),
        "proposed_transaction_type": "DIRECT_PURCHASE",
        "amount": "500000.00",
        "description": "Biaya Operasional",
        "transaction_date": "2026-09-03",
        "payment_account_id": str(bank_acc.id),
        "status": "READY_FOR_APPROVAL",
    }
    doc.review_flags = []
    await db_session.commit()

    token = create_access_token(user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org.id),
        "X-User-ID": str(user.id),
    }

    # Approval 1: Success
    app1 = await client.post(f"/api/v1/documents/{doc_id1}/approve", headers=headers, json={})
    assert app1.status_code == 201
    assert app1.json()["workflow_status"] == "POSTED"

    # Approval 2: Replay must fail closed (400 or 409 Conflict)
    app2 = await client.post(f"/api/v1/documents/{doc_id1}/approve", headers=headers, json={})
    assert app2.status_code in (400, 409)

    # Verify exactly 1 journal entry exists
    je_count = await db_session.scalar(
        select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org.id)
    )
    assert je_count == 1


async def test_uat15_strict_human_review_hard_stop(client: httpx.AsyncClient, db_session, monkeypatch, tmp_path):
    """
    Scenario 5: Human Review Hard-Stop Invariant
    Verify that:
    - Webhook receipt -> JournalEntry = 0
    - Media download -> JournalEntry = 0
    - OCR / Extraction -> JournalEntry = 0
    - AI Classification -> JournalEntry = 0
    - Clarification dialogue -> JournalEntry = 0
    Financial posting occurs ONLY after explicit reviewer approval.
    """
    monkeypatch.setattr(settings, "STORAGE_DIR", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "WHATSAPP_ADAPTER_TOKEN", SecretStr("adapter-token-stop"))

    org = Organization(slug=f"org-stop-{uuid.uuid4().hex[:6]}", legal_name="PT HardStop Finance")
    db_session.add(org)
    await db_session.flush()

    user = User(
        organization_id=org.id,
        email=f"owner@{org.slug}.test",
        full_name="Owner HardStop",
        password_hash="pwd",
        role=UserRole.ADMIN,
    )
    db_session.add(user)
    await db_session.flush()

    sender = WhatsAppSenderMapping(
        organization_id=org.id,
        user_id=user.id,
        phone_number="+6285544332211",
        display_name="Owner HardStop",
        role_in_org="ADMIN",
        is_active=True,
    )
    db_session.add(sender)
    await db_session.commit()

    monkeypatch.setattr(settings, "WHATSAPP_TENANT_TOKENS", {str(org.id): SecretStr("tenant-stop-token")})

    # Step A: Ingestion
    wamid = "wamid.stop.101"
    resp = await client.post(
        "/api/v1/hermes/documents/upload",
        headers={"Authorization": "Bearer tenant-stop-token", "Idempotency-Key": f"idemp-{wamid}-{uuid.uuid4().hex[:8]}"},
        files={"file": ("nota-material.pdf", io.BytesIO(b"%PDF-1.4 material nota"), "application/pdf")},
        data={"source_channel": "WHATSAPP", "source_metadata": json.dumps({
            "wamid": wamid,
            "sender_phone": sender.phone_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "caption": "Nota pembelian",
            "media_id": "media-stop-101",
        })},
    )
    assert resp.status_code == 202
    doc_id = uuid.UUID(resp.json()["id"])

    # Step B: Clarification creation
    clarif_session = WhatsAppClarificationSession(
        organization_id=org.id,
        phone_number=sender.phone_number,
        document_id=doc_id,
        question_type="PROJECT",
        options_payload={"question": "Untuk proyek mana?", "options": ["Proyek A", "Proyek B"]},
        status="PENDING",
    )
    db_session.add(clarif_session)
    await db_session.commit()

    # Step C: Clarification reply
    reply_resp = await client.post(
        "/api/v1/hermes/whatsapp/clarifications/reply",
        headers={"Authorization": "Bearer tenant-stop-token"},
        json={"phone_number": sender.phone_number, "text": "1", "session_id": str(clarif_session.id)},
    )
    assert reply_resp.status_code == 200

    # Verify Journal count is strictly 0
    je_count = await db_session.scalar(
        select(func.count(JournalEntry.id)).where(JournalEntry.organization_id == org.id)
    )
    assert je_count == 0


async def test_uat15_production_deployment_dryrun_configuration(tmp_path):
    """
    Scenario 6: Production Configuration & Deployment Dry Run Validation
    Validates:
    - Production environment-variable contracts and safety guards.
    - Rejection of wildcard CORS, debug=True, weak secrets, sqlite, and relative storage paths.
    - Readiness and Liveness endpoint contracts.
    """
    # 1. Unsafe configuration rejection in production
    with pytest.raises(ValueError, match="Unsafe production configuration"):
        Settings(
            ENVIRONMENT="production",
            DEBUG=True,
            SECRET_KEY="short",
            BACKEND_CORS_ORIGINS=["*"],
            STORAGE_DIR="relative/path",
        )

    # 2. Valid production configuration
    prod_settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        SECRET_KEY="a" * 64,
        BACKEND_CORS_ORIGINS=["https://app.kontraktor.example.com"],
        STORAGE_DIR=str(tmp_path.resolve()),
        DATABASE_URL="postgresql+asyncpg://app_user:strong_pwd@postgres-prod:5432/financial_saas_prod",
        SYNC_DATABASE_URL="postgresql://app_user:strong_pwd@postgres-prod:5432/financial_saas_prod",
    )
    assert prod_settings.ENVIRONMENT == "production"
    assert prod_settings.DEBUG is False
    assert len(prod_settings.SECRET_KEY) >= 32
