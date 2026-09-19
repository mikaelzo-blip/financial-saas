import uuid
from decimal import Decimal
import pytest

from src.models.enums import DocumentType
from src.services.documents.session_matching import SessionMatchingService


class DummyDoc:
    def __init__(self, doc_id, doc_type, total_amount, issuer_name="", recipient_name="", doc_number="", project_id=None):
        self.id = doc_id
        self.document_code = f"DOC-{str(doc_id)[:6]}"
        self.document_type = doc_type
        self.extracted_data = {
            "total_amount": str(total_amount),
            "nominal": str(total_amount),
            "issuer_name": issuer_name,
            "recipient_name": recipient_name,
            "invoice_number": doc_number,
            "document_number": doc_number,
        }
        self.extracted_confidence = {}
        self.source_metadata = {}
        self.matching_results = {}
        self.candidate_transaction = {}
        self.review_flags = []


def test_multi_invoice_payment_matching():
    """Section 28: Multi-invoice payment:
    Invoice A: 5,000,000
    Invoice B: 3,000,000
    Transfer Proof: 8,000,000
    Result:
    - Sum exact match: 5m + 3m == 8m
    - Proposed relationship: MULTI_INVOICE_SUM_EXACT_MATCH
    - Requires review (never auto-post solely because sum matches)
    """
    inv_a = DummyDoc(uuid.uuid4(), DocumentType.VENDOR_INVOICE, 5000000, issuer_name="PT Semen Jaya")
    inv_b = DummyDoc(uuid.uuid4(), DocumentType.VENDOR_INVOICE, 3000000, issuer_name="PT Semen Jaya")
    transfer = DummyDoc(uuid.uuid4(), DocumentType.TRANSFER_PROOF, 8000000, recipient_name="PT Semen Jaya")

    results = SessionMatchingService.match_document_group([inv_a, inv_b, transfer])

    assert len(results["multi_invoice_matches"]) == 1
    m = results["multi_invoice_matches"][0]
    assert m["transfer_document_id"] == str(transfer.id)
    assert set(m["invoice_document_ids"]) == {str(inv_a.id), str(inv_b.id)}
    assert "MULTI_INVOICE_SUM_EXACT_MATCH" in m["signals"]
    assert m["requires_review"] is True

    # Check decorated matching_results on transfer
    assert len(transfer.matching_results.get("session_multi_invoice_matches", [])) == 1


def test_out_of_order_matching_by_financial_signals():
    """Section 29: Out-of-order documents:
    Invoice 1: 5,000,000
    Invoice 2: 8,000,000
    Transfer 1: 8,000,000
    Transfer 2: 5,000,000
    Result:
    - Transfer 1 (8m) matches Invoice 2 (8m)
    - Transfer 2 (5m) matches Invoice 1 (5m)
    - NOT paired by position (Transfer 1 <-> Invoice 1 would be 8m vs 5m)
    """
    inv1 = DummyDoc(uuid.uuid4(), DocumentType.VENDOR_INVOICE, 5000000, doc_number="INV-5M")
    inv2 = DummyDoc(uuid.uuid4(), DocumentType.VENDOR_INVOICE, 8000000, doc_number="INV-8M")
    tr1 = DummyDoc(uuid.uuid4(), DocumentType.TRANSFER_PROOF, 8000000, doc_number="TR-8M")
    tr2 = DummyDoc(uuid.uuid4(), DocumentType.TRANSFER_PROOF, 5000000, doc_number="TR-5M")

    # Order in list is: inv1 (5m), inv2 (8m), tr1 (8m), tr2 (5m)
    results = SessionMatchingService.match_document_group([inv1, inv2, tr1, tr2])

    pairs = results["matched_pairs"]
    assert len(pairs) == 2

    # Find pair for tr1 (8m) -> must be inv2 (8m)
    tr1_pair = next(p for p in pairs if p["transfer_document_id"] == str(tr1.id))
    assert tr1_pair["invoice_document_id"] == str(inv2.id)
    assert "EXACT_AMOUNT_MATCH" in tr1_pair["signals"]

    # Find pair for tr2 (5m) -> must be inv1 (5m)
    tr2_pair = next(p for p in pairs if p["transfer_document_id"] == str(tr2.id))
    assert tr2_pair["invoice_document_id"] == str(inv1.id)
    assert "EXACT_AMOUNT_MATCH" in tr2_pair["signals"]


def test_unrelated_vendors_not_forced():
    """Section 7, 8, 9, 31: 3 documents in same session, but unrelated vendors:
    - Invoice 1: Vendor A, 5m
    - Invoice 2: Vendor B, 3m
    - Transfer: Vendor A, 5m
    Transfer matches Invoice 1 (Vendor A, 5m).
    Invoice 2 (Vendor B) is NOT forced into the transfer relationship.
    """
    inv_a = DummyDoc(uuid.uuid4(), DocumentType.VENDOR_INVOICE, 5000000, issuer_name="PT Vendor A")
    inv_b = DummyDoc(uuid.uuid4(), DocumentType.VENDOR_INVOICE, 3000000, issuer_name="PT Vendor B")
    transfer = DummyDoc(uuid.uuid4(), DocumentType.TRANSFER_PROOF, 5000000, recipient_name="PT Vendor A")

    results = SessionMatchingService.match_document_group([inv_a, inv_b, transfer])

    assert len(results["matched_pairs"]) == 1
    assert results["matched_pairs"][0]["transfer_document_id"] == str(transfer.id)
    assert results["matched_pairs"][0]["invoice_document_id"] == str(inv_a.id)

    # inv_b is unmatched and not forced into any pair
    assert str(inv_b.id) in results["unmatched_invoices"]
    assert "session_matched_documents" not in inv_b.matching_results
