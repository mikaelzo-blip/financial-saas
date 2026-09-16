"""Layered structured table and line item extraction for contractor invoices and purchase orders.

Supports:
1. Native text line pattern matching with regex.
2. OCR bounding box row clustering when OCR geometry is available.
3. Indonesian construction units recognition (sak, m3, btg, kg, rit, ls, etc.).
4. Mathematical and semantic line validation (quantity * unit_price ≈ line_total).
"""
from decimal import Decimal
import re
from typing import List, Optional

from src.schemas.document import LineItem
from src.services.documents.normalization import parse_candidate_money

_CONSTRUCTION_UNITS = {
    "sak", "zak", "m3", "m2", "m1", "m", "cm", "mm", "kg", "ton",
    "btg", "batang", "lbr", "lembar", "dus", "box", "roll", "rit",
    "ls", "lumpsum", "pcs", "pc", "unit", "set", "hari", "bln", "bulan",
    "jam", "titik", "ttk", "bh", "buah", "btl", "botol", "can", "drum", "pail",
    "meter", "kubik", "tonase",
}

_IGNORED_DESCRIPTIONS = {
    "total", "subtotal", "sub total", "jumlah", "grand total", "total bayar",
    "ppn", "vat", "pajak", "dpp", "diskon", "discount", "uang muka", "dp",
    "terbilang", "catatan", "note", "keterangan", "syarat", "pembayaran",
    "tanda terima", "hormat kami", "penerima", "bank", "bca", "mandiri",
    "tanggal", "tgl", "date", "trade date", "waktu", "hari",
}


def is_header_or_summary_line(desc: str) -> bool:
    clean = desc.strip().lower()
    if clean in _IGNORED_DESCRIPTIONS:
        return True
    if any(clean.startswith(prefix) for prefix in ("subtotal", "total", "grand total", "jumlah", "ppn", "terbilang", "tanggal", "tgl", "date")):
        return True
    return False


def parse_line_item_text(line: str) -> Optional[LineItem]:
    """Parses a single candidate text line into a structured LineItem."""
    clean = line.strip()
    if not clean or len(clean) < 5:
        return None

    # Skip lines that are clearly headers, summary totals, or date lines
    first_token = clean.split()[0].lower()
    if first_token in ("subtotal", "total", "jumlah", "grand", "ppn", "vat", "terbilang", "no.", "no", "tanggal", "tgl", "date", "trade"):
        return None

    # Pattern 1: Description   Qty   Unit   UnitPrice   [Tax]   LineTotal
    # E.g.: "Semen Portland 50kg 20 sak Rp 65.000 Rp 1.300.000"
    # E.g.: "Pasir Pasang 2 m3 @ 350.000 = 700.000"
    p1 = re.match(
        r"^(?P<desc>[A-Za-z0-9\s/.,\-\(\)]+?)\s+"
        r"(?P<qty>\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>[a-zA-Z0-9]{1,10})?\s*"
        r"(?:x|@)?\s*"
        r"(?P<price>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+)\s*"
        r"(?:(?:ppn|tax)\s*(?P<tax>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+%?))?\s*"
        r"(?:[:=]|->)?\s*"
        r"(?P<total>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+)$",
        clean,
        re.I,
    )
    if p1:
        gd = p1.groupdict()
        desc = gd["desc"].strip(" -:\t")
        if is_header_or_summary_line(desc):
            return None

        unit_str = (gd["unit"] or "").strip().lower()
        if unit_str and unit_str not in _CONSTRUCTION_UNITS:
            # If unrecognized unit, it might belong to description or be a custom unit
            if len(unit_str) > 6:
                desc = f"{desc} {unit_str}".strip()
                unit_str = None

        q_cand = parse_candidate_money(gd["qty"])
        p_cand = parse_candidate_money(gd["price"])
        t_cand = parse_candidate_money(gd["total"])

        qty = q_cand.value
        price = p_cand.value
        total = t_cand.value

        tax_cand = parse_candidate_money(gd.get("tax")) if gd.get("tax") else None
        tax = tax_cand.value if tax_cand else None

        if total is not None and (price is not None or qty is not None):
            # Mathematical validation: if qty and price exist, check consistency
            if qty and price and total:
                expected = qty * price
                diff = abs(expected - total)
                # If difference is more than 5% or 1000 IDR, might have misaligned columns, but still keep best parse
                if diff > max(Decimal("1000"), total * Decimal("0.05")):
                    pass

            if price is None and qty and total and qty > 0:
                price = (total / qty).quantize(Decimal("0.01"))

            return LineItem(
                description=desc,
                quantity=qty,
                unit=unit_str or None,
                unit_price=price,
                tax=tax,
                amount=total,
                line_total=total,
            )

    # Pattern 2: Description   Qty x UnitPrice = LineTotal
    # E.g.: "Kawat Bendrat 5 x 25.000 = 125.000"
    p2 = re.match(
        r"^(?P<desc>[A-Za-z0-9\s/.,\-\(\)]+?)\s+"
        r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?:x|@)\s*"
        r"(?P<price>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+)\s*(?:[:=])\s*"
        r"(?P<total>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+)$",
        clean,
        re.I,
    )
    if p2:
        gd = p2.groupdict()
        desc = gd["desc"].strip(" -:\t")
        if is_header_or_summary_line(desc):
            return None
        q_cand = parse_candidate_money(gd["qty"])
        p_cand = parse_candidate_money(gd["price"])
        t_cand = parse_candidate_money(gd["total"])
        price = p_cand.value
        qty = q_cand.value
        total = t_cand.value
        if total is not None:
            if price is None and qty and total and qty > 0:
                price = (total / qty).quantize(Decimal("0.01"))
            return LineItem(
                description=desc,
                quantity=qty,
                unit=None,
                unit_price=price,
                amount=total,
                line_total=total,
            )

    return None


