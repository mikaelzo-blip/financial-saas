from __future__ import annotations

from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tenant_sequence import TenantSequence

YEAR_SCOPED_NAMESPACES = frozenset(
    {"TRX", "JE", "PRJ", "DOC", "INV", "BIL", "ADV", "REL", "MM"}
)
SUPPORTED_NAMESPACES = YEAR_SCOPED_NAMESPACES | {"SET"}


class SequenceAllocationError(ValueError):
    pass


class InvalidSequenceOrganizationError(SequenceAllocationError):
    pass


class InvalidSequenceScopeError(SequenceAllocationError):
    pass


def _validate_organization_id(organization_id: UUID) -> None:
    if not isinstance(organization_id, UUID):
        raise InvalidSequenceOrganizationError(
            "Sequence organization_id must be a UUID"
        )


def _validate_scope(namespace: str, scope_key: str) -> None:
    if namespace not in SUPPORTED_NAMESPACES:
        raise InvalidSequenceScopeError("Unsupported sequence namespace")
    if not scope_key:
        raise InvalidSequenceScopeError("Sequence scope key is required")
    if namespace == "SET":
        if scope_key != "GLOBAL":
            raise InvalidSequenceScopeError("SET requires scope_key='GLOBAL'")
        return
    if (
        len(scope_key) != 4
        or not scope_key.isascii()
        or not scope_key.isdigit()
        or int(scope_key) < 1
    ):
        raise InvalidSequenceScopeError(
            "Year-scoped namespaces require a four-digit scope key"
        )


async def allocate_next(
    session: AsyncSession,
    organization_id: UUID,
    namespace: str,
    scope_key: str,
) -> int:
    _validate_organization_id(organization_id)
    _validate_scope(namespace, scope_key)

    statement = (
        insert(TenantSequence)
        .values(
            organization_id=organization_id,
            namespace=namespace,
            scope_key=scope_key,
            current_value=1,
        )
        .on_conflict_do_update(
            constraint="uq_tenant_sequences_org_ns_scope",
            set_={
                "current_value": TenantSequence.current_value + 1,
                "updated_at": func.now(),
            },
        )
        .returning(TenantSequence.current_value)
    )
    return int((await session.execute(statement)).scalar_one())
