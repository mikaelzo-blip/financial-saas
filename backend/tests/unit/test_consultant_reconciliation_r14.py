from decimal import Decimal
from datetime import date
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.organization import Organization
from src.schemas.consultant_reconciliation import (
    ConsultantFinancialStatementData,
    DifferenceClassification,
)
from src.services.coa_seeder import seed_standard_coa
from src.services.reporting.consultant_reconciliation_service import (
    ConsultantReconciliationService,
)


def test_verified_statements_2023_integrity():
    """Verify 2023 consultant statement internal arithmetic ties out."""
    data = ConsultantReconciliationService.VERIFIED_HISTORICAL_STATEMENTS[2023]
    audit = ConsultantReconciliationService.audit_consultant_statement(data)
    assert audit.is_balanced is True
    assert audit.assets_liabilities_equity_discrepancy == Decimal("0.00")
    assert audit.pat_vs_current_earnings_discrepancy == Decimal("0.00")
    assert len(audit.findings) == 0


def test_verified_statements_2024_integrity():
    """Verify 2024 consultant statement internal arithmetic ties out."""
    data = ConsultantReconciliationService.VERIFIED_HISTORICAL_STATEMENTS[2024]
    audit = ConsultantReconciliationService.audit_consultant_statement(data)
    assert audit.is_balanced is True
    assert audit.assets_liabilities_equity_discrepancy == Decimal("0.00")
    assert audit.pat_vs_current_earnings_discrepancy == Decimal("0.00")
    assert len(audit.findings) == 0


def test_verified_statements_2025_discrepancy_detection():
    """Verify 2025 consultant statement accurately reports the Rp 207,630 internal discrepancy."""
    data = ConsultantReconciliationService.VERIFIED_HISTORICAL_STATEMENTS[2025]
    audit = ConsultantReconciliationService.audit_consultant_statement(data)
    # The consultant statement itself has a Rp 207,630 discrepancy
    assert audit.is_balanced is False
    assert audit.assets_liabilities_equity_discrepancy == Decimal("207630.00")
    assert audit.pat_vs_current_earnings_discrepancy == Decimal("207630.00")
    assert len(audit.findings) >= 2
    assert any("207,630" in f for f in audit.findings)


@pytest.mark.asyncio
async def test_reconciliation_with_saas_ledger(db_session: AsyncSession):
    """Verify reconciliation comparison against double-entry ledger without synthetic plug entries."""
    org = Organization(slug="org-rec-test", legal_name="PT Reconcile Test")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await db_session.commit()

    consultant_data = ConsultantReconciliationService.VERIFIED_HISTORICAL_STATEMENTS[2024]

    report = await ConsultantReconciliationService.reconcile_with_saas(
        session=db_session,
        organization_id=org.id,
        consultant_data=consultant_data,
    )

    assert report.year == 2024
    assert report.organization_id == org.id
    assert report.statement_integrity.is_balanced is True
    assert len(report.pl_comparisons) == 10
    assert len(report.bs_comparisons) == 17

    # Since no transactions are posted in SaaS for 2024 in this test org,
    # non-zero consultant items must be classified as MISSING_DATA
    rev_comp = next(c for c in report.pl_comparisons if c.item_key == "REVENUE")
    assert rev_comp.consultant_amount == Decimal("3271190594.00")
    assert rev_comp.saas_amount == Decimal("0.00")
    assert rev_comp.classification == DifferenceClassification.MISSING_DATA

    # Check that net variances are calculated
    assert report.summary.net_pl_variance == Decimal("0.00") - consultant_data.profit_after_tax
    assert report.summary.missing_data_count > 0


@pytest.mark.asyncio
async def test_reconciliation_detects_consultant_defect(db_session: AsyncSession):
    """Verify reconciliation classifies consultant statement internal discrepancy."""
    org = Organization(slug="org-rec-2025", legal_name="PT Reconcile 2025")
    db_session.add(org)
    await db_session.flush()

    await seed_standard_coa(db_session, org.id)
    await db_session.commit()

    consultant_data = ConsultantReconciliationService.VERIFIED_HISTORICAL_STATEMENTS[2025]

    report = await ConsultantReconciliationService.reconcile_with_saas(
        session=db_session,
        organization_id=org.id,
        consultant_data=consultant_data,
    )

    assert report.statement_integrity.is_balanced is False
    # Check that current year earnings item reflects the defect classification
    cy_comp = next(c for c in report.bs_comparisons if c.item_key == "CURRENT_YEAR_EARNINGS")
    assert cy_comp.classification == DifferenceClassification.CONSULTANT_REPORT_DIFFERENCE
    assert "207,630" in cy_comp.notes
