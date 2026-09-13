"""Tests for Alembic migration 024_recon_integrity_invariants.

Verifies:
1. Revision identity and lineage (024 follows 023_historical_seq_bootstrap).
2. Fail-closed preflight on historical data anomalies:
   - Clean valid dataset passes.
   - Duplicate statement-line dataset fails preflight.
   - Duplicate journal-line dataset fails preflight.
   - Duplicate money-movement dataset fails preflight.
   - Duplicate transaction dataset fails preflight.
   - Zero-target dataset fails preflight.
   - Multi-target dataset fails preflight.
   - Non-positive matched_amount fails preflight.
   - Amount mismatch against bank statement line fails preflight.
3. Offline execution avoids running data preflight queries.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "024_recon_integrity_invariants.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("recon_024_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_revision_follows_023_head(migration) -> None:
    assert migration.revision == "024_recon_integrity_invariants"
    assert migration.down_revision == "023_historical_seq_bootstrap"


def test_offline_upgrade_skips_data_preflight(migration, monkeypatch) -> None:
    class OfflineOperations:
        def get_context(self):
            return type("Context", (), {"as_sql": True})()

        def create_check_constraint(self, *args, **kwargs) -> None:
            return None

        def create_index(self, *args, **kwargs) -> None:
            return None

    def preflight_must_not_run(*args, **kwargs) -> None:
        raise AssertionError("offline migration must not query historical data")

    monkeypatch.setattr(migration, "op", OfflineOperations())
    monkeypatch.setattr(migration, "_preflight_historical_data", preflight_must_not_run)

    migration.upgrade()


@pytest.fixture
def memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE bank_statement_lines (
                    id TEXT PRIMARY KEY,
                    debit NUMERIC NOT NULL DEFAULT 0.00,
                    credit NUMERIC NOT NULL DEFAULT 0.00
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE bank_reconciliations (
                    id TEXT PRIMARY KEY,
                    statement_line_id TEXT NOT NULL,
                    journal_line_id TEXT,
                    money_movement_id TEXT,
                    transaction_id TEXT,
                    status TEXT NOT NULL DEFAULT 'MATCHED',
                    matched_amount NUMERIC NOT NULL
                )
                """
            )
        )
    yield engine
    engine.dispose()


def test_preflight_passes_on_clean_dataset(migration, memory_db) -> None:
    stmt_id = str(uuid.uuid4())
    recon_id = str(uuid.uuid4())
    jl_id = str(uuid.uuid4())

    with memory_db.begin() as conn:
        conn.execute(
            text("INSERT INTO bank_statement_lines VALUES (:id, 0.00, 1000.00)"),
            {"id": stmt_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations VALUES
                (:id, :stmt_id, :jl_id, NULL, NULL, 'MATCHED', 1000.00)
                """
            ),
            {"id": recon_id, "stmt_id": stmt_id, "jl_id": jl_id},
        )
        # Preflight should pass without exception
        migration._preflight_historical_data(conn)


def test_preflight_fails_on_duplicate_active_statement_line(migration, memory_db) -> None:
    stmt_id = str(uuid.uuid4())
    with memory_db.begin() as conn:
        conn.execute(
            text("INSERT INTO bank_statement_lines VALUES (:id, 0.00, 1000.00)"),
            {"id": stmt_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations VALUES
                (:id1, :stmt_id, :jl1, NULL, NULL, 'MATCHED', 1000.00),
                (:id2, :stmt_id, :jl2, NULL, NULL, 'MATCHED', 1000.00)
                """
            ),
            {
                "id1": str(uuid.uuid4()),
                "id2": str(uuid.uuid4()),
                "stmt_id": stmt_id,
                "jl1": str(uuid.uuid4()),
                "jl2": str(uuid.uuid4()),
            },
        )
        with pytest.raises(migration.ReconciliationHistoricalDataError) as exc:
            migration._preflight_historical_data(conn)
        assert "duplicate active statement lines" in str(exc.value).lower()


def test_preflight_fails_on_duplicate_active_journal_line(migration, memory_db) -> None:
    stmt1 = str(uuid.uuid4())
    stmt2 = str(uuid.uuid4())
    jl_id = str(uuid.uuid4())

    with memory_db.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO bank_statement_lines VALUES
                (:s1, 0.00, 1000.00),
                (:s2, 0.00, 1000.00)
                """
            ),
            {"s1": stmt1, "s2": stmt2},
        )
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations VALUES
                (:id1, :s1, :jl, NULL, NULL, 'MATCHED', 1000.00),
                (:id2, :s2, :jl, NULL, NULL, 'MATCHED', 1000.00)
                """
            ),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "s1": stmt1, "s2": stmt2, "jl": jl_id},
        )
        with pytest.raises(migration.ReconciliationHistoricalDataError) as exc:
            migration._preflight_historical_data(conn)
        assert "duplicate active journal lines" in str(exc.value).lower()


