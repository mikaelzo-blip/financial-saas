import re
import time
from datetime import date
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

from pypdf import PdfReader
from rapidocr import RapidOCR

from src.models.enums import DocumentType
from src.schemas.document import ConfidenceScores, ExtractedField, LineItem, StructuredExtraction
from src.services.documents.extraction import ExtractionResult
from src.services.documents.normalization import parse_candidate_date, parse_candidate_money


@dataclass(frozen=True)
class ClassificationResult:
    document_type: DocumentType
    confidence: Decimal
    reasons: tuple[str, ...]
    needs_review: bool


_CLASSIFICATION_RULES = (
    (DocumentType.TRANSFER_PROOF, r"bukti\s+transfer|transfer\s+bank|m-banking|internet\s+banking|rekening|struk\s+transfer", "payment-transfer signal"),
    (DocumentType.CUSTOMER_INVOICE, r"customer\s+invoice|invoice\s+pelanggan|faktur\s+penjualan|tagihan\s+proyek", "customer-invoice signal"),
    (DocumentType.VENDOR_INVOICE, r"vendor\s+invoice|invoice\s+vendor|faktur(?!\s+pajak)|tagihan\s+vendor|tagihan\s+pembelian|\btax\s+invoice\b", "vendor-invoice signal"),
    (DocumentType.RECEIPT, r"struk\s+pembelian|purchase\s+receipt|kuitansi|nota\s+kontan|nota\s+pembelian|nota\s+toko", "purchase-receipt signal"),
    (DocumentType.PURCHASE_ORDER, r"purchase\s+order|\bpo\b(?!\s+(?:customer|ref|reference|no|nomor))", "purchase-order signal"),
    (DocumentType.PO_CUSTOMER, r"customer\s+po|po\s+customer|po\s+pelanggan|customer\s+order\s+ref", "customer-PO signal"),
    (DocumentType.SURAT_JALAN, r"surat\s+jalan|delivery\s+order|\bdo\b", "delivery-note signal"),
    (DocumentType.BAST, r"berita\s+acara\s+serah\s+terima|\bbast\b", "BAST signal"),
    (DocumentType.SPK, r"surat\s+perintah\s+kerja|\bspk\b", "SPK signal"),
    (DocumentType.CONTRACT, r"\bkontrak\b|\bcontract\b|perjanjian\s+kontrak", "contract signal"),
    (DocumentType.TAX_INVOICE, r"faktur\s+pajak", "tax-invoice signal"),
)


def classify_text(text: str) -> ClassificationResult:
    if not text or not text.strip():
        return ClassificationResult(DocumentType.UNKNOWN, Decimal("0.00"), ("empty text",), True)

    # Primary header check: if the document header prominently declares the document kind,
    # respect the primary header instead of secondary reference fields (e.g. Delivery Order No, PO Ref on an invoice).
    first_lines = "\n".join(text.splitlines()[:20])
    if re.search(r"\b(?:tax\s+invoice|vendor\s+invoice|invoice\s+vendor|tagihan\s+vendor|tagihan\s+pembelian)\b", first_lines, re.I):
        return ClassificationResult(DocumentType.VENDOR_INVOICE, Decimal("0.95"), ("vendor-invoice signal",), False)
    if re.search(r"\b(?:faktur\s+pajak)\b", first_lines, re.I):
        return ClassificationResult(DocumentType.TAX_INVOICE, Decimal("0.95"), ("tax-invoice signal",), False)
    if re.search(r"\b(?:customer\s+invoice|invoice\s+pelanggan|faktur\s+penjualan)\b", first_lines, re.I):
        return ClassificationResult(DocumentType.CUSTOMER_INVOICE, Decimal("0.95"), ("customer-invoice signal",), False)
    if re.search(r"\b(?:bukti\s+transfer|transfer\s+bank|m-banking|internet\s+banking)\b", first_lines, re.I):
        return ClassificationResult(DocumentType.TRANSFER_PROOF, Decimal("0.95"), ("payment-transfer signal",), False)

    matches = [(kind, reason) for kind, pattern, reason in _CLASSIFICATION_RULES if re.search(pattern, text, re.I)]
    if len(matches) != 1:
        reasons = tuple(reason for _, reason in matches) or ("no supported deterministic signal",)
        return ClassificationResult(DocumentType.UNKNOWN, Decimal("0.30") if matches else Decimal("0.00"), reasons, True)
    kind, reason = matches[0]
    return ClassificationResult(kind, Decimal("0.95"), (reason,), False)


