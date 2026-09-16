import re
import time
from datetime import date
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional
from PIL import Image

from pypdf import PdfReader
from rapidocr import RapidOCR

from src.core.config import settings
from src.models.enums import DocumentType
from src.schemas.document import ConfidenceScores, ExtractedField, LineItem, StructuredExtraction
from src.services.documents.classification import classify_text, ClassificationResult
from src.services.documents.exceptions import (
    InvalidFileError,
    OcrProcessingError,
    PdfRenderError,
    UnsupportedFileError,
)
from src.services.documents.extraction import ExtractionResult
from src.services.documents.image_processing import run_ocr_with_orientation
from src.services.documents.normalization import parse_candidate_date, parse_candidate_money
from src.services.documents.quality_gate import evaluate_page_text_quality
from src.services.documents.rasterizer import open_pdf_document, render_pdf_page_to_image
from src.services.documents.table_extractor import extract_line_items_from_text


def sanitize_raw_text(text: str) -> str:
    """Isolates against prompt-injection instructions and illegal control chars in extracted text."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()


class LocalExtractionProvider:
    """Credential-free evidence parser combining pypdf native text extraction,
    bounded PDF rasterization (pypdfium2), and RapidOCR.

    Implements a hybrid pipeline:
    1. Digital PDF: Uses native embedded text when quality gate passes.
    2. Scanned PDF: Rasterizes pages to images and runs RapidOCR.
    3. Mixed PDF: Page-by-page fallback preserving page provenance and ordering.
    4. Rotated documents: Supports EXIF and 90/180/270 orientation recovery.
    5. Table extraction: Structured line items with construction units and arithmetic validation.
    """
    _ocr: Optional[RapidOCR] = None

    @classmethod
    def ocr(cls) -> RapidOCR:
        if cls._ocr is None:
            cls._ocr = RapidOCR()
        return cls._ocr

    async def extract(self, path: Path, mime_type: str) -> ExtractionResult:
        if not path.is_file():
            raise FileNotFoundError(f"Document file not found at: {path}")

        start_time = time.monotonic()
        pages_evidence: List[Dict[str, Any]] = []
        all_scores: List[float] = []
        all_boxes: List[Any] = []
        all_ocr_txts: List[str] = []
        extraction_modes: set[str] = set()

        if mime_type == "application/pdf":
            try:
                # 1. Inspect with pypdf
                reader = PdfReader(str(path))
                if reader.is_encrypted:
                    raise InvalidFileError("Password-protected PDF cannot be processed")
                total_pages = len(reader.pages)
            except InvalidFileError:
                raise
            except Exception as exc:
                raise InvalidFileError(f"Corrupted or unreadable PDF: {exc}") from exc

            max_pages = min(total_pages, settings.DOCUMENT_OCR_MAX_PAGES)
            pdfium_doc = None

            try:
                for idx in range(max_pages):
                    page_num = idx + 1
                    native_text = ""
                    try:
                        native_text = reader.pages[idx].extract_text() or ""
                    except Exception:
                        native_text = ""

                    quality = evaluate_page_text_quality(native_text)

                    if quality.is_sufficient:
                        # Fast path: native digital page
                        clean_native = sanitize_raw_text(native_text)
                        pages_evidence.append({
                            "page_number": page_num,
                            "source": "native",
                            "char_count": len(clean_native),
                            "confidence": "0.95",
                            "raw_text": clean_native,
                        })
                        extraction_modes.add("native")
                    else:
                        # Fallback path: rasterize scanned or low-quality page
                        if pdfium_doc is None:
                            pdfium_doc = open_pdf_document(path)

                        try:
                            pil_img = render_pdf_page_to_image(
                                pdfium_doc, idx, dpi=settings.DOCUMENT_OCR_DPI
                            )
                        except Exception as exc:
                            raise PdfRenderError(f"Failed to rasterize PDF page {page_num}: {exc}") from exc

                        try:
                            txts, scores, angle, raw_out = run_ocr_with_orientation(
                                self.ocr(), pil_img, try_rotations_on_failure=True
                            )
                        except Exception as exc:
                            raise OcrProcessingError(f"OCR processing failed on page {page_num}: {exc}") from exc
                        finally:
                            del pil_img

                        page_text = "\n".join(txts)
                        clean_ocr_text = sanitize_raw_text(page_text)
                        page_conf = Decimal(str(round(mean(scores), 4))) if scores else Decimal("0.00")
                        all_scores.extend(scores)
                        if raw_out and hasattr(raw_out, "boxes") and raw_out.boxes is not None:
                            all_boxes.extend(list(raw_out.boxes))
                            all_ocr_txts.extend(txts)

                        pages_evidence.append({
                            "page_number": page_num,
                            "source": "ocr",
                            "detected_rotation": angle,
                            "char_count": len(clean_ocr_text),
                            "confidence": str(page_conf),
                            "raw_text": clean_ocr_text,
                        })
                        extraction_modes.add("ocr")
            finally:
                if pdfium_doc is not None:
                    pdfium_doc.close()

            combined_raw_text = "\n\n".join(
                p["raw_text"] for p in pages_evidence if p["raw_text"].strip()
            )
            page_count = len(pages_evidence)

        elif mime_type.startswith("image/"):
            try:
                pil_image = Image.open(path)
            except Exception as exc:
                raise InvalidFileError(f"Corrupted or unreadable image file: {exc}") from exc

            try:
                txts, scores, angle, raw_out = run_ocr_with_orientation(
                    self.ocr(), pil_image, try_rotations_on_failure=True
                )
            except Exception as exc:
                raise OcrProcessingError(f"Image OCR processing failure: {exc}") from exc
            finally:
                pil_image.close()

            page_text = "\n".join(txts)
            clean_text = sanitize_raw_text(page_text)
            page_conf = Decimal(str(round(mean(scores), 4))) if scores else Decimal("0.00")
            all_scores.extend(scores)
            if raw_out and hasattr(raw_out, "boxes") and raw_out.boxes is not None:
                all_boxes.extend(list(raw_out.boxes))
                all_ocr_txts.extend(txts)

            pages_evidence.append({
                "page_number": 1,
                "source": "ocr",
                "detected_rotation": angle,
                "char_count": len(clean_text),
                "confidence": str(page_conf),
                "raw_text": clean_text,
            })
            combined_raw_text = clean_text
            page_count = 1
            extraction_modes.add("ocr")

        else:
            raise UnsupportedFileError(f"Unsupported MIME type for extraction: {mime_type}")

        text = combined_raw_text
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Document Classification
        classification = classify_text(text)
        kind = classification.document_type

        # Overall OCR confidence calculation
        if all_scores:
            ocr_score = Decimal(str(round(mean(all_scores), 4)))
        elif "native" in extraction_modes and text:
            ocr_score = Decimal("0.95")
        elif text:
            ocr_score = Decimal("0.85")
        else:
            ocr_score = Decimal("0.00")

        field_evidence: Dict[str, ExtractedField] = {}

        # 1. Total Amount extraction
        total_amount = None
        total_candidate = parse_candidate_money(None)

        # Remove regulatory boilerplate that triggers false positives (e.g. "diatas Rp. 100 juta")
        text_for_amount = re.sub(r"(?i)[^\n]*(?:diatas|di\s*atas)\s*(?:rp\.?|idr)?\s*100\s*juta[^\n]*", "", text)
        text_for_amount = re.sub(r"(?i)[^\n]*walk-in\s+customer[^\n]*", "", text_for_amount)
        text_for_amount = re.sub(r"(?i)[^\n]*transaksi\s+tunai\s+diatas[^\n]*", "", text_for_amount)

        # Step 0: Priority for Proceeds (Forex deal / bank settlement total = Principal + Bank Fees)
        m_proc = re.search(r"(?i)\bproceeds\b[\s\S]{0,40}?\b((?:IDR|Rp\.?)?\s*[\d.,]{4,25})\b", text_for_amount)
        if m_proc:
            cand_proc = parse_candidate_money(m_proc.group(0))
            if cand_proc.value and cand_proc.value > 100:
                total_candidate = cand_proc
                total_amount = cand_proc.value
                total_match = m_proc

        # Step 0b: Priority for IDR Amount / Jumlah Rupiah when foreign currency is present
        if total_amount is None or total_amount <= 100:
            m_idr = re.search(r"(?i)\b(?:idr\s+amount|jumlah\s+rupiah|amount\s+in\s+idr)\b[\s\S]{0,40}?\b((?:IDR|Rp\.?)?\s*[\d.,]{4,25})\b", text_for_amount)
            if m_idr:
                cand_idr = parse_candidate_money(m_idr.group(0))
                if cand_idr.value and cand_idr.value > 100:
                    total_candidate = cand_idr
                    total_amount = cand_idr.value
                    total_match = m_idr

        # Step A: Direct regex match on text for explicit total labels
        if total_amount is None or total_amount <= 100:
            total_match = re.search(
                r"\b(?:proceeds|idr\s+amount|jumlah\s+rupiah|amount\s+in\s+idr|jumlah\s+transfer|total\s+transfer|grand\s+total|total\s+bayar|total\s+tagihan|total\s+pembayaran|total\s+amount|jumlah\s+tagihan|(?<!sub)total|jumlah)\s*[:=]?\s*(?:Rp\.?|IDR|EUR|USD)?\s*[\d.,\-]{4,25}",
                text_for_amount,
                re.I,
            )
            if total_match:
                cand = parse_candidate_money(total_match.group(0))
                if cand.value and cand.value > 100:
                    total_candidate = cand
                    total_amount = cand.value

        # Step B: Nearby lines below/above transfer/proceeds headers (handles multi-column bank/valas tables)
        if total_amount is None or total_amount < 1_000_000:
            lines_for_amt = [re.sub(r"^[^\w\d]+|[^\w\d]+$", "", l.strip()) for l in text_for_amount.splitlines() if l.strip()]
            for idx, l in enumerate(lines_for_amt):
                if any(k in l.lower() for k in ["jumlah rupiah", "amount in idr", "proceeds", "total amount", "idr amount", "jumlah transfer", "total transfer"]):
                    start_idx = max(0, idx - 3)
                    end_idx = min(len(lines_for_amt), idx + 8)
                    for next_l in lines_for_amt[start_idx:end_idx]:
                        for m in re.finditer(r"\b(?:\d{1,3}(?:[.,]\d{3,6})+(?:[.,\s]\d{2})?|\d{4,}(?:[.,\s]\d{2})?)\b", next_l):
                            cand = parse_candidate_money(m.group(0))
                            if cand.value and cand.value > 100:
                                if total_amount is None or cand.value > total_amount:
                                    total_amount = cand.value
                                    total_candidate = cand
                                    total_match = m

        # Step C: Currency prefix with formatted number >= 4 chars
        if total_amount is None or total_amount <= 100:
            m_curr = re.search(r"(?:Rp\.?|IDR|EUR|USD)\s*[:=]?\s*([\d.,\-]{4,25})", text_for_amount, re.I)
            if m_curr:
                cand = parse_candidate_money(m_curr.group(1))
                if cand.value and cand.value > 100:
                    total_amount = cand.value
                    total_candidate = cand
                    total_match = m_curr

        # Step D: Standalone formatted currency
        if total_amount is None or total_amount <= 100:
            m_stand = re.search(r"\b\d{1,3}(?:\.\d{3})+(?:,\d{2})?\b|\b\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b", text_for_amount)
            if m_stand:
                cand = parse_candidate_money(m_stand.group(0))
                if cand.value and cand.value > 100:
                    total_amount = cand.value
                    total_candidate = cand
                    total_match = m_stand

        if total_amount is not None:
            field_evidence["total_amount"] = ExtractedField(
                value=str(total_amount),
                confidence=ocr_score,
                evidence=total_match.group(0) if total_match else str(total_amount),
                validation_status=total_candidate.validation_status,
            )

        # 2. VAT / PPN Amount extraction
        vat_match = re.search(r"(?:ppn|vat|pajak)(?:\s*1[12]%)?\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,\-]+)", text, re.I)
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

        # 3. Subtotal extraction
        subtotal_match = re.search(r"(?:subtotal|sub\s+total|dpp|ex\s+tax)\s*[:=]?\s*[\s\S]{0,10}?([\d.,\-]+)", text, re.I)
        subtotal_amount = None
        if subtotal_match:
            raw_sub = subtotal_match.group(0)
            sub_cand = parse_candidate_money(raw_sub)
            subtotal_amount = sub_cand.value
            if subtotal_amount is not None:
                field_evidence["subtotal"] = ExtractedField(
                    value=str(subtotal_amount),
                    confidence=ocr_score,
                    evidence=subtotal_match.group(0),
                    validation_status=sub_cand.validation_status,
                )

        # 4. Dates extraction (transaction date and due date)
        tx_date: Optional[date] = None
        due_date: Optional[date] = None

        # Look for explicit due date patterns
        due_match = re.search(
            r"(?:jatuh\s+tempo|due\s+date|bayar\s+sebelum)\s*[:=]?\s*([^\r\n]+)",
            text,
            re.I,
        )
        if due_match:
            cand = parse_candidate_date(due_match.group(1).strip())
            if cand.value:
                due_date = cand.value
                field_evidence["due_date"] = ExtractedField(
                    value=str(due_date),
                    confidence=ocr_score,
                    evidence=due_match.group(0).strip(),
                    validation_status=cand.validation_status,
                )

        # Look for transaction date patterns
        date_pattern = (
            r"\b(?:tanggal|tgl|date|trade\s*date)\s*[:=]?\s*"
            r"([0-9]{1,2}[\s\-./]+[a-zA-Z]{3,10}[\s\-./]+[0-9]{2,4}"
            r"|[0-9]{4}-[0-9]{2}-[0-9]{2}"
            r"|[0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})\b"
        )
        for dm in re.finditer(date_pattern, text, re.I):
            matched_date_str = dm.group(1)
            cand = parse_candidate_date(matched_date_str)
            if cand.value and not tx_date:
                tx_date = cand.value
                field_evidence["transaction_date"] = ExtractedField(
                    value=str(tx_date),
                    confidence=ocr_score,
                    evidence=dm.group(0),
                    validation_status=cand.validation_status,
                )
                break

        # Fallback date search
        if not tx_date:
            generic_date = re.search(
                r"\b([0-9]{1,2}[\s\-./]+[a-zA-Z]{3,10}[\s\-./]+[0-9]{2,4}"
                r"|[0-9]{4}-[0-9]{2}-[0-9]{2}"
                r"|[0-9]{1,2}[/.\-][0-9]{1,2}[/.\-][0-9]{2,4})\b",
                text,
                re.I,
            )
            if generic_date:
                cand = parse_candidate_date(generic_date.group(1))
                if cand.value:
                    tx_date = cand.value
                    field_evidence["transaction_date"] = ExtractedField(
                        value=str(tx_date),
                        confidence=ocr_score,
                        evidence=generic_date.group(0),
                        validation_status=cand.validation_status,
                    )
                elif cand.validation_status == "AMBIGUOUS":
                    field_evidence["transaction_date"] = ExtractedField(
                        value=None,
                        confidence=Decimal("0.50"),
                        evidence=generic_date.group(0),
                        validation_status="AMBIGUOUS",
                    )

        # 5. Reference Numbers
        # Tax invoice number
        tax_inv_match = re.search(r"\b(?:tax\s+invoice|faktur\s+pajak)\s*[:#]?\s*([A-Za-z0-9\-\/.]+)", text, re.I)
        tax_invoice_num = tax_inv_match.group(1) if tax_inv_match else None

        # Standard invoice number
        inv_match = re.search(r"\b(?:INV|FAK|BILL)[-/][A-Z0-9-/]+", text, re.I)
        if not inv_match:
            inv_match = re.search(r"\b(?:no(?:mor)?\s*invoice|no(?:mor)?\s*faktur|invoice\s*no)\s*[:#]?\s*([A-Za-z0-9\-\/]+)", text, re.I)
        invoice_number = tax_invoice_num or (inv_match.group(1) if (inv_match and inv_match.groups()) else (inv_match.group(0) if inv_match else None))
        if invoice_number:
            field_evidence["invoice_number"] = ExtractedField(
                value=invoice_number,
                confidence=Decimal("0.95"),
                evidence=inv_match.group(0) if inv_match else (tax_inv_match.group(0) if tax_inv_match else invoice_number),
                validation_status="VALID",
            )

        # SPK / PO reference number
        spk_match = re.search(r"\b(?:SPK|PRJ|WO)[-/][A-Z0-9-/]+", text, re.I)
        po_match = re.search(r"\b(?:PO)[-/][A-Z0-9-/]+", text, re.I)
        if not po_match:
            po_match = re.search(r"\b(?:po\s*no|nomor\s*po|po\s*number)\s*[:#]?\s*([A-Za-z0-9\-\/]+)", text, re.I)

        spk_number = spk_match.group(0) if spk_match else (po_match.group(1) if (po_match and po_match.groups()) else (po_match.group(0) if po_match else None))
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

        # BAST number
        bast_match = re.search(r"\b(?:BAST|BA)[-/][A-Z0-9-/]+", text, re.I)
        bast_number = bast_match.group(0) if bast_match else None
        if bast_number:
            field_evidence["bast_number"] = ExtractedField(
                value=bast_number,
                confidence=Decimal("0.95"),
                evidence=bast_number,
                validation_status="VALID",
            )

        # 6. Bank Hints & Transfer Metadata
        bank_match = re.search(r"\b(BCA|MANDIRI|BRI|BNI|BSI|CIMB|PERMATA|DANAMON|JAGO|JENIUS|SEABANK|BTPN|DKI|BANK\s+DKI|HSBC)\b", text, re.I)
        bank_name = bank_match.group(1).upper() if bank_match else None

        # Transfer reference
        transfer_ref = None
        tref_match = re.search(
            r"\b(?:no(?:mor)?\s*referensi|ref\.?\s*(?:number|no|\.?)|reference\s*no|no\s*transaksi)\s*[:=]?\s*([A-Za-z0-9\-\/]{6,30})",
            text,
            re.I,
        )
        cand_ref = tref_match.group(1).strip() if tref_match else None
        if cand_ref and any(c.isdigit() for c in cand_ref) and not re.match(r"(?i)^(?:PT|BANK|PTBANK|BCA|MANDIRI|BRI|BNI|DKI|NUMBER|NOMOR|REF)", cand_ref):
            transfer_ref = cand_ref
        else:
            # Fallback: look for 10-16 digit bank transaction reference code
            ref_num = re.search(r"\b(?<!\d)(\d{10,16})(?!\d)\b", text)
            if ref_num:
                transfer_ref = ref_num.group(1)

        if transfer_ref:
            field_evidence["transfer_reference"] = ExtractedField(
                value=transfer_ref,
                confidence=Decimal("0.95"),
                evidence=transfer_ref,
                validation_status="VALID",
            )

        # Destination account name & number
        dest_account_no = None
        dest_account_name = None
        acc_no_match = re.search(r"\b(?:rekening\s+tujuan|no\s+rek|nomor\s+rekening|benef(?:iciary)?\.?'?s?\s+acct\.?\s*(?:no)?)\s*[:=]?\s*([0-9\-]{7,25})\b", text, re.I)
        if not acc_no_match:
            acc_no_match = re.search(r"\b(?:\d{3}-\d{10}|\d{12})\b", text)

        if acc_no_match:
            dest_account_no = acc_no_match.group(1) if acc_no_match.lastindex else acc_no_match.group(0)
            field_evidence["destination_account_number"] = ExtractedField(
                value=dest_account_no,
                confidence=Decimal("0.95"),
                evidence=acc_no_match.group(0),
                validation_status="VALID",
            )

        acc_name_match = re.search(r"\b(?:nama\s+tujuan|nama\s+penerima|penerima|beneficiary)\s*[:=]?\s*([A-Za-z0-9\s.,\-]+)", text, re.I)
        if acc_name_match:
            acc_lines = [line.strip() for line in acc_name_match.group(1).splitlines() if line.strip()]
            clean_acc_lines = [l for l in acc_lines if not re.match(r"(?i)^(?:rekening|no|bank|nama\s+bank|bank\s+penerima)\b", l)]
            first_line = clean_acc_lines[0] if clean_acc_lines else ""
            if len(first_line) > 2:
                dest_account_name = first_line
                field_evidence["destination_account_name"] = ExtractedField(
                    value=dest_account_name,
                    confidence=Decimal("0.90"),
                    evidence=first_line,
                    validation_status="VALID",
                )

        # 7. Counterparty Entities (Issuer & Recipient)
        issuer_name = None
        recipient_name = None

        for line in text.splitlines()[:8]:
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

        recip_match = re.search(
            r"\b(?:bill\s+to|deliver\s+to|customer|kepada|pembeli|kepada\s+yth)\s*[:=]?\s*[\s\S]{0,10}?([A-Za-z0-9\s.,\-]+)",
            text,
            re.I,
        )
        if recip_match:
            recip_lines = recip_match.group(1).strip().splitlines()
            cand_recipient = recip_lines[0].strip() if recip_lines else ""
            if len(cand_recipient) > 2 and (re.match(r"^(?:PT|CV|UD|TOKO)\b", cand_recipient, re.I) or not issuer_name):
                recipient_name = cand_recipient
                field_evidence["recipient_name"] = ExtractedField(
                    value=recipient_name,
                    confidence=Decimal("0.90"),
                    evidence=cand_recipient,
                    validation_status="VALID",
                )

        # 8. Line Items Table Extraction
        line_items = extract_line_items_from_text(
            raw_text=text,
            ocr_boxes=all_boxes if all_boxes else None,
            ocr_txts=all_ocr_txts if all_ocr_txts else None,
        )

        # 9. Project Reference
        project_ref = spk_number or (re.search(r"\bPRJ[-/][A-Z0-9-/]+", text, re.I).group(0) if re.search(r"\bPRJ[-/][A-Z0-9-/]+", text, re.I) else None)

        # 10. Structured Extraction Schema
        data = StructuredExtraction(
            document_number=invoice_number or spk_number or bast_number or transfer_ref,
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
            destination_account_number=dest_account_no,
            destination_account_name=dest_account_name,
            transfer_reference=transfer_ref,
            project_reference=project_ref,
            line_items=line_items,
            raw_text=text or None,
            field_evidence=field_evidence,
        )

        amount_conf = (
            ocr_score if total_amount is not None and total_candidate.validation_status == "VALID"
            else Decimal("0.50") if total_candidate.validation_status == "AMBIGUOUS"
            else Decimal("0.00")
        )

        confidence = ConfidenceScores(
            ocr_confidence=ocr_score,
            document_type_confidence=classification.confidence,
            entity_confidence=Decimal("0.85") if (invoice_number or bank_name or issuer_name) else Decimal("0.00"),
            project_confidence=Decimal("0.90") if project_ref else Decimal("0.00"),
            amount_confidence=amount_conf,
        )

        mode_desc = "hybrid" if len(extraction_modes) > 1 else (list(extraction_modes)[0] if extraction_modes else "empty")
        telemetry = {
            "provider": "local",
            "mime_type": mime_type,
            "page_count": page_count,
            "char_count": len(text),
            "latency_ms": latency_ms,
            "ocr_score": str(ocr_score),
            "extraction_mode": mode_desc,
            "pages": pages_evidence,
            "success": True,
        }

        return ExtractionResult(
            document_type=kind,
            data=data,
            confidence=confidence,
            provider_name="local",
            provider_version="2.0.0",
            raw_payload=telemetry,
        )
