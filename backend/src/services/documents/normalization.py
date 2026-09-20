import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")
ValidationStatus = Literal["VALID", "AMBIGUOUS", "INVALID", "MISSING"]

_MONTH_MAP = {
    # Indonesian & English month names / abbreviations
    "JAN": 1, "JANUARI": 1, "JANUARY": 1,
    "FEB": 2, "FEBRUARI": 2, "FEBRUARY": 2, "PEB": 2, "PEBRUARI": 2,
    "MAR": 3, "MARET": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MEI": 5, "MAY": 5,
    "JUN": 6, "JUNI": 6, "JUNE": 6,
    "JUL": 7, "JULI": 7, "JULY": 7,
    "AGU": 8, "AGUSTUS": 8, "AGS": 8, "AUG": 8, "AUGUST": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OKT": 10, "OKTOBER": 10, "OCT": 10, "OCTOBER": 10,
    "NOV": 11, "NOVEMBER": 11, "NOP": 11, "NOPEMBER": 11,
    "DES": 12, "DESEMBER": 12, "DEC": 12, "DECEMBER": 12,
}


class NormalizedCandidate(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")
    value: T | None = None
    confidence: Decimal
    evidence: str | None = None
    validation_status: ValidationStatus


def parse_candidate_money(raw: str | None) -> NormalizedCandidate[Decimal]:
    if not raw or not raw.strip():
        return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="MISSING")

    clean_raw = raw.strip()
    # Strip common Indonesian trailing notation like ",-" or ".-" (e.g. Rp 1.250.000,-)
    clean_raw = re.sub(r"[,.]\s*[-–—]$", "", clean_raw)

    token = re.sub(r"(?i)^(?:.*?(?:rp\.?|idr))\s*", "", clean_raw)
    # Strip tax percentage or label prefixes like "PPN (11%):", "VAT 12%:", "Total:", "Subtotal:"
    token = re.sub(r"(?i)^(?:ppn|vat|pajak(?:\s+pertambahan\s+nilai)?)\s*(?:\(?\s*\d+\s*%\s*\)?)?\s*[:=]?\s*", "", token)
    # If there's still non-numeric prefix like "PPN:", strip non-digits at the beginning
    token = re.sub(r"^[^\d]+", "", token)
    token = re.sub(r"\s+", "", token)
    if not re.fullmatch(r"\d[\d.,]*", token):
        return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")

    comma, dot = token.count(","), token.count(".")
    if comma and dot:
        decimal_mark = "," if token.rfind(",") > token.rfind(".") else "."
        integer, fraction = token.rsplit(decimal_mark, 1)
        if len(fraction) != 2:
            return NormalizedCandidate(value=None, confidence=Decimal("0.5"), evidence=raw, validation_status="AMBIGUOUS")
        normalized = integer.replace(",", "").replace(".", "") + "." + fraction
    elif comma or dot:
        mark = "," if comma else "."
        parts = token.split(mark)
        if len(parts) > 2 and all(len(part) == 3 for part in parts[1:]):
            normalized = "".join(parts)
        elif len(parts) == 2 and len(parts[1]) == 2:
            normalized = parts[0] + "." + parts[1]
        elif len(parts) == 2 and len(parts[1]) == 3:
            # When context is Indonesian currency with prefix Rp / IDR or exactly 3 digits (e.g. 125.000),
            # if the prefix or token had Rp/IDR, it is unambiguous Indonesian Rupiah thousand separator.
            if re.search(r"(?i)\b(?:rp\.?|idr)(?:\b|(?=\d))", raw or ""):
                normalized = "".join(parts)
            else:
                return NormalizedCandidate(value=None, confidence=Decimal("0.5"), evidence=raw, validation_status="AMBIGUOUS")
        else:
            return NormalizedCandidate(value=None, confidence=Decimal("0.5"), evidence=raw, validation_status="AMBIGUOUS")
    else:
        normalized = token
    try:
        value = Decimal(normalized)
    except InvalidOperation:
        return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")
    return NormalizedCandidate(value=value, confidence=Decimal("1"), evidence=raw, validation_status="VALID")