def sanitize_raw_text(text: str) -> str:
    """Isolate against prompt-injection instructions in extracted text."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()


class LocalExtractionProvider:
    """Credential-free evidence parser using pypdf and RapidOCR.

    Produces structured fields, field-level evidence, and transparent confidence metrics.
    """
    _ocr: RapidOCR | None = None

    @classmethod
    def ocr(cls) -> RapidOCR:
        if cls._ocr is None:
            cls._ocr = RapidOCR()
        return cls._ocr

    async def extract(self, path: Path, mime_type: str) -> ExtractionResult:
        if not path.is_file():
            raise FileNotFoundError(f"Document file not found at: {path}")

        start_time = time.monotonic()
        scores: list[float] = []
        page_count = 1
        text = ""

        if mime_type == "application/pdf":
            try:
                reader = PdfReader(path)
                if reader.is_encrypted:
                    raise ValueError("Password-protected PDF cannot be processed")
                page_count = len(reader.pages)
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as exc:
                if "Password-protected" in str(exc):
                    raise
                raise ValueError(f"Corrupted or unreadable PDF: {exc}") from exc
        else:
            try:
                output = self.ocr()(str(path))
                text = "\n".join(output.txts or ())
                scores = list(output.scores or ())
            except Exception as exc:
                raise ValueError(f"Image OCR processing failure: {exc}") from exc

        text = sanitize_raw_text(text)
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Classification
        classification = classify_text(text)
        kind = classification.document_type

        # OCR score calculation
        if scores:
            ocr_score = Decimal(str(round(mean(scores), 4)))
        elif text:
            ocr_score = Decimal("0.90")
        else:
            ocr_score = Decimal("0.00")

        # Amount extraction: Find total, subtotal, VAT
        total_amount = None
        total_candidate = parse_candidate_money(None)
        field_evidence: Dict[str, ExtractedField] = {}

        # Look for explicit Total pattern first
        total_match = re.search(r"(?:total(?:\s+bayar|\s+transfer|\s+tagihan|\s+pembayaran|\s+amount)?|jumlah(?:\s+transfer|\s+tagihan)?|grand\s+total)\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,]+)", text, re.I)
        if not total_match:
            # Fallback to general amount match
            total_match = re.search(r"(?:Rp\.?|IDR)\s*([\d.,]+)", text, re.I)
        if not total_match:
            # Last resort: standalone large number formatted as money
            total_match = re.search(r"\b\d{1,3}(?:\.\d{3})+(?:,\d{2})?\b|\b\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b", text)

        if total_match:
            raw_val = total_match.group(1) if total_match.groups() else total_match.group(0)
            total_candidate = parse_candidate_money(raw_val)
            total_amount = total_candidate.value
            field_evidence["total_amount"] = ExtractedField(
                value=str(total_amount) if total_amount is not None else None,
                confidence=ocr_score if total_amount is not None else Decimal("0.0"),
                evidence=total_match.group(0),
                validation_status=total_candidate.validation_status,
            )

        # Look for VAT/PPN
        vat_match = re.search(r"(?:ppn|vat|pajak)(?:\s+11%|\s+12%)?\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,]+)", text, re.I)
        vat_amount = None
        if vat_match:
            raw_vat = vat_match.group(0)
            vat_cand = parse_candidate_money(raw_vat)
            vat_amount = vat_cand.value
            if vat_amount is not None:
                field_evidence["vat_amount"] = ExtractedField(
                    value=str(vat_amount),
                    confidence=ocr_score,
                    evidence=vat_match.group(0),
                    validation_status=vat_cand.validation_status,
                )

        # Look for Subtotal
        subtotal_match = re.search(r"(?:subtotal|sub\s+total|dpp|ex\s+tax)\s*[\s\S]{0,10}?([\d.,]+)", text, re.I)
        subtotal_amount = None
        if subtotal_match:
            raw_sub = subtotal_match.group(1) if subtotal_match.groups() else subtotal_match.group(0)
            sub_cand = parse_candidate_money(raw_sub)
            subtotal_amount = sub_cand.value
            if subtotal_amount is not None:
                field_evidence["subtotal"] = ExtractedField(
                    value=str(subtotal_amount),
                    confidence=ocr_score,
                    evidence=subtotal_match.group(0),
                    validation_status=sub_cand.validation_status,
                )

        # Dates extraction
        tx_date = None
        due_date = None
        date_cand = parse_candidate_date(None)
        due_cand = parse_candidate_date(None)

        months_map = {
            "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
            "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
            "MEI": 5, "AGU": 8, "OKT": 10, "DES": 12
        }

        # Check alphanumeric dates first (e.g. 11 MAR 2026, Date: 11 MAR 2026)
        date_pattern = r"\b(?:date|tanggal)?\s*[:=]?\s*(\d{1,2})\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|MEI|AGU|OKT|DES)[A-Z]*\s+(\d{4})\b"
        for dm in re.finditer(date_pattern, text, re.I):
            day, mon_str, yr = dm.group(1), dm.group(2).upper(), dm.group(3)
            try:
                parsed_d = date(int(yr), months_map[mon_str], int(day))
                # Check if preceding text indicates due date
                pre_span = text[max(0, dm.start()-15):dm.start()]
                if re.search(r"due|jatuh\s+tempo", pre_span, re.I):
                    if not due_date:
                        due_date = parsed_d
                        due_cand = parse_candidate_date(str(parsed_d))
                else:
                    if not tx_date:
                        tx_date = parsed_d
                        date_cand = parse_candidate_date(str(parsed_d))
            except Exception:
                pass

        if not tx_date:
            date_match = re.search(r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\b", text)
            if date_match:
                date_cand = parse_candidate_date(date_match.group(0))
                tx_date = date_cand.value
                field_evidence["transaction_date"] = ExtractedField(
                    value=str(tx_date) if tx_date else None,
                    confidence=ocr_score if tx_date else Decimal("0.5"),
                    evidence=date_match.group(0),
                    validation_status=date_cand.validation_status,
                )
        elif tx_date:
            field_evidence["transaction_date"] = ExtractedField(
                value=str(tx_date),
                confidence=ocr_score,
                evidence=str(tx_date),
                validation_status="VALID",
            )

        if due_date:
            field_evidence["due_date"] = ExtractedField(
                value=str(due_date),
                confidence=ocr_score,
                evidence=str(due_date),
                validation_status="VALID",
            )

        # Reference numbers
        tax_inv_match = re.search(r"\b(?:tax\s+invoice|faktur\s+pajak)\s*[:#]?\s*([A-Za-z0-9\-\/]+)", text, re.I)
        tax_invoice_num = tax_inv_match.group(1) if tax_inv_match else None

        inv_match = re.search(r"\b(?:INV|FAK|BILL)[-/][A-Z0-9-/]+", text, re.I)
        invoice_number = (tax_inv_match.group(0) if tax_inv_match else None) or (inv_match.group(0) if inv_match else None)
        if invoice_number:
            field_evidence["invoice_number"] = ExtractedField(
                value=tax_invoice_num or invoice_number,
                confidence=Decimal("0.95"),
                evidence=invoice_number,
                validation_status="VALID",
            )

        spk_match = re.search(r"\b(?:SPK|PO|PRJ)[-/][A-Z0-9-/]+", text, re.I)
        spk_number = spk_match.group(0) if spk_match else None
        slash_ref = re.search(r"\b\d{3}/[A-Z0-9\-]+(?:/[A-Z0-9\-]+)+\b", text)
        if not spk_number and slash_ref:
            spk_number = slash_ref.group(0)
        if spk_number:
            field_evidence["spk_number"] = ExtractedField(
                value=spk_number,
                confidence=Decimal("0.95"),
                evidence=spk_number,
                validation_status="VALID",
            )

        bast_match = re.search(r"\b(?:BAST)[-/][A-Z0-9-/]+", text, re.I)
        bast_number = bast_match.group(0) if bast_match else None
        if bast_number:
            field_evidence["bast_number"] = ExtractedField(
                value=bast_number,
                confidence=Decimal("0.95"),
                evidence=bast_number,
                validation_status="VALID",
            )

        # Bank hints
        bank_match = re.search(r"\b(BCA|MANDIRI|BRI|BNI|BSI|CIMB|PERMATA|DANAMON)\b", text, re.I)
        bank_name = bank_match.group(1).upper() if bank_match else None

        # Counterparty name hints
        issuer_name = None
        recipient_name = None
        for line in text.splitlines()[:5]:
            clean_l = line.strip()
            if re.match(r"^(?:PT|CV|UD|TOKO)\b", clean_l, re.I) and len(clean_l) > 3:
                issuer_name = clean_l
                field_evidence["issuer_name"] = ExtractedField(
                    value=issuer_name,
                    confidence=Decimal("0.90"),
                    evidence=clean_l,
                    validation_status="VALID",
                )
                break

        recip_match = re.search(r"\b(?:bill\s+to|deliver\s+to|customer|kepada|pembeli)\s*[:=]?\s*[\s\S]{0,10}?([A-Za-z0-9\s.,\-]+)", text, re.I)
        if recip_match:
            cand_recipient = recip_match.group(1).strip().splitlines()[0].strip()
            if re.match(r"^(?:PT|CV|UD|TOKO)\b", cand_recipient, re.I):
                recipient_name = cand_recipient
                field_evidence["recipient_name"] = ExtractedField(
                    value=recipient_name,
                    confidence=Decimal("0.90"),
                    evidence=cand_recipient,
                    validation_status="VALID",
                )

        # Line items summary
        line_items: List[LineItem] = []
        for line in text.splitlines():
            line = line.strip()
            item_match = re.match(r"^([A-Za-z0-9\s/.,\-]+?)\s+(\d+)\s*(?:x|@)?\s*(?:Rp\.?|IDR)?\s*([\d.,]+)\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,]+)$", line, re.I)
            if item_match:
                desc, qty_str, price_str, amt_str = item_match.groups()
                q_c = parse_candidate_money(qty_str)
                p_c = parse_candidate_money(price_str)
                a_c = parse_candidate_money(amt_str)
                if desc and a_c.value is not None:
                    line_items.append(LineItem(
                        description=desc.strip(),
                        quantity=q_c.value,
                        unit_price=p_c.value,
                        amount=a_c.value,
                    ))

        # Project reference
        project_ref = spk_number or (re.search(r"\bPRJ[-/][A-Z0-9-/]+", text, re.I).group(0) if re.search(r"\bPRJ[-/][A-Z0-9-/]+", text, re.I) else None)

        # Structured data
        data = StructuredExtraction(
            document_number=invoice_number or spk_number or bast_number,
            invoice_number=invoice_number,
            spk_number=spk_number,
            bast_number=bast_number,
            transaction_date=tx_date,
            due_date=due_date,
            issuer_name=issuer_name,
            recipient_name=recipient_name,
            subtotal=subtotal_amount,
            vat_amount=vat_amount,
            total_amount=total_amount,
            currency_code="IDR" if total_amount is not None else None,
            origin_bank=bank_name if kind == DocumentType.TRANSFER_PROOF else None,
            destination_bank=bank_name if kind == DocumentType.TRANSFER_PROOF else None,
            project_reference=project_ref,
            line_items=line_items,
            raw_text=text or None,
            field_evidence=field_evidence,
        )

        amount_conf = (ocr_score if total_amount is not None and total_candidate.validation_status == "VALID"
                       else Decimal("0.50") if total_candidate.validation_status == "AMBIGUOUS"
                       else Decimal("0.00"))

        confidence = ConfidenceScores(
            ocr_confidence=ocr_score,
            document_type_confidence=classification.confidence,
            entity_confidence=Decimal("0.80") if (invoice_number or bank_name) else Decimal("0.00"),
            project_confidence=Decimal("0.90") if project_ref else Decimal("0.00"),
            amount_confidence=amount_conf,
        )

        telemetry = {
            "provider": "local",
            "mime_type": mime_type,
            "page_count": page_count,
            "char_count": len(text),
            "latency_ms": latency_ms,
            "ocr_score": str(ocr_score),
            "success": True,
        }

        return ExtractionResult(
            document_type=kind,
            data=data,
            confidence=confidence,
            provider_name="local",
            provider_version="1.1.0",
            raw_payload=telemetry,
        )
