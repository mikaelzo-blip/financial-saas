import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from statistics import mean

from pypdf import PdfReader
from rapidocr import RapidOCR

from src.models.enums import DocumentType
from src.schemas.document import ConfidenceScores, StructuredExtraction
from src.services.documents.extraction import ExtractionResult
from src.services.documents.normalization import parse_candidate_money


@dataclass(frozen=True)
class ClassificationResult:
    document_type: DocumentType
    confidence: Decimal
    reasons: tuple[str, ...]
    needs_review: bool


_CLASSIFICATION_RULES = (
    (DocumentType.TRANSFER_PROOF, r"bukti\s+transfer|transfer|rekening|bank", "payment-transfer signal"),
    (DocumentType.CUSTOMER_INVOICE, r"customer\s+invoice|invoice\s+pelanggan", "customer-invoice signal"),
    (DocumentType.VENDOR_INVOICE, r"vendor\s+invoice|invoice\s+vendor|faktur(?!\s+pajak)|tagihan", "vendor-invoice signal"),
    (DocumentType.RECEIPT, r"struk\s+pembelian|purchase\s+receipt|kuitansi|nota", "purchase-receipt signal"),
    (DocumentType.PURCHASE_ORDER, r"purchase\s+order", "purchase-order signal"),
    (DocumentType.PO_CUSTOMER, r"customer\s+po|po\s+customer", "customer-PO signal"),
    (DocumentType.SURAT_JALAN, r"surat\s+jalan", "delivery-note signal"),
    (DocumentType.BAST, r"berita\s+acara\s+serah\s+terima|\bbast\b", "BAST signal"),
    (DocumentType.SPK, r"surat\s+perintah\s+kerja|\bspk\b", "SPK signal"),
    (DocumentType.CONTRACT, r"\bkontrak\b|\bcontract\b", "contract signal"),
    (DocumentType.TAX_INVOICE, r"faktur\s+pajak|tax\s+invoice", "tax-invoice signal"),
)


def classify_text(text: str) -> ClassificationResult:
    matches = [(kind, reason) for kind, pattern, reason in _CLASSIFICATION_RULES if re.search(pattern, text, re.I)]
    if len(matches) != 1:
        reasons = tuple(reason for _, reason in matches) or ("no supported deterministic signal",)
        return ClassificationResult(DocumentType.UNKNOWN, Decimal("0.30") if matches else Decimal("0"), reasons, True)
    kind, reason = matches[0]
    return ClassificationResult(kind, Decimal("0.95"), (reason,), False)


class LocalExtractionProvider:
    """Credential-free evidence parser. Unreadable image evidence safely routes to review."""
    _ocr: RapidOCR | None = None

    @classmethod
    def ocr(cls) -> RapidOCR:
        if cls._ocr is None:
            cls._ocr = RapidOCR()
        return cls._ocr

    async def extract(self, path: Path, mime_type: str) -> ExtractionResult:
        scores: list[float] = []
        if mime_type == "application/pdf":
            reader = PdfReader(path)
            if reader.is_encrypted:
                raise ValueError("Password-protected PDF cannot be processed")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            output = self.ocr()(path)
            text = "\n".join(output.txts or ())
            scores = list(output.scores or ())
        amount_match = re.search(r"(?:Rp\s*)?\d[\d.,]*", text, re.I)
        amount_candidate = parse_candidate_money(amount_match.group(0) if amount_match else None)
        amount = amount_candidate.value
        classification = classify_text(text)
        kind = classification.document_type
        score = Decimal(str(round(mean(scores), 4))) if scores else (Decimal("0.90") if text else Decimal("0.00"))
        score = min(score, classification.confidence) if text else score
        reference = re.search(r"\b(?:PRJ|SPK)[-/][A-Z0-9-/]+", text, re.I)
        data = StructuredExtraction(total_amount=amount, raw_text=text or None,
                                    currency_code="IDR" if amount is not None else None,
                                    project_reference=reference.group(0) if reference else None)
        confidence = ConfidenceScores(ocr_confidence=score, document_type_confidence=score,
            entity_confidence=Decimal("0"), project_confidence=Decimal("0"),
            amount_confidence=score if amount is not None else Decimal("0"))
        return ExtractionResult(kind, data, confidence, "local", "1")