def parse_candidate_date(raw: str | None) -> NormalizedCandidate[date]:
    if not raw or not raw.strip():
        return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="MISSING")
    value = raw.strip()

    # 1. ISO format: YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            parsed = date.fromisoformat(value)
            return NormalizedCandidate(value=parsed, confidence=Decimal("1"), evidence=raw, validation_status="VALID")
        except ValueError:
            return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")

    # 2. Named month format: e.g. "13 September 2026", "13-Sep-2026", "13 Sep 2026", "September 13, 2026"
    named_pattern = r"(?i)^\s*(?:tanggal|tgl|date)?\s*[:=]?\s*(\d{1,2})[\s\-]+([a-zA-Z]+)[\s\-]+(\d{4})\s*$"
    if m := re.match(named_pattern, value):
        day_str, month_str, year_str = m.group(1), m.group(2).upper(), m.group(3)
        month_num = _MONTH_MAP.get(month_str)
        if month_num:
            try:
                parsed = date(int(year_str), month_num, int(day_str))
                return NormalizedCandidate(value=parsed, confidence=Decimal("1"), evidence=raw, validation_status="VALID")
            except ValueError:
                return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")

    # 3. Numeric formats: DD/MM/YYYY, DD-MM-YYYY
    if match := re.fullmatch(r"(\d{2})([/\-])(\d{2})\2(\d{4})", value):
        first, second, year = int(match[1]), int(match[3]), int(match[4])
        # If both are <= 12 and ambiguous without day > 12 context, flag AMBIGUOUS to avoid silent guessing
        if first <= 12 and second <= 12:
            return NormalizedCandidate(value=None, confidence=Decimal("0.5"), evidence=raw, validation_status="AMBIGUOUS")
        try:
            if first > 12 and second <= 12:
                # Unambiguously DD/MM/YYYY
                parsed = date(year, second, first)
            elif first <= 12 and second > 12:
                # Unambiguously MM/DD/YYYY
                parsed = date(year, first, second)
            else:
                return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")
            return NormalizedCandidate(value=parsed, confidence=Decimal("1"), evidence=raw, validation_status="VALID")
        except ValueError:
            return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")

    return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")


