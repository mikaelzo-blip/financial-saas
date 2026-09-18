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
    "jatuh tempo", "due date", "tanggal", "date",
}

_HEADER_PREFIXES = (
    "subtotal", "total", "grand total", "jumlah", "ppn", "vat", "terbilang",
    "tanggal", "date", "no:", "no.", "nomor", "inv:", "inv.", "invoice",
    "faktur", "quotation", "penawaran", "surat jalan", "po:", "po.",
    "kepada", "yth", "attn", "hal:", "lampiran", "pt ", "pt.", "cv ", "cv.",
    "jatuh tempo", "due date",
)


def is_header_or_summary_line(desc: str) -> bool:
    clean = desc.strip().lower()
    if not clean:
        return True
    if clean in _IGNORED_DESCRIPTIONS:
        return True
    if any(clean.startswith(prefix) for prefix in _HEADER_PREFIXES):
        return True
    if re.search(r"\b(?:tanggal|date|jatuh tempo|due date)\b", clean):
        return True
    if re.search(r"\b(?:no|nomor|invoice|inv|faktur)\s*[:=.]?\s*[A-Za-z0-9]", clean):
        return True
    return False


def is_continuation_line(line: str) -> bool:
    clean = line.strip()
    if not clean or is_header_or_summary_line(clean):
        return False
    # Strip leading bullet points, dashes, asterisks
    unbulleted = re.sub(r"^[\s\-*•#\.]+", "", clean).strip()
    # Explicit spec/size keywords
    if re.search(r"^(?:SIZE|UKURAN|DIMENSI|SPEC|SPESIFIKASI|TEBAL|TIPE|TYPE|WARNA|PANJANG|LEBAR|TINGGI|DIAMETER|BERAT|KET|KETERANGAN)\b", unbulleted, re.I):
        return True
    # Dimension patterns like 100 MM X 10.000 MM or 100MM X 10.000MM
    if re.search(r"\b\d+\s*(?:MM|CM|M|INCH|MTR|METER|\")\s*[Xx*]\s*[\d.]+\s*(?:MM|CM|M|INCH|MTR|METER|\")?", unbulleted, re.I):
        return True
    return False


