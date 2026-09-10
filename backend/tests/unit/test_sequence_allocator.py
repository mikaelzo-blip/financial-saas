from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint

from src.models.fixed_asset import FixedAsset
from src.models.money_movement import MoneyMovement, Settlement

from src.core.database import Base
from src.models import TenantSequence
from src.services.tenant_sequence_allocator import (
    InvalidSequenceOrganizationError,
    InvalidSequenceScopeError,
    allocate_next,
)


@pytest.mark.parametrize("organization_id", [None, "not-a-uuid", ""])
async def test_allocator_rejects_invalid_organization_id(
    organization_id: object,
) -> None:
    with pytest.raises(InvalidSequenceOrganizationError):
        await allocate_next(  # type: ignore[arg-type]
            object(), organization_id, "TRX", "2026"
        )


def test_tenant_sequence_model_is_registered_with_required_constraints() -> None:
    table = Base.metadata.tables["tenant_sequences"]

    assert TenantSequence.__table__ is table
    assert {column.name for column in table.primary_key.columns} == {"id"}
    assert table.c.organization_id.nullable is False
    assert table.c.namespace.nullable is False
    assert table.c.scope_key.nullable is False
    assert table.c.current_value.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.nullable is False
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True

    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_constraints["uq_tenant_sequences_org_ns_scope"] == (
        "organization_id",
        "namespace",
        "scope_key",
    )

    check_constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert check_constraints["ck_tenant_sequences_current_value_non_negative"] == (
        "current_value >= 0"
    )

    organization_fk = next(iter(table.c.organization_id.foreign_keys))
    assert organization_fk.target_fullname == "organizations.id"
    assert organization_fk.ondelete == "CASCADE"


def test_tenant_owned_business_codes_use_composite_model_constraints() -> None:
    expected = {
        MoneyMovement.__table__: ("uq_money_movements_org_code", "movement_code"),
        Settlement.__table__: ("uq_settlements_org_code", "settlement_code"),
        FixedAsset.__table__: ("uq_fixed_assets_org_code", "asset_code"),
    }

    for table, (constraint_name, code_column) in expected.items():
        unique_constraints = {
            constraint.name: tuple(column.name for column in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
        assert unique_constraints[constraint_name] == (
            "organization_id",
            code_column,
        )
        assert table.c[code_column].unique is not True


@pytest.mark.parametrize(
    ("namespace", "scope_key"),
    [
        ("", "2026"),
        ("UNKNOWN", "2026"),
        ("TRX", ""),
        ("TRX", "GLOBAL"),
        ("TRX", "0000"),
        ("SET", "2026"),
        ("SET", ""),
        (None, "2026"),
        ("TRX", None),
        ("SET", None),
    ],
)
async def test_allocator_rejects_invalid_namespace_or_scope(
    namespace: str | None,
    scope_key: str | None,
) -> None:
    with pytest.raises(InvalidSequenceScopeError):
        await allocate_next(  # type: ignore[arg-type]
            object(), uuid4(), namespace, scope_key
        )
