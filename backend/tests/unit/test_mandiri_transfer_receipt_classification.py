"""Test classification and extraction for Bank Mandiri / corporate transfer receipts."""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from src.models.enums import DocumentType
from src.services.documents.classification import classify_text
from src.services.documents.local_provider import LocalExtractionProvider
from src.services.documents.normalization import parse_candidate_date


MANDIRI_RECEIPT_TEXT = """mandirı
Transaction Status
Keep track of your transaction
Transaction Status
Transaction Id
202607031259641732
Document Number
202607031259641732
Creation Date
Jul 03, 2026 12:59:32 (GMT +7)
Total Debit Amount
IDR 1,500,000.00
Instruction Mode
Immediate
Transaction Status
Success
Single Transfer To Mandiri - In-House Transfer to Third Party
Source Of Fund
1200012500877 IDR CAKRAWALA BUANA LEST
Destination Account
1200015679173 FARAH ANDINA UTIARAH
Beneficiary Bank Information
PT. Bank Mandiri Tbk
Amount
IDR
1,500,000.00
Total Debit Amount
IDR
1,500,000.00
Transaction Reference
OPS SPK conveyor 1
Remark
Instruction Mode
Immediate
Instruction Date
Jul 03, 2026
Additional Notification
Email
Short Template
cvcakrawala.market@gmail.com"""


def test_mandiri_single_transfer_classified_as_transfer_proof():
    res = classify_text(MANDIRI_RECEIPT_TEXT)
    assert res.document_type == DocumentType.TRANSFER_PROOF
    assert res.confidence >= Decimal("0.85")


def test_parse_month_day_year_date_format():
    res = parse_candidate_date("Jul 03, 2026")
    assert res.value == date(2026, 7, 3)
    assert res.validation_status == "VALID"

    res_long = parse_candidate_date("July 3, 2026")
    assert res_long.value == date(2026, 7, 3)
    assert res_long.validation_status == "VALID"


@pytest.mark.asyncio
async def test_local_provider_extracts_mandiri_receipt_fields(tmp_path: Path):
    doc_path = tmp_path / "mandiri_receipt.pdf"
    c = canvas.Canvas(str(doc_path))
    y = 800
    for line in MANDIRI_RECEIPT_TEXT.splitlines():
        c.drawString(40, y, line)
        y -= 18
    c.save()

    provider = LocalExtractionProvider()
    result = await provider.extract(doc_path, "application/pdf")
    extracted = result.data

    assert result.document_type == DocumentType.TRANSFER_PROOF
    assert extracted.total_amount == Decimal("1500000.00")
    assert extracted.transaction_date == date(2026, 7, 3)
    assert extracted.transfer_reference in ("202607031259641732", "OPS SPK conveyor 1")
    assert extracted.transfer_reference != "erence"
    assert extracted.destination_account_number == "1200015679173"
