"""Supporting system hints extractor for user-supplied captions (e.g. WhatsApp captions).

Strict separation of concerns:
A. RAW USER DESCRIPTION: Preserved as-is in source_metadata['caption'].
B. SYSTEM HINTS: Extracted document_type_hint and project_hint for candidate generation.
C. OCR / DOCUMENT CONTENT: Ground truth extracted strictly from evidentiary file bytes.

The user caption is supporting evidence only, never ground truth.
It MUST NEVER replace:
- OCR raw text
- Document descriptions
- Line items
- Monetary amounts
- Counterparty identity
"""
import re
from typing import Any, Dict, Optional

from src.models.enums import DocumentType


# Mapping of common Indonesian & English document keywords to DocumentType values
_CAPTION_TYPE_PATTERNS = [
    (r"\b(?:po|purchase\s+order|pesanan\s+pembelian|order\s+pembelian)\b", DocumentType.PURCHASE_ORDER.value),
    (r"\b(?:inv(?:oice)?|faktur(?!\s+pajak)|tagihan|bill)\b", DocumentType.VENDOR_INVOICE.value),
    (r"\b(?:bukti\s+transfer|transfer|tf|bayar|bukti\s+bayar|pelunasan|dp)\b", DocumentType.TRANSFER_PROOF.value),
    (r"\b(?:kuitansi|kwitansi|struk|nota(?:\s+kontan)?)\b", DocumentType.RECEIPT.value),
    (r"\b(?:spk|surat\s+perintah\s+kerja)\b", DocumentType.SPK.value),
    (r"\b(?:bast|berita\s+acara(?:\s+serah\s+terima)?)\b", DocumentType.BAST.value),
    (r"\b(?:surat\s+jalan|delivery\s+order)\b", DocumentType.SURAT_JALAN.value),
    (r"\b(?:faktur\s+pajak|e-faktur)\b", DocumentType.TAX_INVOICE.value),
    (r"\b(?:quotation|penawaran(?:\s+harga)?|proforma)\b", DocumentType.QUOTATION.value),
    (r"\b(?:kontrak|perjanjian)\b", DocumentType.CONTRACT.value),
]


def extract_caption_hints(caption: Optional[str]) -> Dict[str, Any]:
    """Extract supporting system hints (document type hint, project hint) from raw user caption.

    Returns:
        dict with:
            - raw_caption: Optional[str]
            - document_type_hint: Optional[str] (e.g. "PURCHASE_ORDER")
            - project_hint: Optional[str] (e.g. "roll arjer")
    """
    if not caption or not caption.strip():
        return {
            "raw_caption": None,
            "document_type_hint": None,
            "project_hint": None,
            "payment_intent": None,
        }

    raw = caption.strip()
    doc_type_hint: Optional[str] = None

    for pattern, dtype in _CAPTION_TYPE_PATTERNS:
        if re.search(pattern, raw, re.I):
            doc_type_hint = dtype
            break

    # Derive project hint by stripping document type keywords and transaction prefixes
    remainder = re.sub(
        r"\b(?:po|purchase\s+order|pesanan\s+pembelian|order\s+pembelian|"
        r"inv(?:oice)?|faktur|tagihan|bill|bukti\s+transfer|transfer|tf|"
        r"spk|bast|surat\s+jalan|nota|kuitansi|kwitansi|proyek|project|"
        r"untuk|utk|buat|byr|bayar|dp|pelunasan|termin(?:\s+\d+)?)\b",
        " ",
        raw,
        flags=re.I,
    )
    remainder = re.sub(r"[:\-_#/()]+", " ", remainder)
    remainder = re.sub(r"\s+", " ", remainder).strip()
    project_hint = remainder if len(remainder) >= 2 else None

    # Derive payment intent hint
    payment_intent: Optional[str] = None
    if re.search(r"\b(?:dp|down\s*payment|uang\s*muka)\b", raw, re.I):
        payment_intent = "DOWN_PAYMENT"
    elif re.search(r"\b(?:lunas|pelunasan|settlement|final\s*payment)\b", raw, re.I):
        payment_intent = "SETTLEMENT"
    elif re.search(r"\b(?:termin|cicilan|angsuran|installment)\b", raw, re.I):
        payment_intent = "INSTALLMENT"

    return {
        "raw_caption": raw,
        "document_type_hint": doc_type_hint,
        "project_hint": project_hint,
        "payment_intent": payment_intent,
    }
