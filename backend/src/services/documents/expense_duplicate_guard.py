"""Anti double-count guard for transfer proofs recorded as direct expenses.

Reference-number based (NOT amount based): an identical normalized reference
number combined with a similar amount is a duplicate. A similar amount with no
matching reference is allowed -- two different transactions may coincidentally
share an amount. File uniqueness is guaranteed by Document.file_hash + created_at.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Optional, Sequence

from src.services.documents.matching import normalize_doc_number

AMOUNT_TOLERANCE = Decimal("0.01")  # +/-1%

_SEPARATORS = re.compile(r"[^0-9A-Z]")


def canonical_reference(value: object) -> str:
    """Normalize a reference for comparison, ignoring separator differences.

    Builds on the shared `normalize_doc_number` (uppercase, whitespace stripped)
    and additionally removes separators so that `2070-8003-319` == `20708003319`.
    The shared normalizer is intentionally NOT changed: other matching logic
    relies on its exact behavior.
    """
    base = normalize_doc_number(str(value)) if value not in (None, "") else ""
    if not base:
        return ""
    return _SEPARATORS.sub("", base)


@dataclass
class DuplicateVerdict:
    duplicate: bool
    flagged: bool
    reason: Optional[str] = None
    matched_reference: Optional[str] = None
    matched_code: Optional[str] = None


def collect_reference_numbers(
    candidate: Mapping[str, object], extracted: Mapping[str, object]
) -> set[str]:
    """Collect and normalize every reference number on the document.

    Sources are intentionally broad (transfer reference, invoice number,
    document number, external reference) because OCR currently copies the bank
    transfer reference into several fields.
    """
    raw_values = [
        extracted.get("transfer_reference"),
        extracted.get("invoice_number"),
        extracted.get("document_number"),
        candidate.get("external_reference"),
        candidate.get("invoice_number"),
    ]
    refs: set[str] = set()
    for value in raw_values:
        normalized = canonical_reference(value)
        if normalized:
            refs.add(normalized)
    return refs


def _amounts_similar(a: Decimal, b: Decimal) -> bool:
    if a <= 0 or b <= 0:
        return False
    base = max(a, b)
    return abs(a - b) <= base * AMOUNT_TOLERANCE


def evaluate_reference_duplicate(
    references: set[str],
    amount: Decimal,
    existing: Sequence[tuple[str, Decimal]],
) -> DuplicateVerdict:
    """Compare document references against already-recorded (code, amount) pairs.

    Scans EVERY pair (spec D3a: compare all reference numbers). Returns a
    duplicate as soon as any reference matches with a similar amount; only
    returns `flagged` after the whole list has been scanned, so a later exact
    duplicate is never masked by an earlier far-amount match.
    """
    scanner = DuplicateScanner(references, amount)
    for code, recorded_amount in existing:
        if scanner.feed(code, recorded_amount):
            break
    return scanner.result()


class DuplicateScanner:
    """Incremental, streaming-friendly version of the duplicate comparison.

    Lets callers feed (code, amount) pairs one row at a time (e.g. from a
    streamed SQL cursor) so the full transaction history is never materialised
    in memory. `feed` returns True as soon as a real duplicate is found, so the
    caller can stop reading; `result` yields the flagged verdict (if any) after
    every row has been scanned. Correctness is identical to
    `evaluate_reference_duplicate`.
    """

    def __init__(self, references: set[str], amount: Decimal):
        self._references = references
        self._amount = Decimal(str(amount))
        self._first_flag: Optional[DuplicateVerdict] = None
        self._duplicate: Optional[DuplicateVerdict] = None

    def feed(self, code: object, recorded_amount: object) -> bool:
        if self._duplicate is not None or not self._references:
            return self._duplicate is not None
        code_norm = canonical_reference(code) if code else ""
        if not code_norm or code_norm not in self._references:
            return False
        if _amounts_similar(self._amount, Decimal(str(recorded_amount))):
            self._duplicate = DuplicateVerdict(
                duplicate=True,
                flagged=False,
                reason=f"Reference {code_norm} already recorded as {code}; possible duplicate",
                matched_reference=code_norm,
                matched_code=code,
            )
            return True
        if self._first_flag is None:
            self._first_flag = DuplicateVerdict(
                duplicate=False,
                flagged=True,
                reason=f"Reference {code_norm} matches {code} but amount differs; review required",
                matched_reference=code_norm,
                matched_code=code,
            )
        return False

    def result(self) -> DuplicateVerdict:
        if self._duplicate is not None:
            return self._duplicate
        if self._first_flag is not None:
            return self._first_flag
        return DuplicateVerdict(duplicate=False, flagged=False)