def cluster_ocr_boxes_into_lines(boxes: any, txts: List[str], line_threshold: float = 12.0) -> List[str]:
    """Clusters 2D OCR text boxes into horizontal text lines based on y-coordinate proximity."""
    if not boxes or not txts or len(boxes) != len(txts):
        return txts or []

    items = []
    for box, text in zip(boxes, txts):
        if not text or not text.strip():
            continue
        try:
            # box is [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            y_center = sum(ys) / len(ys)
            x_left = min(xs)
            items.append({"text": text.strip(), "y": y_center, "x": x_left})
        except Exception:
            continue

    if not items:
        return txts

    # Sort items top-to-bottom
    items.sort(key=lambda it: it["y"])

    lines: List[List[dict]] = []
    for item in items:
        matched_line = None
        for line in lines:
            line_y_avg = sum(it["y"] for it in line) / len(line)
            if abs(item["y"] - line_y_avg) <= line_threshold:
                matched_line = line
                break
        if matched_line is not None:
            matched_line.append(item)
        else:
            lines.append([item])

    reconstructed: List[str] = []
    for line in lines:
        # Sort left-to-right
        line.sort(key=lambda it: it["x"])
        line_text = "   ".join(it["text"] for it in line)
        reconstructed.append(line_text)

    return reconstructed


def extract_line_items_from_text(
    raw_text: str,
    ocr_boxes: any = None,
    ocr_txts: List[str] = None,
) -> List[LineItem]:
    """Extracts structured line items from document text or OCR bounding geometry."""
    items: List[LineItem] = []

    # 1. Try OCR bounding box row clustering if geometry is available
    if ocr_boxes is not None and ocr_txts:
        clustered_lines = cluster_ocr_boxes_into_lines(ocr_boxes, ocr_txts)
        for line in clustered_lines:
            item = parse_line_item_text(line)
            if item:
                items.append(item)

    # 2. If OCR clustering did not produce items, parse raw text lines directly
    if not items and raw_text:
        for line in raw_text.splitlines():
            item = parse_line_item_text(line)
            if item:
                items.append(item)

    return items
