import re
from decimal import Decimal
from pathlib import Path
from statistics import mean

from pypdf import PdfReader
from rapidocr import RapidOCR

from src.models.enums import DocumentType
from src.schemas.document import ConfidenceScores, StructuredExtraction
from src.services.documents.extraction import ExtractionResult


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
        amount_match = re.search(r"(?:Rp\s*)?([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})|[0-9]{4,})", text, re.I)
        amount = None
        if amount_match:
            raw_amount = amount_match.group(1)
            if "," in raw_amount and "." in raw_amount:
                normalized = (raw_amount.replace(".", "").replace(",", ".")
                              if raw_amount.rfind(",") > raw_amount.rfind(".") else raw_amount.replace(",", ""))
            elif "," in raw_amount:
                normalized = raw_amount.replace(".", "").replace(",", ".")
            else:
                parts = raw_amount.split(".")
                normalized = raw_amount if len(parts) == 2 and len(parts[-1]) == 2 else raw_amount.replace(".", "")
            try: amount = Decimal(normalized)
            except Exception: amount = None
        patterns = ((DocumentType.TRANSFER_PROOF, r"transfer|rekening|bank"),
                    (DocumentType.VENDOR_INVOICE, r"invoice|faktur|tagihan"),
                    (DocumentType.SURAT_JALAN, r"surat\s+jalan"),
                    (DocumentType.BAST, r"berita\s+acara|\bbast\b"),
                    (DocumentType.SPK, r"surat\s+perintah\s+kerja|\bspk\b"))
        kind = next((kind for kind, pattern in patterns if re.search(pattern, text, re.I)), DocumentType.UNKNOWN)
        score = Decimal(str(round(mean(scores), 4))) if scores else (Decimal("0.90") if text else Decimal("0.00"))
        reference = re.search(r"\b(?:PRJ|SPK)[-/][A-Z0-9-/]+", text, re.I)
        data = StructuredExtraction(total_amount=amount, raw_text=text or None,
                                    currency_code="IDR" if amount is not None else None,
                                    project_reference=reference.group(0) if reference else None)
        confidence = ConfidenceScores(ocr_confidence=score, document_type_confidence=score,
            entity_confidence=Decimal("0"), project_confidence=Decimal("0"),
            amount_confidence=score if amount is not None else Decimal("0"))
        return ExtractionResult(kind, data, confidence, "local", "1")
