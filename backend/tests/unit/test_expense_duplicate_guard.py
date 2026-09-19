from decimal import Decimal

from src.services.documents.expense_duplicate_guard import (
    DuplicateVerdict,
    collect_reference_numbers,
    evaluate_reference_duplicate,
)


def test_collect_reference_numbers_normalizes_and_dedupes():
    candidate = {"external_reference": "2070-8003-319"}
    extracted = {
        "transfer_reference": "20708003319",
        "invoice_number": "20708003319",
        "document_number": None,
    }
    refs = collect_reference_numbers(candidate, extracted)
    assert refs == {"20708003319"}


def test_collect_reference_numbers_empty_when_all_blank():
    assert collect_reference_numbers({}, {"invoice_number": "", "transfer_reference": None}) == set()


def test_matching_reference_and_similar_amount_is_duplicate():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("48930988.86"), [("20708003319", Decimal("48930988.86"))]
    )
    assert isinstance(verdict, DuplicateVerdict)
    assert verdict.duplicate is True
    assert verdict.flagged is False
    assert verdict.matched_code == "20708003319"


def test_matching_reference_but_far_amount_is_flagged_not_rejected():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("1000000.00"), [("20708003319", Decimal("48930988.86"))]
    )
    assert verdict.duplicate is False
    assert verdict.flagged is True


def test_similar_amount_without_matching_reference_is_allowed():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("48930988.86"), [("BILL-999", Decimal("48930988.86"))]
    )
    assert verdict.duplicate is False
    assert verdict.flagged is False


def test_no_reference_match_at_all_is_allowed():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("48930988.86"), [("BILL-999", Decimal("1.00"))]
    )
    assert verdict.duplicate is False
    assert verdict.flagged is False


def test_empty_references_never_duplicate():
    verdict = evaluate_reference_duplicate(set(), Decimal("48930988.86"), [("BILL-001", Decimal("48930988.86"))])
    assert verdict.duplicate is False
    assert verdict.flagged is False


def test_separator_variants_are_treated_as_equal():
    verdict = evaluate_reference_duplicate(
        {"20708003319"}, Decimal("48930988.86"), [("2070-8003-319", Decimal("48930988.86"))]
    )
    assert verdict.duplicate is True


def test_scans_all_references_and_finds_later_exact_duplicate():
    # I1: references {111, 222}; 111 matches with a FAR amount, 222 is an EXACT
    # duplicate. Spec D3a says compare ALL numbers, so this must be a duplicate.
    verdict = evaluate_reference_duplicate(
        {"111", "222"},
        Decimal("500.00"),
        [("111", Decimal("1000.00")), ("222", Decimal("500.00"))],
    )
    assert verdict.duplicate is True
    assert verdict.matched_code == "222"


def test_flags_only_after_scanning_all_references():
    # No exact duplicate anywhere -> flagged, and the flag is reported.
    verdict = evaluate_reference_duplicate(
        {"111", "222"},
        Decimal("500.00"),
        [("111", Decimal("1000.00")), ("222", Decimal("9000.00"))],
    )
    assert verdict.duplicate is False
    assert verdict.flagged is True
