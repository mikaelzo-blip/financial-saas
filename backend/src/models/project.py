import uuid
from typing import List, Optional, TYPE_CHECKING
from datetime import date
from decimal import Decimal
from sqlalchemy import (
    String,
    Date,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Text,
    Enum as SAEnum,
    CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin
from src.models.enums import ProjectStatus, CostCategory

if TYPE_CHECKING:
    from src.models.organization import Organization
    from src.models.counterparty import Counterparty
    from src.models.user import User


class Project(Base, TimestampMixin):
    """
    Project Master entity representing a contractor client contract/project.
    Central organizing unit for financial analysis and project costing.
    """
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_code", name="uq_projects_org_project_code"),
        CheckConstraint("original_contract_value >= 0", name="ck_projects_original_contract_value_positive"),
        CheckConstraint("revised_contract_value >= 0", name="ck_projects_revised_contract_value_positive"),
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
    project_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    project_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("counterparties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    po_spk_no: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )
    po_spk_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    original_contract_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    variation_order_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    revised_contract_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    target_end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    actual_end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    pic_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    project_status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status"),
        nullable=False,
        default=ProjectStatus.PLANNED
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization"
    )
    customer: Mapped["Counterparty"] = relationship(
        "Counterparty"
    )
    pic_user: Mapped[Optional["User"]] = relationship(
        "User"
    )
    budgets: Mapped[List["ProjectBudget"]] = relationship(
        "ProjectBudget",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    def calculate_revised_contract_value(self) -> Decimal:
        """Enforces Revised Contract Value = Original + Variation Order."""
        return self.original_contract_value + self.variation_order_value

    def __repr__(self) -> str:
        return f"<Project {self.project_code} - {self.project_name} ({self.project_status.value})>"


class ProjectBudget(Base):
    """
    Project budget line item allocating budget per cost category (MAT, SUB, LAB, etc.).
    """
    __tablename__ = "project_budgets"
    __table_args__ = (
        UniqueConstraint("project_id", "cost_category", name="uq_project_budgets_project_category"),
        CheckConstraint("budget_amount >= 0", name="ck_project_budgets_amount_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    cost_category: Mapped[CostCategory] = mapped_column(
        SAEnum(CostCategory, name="cost_category"),
        nullable=False
    )
    budget_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        nullable=False,
        default=Decimal("0.00")
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )

    # Relationships
    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="budgets"
    )

    def __repr__(self) -> str:
        return f"<ProjectBudget {self.cost_category.value}: Rp {self.budget_amount} (Project {self.project_id})>"
