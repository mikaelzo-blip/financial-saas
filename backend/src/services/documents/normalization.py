import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")
ValidationStatus = Literal["VALID", "AMBIGUOUS", "INVALID", "MISSING"]

_MONTH_MAP = {
    # Indonesian & English month names / abbreviations
    "JAN": 1, "JANUARI": 1, "JANUARY": 1,
    "FEB": 2, "FEBRUARI": 2, "FEBRUARY": 2, "PEB": 2, "PEBRUARI": 2, "PEBR": 2, "FEBR": 2,
    "MAR": 3, "MARET": 3, "MARCH": 3,
    "APR": 4, "APRIL": 4,
    "MEI": 5, "MAY": 5,
    "JUN": 6, "JUNI": 6, "JUNE": 6,
    "JUL": 7, "JULI": 7, "JULY": 7,
    "AGU": 8, "AGUSTUS": 8, "AGS": 8, "AUG": 8, "AUGUST": 8, "AUSTUS": 8, "AGUST": 8, "AUIG": 8, "ALIG": 8, "AIIG": 8, "AGST": 8,
    "SEP": 9, "SEPT": 9, "SEPTEMBER": 9,
    "OKT": 10, "OKTOBER": 10, "OCT": 10, "OCTOBER": 10, "OKTB": 10, "OKTR": 10,
    "NOV": 11, "NOVEMBER": 11, "NOP": 11, "NOPEMBER": 11,
    "DES": 12, "DESEMBER": 12, "DEC": 12, "DECEMBER": 12, "DESM": 12,
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
    # Reject regulatory disclaimers and words like "100 juta"
    if re.search(r"(?i)\b(?:juta|milyar)\b", clean_raw) or re.search(r"(?i)\b(?:diatas|di\s*atas|maksimal|minimal|melebihi)\b", clean_raw):
        return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")

    # Strip common Indonesian trailing notation like ",-" or ".-" (e.g. Rp 1.250.000,-)
    clean_raw = re.sub(r"[,.]\s*[-–—]$", "", clean_raw)
    # Fix OCR decimal separator as space, e.g. "93,414,661 30" -> "93,414,661.30"
    clean_raw = re.sub(r"(\d+)\s+(\d{2})$", r"\1.\2", clean_raw)

    token = re.sub(r"(?i)^(?:.*?(?:rp\.?|idr|eur|usd|sgd))\s*|\s", "", clean_raw)
    # If there's still non-numeric prefix like "PPN:", strip non-digits at the beginning
    token = re.sub(r"^[^\d]+", "", token)
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
        elif len(parts) == 2 and len(parts[1]) in (5, 6):
            # OCR missing intermediate thousand separator, e.g. 48,117241 or 72,590129
            normalized = "".join(parts)
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

    # Strip common prefixes like "Tanggal:", "TGL:", "Date:", "Trade Date:"
    value = re.sub(r"(?i)^(?:tanggal|tgl|date|trade\s*date)\s*[:=]?\s*", "", value).strip()

    # 1. ISO format: YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            parsed = date.fromisoformat(value)
            return NormalizedCandidate(value=parsed, confidence=Decimal("1"), evidence=raw, validation_status="VALID")
        except ValueError:
            return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")

    # 2. Named month format: e.g. "13 September 2026", "13-Sep-2026", "13 Sep 2026", "13-Aug-26", "13 Austus 2026"
    named_pattern = r"(?i)^\s*(\d{1,2})[\s\-./]+([a-zA-Z]+)[\s\-./]+(\d{2}|\d{4})\s*$"
    if m := re.match(named_pattern, value):
        day_str, month_str, year_str = m.group(1), m.group(2).upper(), m.group(3)
        month_num = _MONTH_MAP.get(month_str)
        if month_num:
            try:
                year_val = int(year_str)
                if len(year_str) == 2:
                    year_val = 2000 + year_val
                parsed = date(year_val, month_num, int(day_str))
                return NormalizedCandidate(value=parsed, confidence=Decimal("1"), evidence=raw, validation_status="VALID")
            except ValueError:
                return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")

    # 3. Numeric formats: DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, DD/MM/YY
    if match := re.fullmatch(r"(\d{1,2})([/\-.])(\d{1,2})\2(\d{2}|\d{4})", value):
        first, second, year_str = int(match[1]), int(match[3]), match[4]
        year_val = int(year_str)
        if len(year_str) == 2:
            year_val = 2000 + year_val
        # If both are <= 12 and ambiguous without day > 12 context, flag AMBIGUOUS to avoid silent guessing
        if first <= 12 and second <= 12:
            return NormalizedCandidate(value=None, confidence=Decimal("0.5"), evidence=raw, validation_status="AMBIGUOUS")
        try:
            if first > 12 and second <= 12:
                # Unambiguously DD/MM/YYYY
                parsed = date(year_val, second, first)
            elif first <= 12 and second > 12:
                # Unambiguously MM/DD/YYYY
                parsed = date(year_val, first, second)
            else:
                return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")
            return NormalizedCandidate(value=parsed, confidence=Decimal("1"), evidence=raw, validation_status="VALID")
        except ValueError:
            return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")

    return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")
