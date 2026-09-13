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
    payment_account_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    counterparty_id: Optional[uuid.UUID] = None
    cost_category: Optional[CostCategory] = None
    expense_category: Optional[ExpenseCategory] = None
    notes: Optional[str] = None



_EXPENSE_CATEGORY_ACCOUNT_MAP: Dict[ExpenseCategory, str] = {
    ExpenseCategory.SALARY: "6101",
    ExpenseCategory.FEE: "6102",
    ExpenseCategory.OFFICE_ADMIN: "6103",
    ExpenseCategory.TRAVEL_OFFICE: "6104",
    ExpenseCategory.PERMITS: "6105",
    ExpenseCategory.PROFESSIONAL_SERVICE: "6106",
    ExpenseCategory.BANK_CHARGES: "6107",
    ExpenseCategory.DEPRECIATION: "6108",
    ExpenseCategory.OTHER_OPERATIONAL: "6199",
}


def _resolve_expense_account(category: Optional[ExpenseCategory]) -> str:
    if category and category in _EXPENSE_CATEGORY_ACCOUNT_MAP:
        return _EXPENSE_CATEGORY_ACCOUNT_MAP[category]
    return "6199"


class PostingRuleRegistry:
    """
    Deterministic rule catalog mapping Transaction + Allocations -> Journal Legs.
    Enforces double-entry equality (Debit == Credit).
    """

    _RULE_TYPE_BY_TRANSACTION_TYPE: Dict[TransactionType, TransactionType] = {
        TransactionType.DIRECT_PURCHASE: TransactionType.DIRECT_PURCHASE,
        TransactionType.VENDOR_BILL: TransactionType.VENDOR_BILL,
        TransactionType.SUBCONTRACTOR_BILL: TransactionType.VENDOR_BILL,
        TransactionType.PAY_VENDOR_BILL: TransactionType.PAY_VENDOR_BILL,
        TransactionType.PAY_SUBCONTRACTOR: TransactionType.PAY_VENDOR_BILL,
        TransactionType.VENDOR_ADVANCE: TransactionType.VENDOR_ADVANCE,
        TransactionType.SETTLE_VENDOR_ADVANCE: TransactionType.SETTLE_VENDOR_ADVANCE,
        TransactionType.CUSTOMER_INVOICE: TransactionType.CUSTOMER_INVOICE,
        TransactionType.RETENTION_RELEASE: TransactionType.RETENTION_RELEASE,
        TransactionType.CUSTOMER_PAYMENT: TransactionType.CUSTOMER_PAYMENT,
        TransactionType.CUSTOMER_ADVANCE: TransactionType.CUSTOMER_ADVANCE,
        TransactionType.BANK_TO_CASH: TransactionType.INTERBANK_TRANSFER,
        TransactionType.CASH_TO_BANK: TransactionType.INTERBANK_TRANSFER,
        TransactionType.INTERBANK_TRANSFER: TransactionType.INTERBANK_TRANSFER,
        TransactionType.JOURNAL_ADJUSTMENT: TransactionType.JOURNAL_ADJUSTMENT,
        TransactionType.OWNER_CONTRIBUTION: TransactionType.OWNER_CONTRIBUTION,
        TransactionType.OWNER_WITHDRAWAL: TransactionType.OWNER_WITHDRAWAL,
        TransactionType.BANK_CHARGE: TransactionType.BANK_CHARGE,
        TransactionType.FIXED_ASSET_DEPRECIATION: TransactionType.FIXED_ASSET_DEPRECIATION,
        TransactionType.ASSET_PURCHASE: TransactionType.ASSET_PURCHASE,
    }
    POSTING_RULE_SUPPORTED_TYPES: frozenset[TransactionType] = frozenset(
        _RULE_TYPE_BY_TRANSACTION_TYPE
    )
    SPECIAL_WORKFLOW_TYPES: frozenset[TransactionType] = frozenset({
        TransactionType.REVERSAL,
    })

    @classmethod
    def is_generic_ingestible(cls, transaction_type: TransactionType) -> bool:
        return transaction_type in cls.POSTING_RULE_SUPPORTED_TYPES

    @classmethod
    def validate_generic_ingestion(cls, transaction_type: TransactionType) -> None:
        if cls.is_generic_ingestible(transaction_type):
            return

        reason = (
            "SPECIAL_WORKFLOW_ONLY"
            if transaction_type in cls.SPECIAL_WORKFLOW_TYPES
            else "NO_POSTING_RULE"
        )
        raise InvariantViolationException(
            f"Transaction type '{transaction_type.value}' is not supported by the generic transaction workflow.",
            details={
                "transaction_type": transaction_type.value,
                "reason": reason,
            },
        )

    @classmethod
    def generate_journal_legs(cls, transaction: Transaction) -> List[GeneratedJournalLeg]:
        t_type = transaction.transaction_type
        rule_type = cls._RULE_TYPE_BY_TRANSACTION_TYPE.get(t_type)
        amount = transaction.amount
        allocations = transaction.allocations or []

        legs: List[GeneratedJournalLeg] = []

        if rule_type == TransactionType.DIRECT_PURCHASE:
            # Debit Project Cost (5101) or Operational Expense (610x / 6199) per allocation
            if allocations:
                for alloc in allocations:
                    dr_code = "5101" if alloc.project_id else _resolve_expense_account(alloc.expense_category)
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
                    payment_account_id=transaction.payment_account_id,
                    project_id=allocations[0].project_id if allocations and len(allocations) == 1 else None,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )


        elif rule_type == TransactionType.VENDOR_BILL:
            # Debit Project Cost (5101) or Operational Expense (610x / 6199)
            if allocations:
                for alloc in allocations:
                    dr_code = "5101" if alloc.project_id else _resolve_expense_account(alloc.expense_category)
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

        elif rule_type == TransactionType.PAY_VENDOR_BILL:
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
                    payment_account_id=transaction.payment_account_id,
                    counterparty_id=transaction.counterparty_id,
                    project_id=project_id,
                    notes=transaction.description
                )
            )

        elif rule_type == TransactionType.VENDOR_ADVANCE:
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
                    payment_account_id=transaction.payment_account_id,
                    counterparty_id=transaction.counterparty_id,
                    notes=transaction.description
                )
            )


        elif rule_type == TransactionType.SETTLE_VENDOR_ADVANCE:
            # Debit Project Cost (5101) or Operational Expense (610x / 6199)
            if allocations:
                for alloc in allocations:
                    dr_code = "5101" if alloc.project_id else _resolve_expense_account(alloc.expense_category)
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

        elif rule_type == TransactionType.CUSTOMER_INVOICE:
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

        elif rule_type == TransactionType.RETENTION_RELEASE:
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

        elif rule_type == TransactionType.CUSTOMER_PAYMENT:
            # Debit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    payment_account_id=transaction.payment_account_id,
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

        elif rule_type == TransactionType.CUSTOMER_ADVANCE:
            # Debit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    payment_account_id=transaction.payment_account_id,
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

        elif rule_type == TransactionType.INTERBANK_TRANSFER:
            # Cash/Bank -> Cash/Bank (1101 -> 1101)
            # Debit destination payment account (or generic 1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    payment_account_id=getattr(transaction, "destination_payment_account_id", None),
                    notes=f"Transfer Masuk: {transaction.description}"
                )
            )
            # Credit source payment account
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    payment_account_id=transaction.payment_account_id,
                    notes=f"Transfer Keluar: {transaction.description}"
                )
            )

        elif rule_type == TransactionType.JOURNAL_ADJUSTMENT:
            # Multi-leg journal adjustment or opening balance from allocations
            if not allocations:
                raise InvariantViolationException("JOURNAL_ADJUSTMENT requires explicit allocations.")
            for alloc in allocations:
                # Format: "DR:1101" or "CR:2101" or "1101" (defaults to DR)
                notes_val = (alloc.notes or "").strip()
                if notes_val.startswith("CR:"):
                    code = notes_val[3:].strip()
                    legs.append(
                        GeneratedJournalLeg(
                            account_code=code,
                            debit_amount=Decimal("0.00"),
                            credit_amount=alloc.amount,
                            project_id=alloc.project_id,
                            cost_category=alloc.cost_category,
                            expense_category=alloc.expense_category
                        )
                    )
                else:
                    code = notes_val[3:].strip() if notes_val.startswith("DR:") else notes_val
                    legs.append(
                        GeneratedJournalLeg(
                            account_code=code,
                            debit_amount=alloc.amount,
                            credit_amount=Decimal("0.00"),
                            project_id=alloc.project_id,
                            cost_category=alloc.cost_category,
                            expense_category=alloc.expense_category
                        )
                    )

        elif rule_type == TransactionType.OWNER_CONTRIBUTION:
            # Debit Cash/Bank (1101)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1101",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    payment_account_id=transaction.payment_account_id,
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

        elif rule_type == TransactionType.OWNER_WITHDRAWAL:
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
                    payment_account_id=transaction.payment_account_id,
                    notes=transaction.description
                )
            )

        elif rule_type == TransactionType.BANK_CHARGE:
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
                    payment_account_id=transaction.payment_account_id,
                    notes=transaction.description
                )
            )

        elif rule_type == TransactionType.FIXED_ASSET_DEPRECIATION:
            # Debit Beban Penyusutan Aset Tetap (6108)
            legs.append(
                GeneratedJournalLeg(
                    account_code="6108",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    notes=transaction.description
                )
            )
            # Credit Akumulasi Penyusutan Aset Tetap (1502)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1502",
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    notes=transaction.description
                )
            )

        elif rule_type == TransactionType.ASSET_PURCHASE:
            # Debit Aset Tetap Operasional (1501)
            legs.append(
                GeneratedJournalLeg(
                    account_code="1501",
                    debit_amount=amount,
                    credit_amount=Decimal("0.00"),
                    notes=transaction.description,
                    counterparty_id=transaction.counterparty_id
                )
            )
            # Credit Cash/Bank (1101) or Accounts Payable (2101)
            cr_code = "1101" if transaction.payment_account_id else "2101"
            legs.append(
                GeneratedJournalLeg(
                    account_code=cr_code,
                    debit_amount=Decimal("0.00"),
                    credit_amount=amount,
                    payment_account_id=transaction.payment_account_id,
                    counterparty_id=transaction.counterparty_id,
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
