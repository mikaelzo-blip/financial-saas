"""Isolated benchmark harness comparing Current OCR (RapidOCR + pypdf) vs Baidu Unlimited-OCR.
Zero changes to production code.
"""
import asyncio
import base64
import json
import os
import re
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ground_truth import GROUND_TRUTH
from src.services.documents.local_provider import LocalExtractionProvider
from src.services.documents.classification import classify_text
from src.services.documents.normalization import extract_document_monetary_totals, parse_candidate_date
from src.services.documents.table_extractor import extract_line_items_from_text
from src.services.documents.rasterizer import open_pdf_document, render_pdf_page_to_image
from PIL import Image

HF_SPACE_URL = "https://baidu-unlimited-ocr.hf.space"
DET_RE = re.compile(r"<\|det\|>([^<\s]+)(?:\s*\[[^\]]*\])?\s*<\|/det\|>(.*)", re.DOTALL)


def strip_unlimited_ocr_det(raw: str) -> str:
    """Official post-processing from Baidu Unlimited-OCR repo to strip <|det|> markers."""
    blocks = []
    cur = None
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        m = DET_RE.match(line)
        if m:
            category, content = m.group(1).strip(), m.group(2).strip()
            if category == "image":
                continue
            if cur is not None:
                blocks.append(cur)
            cur = [content] if content else []
            continue
        if cur is None:
            cur = []
        cur.append(line)
    if cur is not None:
        blocks.append(cur)
    return "\n\n".join("\n".join(b) for b in blocks).strip()


class CurrentPipelineRunner:
    def __init__(self):
        self.provider = LocalExtractionProvider()

    async def run(self, doc_path: Path, mime_type: str) -> Dict[str, Any]:
        start = time.perf_counter()
        result = await self.provider.extract(doc_path, mime_type)
        latency_ms = int((time.perf_counter() - start) * 1000)

        data = result.data
        return {
            "provider": "Current (RapidOCR + pypdf)",
            "latency_ms": latency_ms,
            "raw_text": data.raw_text or "",
            "document_type": result.document_type.value if result.document_type else "UNKNOWN",
            "document_number": data.document_number,
            "transaction_date": str(data.transaction_date) if data.transaction_date else None,
            "due_date": str(data.due_date) if data.due_date else None,
            "issuer_name": data.issuer_name,
            "recipient_name": data.recipient_name,
            "subtotal": str(data.subtotal) if data.subtotal is not None else None,
            "vat_amount": str(data.vat_amount) if data.vat_amount is not None else None,
            "total_amount": str(data.total_amount) if data.total_amount is not None else None,
            "line_items": [
                {
                    "description": item.description,
                    "quantity": str(item.quantity) if item.quantity is not None else None,
                    "unit": item.unit,
                    "unit_price": str(item.unit_price) if item.unit_price is not None else None,
                    "amount": str(item.amount) if item.amount is not None else None,
                }
                for item in data.line_items
            ],
            "raw_payload": result.raw_payload,
        }


