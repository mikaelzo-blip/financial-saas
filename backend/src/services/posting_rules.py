import uuid
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal
from dataclasses import dataclass

from src.models.enums import TransactionType, CostCategory, ExpenseCategory
from src.models.transaction import Transaction, TransactionAllocation
from src.core.exceptions import InvariantViolationException


@dataclass
class GeneratedJournalLeg:
    account_code: str
    debit_amount: Decimal
    credit_amount: Decimal
    project_id: Optional[uuid.UUID] = None
    counterparty_id: Optional[uuid.UUID] = None
    cost_category: Optional[CostCategory] = None
    expense_category: Optional[ExpenseCategory] = None
    notes: Optional[str] = None


class PostingRuleRegistry:
    """
    Deterministic rule catalog mapping Transaction + Allocations -> Journal Legs.
    Enforces double-entry equality (Debit == Credit).
    """

    @classmethod
    def generate_journal_legs(cls, transaction: Transaction) -> List[GeneratedJournalLeg]:
        t_type = transaction.transaction_type
        amount = transaction.amount
        allocations = transaction.allocations or []

        legs: List[GeneratedJournalLeg] = []

        if t_type == TransactionType.DIRECT_PURCHASE:
            # Debit Project Cost (5101) or Operational Expense (6199) per allocation
            if allocations:
                for alloc in allocations:
                    dr_code = "5101" if alloc.project_id else "6199"
                    legs.append(
                        GeneratedJournalLeg(
                            account_code=dr_code,
                            debit_amount=alloc.amount,
                            credit_amount=Decimal("0.00"),
                            project_id=alloc.project_id,
                            counterparty_id=transaction.counterparty_id,
                            cost_category=alloc.cost_category,
                            expense_category=alloc.expense_category,
                            notes=alloc.notes or transaction.description
                        )
                    )
            else:
                legs.append(
                    GeneratedJournalLeg(
                        account_code="5101",
                        debit_amount=amount,
                        credit_amount=Decimal("0.00"),
                        counterparty_id=transaction.counterparty_id,
                        notes=transaction.description
                    )
                )
            # Credit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )

        elif t_type in (TransactionType.VENDOR_BILL, TransactionType.SUBCONTRACTOR_BILL):
            # Debit Project Cost (5101)
            if allocations:
                for alloc in allocations:
                    dr_code = "5101" if alloc.project_id else "6199"
                    legs.append(
                        GeneratedJournalLeg(
                            account_code=dr_code,
                            debit_amount=alloc.amount,
                            credit_amount=Decimal("0.00"),
                            project_id=alloc.project_id,
                            counterparty_id=transaction.counterparty_id,
                            cost_category=alloc.cost_category,
                            expense_category=alloc.expense_category,
                            notes=alloc.notes or transaction.description
                        )
                    )
            else:
                legs.append(
                    GeneratedJournalLeg(
                        account_code="5101",
                        debit_amount=amount,
                        credit_amount=Decimal("0.00"),
                        counterparty_id=transaction.counterparty_id,
                        notes=transaction.description
                    )
                )
            # Credit Accounts Payable (2101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="2101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )

        elif t_type in (TransactionType.PAY_VENDOR_BILL, TransactionType.PAY_SUBCONTRACTOR):
            # Debit Accounts Payable (2101)
            project_id = None
            if transaction.allocations and len(transaction.allocations) > 0:
                project_id = transaction.allocations[0].project_id
            legs.append(
                GeneratedJournalLeg(
                    account_code="2101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    counterparty_id=transaction.counterparty_id,
                    project_id=project_id,
                    notes=transaction.description
                )
            )
            # Credit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    counterparty_id=transaction.counterparty_id,
                    project_id=project_id,
                    notes=transaction.description
                )
            )

        elif t_type == TransactionType.VENDOR_ADVANCE:
            # Debit Vendor Advance Asset (1301)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1301",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )
            # Credit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )

        elif t_type == TransactionType.SETTLE_VENDOR_ADVANCE:
            # Debit Project Cost (5101)
            if allocations:
                for alloc in allocations:
                    dr_code = "5101" if alloc.project_id else "6199"
                    legs.append(
                        GeneratedJournalLeg(
                            account_code=dr_code,
                            debit_amount=alloc.amount,
                            credit_amount=Decimal("0.00"),
                            project_id=alloc.project_id,
                            counterparty_id=transaction.counterparty_id,
                            cost_category=alloc.cost_category,
                            expense_category=alloc.expense_category,
                            notes=alloc.notes or transaction.description
                        )
                    )
            else:
                legs.append(
                    GeneratedJournalLeg(
                        account_code="5101",
                        debit_amount=amount,
                        credit_amount=Decimal("0.00"),
                        counterparty_id=transaction.counterparty_id,
                        notes=transaction.description
                    )
                )
            # Credit Vendor Advance Asset (1301)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1301",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )

        elif t_type == TransactionType.CUSTOMER_INVOICE:
            ret_amt = getattr(transaction, "retention_amount", Decimal("0.00")) or Decimal("0.00")
            collectible_amt = amount - ret_amt

            if collectible_amt > Decimal("0.00"):
                # Debit Accounts Receivable (1201)
                legs.append(
                    GeneratedJournalLeg(
                        account_code="1201",
                        debit_amount=collectible_amt,
                        credit_amount=Decimal("0.00"),
                        counterparty_id=transaction.counterparty_id,
                        notes=transaction.description
                    )
                )

            if ret_amt > Decimal("0.00"):
                # Debit Retention Receivable (1202)
                legs.append(
                    GeneratedJournalLeg(
                        account_code="1202",
                        debit_amount=ret_amt,
                        credit_amount=Decimal("0.00"),
                        counterparty_id=transaction.counterparty_id,
                        notes=f"Retensi: {transaction.description}"
                    )
                )

            # Credit Contract Revenue (4101) - full earned revenue
            if allocations:
                for alloc in allocations:
                    legs.append(
                        GeneratedJournalLeg(
                            account_code="4101",
                            debit_amount=Decimal("0.00"),
                            credit_amount=alloc.amount,
                            project_id=alloc.project_id,
                            counterparty_id=transaction.counterparty_id,
                            notes=alloc.notes or transaction.description
                        )
                    )
            else:
                legs.append(
                    GeneratedJournalLeg(
                        account_code="4101",
                        debit_amount=Decimal("0.00"),
                        credit_amount=amount,
                        counterparty_id=transaction.counterparty_id,
                        notes=transaction.description
                    )
                )

        elif t_type == TransactionType.RETENTION_RELEASE:
            # Debit Accounts Receivable (1201)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1201",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )
            # Credit Retention Receivable (1202)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1202",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )

        elif t_type == TransactionType.CUSTOMER_PAYMENT:
            # Debit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )
            # Credit Accounts Receivable (1201)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1201",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )

        elif t_type == TransactionType.CUSTOMER_ADVANCE:
            # Debit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )
            # Credit Customer Advance Liability (2201)
            legs.append(
                GeneratedJournalLeg(
                    account_code="2201",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )

        elif t_type in (TransactionType.BANK_TO_CASH, TransactionType.CASH_TO_BANK, TransactionType.INTERBANK_TRANSFER):
            # Cash/Bank -> Cash/Bank (1101 -> 1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    notes=transaction.description
                )
            )
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    notes=transaction.description
                )
            )

        elif t_type == TransactionType.OWNER_CONTRIBUTION:
            # Debit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    notes=transaction.description
                )
            )
            # Credit Modal Pemilik (3101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="3101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    notes=transaction.description
                )
            )

        elif t_type == TransactionType.OWNER_WITHDRAWAL:
            # Debit Prive Pemilik (3301)
            legs.append(
                GeneratedJournalLeg(
                    account_code="3301",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    notes=transaction.description
                )
            )
            # Credit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    notes=transaction.description
                )
            )

        elif t_type == TransactionType.BANK_CHARGE:
            # Debit Beban Administrasi Bank (6107)
            legs.append(
                GeneratedJournalLeg(
                    account_code="6107",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    notes=transaction.description
                )
            )
            # Credit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    notes=transaction.description
                )
            )

        else:
            raise InvariantViolationException(
                f"No posting rule defined for transaction type: {t_type.value}.",
                details={"transaction_type": t_type.value}
            )

        # Invariant Verification: Total Debit == Total Credit
        total_dr = sum(l.debit_amount for l in legs)
        total_cr = sum(l.credit_amount for l in legs)
        if total_dr != total_cr:
            raise InvariantViolationException(
                f"Generated journal is unbalanced: Total Debit ({total_dr}) != Total Credit ({total_cr}).",
                details={"total_debit": str(total_dr), "total_credit": str(total_cr)}
            )

        return legs
