import re

from src.schemas.document import SourceMoney, TransferDetails
from src.services.documents.normalization import parse_candidate_money


def extract_transfer_details(text: str) -> TransferDetails:
    """Read labelled observations; never calculate a rate or infer a debit."""
    details = TransferDetails()
    labels = {
        "foreign": r"foreign\s+amount|jumlah\s+valas|amount\s+in\s+(?:eur|usd|sgd)",
        "principal": r"jumlah\s+rupiah(?:\s*/\s*amount\s+in\s+idr)?|idr\s+amount|amount\s+in\s+idr|jumlah\s+transfer|transfer\s+amount|nominal(?:\s+transfer)?|principal",
        "fee": r"biaya\s+admin(?:istrasi)?|admin\s+fee|bank\s+fees?|biaya\s+bank",
        "debit": r"total\s+debit|total\s+debet|jumlah\s+debit|debited\s+amount|proceeds",
    }
    for field, label in labels.items():
        pattern = rf"(?im)^[ \t]*(?:{label})[ \t]*[:=]?[ \t]*(?:\n[ \t]*)?(?:(IDR|Rp\.?|EUR|USD|SGD|GBP|JPY|AUD|CNY)[ \t]*)?([\d.,]+)[ \t]*$"
        hits = list(re.finditer(pattern, text))
        # Multiple labelled values need spatial/context review, not a largest-number guess.
        if len(hits) != 1:
            continue
        match = hits[0]
        currency = match.group(1)
        if not currency and re.search(r"(?i)rupiah|\bidr\b", match.group(0)):
            currency = "IDR"
        if not currency:
            continue
        currency = "IDR" if currency.lower().startswith("rp") else currency.upper()
        value = parse_candidate_money(match.group(2))
        if value.value is not None and value.validation_status == "VALID":
            setattr(details, field, SourceMoney(
                amount=value.value, currency_code=currency, evidence=match.group(0).strip(),
            ))
    purpose = re.search(r"(?im)^[ \t]*(?:tujuan\s+transfer|purpose|payment\s+details|berita)[ \t]*[:=][ \t]*([^\n]+)", text)
    if purpose:
        details.purpose = purpose.group(1).strip()
    requested = re.search(r"(?im)^.*\b(?:aplikasi\s+kiriman|overbooking\s+application|transfer\s+application|deal\s+confirmation|pending|menunggu|belum\s+berhasil|gagal|failed)\b.*$", text)
    executed = re.search(r"(?im)^[ \t]*(?:status[ \t]*:[ \t]*)?(?:transfer\s+berhasil|transfer\s+sukses|transaksi\s+berhasil|transfer\s+successful|completed)[ \t]*[.!]?[ \t]*$", text)
    if requested:
        details.execution_status = "REQUESTED"
        details.execution_evidence = requested.group(0).strip()
    elif executed:
        details.execution_status = "EXECUTED"
        details.execution_evidence = executed.group(0).strip()
    return details


def normalize_transfer_extraction(data):
    """Apply the transfer contract at provider and persistence boundaries."""
    details = data.transfer_details
    principal = (details.principal or details.foreign) if details else None
    evidence = {key: value for key, value in data.field_evidence.items()
                if key not in {"due_date", "subtotal", "vat_amount", "line_items"}}
    updates = {"line_items": [], "due_date": None, "subtotal": None, "vat_amount": None,
               "field_evidence": evidence}
    if details and any((details.principal, details.foreign, details.fee, details.debit)):
        updates.update(total_amount=principal.amount if principal else data.total_amount,
                       currency_code=principal.currency_code if principal else (data.currency_code or "IDR"))
    return data.model_copy(update=updates)


TRANSFER_REVIEW_FLAGS = {"TRANSFER_EXECUTION_UNCONFIRMED", "TRANSFER_AMOUNT_REVIEW"}


def transfer_review_flags(data) -> list[str]:
    details = data.transfer_details
    flags = []
    if not details or details.execution_status != "EXECUTED" or not (details.execution_evidence or "").strip():
        flags.append("TRANSFER_EXECUTION_UNCONFIRMED")
    # The posting contract has a single IDR amount, not a multi-currency/fee split.
    if data.currency_code != "IDR" or data.total_amount is None:
        flags.append("TRANSFER_AMOUNT_REVIEW")
    elif (data.admin_fee and data.admin_fee > 0) or (
        details and (
            (details.fee and details.fee.amount > 0)
            or (details.debit and (details.debit.currency_code != data.currency_code
                                  or details.debit.amount != data.total_amount))
        )
    ):
        flags.append("TRANSFER_AMOUNT_REVIEW")
    return flags
