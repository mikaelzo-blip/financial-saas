"""Regression tests for authoritative SQLAlchemy model registration and schema parity."""

import re
from pathlib import Path

from src.core.database import Base
import src.models


def get_migration_tables() -> set[str]:
    """Extract all table names created across Alembic migrations."""
    versions_dir = Path(__file__).resolve().parent.parent.parent / "alembic" / "versions"
    tables = set()
    for file in versions_dir.glob("*.py"):
        content = file.read_text(encoding="utf-8")
        for match in re.finditer(r'op\.create_table\(\s*[\'"]([^\'"]+)[\'"]', content):
            tables.add(match.group(1))
    return tables


def test_base_metadata_contains_all_migration_tables():
    """Verify that authoritative Base.metadata contains every production table created by migrations."""
    migration_tables = get_migration_tables()
    metadata_tables = set(Base.metadata.tables.keys())

    assert len(migration_tables) > 0, "No tables found in migrations directory"
    missing_tables = migration_tables - metadata_tables
    assert not missing_tables, f"Base.metadata is missing production tables created by migrations: {sorted(missing_tables)}"


def test_no_unapproved_orphan_tables_in_base_metadata():
    """Allow only the Feature-012 model intentionally pending its CP4 migration."""
    migration_tables = get_migration_tables()
    metadata_tables = set(Base.metadata.tables.keys())

    extra_tables = metadata_tables - migration_tables
    assert extra_tables == {"tenant_sequences"}, (
        "Base.metadata drift must be limited to the approved Feature-012 table: "
        f"{sorted(extra_tables)}"
    )


def test_all_production_models_exported_in_models_init():
    """Verify that all active model classes are exported in src.models.__all__."""
    expected_models = [
        # Core & Master Data
        "Organization",
        "User",
        "Counterparty",
        "ChartOfAccount",
        "PaymentAccount",
        "AuditLog",
        "Project",
        "ProjectBudget",
        # Documents & Intake
        "Document",
        "ProjectDocumentLink",
        "TransactionDocumentLink",
        "DocumentCorrection",
        "HermesSubmission",
        "InboxMessage",
        "InboxAttachment",
        "DocumentSession",
        "MatchEvidence",
        # Financial Core
        "Transaction",
        "TransactionAllocation",
        "TransactionReviewFlag",
        "JournalEntry",
        "JournalLine",
        "VendorBill",
        "VendorPaymentAllocation",
        "VendorAdvance",
        "CustomerInvoice",
        "CustomerPaymentAllocation",
        "CustomerRetentionRelease",
        # Money Movement & Settlements
        "MoneyMovement",
        "Settlement",
        "SettlementAllocation",
        "TenantSequence",
        # Bank Reconciliation
        "BankStatementImport",
        "BankStatementLine",
        "BankReconciliation",
        # Fixed Assets
        "FixedAsset",
        "FixedAssetDepreciation",
        # Periods & Jobs
        "AccountingPeriod",
        "BackgroundJob",
        # Integrations
        "WhatsAppSenderMapping",
        "WhatsAppMessageLog",
        "WhatsAppClarificationSession",
        "AIInsightLog",
        "AIConversationSession",
        "AIConversationMessage",
    ]

    for model_name in expected_models:
        assert hasattr(src.models, model_name), f"src.models is missing model: {model_name}"
        assert model_name in src.models.__all__, f"{model_name} is not in src.models.__all__"


def test_timestamp_metadata_timezone_awareness():
    """Verify that models with PostgreSQL timestamptz columns specify timezone=True."""
    expected_timestamptz_columns = [
        ("audit_logs", "timestamp"),
        ("chart_of_accounts", "created_at"),
        ("counterparties", "created_at"),
        ("counterparties", "updated_at"),
        ("customer_invoices", "created_at"),
        ("customer_invoices", "updated_at"),
        ("document_corrections", "corrected_at"),
        ("documents", "created_at"),
        ("documents", "updated_at"),
        ("hermes_submissions", "created_at"),
        ("hermes_submissions", "updated_at"),
        ("organizations", "created_at"),
        ("organizations", "updated_at"),
        ("payment_accounts", "created_at"),
        ("project_document_links", "created_at"),
        ("projects", "created_at"),
        ("projects", "updated_at"),
        ("transaction_document_links", "created_at"),
        ("transactions", "created_at"),
        ("transactions", "updated_at"),
        ("users", "created_at"),
        ("users", "updated_at"),
        ("vendor_advances", "created_at"),
        ("vendor_advances", "updated_at"),
        ("vendor_bills", "created_at"),
        ("vendor_bills", "updated_at"),
    ]

    for table_name, column_name in expected_timestamptz_columns:
        table = Base.metadata.tables[table_name]
        col = table.columns[column_name]
        assert getattr(col.type, "timezone", False) is True, (
            f"{table_name}.{column_name} is not timezone-aware: {col.type}"
        )
