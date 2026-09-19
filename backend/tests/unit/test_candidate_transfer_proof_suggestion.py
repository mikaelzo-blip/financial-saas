import uuid

from src.models.enums import DocumentType
from src.schemas.document import StructuredExtraction
from src.services.documents.candidate import build_candidate


def test_transfer_proof_without_allocation_suggests_category():
    data = StructuredExtraction(
        raw_text="Pembelian bensin operasional kendaraan kantor",
        description="Pembelian bensin operasional kendaraan kantor",
        issuer_name="PT Pertamina",
        invoice_number="20708003319",
    )
    matches: dict = {}
    result = build_candidate(
        uuid.uuid4(), DocumentType.TRANSFER_PROOF, data, matches, flags=[]
    )
    assert result is not None
    assert result.proposed_transaction_type is None
    assert "expense_classification" in matches
    assert matches.get("suggested_cost_category") or matches.get("suggested_expense_category")
