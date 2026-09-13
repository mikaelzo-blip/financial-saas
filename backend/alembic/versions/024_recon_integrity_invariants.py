"""024_recon_integrity_invariants

Revision ID: 024_recon_integrity_invariants
Revises: 023_historical_seq_bootstrap
Create Date: 2026-09-13

Adds database integrity invariants for BankReconciliation:
1. Fail-closed preflight inspection on historical data (when run online):
   - duplicate active statement_line_id
   - duplicate active journal_line_id
   - duplicate active money_movement_id
   - duplicate active transaction_id
   - zero-target reconciliation rows
   - multi-target reconciliation rows
   - non-positive matched_amount (<= 0)
   - amount mismatch against statement line
2. Check constraints:
   - ck_bank_recon_exactly_one_target (exactly one target foreign key populated)
   - ck_bank_recon_matched_amount_positive (matched_amount > 0)
3. Partial unique indexes:
   - uq_bank_reconciliations_statement_line (WHERE status = 'MATCHED')
   - uq_bank_reconciliations_journal_line (WHERE journal_line_id IS NOT NULL AND status = 'MATCHED')
   - uq_bank_reconciliations_money_movement (WHERE money_movement_id IS NOT NULL AND status = 'MATCHED')
   - uq_bank_reconciliations_transaction (WHERE transaction_id IS NOT NULL AND status = 'MATCHED')

Downgrade cleanly drops the constraints and unique indexes without altering historical data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.sql.naming import conv


revision: str = "024_recon_integrity_invariants"
down_revision: Union[str, None] = "023_historical_seq_bootstrap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class ReconciliationHistoricalDataError(RuntimeError):
    """Raised when historical reconciliation data violates integrity invariants."""


def _preflight_historical_data(bind: Connection) -> None:
    # 1. Duplicate active statement_line_id
    dup_stmts = bind.execute(
        sa.text(
            """
            SELECT statement_line_id, count(*) AS cnt
            FROM bank_reconciliations
            WHERE status = 'MATCHED'
            GROUP BY statement_line_id
            HAVING count(*) > 1
            """
        )
    ).all()
    if dup_stmts:
        details = ", ".join(f"{row[0]} (count: {row[1]})" for row in dup_stmts)
        raise ReconciliationHistoricalDataError(
            f"Preflight failed: duplicate active statement lines detected in bank_reconciliations: {details}"
        )

    # 2. Duplicate active journal_line_id
    dup_jls = bind.execute(
        sa.text(
            """
            SELECT journal_line_id, count(*) AS cnt
            FROM bank_reconciliations
            WHERE journal_line_id IS NOT NULL AND status = 'MATCHED'
            GROUP BY journal_line_id
            HAVING count(*) > 1
            """
        )
    ).all()
    if dup_jls:
        details = ", ".join(f"{row[0]} (count: {row[1]})" for row in dup_jls)
        raise ReconciliationHistoricalDataError(
            f"Preflight failed: duplicate active journal lines detected in bank_reconciliations: {details}"
        )

    # 3. Duplicate active money_movement_id
    dup_mms = bind.execute(
        sa.text(
            """
            SELECT money_movement_id, count(*) AS cnt
            FROM bank_reconciliations
            WHERE money_movement_id IS NOT NULL AND status = 'MATCHED'
            GROUP BY money_movement_id
            HAVING count(*) > 1
            """
        )
    ).all()
    if dup_mms:
        details = ", ".join(f"{row[0]} (count: {row[1]})" for row in dup_mms)
        raise ReconciliationHistoricalDataError(
            f"Preflight failed: duplicate active money movements detected in bank_reconciliations: {details}"
        )

    # 4. Duplicate active transaction_id
    dup_txs = bind.execute(
        sa.text(
            """
            SELECT transaction_id, count(*) AS cnt
            FROM bank_reconciliations
            WHERE transaction_id IS NOT NULL AND status = 'MATCHED'
            GROUP BY transaction_id
            HAVING count(*) > 1
            """
        )
    ).all()
    if dup_txs:
        details = ", ".join(f"{row[0]} (count: {row[1]})" for row in dup_txs)
        raise ReconciliationHistoricalDataError(
            f"Preflight failed: duplicate active transactions detected in bank_reconciliations: {details}"
        )

    # 5. Zero-target reconciliation rows
    zero_targets = bind.execute(
        sa.text(
            """
            SELECT id
            FROM bank_reconciliations
            WHERE journal_line_id IS NULL
              AND money_movement_id IS NULL
              AND transaction_id IS NULL
            """
        )
    ).all()
    if zero_targets:
        details = ", ".join(str(row[0]) for row in zero_targets)
        raise ReconciliationHistoricalDataError(
            f"Preflight failed: zero-target rows detected in bank_reconciliations: {details}"
        )

    # 6. Multi-target reconciliation rows
    multi_targets = bind.execute(
        sa.text(
            """
            SELECT id
            FROM bank_reconciliations
            WHERE (
                CASE WHEN journal_line_id IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN money_movement_id IS NOT NULL THEN 1 ELSE 0 END +
                CASE WHEN transaction_id IS NOT NULL THEN 1 ELSE 0 END
            ) > 1
            """
        )
    ).all()
    if multi_targets:
        details = ", ".join(str(row[0]) for row in multi_targets)
        raise ReconciliationHistoricalDataError(
            f"Preflight failed: multi-target rows detected in bank_reconciliations: {details}"
        )

    # 7. Non-positive matched_amount
    non_positive = bind.execute(
        sa.text(
            """
            SELECT id, matched_amount
            FROM bank_reconciliations
            WHERE matched_amount <= 0
            """
        )
    ).all()
    if non_positive:
        details = ", ".join(f"{row[0]} (amount: {row[1]})" for row in non_positive)
        raise ReconciliationHistoricalDataError(
            f"Preflight failed: non-positive matched_amount detected in bank_reconciliations: {details}"
        )

    # 8. Amount discrepancy against statement line
    amount_mismatch = bind.execute(
        sa.text(
            """
            SELECT br.id, br.matched_amount,
                   CASE WHEN bsl.credit > 0 THEN bsl.credit ELSE bsl.debit END AS line_amount
            FROM bank_reconciliations br
            JOIN bank_statement_lines bsl ON br.statement_line_id = bsl.id
            WHERE br.status = 'MATCHED'
              AND br.matched_amount != (CASE WHEN bsl.credit > 0 THEN bsl.credit ELSE bsl.debit END)
            """
        )
    ).all()
    if amount_mismatch:
        details = ", ".join(f"{row[0]} (matched: {row[1]}, line: {row[2]})" for row in amount_mismatch)
        raise ReconciliationHistoricalDataError(
            f"Preflight failed: amount mismatch between bank_reconciliations and bank_statement_lines: {details}"
        )


def upgrade() -> None:
    if not op.get_context().as_sql:
        bind = op.get_bind()
        _preflight_historical_data(bind)

    # 1. Check constraints
    op.create_check_constraint(
        conv("ck_bank_recon_exactly_one_target"),
        "bank_reconciliations",
        "(CASE WHEN journal_line_id IS NOT NULL THEN 1 ELSE 0 END + "
        "CASE WHEN money_movement_id IS NOT NULL THEN 1 ELSE 0 END + "
        "CASE WHEN transaction_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
    )
    op.create_check_constraint(
        conv("ck_bank_recon_matched_amount_positive"),
        "bank_reconciliations",
        "matched_amount > 0",
    )

    # 2. Unique partial indexes
    op.create_index(
        "uq_bank_reconciliations_statement_line",
        "bank_reconciliations",
        ["statement_line_id"],
        unique=True,
        postgresql_where=sa.text("status = 'MATCHED'"),
        sqlite_where=sa.text("status = 'MATCHED'"),
    )
    op.create_index(
        "uq_bank_reconciliations_journal_line",
        "bank_reconciliations",
        ["journal_line_id"],
        unique=True,
        postgresql_where=sa.text("journal_line_id IS NOT NULL AND status = 'MATCHED'"),
        sqlite_where=sa.text("journal_line_id IS NOT NULL AND status = 'MATCHED'"),
    )
    op.create_index(
        "uq_bank_reconciliations_money_movement",
        "bank_reconciliations",
        ["money_movement_id"],
        unique=True,
        postgresql_where=sa.text("money_movement_id IS NOT NULL AND status = 'MATCHED'"),
        sqlite_where=sa.text("money_movement_id IS NOT NULL AND status = 'MATCHED'"),
    )
    op.create_index(
        "uq_bank_reconciliations_transaction",
        "bank_reconciliations",
        ["transaction_id"],
        unique=True,
        postgresql_where=sa.text("transaction_id IS NOT NULL AND status = 'MATCHED'"),
        sqlite_where=sa.text("transaction_id IS NOT NULL AND status = 'MATCHED'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_bank_reconciliations_transaction",
        table_name="bank_reconciliations",
    )
    op.drop_index(
        "uq_bank_reconciliations_money_movement",
        table_name="bank_reconciliations",
    )
    op.drop_index(
        "uq_bank_reconciliations_journal_line",
        table_name="bank_reconciliations",
    )
    op.drop_index(
        "uq_bank_reconciliations_statement_line",
        table_name="bank_reconciliations",
    )
    op.drop_constraint(
        conv("ck_bank_recon_matched_amount_positive"),
        "bank_reconciliations",
        type_="check",
    )
    op.drop_constraint(
        conv("ck_bank_recon_exactly_one_target"),
        "bank_reconciliations",
        type_="check",
    )
