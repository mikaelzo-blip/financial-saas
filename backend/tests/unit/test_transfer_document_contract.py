from decimal import Decimal
from unittest.mock import patch

import pytest
from PIL import Image

from src.models.enums import DocumentType
from src.services.documents.local_provider import LocalExtractionProvider


async def extract_text(tmp_path, text):
    path = tmp_path / "transfer.png"
    Image.new("RGB", (40, 40), "white").save(path)
    lines = text.splitlines()
    with patch("src.services.documents.local_provider.run_ocr_with_orientation",
               return_value=(lines, [0.95] * len(lines), 0, None)), \
         patch.object(LocalExtractionProvider, "ocr", return_value=object()):
        return await LocalExtractionProvider().extract(path, "image/png")


@pytest.mark.asyncio
async def test_bank_application_does_not_extract_goods_or_invoice_due_date(tmp_path):
    result = await extract_text(tmp_path, """Aplikasi Kiriman Uang dan Pemindahbukuan Valas
PT BANK DKI
Tanggal 13 Agustus 2026
Ref. Number: 20708003319
Jumlah Rupiah: IDR 48.110.249,26
Jatuh tempo: 2026-09-30
3A1G 20 pcs 2.000 40.000
""")
    assert result.document_type == DocumentType.TRANSFER_PROOF
    assert result.data.line_items == []
    assert result.data.due_date is None
    assert result.data.total_amount == Decimal("48110249.26")


@pytest.mark.asyncio
async def test_transfer_keeps_source_amounts_separate_without_currency_conversion(tmp_path):
    result = await extract_text(tmp_path, """Foreign Transfer / Overbooking Application
Tanggal: 2026-08-13
Foreign Amount: EUR 2,500.00
Jumlah Rupiah: IDR 48.110.249,26
Biaya Admin: IDR 25.000,00
Total Debit: IDR 48.135.249,26
Tujuan Transfer: Pembayaran barang sesuai INV-2026-001
""")
    details = result.data.transfer_details
    assert details.foreign.amount == Decimal("2500.00")
    assert details.foreign.currency_code == "EUR"
    assert details.principal.amount == Decimal("48110249.26")
    assert details.fee.amount == Decimal("25000.00")
    assert details.debit.amount == Decimal("48135249.26")
    assert details.principal.evidence == "Jumlah Rupiah: IDR 48.110.249,26"
    assert details.execution_status == "REQUESTED"
    assert details.purpose == "Pembayaran barang sesuai INV-2026-001"
    assert result.data.total_amount == details.principal.amount
    assert result.data.currency_code == "IDR"


@pytest.mark.asyncio
async def test_foreign_only_transfer_never_becomes_rupiah_or_invented_debit(tmp_path):
    result = await extract_text(tmp_path, """BUKTI TRANSFER
Tanggal: 2026-08-13
Jumlah Transfer: EUR 2,500.00
""")
    assert result.data.total_amount == Decimal("2500.00")
    assert result.data.currency_code == "EUR"
    assert result.data.transfer_details.debit is None
    assert result.data.transfer_details.execution_status == "UNKNOWN"


@pytest.mark.asyncio
async def test_cloud_transfer_cannot_return_goods_due_date_or_unlabelled_currency(tmp_path):
    import json
    from src.services.documents.cloud_vision_provider import CloudVisionExtractionProvider
    path = tmp_path / "source.png"
    Image.new("RGB", (40, 40), "white").save(path)
    provider = CloudVisionExtractionProvider(transport=lambda _: {
        "choices": [{"message": {"content": json.dumps({
            "document_type": "TRANSFER_PROOF", "total_amount": "2500.00",
            "due_date": "2026-09-30", "line_items": [{"description": "3A1G", "quantity": 20}],
            "transfer_details": {"foreign": {"amount": "2500.00", "currency_code": "EUR", "evidence": "Foreign Amount: EUR 2,500.00"}},
        })}}],
    })
    result = await provider.extract(path, "image/png")
    assert result.data.line_items == []
    assert result.data.due_date is None
    assert result.data.currency_code == "EUR"
    assert result.data.transfer_details.foreign.amount == Decimal("2500.00")


def test_uncertain_execution_and_currency_remain_review_even_with_known_vendor():
    import uuid
    from src.schemas.document import StructuredExtraction
    from src.services.documents.candidate import derive_flags, build_candidate
    data = StructuredExtraction(total_amount="2500", currency_code="EUR")
    matches = {"counterparty_id": str(uuid.uuid4()), "counterparty_role": "VENDOR"}
    flags = derive_flags(DocumentType.TRANSFER_PROOF, data, matches, False)
    assert "TRANSFER_EXECUTION_UNCONFIRMED" in flags
    assert "TRANSFER_AMOUNT_REVIEW" in flags
    candidate = build_candidate(uuid.uuid4(), DocumentType.TRANSFER_PROOF, data, matches, flags)
    assert candidate.proposed_transaction_type != "VENDOR_ADVANCE"
    assert candidate.status == "REVIEW_REQUIRED"