def extract_document_monetary_totals(text: str | None) -> dict[str, Any]:
    """Extract and distinguish subtotal, vat_amount, and total_amount from document text.

    Enforces strict semantic priority for canonical total_amount:
    1. GRAND TOTAL / TOTAL BAYAR / TOTAL PEMBAYARAN / JUMLAH DIBAYARKAN
    2. TOTAL AMOUNT / TOTAL TAGIHAN / JUMLAH TAGIHAN / TOTAL TRANSFER / JUMLAH TRANSFER
    3. AMOUNT DUE / TOTAL DUE / BALANCE DUE / JUMLAH JATUH TEMPO
    4. NET PAYABLE / TOTAL PAYABLE / NET AMOUNT / JUMLAH BERSIH
    5. TOTAL (generic final total line, excluding subtotal/ex-tax/dpp/qty)
    6. Calculated sum (subtotal + vat_amount) if both present
    7. Standalone formatted currency
    8. Subtotal only as fallback when no final total exists.

    Invariants:
    - Never select Ex Tax, Subtotal, or DPP as total_amount when a final total is present.
    """
    from typing import Any

    empty_cand = parse_candidate_money(None)
    if not text or not text.strip():
        return {
            "total_amount": None,
            "total_evidence": None,
            "total_candidate": empty_cand,
            "subtotal": None,
            "subtotal_evidence": None,
            "subtotal_candidate": empty_cand,
            "vat_amount": None,
            "vat_evidence": None,
            "vat_candidate": empty_cand,
        }

    # 1. Subtotal / Ex-Tax / DPP extraction
    subtotal_cand = empty_cand
    subtotal_val: Decimal | None = None
    subtotal_ev: str | None = None
    sub_patterns = [
        r"\b(?:sub[\s-]*total|dpp|dasar\s+pengenaan\s+pajak|ex[\s-]*tax|exclusive\s+tax|sebelum\s+pajak|total\s+dpp|total\s+sebelum\s+pajak|total[\s-]+ex[\s-]*tax)\b\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,\-]+)",
    ]
    for pat in sub_patterns:
        for m in re.finditer(pat, text, re.I):
            cand = parse_candidate_money(m.group(0))
            if cand.value is None:
                cand = parse_candidate_money(m.group(1))
            if cand.value is not None:
                subtotal_cand = cand
                subtotal_val = cand.value
                subtotal_ev = m.group(0).strip()
                break
        if subtotal_val is not None:
            break

    # 2. VAT / PPN Amount extraction
    vat_cand = empty_cand
    vat_val: Decimal | None = None
    vat_ev: str | None = None
    vat_patterns = [
        r"(?<!faktur\s)(?<!faktur)(?<!nomor\s)(?<!nomor)(?<!seri\s)(?<!seri)(?<!kantor\s)(?<!objek\s)(?<!wajib\s)\b(?:ppn|vat|pajak\s+pertambahan\s+nilai|nilai\s+pajak|jumlah\s+pajak)(?:\s*\(?\s*1[12]\s*%\s*\)?)?\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,\-]+)",
    ]
    for pat in vat_patterns:
        for m in re.finditer(pat, text, re.I):
            # Check surrounding context to avoid false matches like "Faktur Pajak: 040..."
            start_pos = max(0, m.start() - 25)
            prefix = text[start_pos:m.start()].lower()
            if any(w in prefix for w in ("faktur", "seri", "nomor", "npwp", "kantor", "objek", "wajib")):
                continue

            cand = parse_candidate_money(m.group(0))
            if cand.value is None:
                cand = parse_candidate_money(m.group(1))
            if cand.value is not None:
                # Serial numbers, tax invoice codes or NPWP have 15-16 bare digits
                raw_digits = re.sub(r"\D", "", m.group(1))
                if len(raw_digits) >= 13 and ("." not in m.group(1) and "," not in m.group(1)):
                    continue
                vat_cand = cand
                vat_val = cand.value
                vat_ev = m.group(0).strip()
                break
        if vat_val is not None:
            break

    # 3. Total Amount extraction by priority
    total_cand = empty_cand
    total_val: Decimal | None = None
    total_ev: str | None = None

    # Priority 1: GRAND TOTAL
    p1_patterns = [
        r"\b(?:grand\s+total|total\s+bayar|total\s+pembayaran|jumlah\s+pembayaran|jumlah\s+dibayarkan)\b\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,\-]+)",
    ]
    for pat in p1_patterns:
        for m in re.finditer(pat, text, re.I):
            cand = parse_candidate_money(m.group(0))
            if cand.value is not None:
                total_cand = cand
                total_val = cand.value
                total_ev = m.group(0).strip()
                break
        if total_val is not None:
            break

    # Priority 2: TOTAL AMOUNT / TOTAL TAGIHAN / JUMLAH TAGIHAN / TOTAL TRANSFER / JUMLAH TRANSFER
    if total_val is None:
        p2_patterns = [
            r"\b(?:total\s+amount|total\s+tagihan|jumlah\s+tagihan|total\s+transfer|jumlah\s+transfer)\b\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,\-]+)",
        ]
        for pat in p2_patterns:
            for m in re.finditer(pat, text, re.I):
                cand = parse_candidate_money(m.group(0))
                if cand.value is not None:
                    total_cand = cand
                    total_val = cand.value
                    total_ev = m.group(0).strip()
                    break
            if total_val is not None:
                break

    # Priority 3: AMOUNT DUE / TOTAL DUE
    if total_val is None:
        p3_patterns = [
            r"\b(?:amount\s+due|total\s+due|balance\s+due|jumlah\s+jatuh\s+tempo)\b\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,\-]+)",
        ]
        for pat in p3_patterns:
            for m in re.finditer(pat, text, re.I):
                cand = parse_candidate_money(m.group(0))
                if cand.value is not None:
                    total_cand = cand
                    total_val = cand.value
                    total_ev = m.group(0).strip()
                    break
            if total_val is not None:
                break

    # Priority 4: NET PAYABLE
    if total_val is None:
        p4_patterns = [
            r"\b(?:net\s+payable|total\s+payable|net\s+amount|jumlah\s+bersih)\b\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,\-]+)",
        ]
        for pat in p4_patterns:
            for m in re.finditer(pat, text, re.I):
                cand = parse_candidate_money(m.group(0))
                if cand.value is not None:
                    total_cand = cand
                    total_val = cand.value
                    total_ev = m.group(0).strip()
                    break
            if total_val is not None:
                break

    # Priority 5: Generic TOTAL (where TOTAL is NOT subtotal/dpp/ex-tax/qty/item)
    if total_val is None:
        p5_pat = r"(?<!sub\s)(?<!sub)(?<!sub-)(?<!dpp\s)(?<!dpp)(?<!ex\s)(?<!ex-)\b(?:total|jumlah)\b(?!\s*[-:]?\s*(?:ex[\s-]*tax|dpp|sebelum\s+pajak|qty|kuantiti|barang|item|items))\s*[:=]?\s*(?:Rp\.?|IDR)?\s*([\d.,\-]+)"
        p5_matches = []
        for m in re.finditer(p5_pat, text, re.I):
            cand = parse_candidate_money(m.group(0))
            if cand.value is not None:
                p5_matches.append((m, cand))

        if p5_matches:
            if subtotal_val is not None and vat_val is not None:
                expected = subtotal_val + vat_val
                exact_match = next((mc for mc in p5_matches if mc[1].value == expected), None)
                if exact_match:
                    m, cand = exact_match
                    total_cand, total_val, total_ev = cand, cand.value, m.group(0).strip()

            if total_val is None:
                non_sub = [mc for mc in p5_matches if mc[1].value != subtotal_val]
                if non_sub:
                    m, cand = non_sub[-1]
                    total_cand, total_val, total_ev = cand, cand.value, m.group(0).strip()
                elif p5_matches:
                    m, cand = p5_matches[-1]
                    total_cand, total_val, total_ev = cand, cand.value, m.group(0).strip()

    # Priority 6: If subtotal and vat exist, check if the mathematical sum appears in text
    if total_val is None and subtotal_val is not None and vat_val is not None:
        expected_total = subtotal_val + vat_val
        for m in re.finditer(r"(?:Rp\.?|IDR)?\s*([\d.,]+)", text, re.I):
            cand = parse_candidate_money(m.group(0))
            if cand.value == expected_total:
                total_cand, total_val, total_ev = cand, cand.value, m.group(0).strip()
                break
        if total_val is None:
            total_val = expected_total
            total_ev = f"Calculated: {subtotal_val} + {vat_val}"
            total_cand = NormalizedCandidate(value=total_val, confidence=Decimal("0.95"), evidence=total_ev, validation_status="VALID")

    # Priority 7: Standalone formatted currency
    if total_val is None:
        for pat in [r"(?:Rp\.?|IDR)\s*([\d.,\-]+)", r"\b\d{1,3}(?:\.\d{3})+(?:,\d{2})?\b|\b\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b"]:
            candidates = []
            for m in re.finditer(pat, text, re.I):
                cand = parse_candidate_money(m.group(0))
                if cand.value is not None and cand.value != subtotal_val:
                    candidates.append((m, cand))
            if candidates:
                m, cand = candidates[-1]
                total_cand, total_val, total_ev = cand, cand.value, m.group(0).strip()
                break

    # Priority 8: Subtotal only as fallback when no final total exists
    if total_val is None and subtotal_val is not None:
        total_val = subtotal_val
        total_ev = subtotal_ev
        total_cand = subtotal_cand

    return {
        "total_amount": total_val,
        "total_evidence": total_ev,
        "total_candidate": total_cand,
        "subtotal": subtotal_val,
        "subtotal_evidence": subtotal_ev,
        "subtotal_candidate": subtotal_cand,
        "vat_amount": vat_val,
        "vat_evidence": vat_ev,
        "vat_candidate": vat_cand,
    }
