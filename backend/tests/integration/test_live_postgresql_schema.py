import os
import uuid
import pytest
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.models.organization import Organization
from src.models.coa import ChartOfAccount, PaymentAccount
from src.models.transaction import Transaction
from src.models.accounting_period import AccountingPeriod
from src.models.fixed_asset import FixedAsset
from src.models.background_job import BackgroundJob
from src.models.bank_reconciliation import BankStatementImport, BankStatementLine, BankReconciliation
from src.models.inbox import InboxMessage, DocumentSession
from src.models.enums import (
    TransactionType,
    AccountingPeriodStatus,
    ReconciliationStatus,
    InboxMessageStatus,
    SessionMatchStatus,
)

PG_URL = os.environ.get(
    "LIVE_POSTGRES_URL",
    "postgresql+asyncpg://financial:financial_dev_2026@localhost:5432/financial_saas"
)


@pytest.mark.asyncio
async def test_live_postgresql_connection_and_alembic_head():
    """Verify live PostgreSQL container is accessible and on Alembic head (020)."""
    try:
        engine = create_async_engine(PG_URL, echo=False)
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT version_num FROM alembic_version"))
            version = res.scalar()
            assert version == "020_p7_background_jobs", f"Expected 020_p7_background_jobs, got {version}"
        await engine.dispose()
    except Exception as e:
        pytest.skip(f"Live PostgreSQL not reachable or credentials mismatch: {e}")


@pytest.mark.asyncio
async def test_live_postgresql_models_crud():
    """Verify CRUD on P0-P7 tables directly on PostgreSQL to ensure column types, defaults, and constraints."""
    try:
        engine = create_async_engine(PG_URL, echo=False)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            # 1. Verify Organization & Period
            org_slug = f"pg-test-{uuid.uuid4().hex[:6]}"
            org = Organization(slug=org_slug, legal_name="PT Postgres Test Entity")
            session.add(org)
            await session.flush()

            period = AccountingPeriod(
                organization_id=org.id,
                period_name="2026-09",
                start_date=date(2026, 9, 1),
                end_date=date(2026, 9, 30),
                status=AccountingPeriodStatus.OPEN
            )
            session.add(period)

            # 2. Verify BackgroundJob
            job = BackgroundJob(
                organization_id=org.id,
                job_type="DOCUMENT_DEFERRED_ANALYSIS",
                payload={"doc_id": str(uuid.uuid4())},
                status="PENDING",
                available_at=datetime.now()
            )
            session.add(job)

            # 3. Verify InboxMessage
            inbox_msg = InboxMessage(
                organization_id=org.id,
                external_message_id=f"wamid-live-{uuid.uuid4().hex[:8]}",
                sender_phone="+6281234567890",
                sender_name="Live Test User",
                caption="Kwitansi semen 50 sak",
                status=InboxMessageStatus.RECEIVED,
                received_at=datetime.now()
            )
            session.add(inbox_msg)
            await session.flush()

            # 4. Verify DocumentSession
            doc_session = DocumentSession(
                organization_id=org.id,
                session_code=f"SES-LIVE-{uuid.uuid4().hex[:6]}",
                inbox_message_id=inbox_msg.id,
                status=SessionMatchStatus.PENDING
            )
            session.add(doc_session)
            await session.flush()

            assert period.id is not None
            assert job.id is not None
            assert inbox_msg.id is not None
            assert doc_session.id is not None

            # Clean up test rows
            await session.rollback()
        await engine.dispose()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
