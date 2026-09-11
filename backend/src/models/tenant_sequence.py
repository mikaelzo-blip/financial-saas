import uuid

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base, TimestampMixin


class TenantSequence(Base, TimestampMixin):
    __tablename__ = "tenant_sequences"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "namespace",
            "scope_key",
            name="uq_tenant_sequences_org_ns_scope",
        ),
        CheckConstraint(
            "current_value >= 0",
            name="current_value_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    namespace: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(32), nullable=False)
    current_value: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
