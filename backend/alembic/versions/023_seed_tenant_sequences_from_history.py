"""023_historical_seq_bootstrap

Revision ID: 023_historical_seq_bootstrap
Revises: 022_tenant_sequence_scope
Create Date: 2026-09-10

This is a one-time, online PostgreSQL transition. It derives sequence
high-water marks from canonical historical business identifiers and merges them
monotonically into tenant_sequences. Historical business rows are never
updated, deleted, or renumbered.

The downgrade intentionally fails closed. tenant_sequences does not record
whether a row was seeded by this revision, pre-existed it, or was advanced by
runtime allocation, so deleting or reversing allocation state cannot be proven
safe. Historical records are therefore preserved and the allocation state is
retained.
"""

from dataclasses import dataclass
import re
import uuid
from collections.abc import Iterable
from typing import Final, Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "023_historical_seq_bootstrap"
down_revision: Union[str, None] = "022_tenant_sequence_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class HistoricalSequenceBootstrapError(RuntimeError):
    """Raised when historical sequence state cannot be interpreted safely."""


@dataclass(frozen=True)
class HistoricalSource:
    namespace: str
    table_name: str
    code_column: str
    organization_column: str
    suffix_width: int
    scope_kind: str
    out_of_scope_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedHistoricalCode:
    scope_key: str
    value: int


HISTORICAL_SOURCES: Final[tuple[HistoricalSource, ...]] = (
    HistoricalSource("TRX", "transactions", "transaction_code", "organization_id", 6, "YEAR", out_of_scope_prefixes=("OPB-", "DEP-")),
    HistoricalSource("JE", "journal_entries", "entry_number", "organization_id", 6, "YEAR"),
    HistoricalSource("PRJ", "projects", "project_code", "organization_id", 3, "YEAR"),
    HistoricalSource("DOC", "documents", "document_code", "organization_id", 6, "YEAR", out_of_scope_prefixes=("DOC-WA-",)),
    HistoricalSource("INV", "customer_invoices", "invoice_code", "organization_id", 6, "YEAR"),
    HistoricalSource("BIL", "vendor_bills", "bill_code", "organization_id", 6, "YEAR"),
    HistoricalSource("ADV", "vendor_advances", "advance_code", "organization_id", 6, "YEAR"),
    HistoricalSource("REL", "customer_retention_releases", "release_code", "organization_id", 6, "YEAR"),
    HistoricalSource("MM", "money_movements", "movement_code", "organization_id", 6, "YEAR"),
    HistoricalSource("SET", "settlements", "settlement_code", "organization_id", 6, "GLOBAL"),
)


def _parse_historical_code(
    *,
    namespace: str,
    code: str,
    suffix_width: int,
    scope_kind: str,
) -> ParsedHistoricalCode:
    """Parse one canonical code without using record dates or current time."""
    if scope_kind == "YEAR":
        pattern = rf"^{re.escape(namespace)}-([0-9]{{4}})-([0-9]{{{suffix_width}}})$"
        match = re.fullmatch(pattern, code)
        if match is None:
            raise HistoricalSequenceBootstrapError(
                f"Malformed historical {namespace} identifier; expected canonical year format."
            )
        year, suffix = match.groups()
        if not 1 <= int(year) <= 9999:
            raise HistoricalSequenceBootstrapError(
                f"Historical {namespace} identifier has an impossible year scope."
            )
    elif scope_kind == "GLOBAL":
        pattern = rf"^{re.escape(namespace)}-([0-9]{{{suffix_width}}})$"
        match = re.fullmatch(pattern, code)
        if match is None:
            raise HistoricalSequenceBootstrapError(
                f"Malformed historical {namespace} identifier; expected canonical global format."
            )
        year = "GLOBAL"
        suffix = match.group(1)
    else:
        raise HistoricalSequenceBootstrapError(f"Unsupported historical scope kind: {scope_kind!r}.")

    value = int(suffix)
    maximum = (10**suffix_width) - 1
    if value < 1 or value > maximum:
        raise HistoricalSequenceBootstrapError(
            f"Historical {namespace} identifier is outside the supported allocator range."
        )
    return ParsedHistoricalCode(scope_key=year, value=value)


def _classify_noncanonical_code(namespace: str, code: str) -> str:
    """Classify known non-sequential values, otherwise fail closed."""
    source = next(source for source in HISTORICAL_SOURCES if source.namespace == namespace)
    if code.startswith(source.out_of_scope_prefixes):
        return "OUT_OF_SCOPE"
    raise HistoricalSequenceBootstrapError(
        f"Unresolved historical {namespace} identifier cannot be classified safely."
    )


def _monotonic_value(existing_value: int | None, historical_value: int) -> int:
    """Return a high-water mark that never lowers authoritative state."""
    if existing_value is None:
        return historical_value
    return max(existing_value, historical_value)


def _parse_source_row(source: HistoricalSource, organization_id: object, code: object) -> tuple[object, ParsedHistoricalCode] | None:
    if organization_id is None or code is None:
        raise HistoricalSequenceBootstrapError(
            f"Historical {source.namespace} identifier is missing its organization or code."
        )
    if not isinstance(code, str):
        raise HistoricalSequenceBootstrapError(
            f"Historical {source.namespace} identifier is not text."
        )
    try:
        parsed = _parse_historical_code(
            namespace=source.namespace,
            code=code,
            suffix_width=source.suffix_width,
            scope_kind=source.scope_kind,
        )
    except HistoricalSequenceBootstrapError:
        if _classify_noncanonical_code(source.namespace, code) == "OUT_OF_SCOPE":
            return None
        raise
    return organization_id, parsed


def _historical_high_water_marks(bind: Connection) -> dict[tuple[object, str, str], int]:
    marks: dict[tuple[object, str, str], int] = {}
    for source in HISTORICAL_SOURCES:
        rows = bind.execute(
            sa.text(
                f"SELECT {source.organization_column}, {source.code_column} "
                f"FROM {source.table_name} "
                f"ORDER BY {source.organization_column}, {source.code_column}"
            )
        )
        for organization_id, code in rows:
            parsed_row = _parse_source_row(source, organization_id, code)
            if parsed_row is None:
                continue
            organization_id, parsed = parsed_row
            key = (organization_id, source.namespace, parsed.scope_key)
            marks[key] = max(marks.get(key, 0), parsed.value)
    return marks


def _seed_high_water_marks(bind: Connection, marks: Iterable[tuple[tuple[object, str, str], int]]) -> None:
    for (organization_id, namespace, scope_key), historical_value in marks:
        bind.execute(
            sa.text(
                """
                INSERT INTO tenant_sequences (
                    id, organization_id, namespace, scope_key, current_value
                ) VALUES (
                    :id, :organization_id, :namespace, :scope_key, :current_value
                )
                ON CONFLICT (organization_id, namespace, scope_key)
                DO UPDATE SET
                    current_value = GREATEST(
                        tenant_sequences.current_value,
                        EXCLUDED.current_value
                    ),
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "id": uuid.uuid4(),
                "organization_id": organization_id,
                "namespace": namespace,
                "scope_key": scope_key,
                "current_value": historical_value,
            },
        )


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError(
            "Historical sequence bootstrap requires an online PostgreSQL database "
            "so every historical identifier can be validated before seeding."
        )

    bind = op.get_bind()
    marks = _historical_high_water_marks(bind)
    _seed_high_water_marks(bind, marks.items())


def downgrade() -> None:
    raise RuntimeError(
        "Historical sequence bootstrap cannot be downgraded safely: allocation "
        "state has no provenance marker and may already include runtime allocations. "
        "Historical records and tenant_sequences were retained."
    )