def test_preflight_fails_on_duplicate_active_money_movement(migration, memory_db) -> None:
    stmt1 = str(uuid.uuid4())
    stmt2 = str(uuid.uuid4())
    mm_id = str(uuid.uuid4())

    with memory_db.begin() as conn:
        conn.execute(
            text("INSERT INTO bank_statement_lines VALUES (:s1, 0.00, 1000.00), (:s2, 0.00, 1000.00)"),
            {"s1": stmt1, "s2": stmt2},
        )
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations VALUES
                (:id1, :s1, NULL, :mm, NULL, 'MATCHED', 1000.00),
                (:id2, :s2, NULL, :mm, NULL, 'MATCHED', 1000.00)
                """
            ),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "s1": stmt1, "s2": stmt2, "mm": mm_id},
        )
        with pytest.raises(migration.ReconciliationHistoricalDataError) as exc:
            migration._preflight_historical_data(conn)
        assert "duplicate active money movements" in str(exc.value).lower()


def test_preflight_fails_on_duplicate_active_transaction(migration, memory_db) -> None:
    stmt1 = str(uuid.uuid4())
    stmt2 = str(uuid.uuid4())
    tx_id = str(uuid.uuid4())

    with memory_db.begin() as conn:
        conn.execute(
            text("INSERT INTO bank_statement_lines VALUES (:s1, 0.00, 1000.00), (:s2, 0.00, 1000.00)"),
            {"s1": stmt1, "s2": stmt2},
        )
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations VALUES
                (:id1, :s1, NULL, NULL, :tx, 'MATCHED', 1000.00),
                (:id2, :s2, NULL, NULL, :tx, 'MATCHED', 1000.00)
                """
            ),
            {"id1": str(uuid.uuid4()), "id2": str(uuid.uuid4()), "s1": stmt1, "s2": stmt2, "tx": tx_id},
        )
        with pytest.raises(migration.ReconciliationHistoricalDataError) as exc:
            migration._preflight_historical_data(conn)
        assert "duplicate active transactions" in str(exc.value).lower()


def test_preflight_fails_on_zero_target(migration, memory_db) -> None:
    stmt = str(uuid.uuid4())
    with memory_db.begin() as conn:
        conn.execute(
            text("INSERT INTO bank_statement_lines VALUES (:s, 0.00, 1000.00)"),
            {"s": stmt},
        )
        conn.execute(
            text("INSERT INTO bank_reconciliations VALUES (:id, :s, NULL, NULL, NULL, 'MATCHED', 1000.00)"),
            {"id": str(uuid.uuid4()), "s": stmt},
        )
        with pytest.raises(migration.ReconciliationHistoricalDataError) as exc:
            migration._preflight_historical_data(conn)
        assert "zero-target rows" in str(exc.value).lower()


def test_preflight_fails_on_multi_target(migration, memory_db) -> None:
    stmt = str(uuid.uuid4())
    with memory_db.begin() as conn:
        conn.execute(
            text("INSERT INTO bank_statement_lines VALUES (:s, 0.00, 1000.00)"),
            {"s": stmt},
        )
        conn.execute(
            text(
                """
                INSERT INTO bank_reconciliations VALUES
                (:id, :s, :jl, :mm, NULL, 'MATCHED', 1000.00)
                """
            ),
            {"id": str(uuid.uuid4()), "s": stmt, "jl": str(uuid.uuid4()), "mm": str(uuid.uuid4())},
        )
        with pytest.raises(migration.ReconciliationHistoricalDataError) as exc:
            migration._preflight_historical_data(conn)
        assert "multi-target rows" in str(exc.value).lower()


def test_preflight_fails_on_non_positive_matched_amount(migration, memory_db) -> None:
    stmt = str(uuid.uuid4())
    with memory_db.begin() as conn:
        conn.execute(
            text("INSERT INTO bank_statement_lines VALUES (:s, 0.00, 1000.00)"),
            {"s": stmt},
        )
        conn.execute(
            text("INSERT INTO bank_reconciliations VALUES (:id, :s, :jl, NULL, NULL, 'MATCHED', 0.00)"),
            {"id": str(uuid.uuid4()), "s": stmt, "jl": str(uuid.uuid4())},
        )
        with pytest.raises(migration.ReconciliationHistoricalDataError) as exc:
            migration._preflight_historical_data(conn)
        assert "non-positive matched_amount" in str(exc.value).lower()


def test_preflight_fails_on_amount_mismatch_against_statement(migration, memory_db) -> None:
    stmt = str(uuid.uuid4())
    with memory_db.begin() as conn:
        conn.execute(
            text("INSERT INTO bank_statement_lines VALUES (:s, 0.00, 1000.00)"),
            {"s": stmt},
        )
        conn.execute(
            text("INSERT INTO bank_reconciliations VALUES (:id, :s, :jl, NULL, NULL, 'MATCHED', 999.00)"),
            {"id": str(uuid.uuid4()), "s": stmt, "jl": str(uuid.uuid4())},
        )
        with pytest.raises(migration.ReconciliationHistoricalDataError) as exc:
            migration._preflight_historical_data(conn)
        assert "amount mismatch" in str(exc.value).lower()