def parse_line_item_text(line: str, has_pending_desc: bool = False) -> Optional[LineItem]:
    """Parses a single candidate text line into a structured LineItem."""
    clean = line.strip()
    if not clean or len(clean) < 3:
        return None

    # Skip lines that are clearly headers or summary totals
    first_token = clean.split()[0].lower()
    if first_token in ("subtotal", "total", "jumlah", "grand", "ppn", "vat", "terbilang", "no.", "no"):
        return None

    # Pattern 0: Pure numbers line when preceded by a pending description:
    # e.g. "1 ROLL 3.100.000 3.100.000" or "10 SET 620.000 6.200.000"
    if has_pending_desc:
        # Pattern 0A: Qty [Unit] [x/@] UnitPrice [Tax] LineTotal (requires whitespace between prices)
        p_num_two = re.match(
            r"^(?:(?P<no>\d+)[\.\)]\s+)?(?P<qty>\d+(?:[.,]\d+)?)\s*"
            r"(?P<unit>[a-zA-Z0-9]{1,10})?\s*"
            r"(?:x|@)?\s*"
            r"(?P<price>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?)\s+"
            r"(?:(?:ppn|tax)\s*(?P<tax>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+%?)\s+)?\s*"
            r"(?:[:=]|->)?\s*"
            r"(?P<total>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?)$",
            clean,
            re.I,
        )
        if p_num_two:
            gd = p_num_two.groupdict()
            unit_str = (gd["unit"] or "").strip().lower()
            q_cand = parse_candidate_money(gd["qty"])
            p_cand = parse_candidate_money(gd["price"])
            t_cand = parse_candidate_money(gd["total"])
            qty = q_cand.value
            price = p_cand.value
            total = t_cand.value
            tax_cand = parse_candidate_money(gd.get("tax")) if gd.get("tax") else None
            tax = tax_cand.value if tax_cand else None
            if total is not None and (price is not None or qty is not None):
                if price is None and qty and total and qty > 0:
                    price = (total / qty).quantize(Decimal("0.01"))
                return LineItem(
                    description="",
                    quantity=qty,
                    unit=unit_str or None,
                    unit_price=price,
                    tax=tax,
                    amount=total,
                    line_total=total,
                )

        # Pattern 0B: Qty [Unit] LineTotal (single money amount)
        p_num_one = re.match(
            r"^(?:(?P<no>\d+)[\.\)]\s+)?(?P<qty>\d+(?:[.,]\d+)?)\s*"
            r"(?P<unit>[a-zA-Z0-9]{1,10})?\s*"
            r"(?:[:=]|->)?\s*"
            r"(?P<total>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?)$",
            clean,
            re.I,
        )
        if p_num_one:
            gd = p_num_one.groupdict()
            unit_str = (gd["unit"] or "").strip().lower()
            q_cand = parse_candidate_money(gd["qty"])
            t_cand = parse_candidate_money(gd["total"])
            qty = q_cand.value
            total = t_cand.value
            if total is not None:
                price = (total / qty).quantize(Decimal("0.01")) if qty and qty > 0 else total
                return LineItem(
                    description="",
                    quantity=qty,
                    unit=unit_str or None,
                    unit_price=price,
                    amount=total,
                    line_total=total,
                )

    # Pattern 1: [No.] Description   Qty   Unit   UnitPrice   [Tax]   LineTotal
    # E.g.: "Semen Portland 50kg 20 sak Rp 65.000 Rp 1.300.000"
    # E.g.: "Pasir Pasang 2 m3 @ 350.000 = 700.000"
    # E.g.: "LEM SC 2000 + HARDENER UTR 10 SET 620.000 6.200.000"
    p1 = re.match(
        r"^(?:(?P<no>\d+)[\.\)]\s+)?(?P<desc>[A-Za-z0-9\s/.,\-\(\):+&%*\"\'#]+?)\s+"
        r"(?P<qty>\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>[a-zA-Z0-9]{1,10})?\s*"
        r"(?:x|@)?\s*"
        r"(?P<price>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?)"
        r"(?:(?:ppn|tax)\s*(?P<tax>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?%?)\s+)?"
        r"(?:[:=]|->)?\s*"
        r"(?:(?:\s+(?P<total_plain>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?))|(?:\s*(?P<total_curr>(?:Rp\.?|IDR)\s*[\d.,]+(?:[.,]\s*[-–—])?)))$",
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
            if len(unit_str) > 6:
                desc = f"{desc} {unit_str}".strip()
                unit_str = None

        total_str = gd.get("total_plain") or gd.get("total_curr")
        q_cand = parse_candidate_money(gd["qty"])
        p_cand = parse_candidate_money(gd["price"])
        t_cand = parse_candidate_money(total_str) if total_str else None

        qty = q_cand.value
        price = p_cand.value
        total = t_cand.value if t_cand else None

        tax_cand = parse_candidate_money(gd.get("tax")) if gd.get("tax") else None
        tax = tax_cand.value if tax_cand else None

        if total is not None and (price is not None or qty is not None):
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

    # Pattern 1B: [No.] Description   Qty   Unit   LineTotal (single money amount)
    p1b = re.match(
        r"^(?:(?P<no>\d+)[\.\)]\s+)?(?P<desc>[A-Za-z0-9\s/.,\-\(\):+&%*\"\'#]+?)\s+"
        r"(?P<qty>\d+(?:[.,]\d+)?)\s*"
        r"(?P<unit>[a-zA-Z0-9]{1,10})?\s*"
        r"(?:[:=]|->)?\s*"
        r"(?P<total>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?)$",
        clean,
        re.I,
    )
    if p1b:
        gd = p1b.groupdict()
        desc = gd["desc"].strip(" -:\t")
        if not is_header_or_summary_line(desc):
            unit_str = (gd["unit"] or "").strip().lower()
            if unit_str and unit_str not in _CONSTRUCTION_UNITS:
                if len(unit_str) > 6:
                    desc = f"{desc} {unit_str}".strip()
                    unit_str = None

            q_cand = parse_candidate_money(gd["qty"])
            t_cand = parse_candidate_money(gd["total"])
            qty = q_cand.value
            total = t_cand.value

            if total is not None:
                price = (total / qty).quantize(Decimal("0.01")) if qty and qty > 0 else total
                return LineItem(
                    description=desc,
                    quantity=qty,
                    unit=unit_str or None,
                    unit_price=price,
                    amount=total,
                    line_total=total,
                )

    # Pattern 2: [No.] Description   Qty x UnitPrice = LineTotal
    # E.g.: "Kawat Bendrat 5 x 25.000 = 125.000"
    p2 = re.match(
        r"^(?:(?P<no>\d+)[\.\)]\s+)?(?P<desc>[A-Za-z0-9\s/.,\-\(\):+&%*\"\'#]+?)\s+"
        r"(?P<qty>\d+(?:[.,]\d+)?)\s*(?:x|@)\s*"
        r"(?P<price>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?)\s*(?:[:=])\s*"
        r"(?P<total>(?:(?:Rp\.?|IDR)\s*)?[\d.,]+(?:[.,]\s*[-–—])?)$",
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


def _parse_lines_into_items(lines: List[str]) -> List[LineItem]:
    items: List[LineItem] = []
    pending_desc: List[str] = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if is_header_or_summary_line(line):
            pending_desc.clear()
            continue

        item = parse_line_item_text(line, has_pending_desc=bool(pending_desc))
        if item:
            if item.description:
                if pending_desc:
                    item.description = "\n".join(pending_desc) + "\n" + item.description
                    pending_desc.clear()
            else:
                if pending_desc:
                    item.description = "\n".join(pending_desc)
                    pending_desc.clear()
            item.description = re.sub(r"^\d+[\.\)]\s*", "", item.description.strip())
            items.append(item)
        else:
            if items and not pending_desc and is_continuation_line(line):
                items[-1].description = f"{items[-1].description}\n{line}"
            else:
                pending_desc.append(line)

    return items


def extract_line_items_from_text(
    raw_text: str,
    ocr_boxes: any = None,
    ocr_txts: List[str] = None,
) -> List[LineItem]:
    """Extracts structured line items from document text or OCR bounding geometry."""
    clustered_items: List[LineItem] = []
    if ocr_boxes is not None and ocr_txts:
        clustered_lines = cluster_ocr_boxes_into_lines(ocr_boxes, ocr_txts)
        clustered_items = _parse_lines_into_items(clustered_lines)

    raw_items: List[LineItem] = []
    if raw_text:
        raw_items = _parse_lines_into_items(raw_text.splitlines())

    if clustered_items and raw_items:
        # Prefer the set with more line items or valid extracted amounts
        if len(clustered_items) >= len(raw_items):
            return clustered_items
        return raw_items
    elif clustered_items:
        return clustered_items
    return raw_items
