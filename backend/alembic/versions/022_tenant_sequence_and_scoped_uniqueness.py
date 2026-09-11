"""022_tenant_sequence_scope

Revision ID: 022_tenant_sequence_scope
Revises: 021_fixed_asset_enhancements
Create Date: 2026-09-10

The online downgrade refuses to restore global business-code uniqueness when
any affected code exists in more than one organization. It aborts before DDL
and never renames, deletes, or rewrites business records. A successful
downgrade drops tenant_sequences because it stores allocation state rather
than authoritative accounting history; callers must not depend on that state
across a downgrade. Offline SQL rendering cannot inspect live constraints or
data, so the duplicate and constraint preflights are enforced only when the
migration executes online against PostgreSQL.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision: str = "022_tenant_sequence_scope"
down_revision: Union[str, None] = "021_fixed_asset_enhancements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_GLOBAL_CONSTRAINTS = {
    "money_movements": (
        "movement_code",
        "uq_money_movements_movement_code",
        "UNIQUE (movement_code)",
        "uq_money_movements_org_code",
    ),
    "settlements": (
        "settlement_code",
        "uq_settlements_settlement_code",
        "UNIQUE (settlement_code)",
        "uq_settlements_org_code",
    ),
    "fixed_assets": (
        "asset_code",
        "uq_fixed_assets_asset_code",
        "UNIQUE (asset_code)",
        "uq_fixed_assets_org_code",
    ),
}


def _constraint_definitions(bind: Connection, table_name: str) -> list[tuple[str, str]]:
    rows = bind.execute(
        sa.text(
            """
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = CAST(:table_name AS regclass)
              AND contype = 'u'
            ORDER BY conname
            """
        ),
        {"table_name": f"public.{table_name}"},
    ).all()
    return [(str(name), str(definition)) for name, definition in rows]


def _constraint_definition(
    bind: Connection,
    table_name: str,
    constraint_name: str,
) -> str | None:
    return bind.execute(
        sa.text(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = CAST(:table_name AS regclass)
              AND conname = :constraint_name
              AND contype = 'u'
            """
        ),
        {
            "table_name": f"public.{table_name}",
            "constraint_name": constraint_name,
        },
    ).scalar_one_or_none()


def _require_constraint(
    bind: Connection,
    table_name: str,
    constraint_name: str,
    expected_definition: str,
) -> None:
    definition = _constraint_definition(bind, table_name, constraint_name)
    if definition != expected_definition:
        raise RuntimeError(
            f"Feature 012 expected {table_name}.{constraint_name} to be "
            f"{expected_definition}, found {definition!r}."
        )


def _require_global_constraint_state(bind: Connection) -> None:
    for table_name, (_, constraint_name, expected_definition, _) in _GLOBAL_CONSTRAINTS.items():
        actual = _constraint_definitions(bind, table_name)
        expected = [(constraint_name, expected_definition)]
        if actual != expected:
            raise RuntimeError(
                f"Feature 012 refuses to migrate {table_name}: expected unique "
                f"constraint state {expected!r}, found {actual!r}."
            )


def _preflight_tenant_duplicates(bind: Connection) -> None:
    for table_name, (code_column, _, _, _) in _GLOBAL_CONSTRAINTS.items():
        conflict = bind.execute(
            sa.text(
                f"""
                SELECT organization_id, {code_column}, COUNT(*)
                FROM {table_name}
                GROUP BY organization_id, {code_column}
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).first()
        if conflict is not None:
            raise RuntimeError(
                f"Feature 012 found duplicate tenant-scoped key in {table_name}: "
                f"organization_id={conflict[0]!s}, {code_column}={conflict[1]!r}, "
                f"count={conflict[2]}. No data was changed."
            )


def _preflight_global_duplicates(bind: Connection) -> None:
    for table_name, (code_column, _, _, _) in _GLOBAL_CONSTRAINTS.items():
        conflict = bind.execute(
            sa.text(
                f"""
                SELECT {code_column}, COUNT(DISTINCT organization_id)
                FROM {table_name}
                GROUP BY {code_column}
                HAVING COUNT(DISTINCT organization_id) > 1
                LIMIT 1
                """
            )
        ).first()
        if conflict is not None:
            raise RuntimeError(
                f"Feature 012 cannot downgrade {table_name}: code "
                f"{conflict[0]!r} exists in {conflict[1]} organizations. "
                "Global uniqueness was not restored and no data was changed."
            )


def _create_tenant_sequences() -> None:
    op.create_table(
        "tenant_sequences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "organization_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column("namespace", sa.String(32), nullable=False),
        sa.Column("scope_key", sa.String(32), nullable=False),
        sa.Column(
            "current_value",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "current_value >= 0",
            name=op.f("ck_tenant_sequences_current_value_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_tenant_sequences_organization_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_sequences")),
        sa.UniqueConstraint(
            "organization_id",
            "namespace",
            "scope_key",
            name="uq_tenant_sequences_org_ns_scope",
        ),
    )


def _replace_global_constraint(table_name: str, *, verify: bool = True) -> None:
    code_column, old_name, _, new_name = _GLOBAL_CONSTRAINTS[table_name]
    op.create_unique_constraint(
        new_name,
        table_name,
        ["organization_id", code_column],
    )
    if verify:
        bind = op.get_bind()
        _require_constraint(
            bind,
            table_name,
            new_name,
            f"UNIQUE (organization_id, {code_column})",
        )
    op.drop_constraint(old_name, table_name, type_="unique")
    if verify and _constraint_definition(op.get_bind(), table_name, old_name) is not None:
        raise RuntimeError(
            f"Feature 012 failed to remove obsolete constraint "
            f"{table_name}.{old_name}."
        )


def _upgrade_offline() -> None:
    """Render SQL only; live preflights run during an online migration."""
    _create_tenant_sequences()
    for table_name in _GLOBAL_CONSTRAINTS:
        _replace_global_constraint(table_name, verify=False)


def upgrade() -> None:
    if op.get_context().as_sql:
        _upgrade_offline()
        return

    bind = op.get_bind()
    _require_global_constraint_state(bind)
    _preflight_tenant_duplicates(bind)

    _create_tenant_sequences()
    for table_name in _GLOBAL_CONSTRAINTS:
        _replace_global_constraint(table_name)


def _downgrade_offline() -> None:
    """Render SQL only; live cross-tenant preflights run online."""
    for table_name, (code_column, old_name, _, new_name) in _GLOBAL_CONSTRAINTS.items():
        op.create_unique_constraint(old_name, table_name, [code_column])
        op.drop_constraint(new_name, table_name, type_="unique")
    op.drop_table("tenant_sequences")


def downgrade() -> None:
    if op.get_context().as_sql:
        _downgrade_offline()
        return

    bind = op.get_bind()
    _preflight_global_duplicates(bind)

    for table_name, (code_column, _, _, new_name) in _GLOBAL_CONSTRAINTS.items():
        _require_constraint(
            bind,
            table_name,
            new_name,
            f"UNIQUE (organization_id, {code_column})",
        )

    for table_name, (code_column, old_name, old_definition, new_name) in _GLOBAL_CONSTRAINTS.items():
        op.create_unique_constraint(old_name, table_name, [code_column])
        _require_constraint(bind, table_name, old_name, old_definition)
        op.drop_constraint(new_name, table_name, type_="unique")
        if _constraint_definition(bind, table_name, new_name) is not None:
            raise RuntimeError(
                f"Feature 012 failed to remove composite constraint "
                f"{table_name}.{new_name}."
            )

    op.drop_table("tenant_sequences")
