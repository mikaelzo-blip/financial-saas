"""Tests for the one-time historical tenant-sequence transition."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "023_seed_tenant_sequences_from_history.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("historical_sequence_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_revision_follows_feature_012_schema_revision(migration) -> None:
    assert migration.revision == "023_historical_seq_bootstrap"
    assert migration.down_revision == "022_tenant_sequence_scope"


def test_inventory_contains_only_approved_sequence_sources(migration) -> None:
    assert tuple(source.namespace for source in migration.HISTORICAL_SOURCES) == (
        "TRX",
        "JE",
        "PRJ",
        "DOC",
        "INV",
        "BIL",
        "ADV",
        "REL",
        "MM",
        "SET",
    )

    assert migration.HISTORICAL_SOURCES[0].table_name == "transactions"
    assert migration.HISTORICAL_SOURCES[0].code_column == "transaction_code"
    assert migration.HISTORICAL_SOURCES[0].scope_kind == "YEAR"
    assert migration.HISTORICAL_SOURCES[-1].table_name == "settlements"
    assert migration.HISTORICAL_SOURCES[-1].scope_kind == "GLOBAL"


def test_year_code_parser_uses_code_year_and_exact_suffix_width(migration) -> None:
    parsed = migration._parse_historical_code(
        namespace="TRX",
        code="TRX-2026-000143",
        suffix_width=6,
        scope_kind="YEAR",
    )

    assert parsed.scope_key == "2026"
    assert parsed.value == 143


def test_set_parser_uses_global_scope(migration) -> None:
    parsed = migration._parse_historical_code(
        namespace="SET",
        code="SET-000027",
        suffix_width=6,
        scope_kind="GLOBAL",
    )

    assert parsed.scope_key == "GLOBAL"
    assert parsed.value == 27


@pytest.mark.parametrize(
    "namespace,code,width,scope_kind",
    [
        ("TRX", "TRX-2026-143", 6, "YEAR"),
        ("TRX", "TRX-2026-ABC143", 6, "YEAR"),
        ("TRX", "TRX-0000-000143", 6, "YEAR"),
        ("TRX", "TRX-2026-1000000", 6, "YEAR"),
        ("SET", "SET-27", 6, "GLOBAL"),
        ("SET", "SET-000000", 6, "GLOBAL"),
    ],
)
def test_managed_malformed_codes_fail_closed(
    migration,
    namespace: str,
    code: str,
    width: int,
    scope_kind: str,
) -> None:
    with pytest.raises(migration.HistoricalSequenceBootstrapError):
        migration._parse_historical_code(
            namespace=namespace,
            code=code,
            suffix_width=width,
            scope_kind=scope_kind,
        )


def test_known_nonsequential_codes_are_out_of_scope(migration) -> None:
    assert migration._classify_noncanonical_code("DOC", "DOC-WA-ABC123") == "OUT_OF_SCOPE"
    assert migration._classify_noncanonical_code("TRX", "OPB-2026-ABC123") == "OUT_OF_SCOPE"
    assert migration._classify_noncanonical_code("TRX", "DEP-AST-001-202609") == "OUT_OF_SCOPE"


def test_unresolved_namespace_shaped_codes_fail_closed(migration) -> None:
    with pytest.raises(migration.HistoricalSequenceBootstrapError):
        migration._classify_noncanonical_code("TRX", "TRX-2026-NOTNUM")


def test_monotonic_merge_never_lowers_existing_state(migration) -> None:
    assert migration._monotonic_value(existing_value=150, historical_value=143) == 150
    assert migration._monotonic_value(existing_value=143, historical_value=150) == 150
    assert migration._monotonic_value(existing_value=None, historical_value=150) == 150
