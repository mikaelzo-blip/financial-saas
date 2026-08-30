from datetime import date, datetime, timedelta, timezone
import uuid

from sqlalchemy import select, func

from tests.integration.test_whatsapp_intake_flow import wa, send
from src.models import Document, Project, Counterparty, WhatsAppClarificationSession, JournalEntry, DocumentCorrection
from src.models.enums import DocumentProcessingStatus, ProjectStatus
import pytest


async def review_document(wa, db_session):
    await send(wa)
    doc = await db_session.scalar(select(Document))
    customer = Counterparty(organization_id=doc.organization_id, name="Customer", is_customer=True, is_vendor=False)
    db_session.add(customer)
    await db_session.flush()
    project = Project(organization_id=doc.organization_id, project_code="P-WA-1", project_name="Ruko Thamrin", customer_id=customer.id, start_date=date.today(), project_status=ProjectStatus.ACTIVE)
    db_session.add(project)
    doc.candidate_transaction = {"id": str(uuid.uuid4()), "status": "REVIEW_REQUIRED", "amount": "150000.01"}
    doc.review_flags = ["PROJECT_UNKNOWN", "OCR_LOW_CONFIDENCE"]
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    await db_session.commit()
    await wa["service"].deliver_pending_notifications()
    return doc, project


async def test_clarification_never_approves_or_posts(wa, db_session):
    doc, project = await review_document(wa, db_session)
    session = await db_session.scalar(select(WhatsAppClarificationSession))
    assert session.status == "PENDING"
    assert "Ruko Thamrin" in wa["provider"].outbound[-1].body_text
    await send(wa, wamid="wamid.invalid-choice", text="debit cash credit sales")
    assert session.status == "PENDING"
    assert "pilihan" in wa["provider"].outbound[-1].body_text
    await send(wa, wamid="wamid.valid-choice", text="1")
    await db_session.refresh(session)
    await db_session.refresh(doc)
    assert session.status == "ANSWERED"
    assert doc.candidate_transaction["project_id"] == str(project.id)
    assert doc.candidate_transaction["amount"] == "150000.01"
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED
    assert doc.review_flags == ["PROJECT_UNKNOWN", "OCR_LOW_CONFIDENCE"]
    assert await db_session.scalar(select(func.count()).select_from(JournalEntry)) == 0
    assert await db_session.scalar(select(func.count()).select_from(DocumentCorrection)) == 1
    await send(wa, wamid="wamid.valid-choice", text="1")
    assert await db_session.scalar(select(func.count()).select_from(DocumentCorrection)) == 1


async def test_session_expiry_and_wrong_sender(wa, db_session):
    doc, project = await review_document(wa, db_session)
    session = await db_session.scalar(select(WhatsAppClarificationSession))
    response = await wa["client"].post("/api/v1/hermes/whatsapp/clarifications/reply", headers={"Authorization": "Bearer test-tenant-1"}, json={"phone_number": wa["phones"][1], "text": "1", "session_id": str(session.id)})
    assert response.status_code == 404
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()
    await wa["service"].deliver_pending_notifications()
    await db_session.refresh(session)
    assert session.status == "EXPIRED"
    assert "project_id" not in doc.candidate_transaction


@pytest.mark.parametrize("question,field,value", [("CONFIRM_AMOUNT", "amount", "123.4501"), ("SELECT_CATEGORY", "cost_category", "MAT")])
async def test_typed_choices_preserve_review_and_decimal(wa, db_session, question, field, value):
    await send(wa)
    doc = await db_session.scalar(select(Document))
    doc.processing_status = DocumentProcessingStatus.REVIEW_REQUIRED
    doc.candidate_transaction = {"id": str(uuid.uuid4()), "status": "REVIEW_REQUIRED"}
    doc.review_flags = ["OCR_LOW_CONFIDENCE"]
    doc.extracted_data = {"total_amount": "123.4501"}
    await db_session.commit()
    response = await wa["client"].post("/api/v1/hermes/whatsapp/clarifications/open", headers={"Authorization": "Bearer test-tenant-0"}, json={"phone_number": wa["phones"][0], "document_id": str(doc.id), "question_type": question})
    assert response.status_code == 200, response.text
    await wa["service"].deliver_pending_notifications()
    await send(wa, wamid="wamid.typed-choice-1", text="1")
    await db_session.refresh(doc)
    assert doc.candidate_transaction[field] == value
    assert doc.review_flags == ["OCR_LOW_CONFIDENCE"]
    assert doc.processing_status == DocumentProcessingStatus.REVIEW_REQUIRED


async def test_converted_document_is_immutable_to_chat(wa, db_session):
    doc, project = await review_document(wa, db_session)
    session = await db_session.scalar(select(WhatsAppClarificationSession))
    doc.candidate_transaction = {**doc.candidate_transaction, "converted_transaction_id": str(uuid.uuid4())}
    await db_session.commit()
    before = dict(doc.candidate_transaction)
    response = await wa["client"].post("/api/v1/hermes/whatsapp/clarifications/reply", headers={"Authorization": "Bearer test-tenant-0"}, json={"phone_number": wa["phones"][0], "text": "1", "session_id": str(session.id)})
    assert response.status_code == 409
    await db_session.refresh(doc)
    assert doc.candidate_transaction == before
