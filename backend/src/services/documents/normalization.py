import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")
ValidationStatus = Literal["VALID", "AMBIGUOUS", "INVALID", "MISSING"]


class NormalizedCandidate(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")
    value: T | None = None
    confidence: Decimal
    evidence: str | None = None
    validation_status: ValidationStatus


def parse_candidate_money(raw: str | None) -> NormalizedCandidate[Decimal]:
    if not raw or not raw.strip():
        return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="MISSING")
    token = re.sub(r"(?i)^(?:rp|idr)\s*|\s", "", raw.strip())
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
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            parsed = date.fromisoformat(value)
        elif match := re.fullmatch(r"(\d{2})([/\-])(\d{2})\2(\d{4})", value):
            first, second, year = int(match[1]), int(match[3]), int(match[4])
            if first <= 12 and second <= 12:
                return NormalizedCandidate(value=None, confidence=Decimal("0.5"), evidence=raw, validation_status="AMBIGUOUS")
            parsed = date(year, second, first)
        else:
            return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")
    except ValueError:
        return NormalizedCandidate(value=None, confidence=Decimal("0"), evidence=raw, validation_status="INVALID")
    return NormalizedCandidate(value=parsed, confidence=Decimal("1"), evidence=raw, validation_status="VALID")