class UnlimitedOCRRunner:
    def __init__(self, base_url: str = HF_SPACE_URL, mode: str = "base"):
        self.base_url = base_url.rstrip("/")
        self.mode = mode  # 'base' (1024px) or 'gundam' (640px)
        self.session = requests.Session()
        self.session.trust_env = False

    def _upload_file(self, file_path: Path) -> str:
        mime = "image/png" if file_path.suffix.lower() == ".png" else "application/pdf"
        with open(file_path, "rb") as f:
            resp = self.session.post(
                f"{self.base_url}/gradio_api/upload",
                files={"files": (file_path.name, f, mime)},
                timeout=60,
            )
        resp.raise_for_status()
        uploaded_paths = resp.json()
        if not uploaded_paths or not isinstance(uploaded_paths, list):
            raise RuntimeError(f"Unexpected upload response: {uploaded_paths}")
        return uploaded_paths[0]

    def _call_run_ocr(self, remote_file_path: str, prompt: str = "document parsing.") -> str:
        payload = {
            "data": [
                {"path": remote_file_path, "meta": {"_type": "gradio.FileData"}},
                self.mode,
                prompt,
            ]
        }
        resp = self.session.post(
            f"{self.base_url}/gradio_api/call/run_ocr",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        event_id = resp.json().get("event_id")
        if not event_id:
            raise RuntimeError(f"No event_id returned from run_ocr: {resp.text}")

        # Stream SSE results
        stream_resp = self.session.get(
            f"{self.base_url}/gradio_api/call/run_ocr/{event_id}",
            stream=True,
            timeout=180,
        )
        stream_resp.raise_for_status()

        final_text = ""
        accumulated_text = ""
        for line in stream_resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                raw_json = line[len("data: ") :]
                try:
                    data = json.loads(raw_json)
                    if isinstance(data, list) and data:
                        chunk = data[0]
                        if isinstance(chunk, dict):
                            t = chunk.get("text", "")
                            if chunk.get("done"):
                                final_text = t
                            else:
                                accumulated_text = t
                except Exception:
                    continue

        return final_text or accumulated_text

    async def run(self, doc_path: Path, mime_type: str) -> Dict[str, Any]:
        start = time.perf_counter()
        raw_ocr_pages = []
        cleaned_ocr_pages = []

        if mime_type == "application/pdf":
            # PDF handling: render pages to temporary PNGs and run OCR per page
            pdfium_doc = open_pdf_document(doc_path)
            try:
                page_count = len(pdfium_doc)
                for i in range(min(page_count, 5)):
                    pil_img = render_pdf_page_to_image(pdfium_doc, i, dpi=200)
                    temp_img_path = doc_path.parent / f"_temp_{doc_path.stem}_p{i+1}.png"
                    try:
                        pil_img.save(str(temp_img_path), "PNG")
                        remote_path = self._upload_file(temp_img_path)
                        page_ocr_raw = self._call_run_ocr(remote_path, "document parsing.")
                        clean_page = strip_unlimited_ocr_det(page_ocr_raw)
                        raw_ocr_pages.append(page_ocr_raw)
                        cleaned_ocr_pages.append(clean_page)
                    finally:
                        if temp_img_path.exists():
                            temp_img_path.unlink()
            finally:
                pdfium_doc.close()
        else:
            remote_path = self._upload_file(doc_path)
            raw_ocr = self._call_run_ocr(remote_path, "document parsing.")
            clean_text = strip_unlimited_ocr_det(raw_ocr)
            raw_ocr_pages.append(raw_ocr)
            cleaned_ocr_pages.append(clean_text)

        latency_ms = int((time.perf_counter() - start) * 1000)

        combined_raw = "\n\n--- PAGE BREAK ---\n\n".join(raw_ocr_pages)
        combined_cleaned = "\n\n".join(cleaned_ocr_pages)

        # Downstream parsing using our standard financial parsers to test apples-to-apples
        classification = classify_text(combined_cleaned)
        totals = extract_document_monetary_totals(combined_cleaned)
        items = extract_line_items_from_text(combined_cleaned)

        # Dates & References
        inv_match = re.search(r"\b(?:INV|FAK|BILL)[-/][A-Z0-9-/]+", combined_cleaned, re.I)
        if not inv_match:
            inv_match = re.search(r"\b(?:no(?:mor)?\s*invoice|no(?:mor)?\s*faktur|invoice\s*no)\s*[:#]?\s*([A-Za-z0-9\-\/]+)", combined_cleaned, re.I)
        invoice_number = inv_match.group(1) if (inv_match and inv_match.groups()) else (inv_match.group(0) if inv_match else None)

        spk_match = re.search(r"\b(?:SPK|PRJ|WO)[-/][A-Z0-9-/]+", combined_cleaned, re.I)
        po_match = re.search(r"\b(?:PO)[-/][A-Z0-9-/]+", combined_cleaned, re.I)
        if not po_match:
            po_match = re.search(r"\b(?:po\s*no|nomor\s*po|po\s*number)\s*[:#]?\s*([A-Za-z0-9\-\/]+)", combined_cleaned, re.I)
        doc_no = invoice_number or (spk_match.group(0) if spk_match else (po_match.group(1) if (po_match and po_match.groups()) else (po_match.group(0) if po_match else None)))

        date_match = re.search(
            r"\b(\d{1,2}\s+(?:JANUARI|FEBRUARI|MARET|APRIL|MEI|JUNI|JULI|AGUSTUS|SEPTEMBER|OKTOBER|NOVEMBER|DESEMBER|JAN|FEB|PEB|MAR|APR|MAY|JUN|JUL|AGU|AGS|AUG|SEP|OKT|OCT|NOV|NOP|DES|DEC)\s+\d{4}"
            r"|\d{4}-\d{2}-\d{2}"
            r"|\d{2}[/-]\d{2}[/-]\d{4})\b",
            combined_cleaned,
            re.I,
        )
        tx_date = None
        if date_match:
            cand = parse_candidate_date(date_match.group(1))
            if cand.value:
                tx_date = str(cand.value)

        return {
            "provider": "Baidu Unlimited-OCR (Official ZeroGPU)",
            "latency_ms": latency_ms,
            "raw_output": combined_raw,
            "raw_text": combined_cleaned,
            "document_type": classification.document_type.value,
            "document_number": doc_no,
            "transaction_date": tx_date,
            "subtotal": str(totals["subtotal"]) if totals["subtotal"] is not None else None,
            "vat_amount": str(totals["vat_amount"]) if totals["vat_amount"] is not None else None,
            "total_amount": str(totals["total_amount"]) if totals["total_amount"] is not None else None,
            "line_items": [
                {
                    "description": item.description,
                    "quantity": str(item.quantity) if item.quantity is not None else None,
                    "unit": item.unit,
                    "unit_price": str(item.unit_price) if item.unit_price is not None else None,
                    "amount": str(item.amount) if item.amount is not None else None,
                }
                for item in items
            ],
        }
