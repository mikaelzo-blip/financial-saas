import uuid
import hashlib
import csv
import io
from decimal import Decimal
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import select, and_, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bank_reconciliation import (
    BankStatementImport,
    BankStatementLine,
    BankReconciliation,
)
from src.models.coa import PaymentAccount
from src.models.journal import JournalLine, JournalEntry
from src.models.money_movement import MoneyMovement, Settlement

from src.models.enums import ReconciliationStatus, StatementImportStatus, MovementDirection
from src.schemas.bank_reconciliation import (
    BankStatementLineCreate,
    BankReconciliationMatchRequest,
    CashCompletenessDashboardResponse,
)
from src.core.exceptions import (
    InvariantViolationException,
    EntityNotFoundException,
    DuplicateEntityException,
)


class BankReconciliationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def import_statement(
        self,
        organization_id: uuid.UUID,
        payment_account_id: uuid.UUID,
        source_file: str,
        file_content: bytes,
        parsed_lines: Optional[List[BankStatementLineCreate]] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None
    ) -> BankStatementImport:
        """
        Imports a bank statement with cryptographic deduplication.
        Blocks duplicate statement import attempts.
        """
        # Validate PaymentAccount belongs to org
        pa = await self.session.scalar(
            select(PaymentAccount).where(
                PaymentAccount.id == payment_account_id,
                PaymentAccount.organization_id == organization_id
            )
        )
        if not pa:
            raise EntityNotFoundException("Payment account not found in organization")

        # Compute SHA-256
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Check for duplicate
        existing = await self.session.scalar(
            select(BankStatementImport).where(
                BankStatementImport.organization_id == organization_id,
                BankStatementImport.file_hash == file_hash
            )
        )
        if existing:
            raise DuplicateEntityException(f"Duplicate statement file import detected (hash: {file_hash[:8]})")

        # If lines not provided via parser, attempt standard CSV parsing
        lines_to_add = parsed_lines
        if lines_to_add is None:
            lines_to_add = self.parse_csv(file_content.decode("utf-8", errors="ignore"))

        stmt_import = BankStatementImport(
            organization_id=organization_id,
            payment_account_id=payment_account_id,
            period_start=period_start,
            period_end=period_end,
            file_hash=file_hash,
            source_file=source_file,
            status=StatementImportStatus.COMPLETED
        )
        self.session.add(stmt_import)
        await self.session.flush()

        for idx, line_data in enumerate(lines_to_add, start=1):
            stmt_line = BankStatementLine(
                import_id=stmt_import.id,
                organization_id=organization_id,
                line_number=idx,
                transaction_date=line_data.transaction_date,
                description=line_data.description,
                debit=line_data.debit,
                credit=line_data.credit,
                balance=line_data.balance,
                reference=line_data.reference,
                counterparty_name=line_data.counterparty_name,
                reconciliation_status=ReconciliationStatus.UNMATCHED_BANK
            )
            self.session.add(stmt_line)

        await self.session.flush()

        loaded_stmt = await self.session.scalar(
            select(BankStatementImport)
            .where(BankStatementImport.id == stmt_import.id)
            .options(selectinload(BankStatementImport.lines))
        )
        return loaded_stmt



    def parse_csv(self, csv_text: str) -> List[BankStatementLineCreate]:
        """
        Parses standard CSV statement formats (date, description, debit, credit, balance, reference).
        """
        lines: List[BankStatementLineCreate] = []
        reader = csv.DictReader(io.StringIO(csv_text))
        for idx, row in enumerate(reader, start=1):
            # Safe field access with Indonesian & English aliases
            date_str = row.get("date") or row.get("tanggal") or row.get("Date") or str(date.today())
            try:
                trx_date = date.fromisoformat(date_str.strip())
            except Exception:
                trx_date = date.today()

            desc = row.get("description") or row.get("keterangan") or row.get("Description") or "Transaction"
            debit_val = Decimal(str(row.get("debit") or row.get("keluar") or row.get("mutasi_debet") or "0.00").replace(",", "").strip() or "0.00")
            credit_val = Decimal(str(row.get("credit") or row.get("masuk") or row.get("mutasi_kredit") or "0.00").replace(",", "").strip() or "0.00")
            bal_str = row.get("balance") or row.get("saldo")
            bal_val = Decimal(str(bal_str).replace(",", "").strip()) if bal_str else None
            ref = row.get("reference") or row.get("no_referensi") or row.get("ref")

            lines.append(
                BankStatementLineCreate(
                    line_number=idx,
                    transaction_date=trx_date,
                    description=desc.strip(),
                    debit=debit_val,
                    credit=credit_val,
                    balance=bal_val,
                    reference=ref.strip() if ref else None,
                    counterparty_name=row.get("counterparty") or row.get("pihak_ketiga")
                )
            )
        return lines

    async def auto_match_statement(
        self,
        organization_id: uuid.UUID,
        import_id: uuid.UUID
    ) -> Dict[str, int]:
        """
        Deterministic matching engine:
        Matches bank statement lines with MoneyMovements and JournalLines by:
        1. Exact reference & bank
        2. Exact amount, payment account, and date
        """
        stmt_import = await self.session.scalar(
            select(BankStatementImport).where(
                BankStatementImport.id == import_id,
                BankStatementImport.organization_id == organization_id
            )
        )
        if not stmt_import:
            raise EntityNotFoundException("Bank statement import not found")

        # Load unmatched lines
        lines = (await self.session.scalars(
            select(BankStatementLine).where(
                BankStatementLine.import_id == import_id,
                BankStatementLine.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK
            )
        )).all()

        stats = {"matched": 0, "review_required": 0, "unmatched": 0}

        for line in lines:
            # 1. Match by reference if present
            matched = False
            line_amount = line.credit if line.credit > 0 else line.debit

            if line.reference:
                # Look for matching money movement
                mm = await self.session.scalar(
                    select(MoneyMovement).where(
                        MoneyMovement.organization_id == organization_id,
                        MoneyMovement.payment_account_id == stmt_import.payment_account_id,
                        MoneyMovement.reference_no == line.reference,
                        MoneyMovement.amount == line_amount
                    )
                )
                if mm:
                    reconcil = BankReconciliation(
                        organization_id=organization_id,
                        statement_line_id=line.id,
                        money_movement_id=mm.id,
                        status=ReconciliationStatus.MATCHED,
                        matched_amount=line_amount,
                        match_rule="EXACT_REFERENCE_AND_AMOUNT"
                    )
                    self.session.add(reconcil)
                    line.reconciliation_status = ReconciliationStatus.MATCHED
                    stats["matched"] += 1
                    matched = True

            # 2. Match by exact amount and date
            if not matched:
                jl = await self.session.scalar(
                    select(JournalLine)
                    .join(JournalEntry)
                    .where(
                        JournalLine.payment_account_id == stmt_import.payment_account_id,
                        JournalEntry.organization_id == organization_id,
                        JournalEntry.posting_date == line.transaction_date,
                        or_(
                            and_(line.credit > 0, JournalLine.debit_amount == line.credit),
                            and_(line.debit > 0, JournalLine.credit_amount == line.debit)
                        )
                    )
                )
                if jl:
                    reconcil = BankReconciliation(
                        organization_id=organization_id,
                        statement_line_id=line.id,
                        journal_line_id=jl.id,
                        status=ReconciliationStatus.MATCHED,
                        matched_amount=line_amount,
                        match_rule="EXACT_DATE_AND_AMOUNT"
                    )
                    self.session.add(reconcil)
                    line.reconciliation_status = ReconciliationStatus.MATCHED
                    stats["matched"] += 1
                    matched = True

            if not matched:
                stats["unmatched"] += 1

        await self.session.flush()
        return stats

    async def match_manual(
        self,
        organization_id: uuid.UUID,
        req: BankReconciliationMatchRequest,
        matched_by: Optional[uuid.UUID] = None
    ) -> BankReconciliation:
        """
        Manual user match from Web App.
        """
        line = await self.session.scalar(
            select(BankStatementLine).where(
                BankStatementLine.id == req.statement_line_id,
                BankStatementLine.organization_id == organization_id
            )
        )
        if not line:
            raise EntityNotFoundException("Statement line not found")

        reconcil = BankReconciliation(
            organization_id=organization_id,
            statement_line_id=line.id,
            journal_line_id=req.journal_line_id,
            money_movement_id=req.money_movement_id,
            transaction_id=req.transaction_id,
            status=ReconciliationStatus.MATCHED,
            matched_amount=req.matched_amount,
            match_rule="MANUAL_WEB_MATCH",
            notes=req.notes,
            matched_by=matched_by
        )
        line.reconciliation_status = ReconciliationStatus.MATCHED
        self.session.add(reconcil)
        await self.session.flush()
        return reconcil

    async def get_cash_completeness_dashboard(
        self,
        organization_id: uuid.UUID,
        payment_account_id: Optional[uuid.UUID] = None
    ) -> CashCompletenessDashboardResponse:
        """
        Cash Completeness Dashboard metrics:
        - Total Bank Inflow & Outflow
        - Matched total
        - Unmatched Bank total
        - Unmatched Book total (Ledger lines without reconciliation)
        - Unallocated Cash total
        """
        # Bank lines query
        query_lines = select(BankStatementLine).where(BankStatementLine.organization_id == organization_id)
        if payment_account_id:
            query_lines = query_lines.join(BankStatementImport).where(BankStatementImport.payment_account_id == payment_account_id)

        all_lines = (await self.session.scalars(query_lines)).all()

        total_inflow = sum(l.credit for l in all_lines)
        total_outflow = sum(l.debit for l in all_lines)
        total_bank_volume = total_inflow + total_outflow

        matched_amount = sum(l.credit + l.debit for l in all_lines if l.reconciliation_status == ReconciliationStatus.MATCHED)
        unmatched_bank = sum(l.credit + l.debit for l in all_lines if l.reconciliation_status == ReconciliationStatus.UNMATCHED_BANK)

        # Unmatched book lines (Cash journal lines not referenced in bank_reconciliations)
        jl_query = (
            select(func.coalesce(func.sum(JournalLine.debit_amount + JournalLine.credit_amount), Decimal("0.00")))
            .join(JournalEntry)
            .where(
                JournalEntry.organization_id == organization_id,
                JournalLine.payment_account_id.is_not(None)
            )
        )
        if payment_account_id:
            jl_query = jl_query.where(JournalLine.payment_account_id == payment_account_id)

        total_book_cash = await self.session.scalar(jl_query) or Decimal("0.00")
        unmatched_book = max(Decimal("0.00"), total_book_cash - matched_amount)

        # Unallocated cash movements via money movement service logic
        in_stmt = select(func.coalesce(func.sum(MoneyMovement.amount), Decimal("0.00"))).where(
            MoneyMovement.organization_id == organization_id,
            MoneyMovement.direction == MovementDirection.IN
        )
        settled_stmt = (
            select(func.coalesce(func.sum(Settlement.amount), Decimal("0.00")))
            .join(MoneyMovement, Settlement.money_movement_id == MoneyMovement.id)
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.direction == MovementDirection.IN
            )
        )
        if payment_account_id:
            in_stmt = in_stmt.where(MoneyMovement.payment_account_id == payment_account_id)
            settled_stmt = settled_stmt.where(MoneyMovement.payment_account_id == payment_account_id)

        tot_in = await self.session.scalar(in_stmt) or Decimal("0.00")
        tot_settled = await self.session.scalar(settled_stmt) or Decimal("0.00")
        unallocated_cash = max(Decimal("0.00"), tot_in - tot_settled)


        completeness_pct = (
            (matched_amount / total_bank_volume * Decimal("100.00"))
            if total_bank_volume > 0
            else Decimal("100.00")
        )

        return CashCompletenessDashboardResponse(
            payment_account_id=payment_account_id,
            total_bank_inflow=total_inflow,
            total_bank_outflow=total_outflow,
            matched_amount=matched_amount,
            unmatched_bank_amount=unmatched_bank,
            unmatched_book_amount=unmatched_book,
            unallocated_cash_total=unallocated_cash,
            completeness_percentage=completeness_pct.quantize(Decimal("0.01"))
        )
