import uuid
from datetime import date
from decimal import Decimal
import pytest

from src.models.counterparty import Counterparty
from src.models.organization import Organization
from src.models.project import Project
from src.models.payable import VendorBill
from src.models.receivable import CustomerInvoice
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.enums import AccountType, NormalBalance, DocumentType
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path

from src.models.document import Document
from src.models.enums import DocumentProcessingStatus, CandidateStatus
from src.schemas.document import ConfidenceScores, StructuredExtraction, LineItem
from src.services.documents.pipeline import DocumentPipeline
from src.services.documents.extraction import ExtractionResult
from src.services.documents.matching import (
    normalize_doc_number,
    normalize_party_name,
    normalize_bank_reference,
    ConfidenceBand,
    MatchCandidate,
    MatchResult,
    match_counterparties,
    match_projects,
    match_vendor_bills,
    match_customer_invoices,
    compute_line_item_overlap,
    match_entities,
)


def test_normalize_doc_number():
    assert normalize_doc_number("  INV/2026/001  ") == "INV/2026/001"
    assert normalize_doc_number("inv-2026-001") == "INV-2026-001"
    assert normalize_doc_number("PO #12345") == "PO#12345"
    assert normalize_doc_number(None) == ""


def test_normalize_party_name():
    assert normalize_party_name("  PT.  Sumber   Makmur,  Tbk. ") == "pt sumber makmur tbk"
    assert normalize_party_name("CV. Maju Mapan") == "cv maju mapan"
    assert normalize_party_name(None) == ""


def test_normalize_bank_reference():
    assert normalize_bank_reference("  TRF-BCA 9876543210  ") == "TRF-BCA9876543210"
    assert normalize_bank_reference(None) == ""


def test_match_candidate_contract():
    candidate_id = uuid.uuid4()
    candidate = MatchCandidate(
        entity_type="VENDOR_BILL",
        entity_id=candidate_id,
        score=Decimal("0.95"),
        confidence_band=ConfidenceBand.HIGH,
        positive_signals=["EXACT_INVOICE_NUMBER", "EXACT_VENDOR", "EXACT_AMOUNT"],
        negative_signals=[],
        explanation="Matched VendorBill INV-001 with exact number, vendor, and amount.",
    )
    assert candidate.entity_type == "VENDOR_BILL"
    assert candidate.entity_id == candidate_id
    assert candidate.score == Decimal("0.95")
    assert candidate.confidence_band == ConfidenceBand.HIGH
    assert len(candidate.positive_signals) == 3
    assert candidate.negative_signals == []


