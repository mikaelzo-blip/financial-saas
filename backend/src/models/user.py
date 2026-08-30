import uuid
from typing import TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin
from src.models.enums import UserRole

if TYPE_CHECKING:
    from src.models.organization import Organization


class User(Base, TimestampMixin):
    """Authenticated user within an organization."""
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_users_org_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"),
        nullable=False,
        default=UserRole.OPERATOR
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="users"
    )

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"