@pytest.mark.asyncio
async def test_match_counterparty_exact_tax_id_beats_fuzzy_name(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-a", legal_name="Org A")
    db_session.add(org)

    vendor_a = Counterparty(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="PT Indo Perkasa Gemilang",
        tax_id="01.234.567.8-999.000",
        is_vendor=True,
        is_active=True,
    )
    vendor_b = Counterparty(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="PT Indo Perkasa Sejahtera",
        tax_id="99.999.999.9-999.000",
        is_vendor=True,
        is_active=True,
    )
    db_session.add_all([vendor_a, vendor_b])
    await db_session.flush()

    # Extraction has vendor_b's fuzzy name ("PT Indo Perkasa S") but vendor_a's exact NPWP
    data = StructuredExtraction(
        issuer_name="PT Indo Perkasa S",
        raw_text="NPWP: 01.234.567.8-999.000",
    )
    candidates = await match_counterparties(db_session, org.id, data)

    assert len(candidates) > 0
    top = candidates[0]
    assert top.entity_id == vendor_a.id
    assert "EXACT_TAX_ID" in top.positive_signals
    assert top.confidence_band == ConfidenceBand.HIGH


@pytest.mark.asyncio
async def test_match_counterparty_fuzzy_name_capped_at_medium(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-b", legal_name="Org B")
    db_session.add(org)

    vendor = Counterparty(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="PT Bangun Cipta Pratama",
        is_vendor=True,
        is_active=True,
    )
    db_session.add(vendor)
    await db_session.flush()

    data = StructuredExtraction(
        issuer_name="PT Bangun Cipta Pratama Raya",
    )
    candidates = await match_counterparties(db_session, org.id, data)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.entity_id == vendor.id
    # Must NOT be HIGH confidence when only fuzzy string similarity matched
    assert candidate.confidence_band == ConfidenceBand.MEDIUM


@pytest.mark.asyncio
async def test_match_counterparty_generic_short_names_prevent_false_high(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-c", legal_name="Org C")
    db_session.add(org)

    vendor = Counterparty(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="PT Maju Jaya",
        is_vendor=True,
        is_active=True,
    )
    db_session.add(vendor)
    await db_session.flush()

    data = StructuredExtraction(
        issuer_name="CV Maju",
    )
    candidates = await match_counterparties(db_session, org.id, data)
    for c in candidates:
        assert c.confidence_band != ConfidenceBand.HIGH


@pytest.mark.asyncio
async def test_match_counterparty_exact_bank_account(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-d", legal_name="Org D")
    db_session.add(org)

    vendor = Counterparty(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="PT Sumber Logam",
        bank_accounts=[{"bank_name": "BCA", "account_number": "1234567890"}],
        is_vendor=True,
        is_active=True,
    )
    db_session.add(vendor)
    await db_session.flush()

    data = StructuredExtraction(
        destination_account_number="1234567890",
        destination_bank="BCA",
    )
    candidates = await match_counterparties(db_session, org.id, data)

    assert len(candidates) >= 1
    assert candidates[0].entity_id == vendor.id
    assert "EXACT_BANK_ACCOUNT" in candidates[0].positive_signals
    assert candidates[0].confidence_band == ConfidenceBand.HIGH


@pytest.mark.asyncio
async def test_match_counterparty_tenant_isolation(db_session):
    org_1 = Organization(id=uuid.uuid4(), slug="org-1", legal_name="Org 1")
    org_2 = Organization(id=uuid.uuid4(), slug="org-2", legal_name="Org 2")
    db_session.add_all([org_1, org_2])

    vendor_org_2 = Counterparty(
        id=uuid.uuid4(),
        organization_id=org_2.id,
        name="PT Rahasia Org Lain",
        tax_id="11.222.333.4-555.000",
        is_vendor=True,
        is_active=True,
    )
    db_session.add(vendor_org_2)
    await db_session.flush()

    data = StructuredExtraction(
        issuer_name="PT Rahasia Org Lain",
        raw_text="NPWP 11.222.333.4-555.000",
    )
    # Query for org_1
    candidates = await match_counterparties(db_session, org_1.id, data)
    assert len(candidates) == 0


@pytest.mark.asyncio
async def test_match_project_exact_project_code(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-proj-1", legal_name="Org P1")
    customer = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="Client A", is_customer=True, is_active=True)
    proj = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-2026-001",
        project_name="Pembangunan Gedung Kantor A",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
    )
    db_session.add_all([org, customer, proj])
    await db_session.flush()

    data = StructuredExtraction(
        project_reference="PRJ-2026-001",
    )
    candidates = await match_projects(db_session, org.id, data)
    assert len(candidates) == 1
    assert candidates[0].entity_id == proj.id
    assert "EXACT_PROJECT_CODE" in candidates[0].positive_signals
    assert candidates[0].confidence_band == ConfidenceBand.HIGH


@pytest.mark.asyncio
async def test_match_project_exact_po_spk(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-proj-2", legal_name="Org P2")
    customer = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="Client B", is_customer=True, is_active=True)
    proj = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-2026-002",
        project_name="Jalan Tol Ruas B",
        customer_id=customer.id,
        po_spk_no="SPK/TOL/2026/088",
        start_date=date(2026, 1, 1),
    )
    db_session.add_all([org, customer, proj])
    await db_session.flush()

    data = StructuredExtraction(
        spk_number="SPK/TOL/2026/088",
    )
    candidates = await match_projects(db_session, org.id, data)
    assert len(candidates) == 1
    assert candidates[0].entity_id == proj.id
    assert "EXACT_PO_SPK" in candidates[0].positive_signals
    assert candidates[0].confidence_band == ConfidenceBand.HIGH


@pytest.mark.asyncio
async def test_match_project_fuzzy_name_supporting_only(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-proj-3", legal_name="Org P3")
    customer = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="Client C", is_customer=True, is_active=True)
    proj = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-2026-003",
        project_name="Renovasi Jembatan Ciliwung Barat",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
    )
    db_session.add_all([org, customer, proj])
    await db_session.flush()

    data = StructuredExtraction(
        description="Pekerjaan Renovasi Jembatan Ciliwung Barat Tahap 1",
    )
    candidates = await match_projects(db_session, org.id, data)
    assert len(candidates) >= 1
    assert candidates[0].confidence_band == ConfidenceBand.MEDIUM


@pytest.mark.asyncio
async def test_match_project_tenant_isolation(db_session):
    org_1 = Organization(id=uuid.uuid4(), slug="org-proj-t1", legal_name="Org T1")
    org_2 = Organization(id=uuid.uuid4(), slug="org-proj-t2", legal_name="Org T2")
    customer_2 = Counterparty(id=uuid.uuid4(), organization_id=org_2.id, name="Client T2", is_customer=True, is_active=True)
    proj_2 = Project(
        id=uuid.uuid4(),
        organization_id=org_2.id,
        project_code="PRJ-SECRET-999",
        project_name="Proyek Rahasia",
        customer_id=customer_2.id,
        start_date=date(2026, 1, 1),
    )
    db_session.add_all([org_1, org_2, customer_2, proj_2])
    await db_session.flush()

    data = StructuredExtraction(project_reference="PRJ-SECRET-999")
    candidates = await match_projects(db_session, org_1.id, data)
    assert len(candidates) == 0


@pytest.mark.asyncio
async def test_match_vendor_bill_exact(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-vb-1", legal_name="Org VB1")
    vendor = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Semen Gresik", is_vendor=True, is_active=True)
    bill = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="INV-SG-2026-001",
        vendor_id=vendor.id,
        bill_date=date(2026, 3, 1),
        due_date=date(2026, 3, 31),
        total_amount=Decimal("15000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, vendor, bill])
    await db_session.flush()

    data = StructuredExtraction(
        invoice_number="INV-SG-2026-001",
        issuer_name="PT Semen Gresik",
        total_amount=Decimal("15000000.00"),
        transaction_date=date(2026, 3, 2),
    )
    res = await match_vendor_bills(db_session, org.id, data, matched_counterparty_id=vendor.id)
    assert len(res.ranked_candidates) == 1
    top = res.ranked_candidates[0]
    assert top.entity_id == bill.id
    assert "EXACT_INVOICE_NUMBER" in top.positive_signals
    assert "EXACT_VENDOR" in top.positive_signals
    assert "EXACT_AMOUNT" in top.positive_signals
    assert top.confidence_band == ConfidenceBand.HIGH
    assert not res.ambiguous


@pytest.mark.asyncio
async def test_match_customer_invoice_exact(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-ci-1", legal_name="Org CI1")
    customer = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Waskita Karya", is_customer=True, is_active=True)
    proj = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-WAS-01",
        project_name="Gedung Waskita",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
    )
    inv = CustomerInvoice(
        id=uuid.uuid4(),
        organization_id=org.id,
        invoice_code="INV-CI-2026-999",
        customer_id=customer.id,
        project_id=proj.id,
        invoice_date=date(2026, 4, 10),
        due_date=date(2026, 5, 10),
        total_amount=Decimal("50000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, customer, proj, inv])
    await db_session.flush()

    data = StructuredExtraction(
        invoice_number="INV-CI-2026-999",
        recipient_name="PT Waskita Karya",
        total_amount=Decimal("50000000.00"),
        transaction_date=date(2026, 4, 12),
    )
    res = await match_customer_invoices(db_session, org.id, data, matched_counterparty_id=customer.id)
    assert len(res.ranked_candidates) == 1
    top = res.ranked_candidates[0]
    assert top.entity_id == inv.id
    assert "EXACT_INVOICE_NUMBER" in top.positive_signals
    assert "EXACT_CUSTOMER" in top.positive_signals
    assert "EXACT_AMOUNT" in top.positive_signals
    assert top.confidence_band == ConfidenceBand.HIGH


@pytest.mark.asyncio
async def test_match_closed_invoice_and_bill_excluded(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-closed", legal_name="Org Closed")
    customer = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="Cust Closed", is_customer=True, is_active=True)
    vendor = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="Vend Closed", is_vendor=True, is_active=True)
    proj = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-CLOSED",
        project_name="Proyek Selesai",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
    )
    paid_inv = CustomerInvoice(
        id=uuid.uuid4(),
        organization_id=org.id,
        invoice_code="INV-PAID-001",
        customer_id=customer.id,
        project_id=proj.id,
        invoice_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        total_amount=Decimal("10000000.00"),
        status="PAID",
    )
    cancelled_bill = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="BILL-CANC-001",
        vendor_id=vendor.id,
        bill_date=date(2026, 1, 1),
        due_date=date(2026, 1, 31),
        total_amount=Decimal("10000000.00"),
        status="CANCELLED",
    )
    db_session.add_all([org, customer, vendor, proj, paid_inv, cancelled_bill])
    await db_session.flush()

    data_inv = StructuredExtraction(invoice_number="INV-PAID-001", total_amount=Decimal("10000000.00"))
    res_inv = await match_customer_invoices(db_session, org.id, data_inv)
    assert len(res_inv.ranked_candidates) == 0

    data_bill = StructuredExtraction(invoice_number="BILL-CANC-001", total_amount=Decimal("10000000.00"))
    res_bill = await match_vendor_bills(db_session, org.id, data_bill)
    assert len(res_bill.ranked_candidates) == 0


@pytest.mark.asyncio
async def test_match_invoice_cross_tenant_isolation(db_session):
    org_1 = Organization(id=uuid.uuid4(), slug="org-cross-1", legal_name="Org Cross 1")
    org_2 = Organization(id=uuid.uuid4(), slug="org-cross-2", legal_name="Org Cross 2")
    vendor_2 = Counterparty(id=uuid.uuid4(), organization_id=org_2.id, name="PT Vendor Org 2", is_vendor=True, is_active=True)
    bill_2 = VendorBill(
        id=uuid.uuid4(),
        organization_id=org_2.id,
        bill_code="INV-SECRET-TENANT-2",
        vendor_id=vendor_2.id,
        bill_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("99000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org_1, org_2, vendor_2, bill_2])
    await db_session.flush()

    # Org 1 tries to match a document with Org 2's bill_code and amount
    data = StructuredExtraction(
        invoice_number="INV-SECRET-TENANT-2",
        total_amount=Decimal("99000000.00"),
    )
    res = await match_vendor_bills(db_session, org_1.id, data)
    assert len(res.ranked_candidates) == 0
    assert res.primary_candidate is None



@pytest.mark.asyncio
async def test_match_invoice_amount_conflict_records_negative_signal(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-conf", legal_name="Org Conf")
    vendor = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Baja Utama", is_vendor=True, is_active=True)
    bill = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="INV-BAJA-777",
        vendor_id=vendor.id,
        bill_date=date(2026, 5, 1),
        due_date=date(2026, 5, 31),
        total_amount=Decimal("20000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, vendor, bill])
    await db_session.flush()

    # Document has matching number but different amount (25,000,000 vs 20,000,000)
    data = StructuredExtraction(
        invoice_number="INV-BAJA-777",
        issuer_name="PT Baja Utama",
        total_amount=Decimal("25000000.00"),
    )
    res = await match_vendor_bills(db_session, org.id, data, matched_counterparty_id=vendor.id)
    assert len(res.ranked_candidates) == 1
    top = res.ranked_candidates[0]
    assert "AMOUNT_MISMATCH" in top.negative_signals
    # Must not be HIGH confidence with amount conflict
    assert top.confidence_band != ConfidenceBand.HIGH


@pytest.mark.asyncio
async def test_match_invoice_wrong_counterparty_conflict(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-wrong-v", legal_name="Org Wrong V")
    vendor_actual = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Vendor Asli", is_vendor=True, is_active=True)
    vendor_other = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Vendor Lain", is_vendor=True, is_active=True)
    bill = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="INV-COMMON-123",
        vendor_id=vendor_actual.id,
        bill_date=date(2026, 5, 1),
        due_date=date(2026, 5, 31),
        total_amount=Decimal("10000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, vendor_actual, vendor_other, bill])
    await db_session.flush()

    # Document says it's from vendor_other
    data = StructuredExtraction(
        invoice_number="INV-COMMON-123",
        issuer_name="PT Vendor Lain",
        total_amount=Decimal("10000000.00"),
    )
    res = await match_vendor_bills(db_session, org.id, data, matched_counterparty_id=vendor_other.id)
    assert len(res.ranked_candidates) == 1
    top = res.ranked_candidates[0]
    assert "COUNTERPARTY_MISMATCH" in top.negative_signals
    assert top.confidence_band == ConfidenceBand.LOW


@pytest.mark.asyncio
async def test_match_ambiguous_invoices(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-ambig", legal_name="Org Ambig")
    vendor = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Pemasok Beton", is_vendor=True, is_active=True)
    bill_1 = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="INV-BETON-A",
        vendor_id=vendor.id,
        bill_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        total_amount=Decimal("10000000.00"),
        status="UNPAID",
    )
    bill_2 = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="INV-BETON-B",
        vendor_id=vendor.id,
        bill_date=date(2026, 6, 2),
        due_date=date(2026, 7, 1),
        total_amount=Decimal("10000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, vendor, bill_1, bill_2])
    await db_session.flush()

    # Document only has amount and vendor, but no invoice number
    data = StructuredExtraction(
        issuer_name="PT Pemasok Beton",
        total_amount=Decimal("10000000.00"),
        transaction_date=date(2026, 6, 2),
    )
    res = await match_vendor_bills(db_session, org.id, data, matched_counterparty_id=vendor.id)
    assert len(res.ranked_candidates) == 2
    assert res.ambiguous is True
    assert res.requires_review is True


def test_line_item_overlap_supporting_signal():
    items = [
        LineItem(description="Semen Gresik 50kg", quantity=Decimal("100"), line_total=Decimal("7000000.00")),
        LineItem(description="Pasir Beton", quantity=Decimal("5"), line_total=Decimal("1500000.00")),
    ]
    ref_text = "Pengadaan Semen Gresik dan Pasir Beton untuk cor lantai 2"
    overlap = compute_line_item_overlap(items, ref_text)
    assert overlap > 0.5

    no_match_text = "Jasa Desain Arsitektur Landscape"
    no_overlap = compute_line_item_overlap(items, no_match_text)
    assert no_overlap == 0.0


@pytest.mark.asyncio
async def test_match_entities_transfer_proof_to_open_customer_invoice(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-trf-ar", legal_name="Org TRF AR")
    customer = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Pelanggan Setia", is_customer=True, is_active=True)
    proj = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-TRF-01",
        project_name="Proyek Pelanggan",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
    )
    coa = ChartOfAccount(
        id=uuid.uuid4(),
        organization_id=org.id,
        account_code="1101-BCA",
        account_name="Kas BCA",
        account_type=AccountType.ASSET,
        normal_balance=NormalBalance.DEBIT,
        report_group="Kas & Bank",
    )
    pay_acc = PaymentAccount(
        id=uuid.uuid4(),
        organization_id=org.id,
        coa_account_id=coa.id,
        name="BCA Operasional",
        bank_name="BCA",
        account_number="5544332211",
        is_active=True,
    )
    inv = CustomerInvoice(
        id=uuid.uuid4(),
        organization_id=org.id,
        invoice_code="INV-AR-2026-101",
        customer_id=customer.id,
        project_id=proj.id,
        invoice_date=date(2026, 6, 1),
        due_date=date(2026, 6, 30),
        total_amount=Decimal("35000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, customer, proj, coa, pay_acc, inv])
    await db_session.flush()

    data = StructuredExtraction(
        issuer_name="PT Pelanggan Setia",
        destination_bank="BCA",
        destination_account_number="5544332211",
        total_amount=Decimal("35000000.00"),
        transfer_reference="INV-AR-2026-101",
        transaction_date=date(2026, 6, 2),
    )
    matches = await match_entities(db_session, org.id, data, document_type=DocumentType.TRANSFER_PROOF)

    assert matches["counterparty_id"] == str(customer.id)
    assert matches["counterparty_role"] == "CUSTOMER"
    assert matches["payment_account_id"] == str(pay_acc.id)
    assert matches["allocation_target_id"] == str(inv.id)
    assert matches["allocation_target_type"] == "CUSTOMER_INVOICE"
    assert matches["ambiguous"] is False


@pytest.mark.asyncio
async def test_match_entities_transfer_proof_to_open_vendor_bill(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-trf-ap", legal_name="Org TRF AP")
    vendor = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Supplier Utama", is_vendor=True, is_active=True)
    bill = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="BILL-AP-2026-202",
        vendor_id=vendor.id,
        bill_date=date(2026, 7, 1),
        due_date=date(2026, 7, 31),
        total_amount=Decimal("12000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, vendor, bill])
    await db_session.flush()

    data = StructuredExtraction(
        recipient_name="PT Supplier Utama",
        invoice_number="BILL-AP-2026-202",
        total_amount=Decimal("12000000.00"),
        transaction_date=date(2026, 7, 2),
    )
    matches = await match_entities(db_session, org.id, data, document_type=DocumentType.TRANSFER_PROOF)

    assert matches["counterparty_id"] == str(vendor.id)
    assert matches["counterparty_role"] == "VENDOR"
    assert matches["allocation_target_id"] == str(bill.id)
    assert matches["allocation_target_type"] == "VENDOR_BILL"


@pytest.mark.asyncio
async def test_match_entities_ambiguous_does_not_set_allocation_target(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-trf-ambig", legal_name="Org TRF Ambig")
    customer = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Klien Ganda", is_customer=True, is_active=True)
    proj = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        project_code="PRJ-GANDA",
        project_name="Proyek Ganda",
        customer_id=customer.id,
        start_date=date(2026, 1, 1),
    )
    inv1 = CustomerInvoice(
        id=uuid.uuid4(),
        organization_id=org.id,
        invoice_code="INV-GANDA-1",
        customer_id=customer.id,
        project_id=proj.id,
        invoice_date=date(2026, 8, 1),
        due_date=date(2026, 8, 31),
        total_amount=Decimal("20000000.00"),
        status="UNPAID",
    )
    inv2 = CustomerInvoice(
        id=uuid.uuid4(),
        organization_id=org.id,
        invoice_code="INV-GANDA-2",
        customer_id=customer.id,
        project_id=proj.id,
        invoice_date=date(2026, 8, 2),
        due_date=date(2026, 9, 1),
        total_amount=Decimal("20000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, customer, proj, inv1, inv2])
    await db_session.flush()

    # Transfer has same amount and customer, but no invoice number reference
    data = StructuredExtraction(
        issuer_name="PT Klien Ganda",
        total_amount=Decimal("20000000.00"),
        transaction_date=date(2026, 8, 2),
    )
    matches = await match_entities(db_session, org.id, data, document_type=DocumentType.TRANSFER_PROOF)

    assert matches["ambiguous"] is True
    assert matches["requires_review"] is True
    # Must NOT silently choose one candidate as authoritative target when ambiguous!
    assert matches.get("allocation_target_id") is None


@pytest.mark.asyncio
async def test_match_entities_no_match_requires_review(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-none", legal_name="Org None")
    db_session.add(org)
    await db_session.flush()

    data = StructuredExtraction(
        issuer_name="PT Entitas Asing",
        total_amount=Decimal("99999999.00"),
    )
    matches = await match_entities(db_session, org.id, data)
    assert matches["counterparty_id"] is None
    assert matches["requires_review"] is True


@pytest.mark.asyncio
async def test_match_entities_deterministic_output_ordering(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-determ", legal_name="Org Determ")
    vendor1 = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Pemasok Alfa", is_vendor=True, is_active=True)
    vendor2 = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Pemasok Beta", is_vendor=True, is_active=True)
    db_session.add_all([org, vendor1, vendor2])
    await db_session.flush()

    data = StructuredExtraction(issuer_name="PT Pemasok Alfa")
    run1 = await match_entities(db_session, org.id, data)
    run2 = await match_entities(db_session, org.id, data)

    assert run1["counterparty_id"] == run2["counterparty_id"]
    assert run1["alternatives"] == run2["alternatives"]


@pytest.mark.asyncio
async def test_pipeline_matching_populates_allocation_target(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-pipe-match", legal_name="Org Pipe")
    vendor = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Supplier Pipa", is_vendor=True, is_active=True)
    bill = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="BILL-PIPA-900",
        vendor_id=vendor.id,
        bill_date=date(2026, 8, 1),
        due_date=date(2026, 8, 31),
        total_amount=Decimal("18000000.00"),
        status="UNPAID",
    )
    doc = Document(
        id=uuid.uuid4(),
        organization_id=org.id,
        document_code="DOC-PIPA-001",
        document_type=DocumentType.TRANSFER_PROOF,
        file_name="bukti_trf_pipa.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1024,
        file_hash="hashpipa123",
        source_channel="MANUAL_UPLOAD",
        storage_path="uploads/bukti_trf_pipa.jpg",
        processing_status=DocumentProcessingStatus.UPLOADED,
    )
    db_session.add_all([org, vendor, bill, doc])
    await db_session.flush()

    extraction_data = {
        "recipient_name": "PT Supplier Pipa",
        "invoice_number": "BILL-PIPA-900",
        "total_amount": "18000000.00",
        "transaction_date": "2026-08-02",
        "field_evidence": {},
    }
    confidence = ConfidenceScores(
        ocr_confidence=Decimal("0.95"),
        document_type_confidence=Decimal("0.95"),
        entity_confidence=Decimal("0.95"),
        project_confidence=Decimal("0.90"),
        amount_confidence=Decimal("0.98"),
    )
    mock_result = ExtractionResult(
        document_type=DocumentType.TRANSFER_PROOF,
        data=extraction_data,
        confidence=confidence,
        raw_payload={},
        provider_name="MockProvider",
        provider_version="1.0",
    )

    mock_provider = MagicMock()
    mock_provider.extract = AsyncMock(return_value=mock_result)

    pipeline = DocumentPipeline(db_session, mock_provider)
    processed_doc = await pipeline.process(doc, Path("/dummy/path.jpg"))

    assert processed_doc.matching_results.get("allocation_target_id") == str(bill.id)
    assert processed_doc.candidate_transaction.get("allocation_target_id") == str(bill.id)
    assert processed_doc.candidate_transaction.get("counterparty_id") == str(vendor.id)


@pytest.mark.asyncio
async def test_matching_failure_does_not_destroy_extracted_data(db_session, monkeypatch):
    org = Organization(id=uuid.uuid4(), slug="org-pipe-err", legal_name="Org Pipe Err")
    doc = Document(
        id=uuid.uuid4(),
        organization_id=org.id,
        document_code="DOC-ERR-001",
        document_type=DocumentType.RECEIPT,
        file_name="receipt.jpg",
        mime_type="image/jpeg",
        file_size_bytes=512,
        file_hash="hasherr123",
        source_channel="MANUAL_UPLOAD",
        storage_path="uploads/receipt.jpg",
        processing_status=DocumentProcessingStatus.UPLOADED,
    )
    db_session.add_all([org, doc])
    await db_session.flush()

    extraction_data = {
        "issuer_name": "Toko Material",
        "total_amount": "50000.00",
        "transaction_date": "2026-08-05",
        "field_evidence": {},
    }
    confidence = ConfidenceScores(
        ocr_confidence=Decimal("0.90"),
        document_type_confidence=Decimal("0.90"),
        entity_confidence=Decimal("0.90"),
        project_confidence=Decimal("0.90"),
        amount_confidence=Decimal("0.90"),
    )
    mock_result = ExtractionResult(
        document_type=DocumentType.RECEIPT,
        data=extraction_data,
        confidence=confidence,
        raw_payload={},
        provider_name="MockProvider",
        provider_version="1.0",
    )
    mock_provider = MagicMock()
    mock_provider.extract = AsyncMock(return_value=mock_result)

    from src.services.documents import pipeline as pipeline_module

    async def fail_match(*args, **kwargs):
        raise RuntimeError("Database connection glitch during matching")

    monkeypatch.setattr(pipeline_module, "match_entities", fail_match)

    pipeline = DocumentPipeline(db_session, mock_provider)
    processed_doc = await pipeline.process(doc, Path("/dummy/path.jpg"))

    # Extracted data MUST be preserved even though matching failed!
    assert processed_doc.extracted_data is not None
    assert processed_doc.extracted_data["issuer_name"] == "Toko Material"
    assert processed_doc.processing_status in (DocumentProcessingStatus.REVIEW_REQUIRED, DocumentProcessingStatus.FAILED)


@pytest.mark.asyncio
async def test_payment_account_bank_name_multiple_accounts_is_ambiguous(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-pay-ambig", legal_name="Org Pay Ambig")
    coa = ChartOfAccount(id=uuid.uuid4(), organization_id=org.id, account_code="1101", account_name="Kas Bank", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="Kas & Bank")
    acc1 = PaymentAccount(id=uuid.uuid4(), organization_id=org.id, coa_account_id=coa.id, name="BCA Operasional 1", bank_name="Bank BCA", account_number="111222333", is_active=True)
    acc2 = PaymentAccount(id=uuid.uuid4(), organization_id=org.id, coa_account_id=coa.id, name="BCA Operasional 2", bank_name="Bank BCA", account_number="444555666", is_active=True)
    db_session.add_all([org, coa, acc1, acc2])
    await db_session.flush()

    # Data only has bank name "BCA", no account number
    data = StructuredExtraction(origin_bank="BCA")
    result = await match_entities(db_session, org.id, data)

    # Bank-name-only with multiple accounts must be ambiguous and require review
    assert result["payment_account_id"] is None
    assert result["ambiguous"] is True
    assert result["requires_review"] is True


@pytest.mark.asyncio
async def test_payment_account_exact_number_preferred_over_bank_name(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-pay-exact", legal_name="Org Pay Exact")
    coa = ChartOfAccount(id=uuid.uuid4(), organization_id=org.id, account_code="1102", account_name="Kas Bank 2", account_type=AccountType.ASSET, normal_balance=NormalBalance.DEBIT, report_group="Kas & Bank")
    acc1 = PaymentAccount(id=uuid.uuid4(), organization_id=org.id, coa_account_id=coa.id, name="BCA Operasional 1", bank_name="Bank BCA", account_number="111222333", is_active=True)
    acc2 = PaymentAccount(id=uuid.uuid4(), organization_id=org.id, coa_account_id=coa.id, name="BCA Operasional 2", bank_name="Bank BCA", account_number="444555666", is_active=True)
    db_session.add_all([org, coa, acc1, acc2])
    await db_session.flush()

    # Data has bank name "BCA" and exact account number for acc2
    data = StructuredExtraction(destination_bank="BCA", destination_account_number="444555666")
    result = await match_entities(db_session, org.id, data)

    assert result["payment_account_id"] == str(acc2.id)
    assert result["payment_account_method"] == "EXACT_ACCOUNT_NO"


@pytest.mark.asyncio
async def test_deterministic_ordering_on_tied_scores(db_session):
    org = Organization(id=uuid.uuid4(), slug="org-tied-order", legal_name="Org Tied Order")
    vendor = Counterparty(id=uuid.uuid4(), organization_id=org.id, name="PT Supplier Bersama", is_vendor=True, is_active=True)
    bill1 = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="BILL-TIED-A",
        vendor_id=vendor.id,
        bill_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("5000000.00"),
        status="UNPAID",
    )
    bill2 = VendorBill(
        id=uuid.uuid4(),
        organization_id=org.id,
        bill_code="BILL-TIED-B",
        vendor_id=vendor.id,
        bill_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("5000000.00"),
        status="UNPAID",
    )
    db_session.add_all([org, vendor, bill1, bill2])
    await db_session.flush()

    data = StructuredExtraction(
        recipient_name="PT Supplier Bersama",
        total_amount=Decimal("5000000.00"),
        transaction_date=date(2026, 9, 1),
    )
    res1 = await match_vendor_bills(db_session, org.id, data, matched_counterparty_id=vendor.id)
    res2 = await match_vendor_bills(db_session, org.id, data, matched_counterparty_id=vendor.id)

    order1 = [c.entity_id for c in res1.ranked_candidates]
    order2 = [c.entity_id for c in res2.ranked_candidates]
    assert order1 == order2
    assert len(order1) == 2
    assert res1.ambiguous is True
