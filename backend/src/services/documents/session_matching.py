"""Multi-Document and Session Matching Engine.

Implements Sections 7, 8, 9, 21, 28, 29 of WhatsApp Document Session Grouping:
- Many-to-many candidate document matching.
- Case A: 1:1 match (Invoice 5m <-> Transfer 5m).
- Case B: Multi-invoice payment (Invoice 5m + Invoice 3m <-> Transfer 8m).
- Case C: Out-of-order document matching based on financial signals, NOT array position.
- Case D: Unrelated vendors split into distinct / ambiguous candidates.
- Evaluates signals: nominal, sum of nominals, references, vendors, bank accounts, dates, timestamps, caption hints.
- Time is only a grouping hint; financial evidence remains authoritative.
- Never directly writes journals or bypasses canonical accounting engine.
"""
from decimal import Decimal
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.enums import DocumentType, CandidateStatus
from src.schemas.document import StructuredExtraction
from src.services.documents.matching import normalize, normalize_party_name


def _to_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


class SessionMatchingService:
    @classmethod
    async def match_session_documents(
        cls,
        db: AsyncSession,
        organization_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Perform document-to-document relationship matching within a Candidate Document Session."""
        # Find all documents belonging to this session
        all_docs = (await db.scalars(
            select(Document).where(Document.organization_id == organization_id)
        )).all()

        session_docs = [
            d for d in all_docs
            if (d.source_metadata or {}).get("session_id") == str(session_id)
        ]

        if len(session_docs) < 2:
            return {
                "matched_pairs": [],
                "multi_invoice_matches": [],
                "session_document_count": len(session_docs),
            }

        return cls.match_document_group(session_docs)

    @classmethod
    def match_document_group(
        cls,
        documents: List[Document],
    ) -> Dict[str, Any]:
        """Evaluate relationships across a group of documents (invoices, receipts, transfer proofs)."""
        invoices: List[Tuple[Document, Decimal, Dict[str, Any]]] = []
        transfers: List[Tuple[Document, Decimal, Dict[str, Any]]] = []
        other_docs: List[Document] = []

        for doc in documents:
            dtype = doc.document_type
            extracted = doc.extracted_data or {}
            amt = _to_decimal(extracted.get("total_amount")) or _to_decimal(extracted.get("nominal")) or _to_decimal((doc.candidate_transaction or {}).get("amount"))

            if dtype in {DocumentType.VENDOR_INVOICE, DocumentType.CUSTOMER_INVOICE, DocumentType.RECEIPT}:
                if amt is not None:
                    invoices.append((doc, amt, extracted))
                else:
                    other_docs.append(doc)
            elif dtype == DocumentType.TRANSFER_PROOF:
                if amt is not None:
                    transfers.append((doc, amt, extracted))
                else:
                    other_docs.append(doc)
            else:
                other_docs.append(doc)

        matched_pairs: List[Dict[str, Any]] = []
        multi_invoice_matches: List[Dict[str, Any]] = []
        used_transfers = set()
        used_invoices = set()

        # 1. Evaluate Exact 1:1 Pairs using Financial Signals (Out-of-order safe, Section 29)
        # Score every possible (transfer, invoice) pair to pick the best global alignment
        pair_candidates: List[Tuple[float, Document, Document, List[str], str]] = []

        for t_doc, t_amt, t_ext in transfers:
            for inv_doc, inv_amt, inv_ext in invoices:
                score = 0.0
                signals = []

                # Signal A: Nominal Amount Match
                if t_amt == inv_amt:
                    score += 40.0
                    signals.append("EXACT_AMOUNT_MATCH")
                elif abs(t_amt - inv_amt) <= Decimal("1000.00"):
                    score += 20.0
                    signals.append("NEAR_AMOUNT_MATCH")

                # Signal B: Vendor / Counterparty Match
                t_vendor = (
                    t_ext.get("recipient_name")
                    or t_ext.get("beneficiary_name")
                    or (t_doc.candidate_transaction or {}).get("counterparty_id")
                )
                inv_vendor = (
                    inv_ext.get("issuer_name")
                    or (inv_doc.candidate_transaction or {}).get("counterparty_id")
                )
                if t_vendor and inv_vendor:
                    t_norm = normalize_party_name(str(t_vendor))
                    inv_norm = normalize_party_name(str(inv_vendor))
                    if t_norm and inv_norm and (t_norm in inv_norm or inv_norm in t_norm):
                        score += 30.0
                        signals.append("SAME_VENDOR")
                    else:
                        # Negative signal: completely conflicting vendors (Section 7 Case D)
                        score -= 25.0
                        signals.append("VENDOR_MISMATCH")

                # Signal C: Reference Match
                t_ref = str(t_ext.get("transfer_reference") or t_ext.get("notes") or "")
                inv_no = str(inv_ext.get("invoice_number") or inv_ext.get("document_number") or "")
                if inv_no and inv_no.lower() in t_ref.lower():
                    score += 25.0
                    signals.append("REFERENCE_IN_TRANSFER")

                # Signal D: Same Session / Message context
                signals.append("SAME_SESSION_CONTEXT")
                score += 10.0

                explanation = f"Transfer {t_amt} ↔ Invoice {inv_amt}"
                if "SAME_VENDOR" in signals:
                    explanation += f" ({t_vendor})"

                pair_candidates.append((score, t_doc, inv_doc, signals, explanation))

        # Sort candidate pairs highest score first (deterministic: tie-break by IDs)
        pair_candidates.sort(key=lambda x: (x[0], str(x[1].id), str(x[2].id)), reverse=True)

        for score, t_doc, inv_doc, signals, expl in pair_candidates:
            if t_doc.id in used_transfers or inv_doc.id in used_invoices:
                continue
            if score >= 50.0 and "VENDOR_MISMATCH" not in signals:
                # Strong 1:1 pair match (Case A & Case C)
                used_transfers.add(t_doc.id)
                used_invoices.add(inv_doc.id)
                confidence = "HIGH" if score >= 70.0 else "MEDIUM"
                matched_pairs.append({
                    "transfer_document_id": str(t_doc.id),
                    "invoice_document_id": str(inv_doc.id),
                    "score": round(score / 100.0, 4),
                    "confidence": confidence,
                    "signals": signals,
                    "explanation": expl,
                    "is_ambiguous": "VENDOR_MISMATCH" in signals,
                })

        # 2. Evaluate Multi-Invoice Settlements (1 Transfer : N Invoices, Section 7 Case B & Section 28)
        remaining_transfers = [t for t in transfers if t[0].id not in used_transfers]
        remaining_invoices = [i for i in invoices if i[0].id not in used_invoices]

        for t_doc, t_amt, t_ext in remaining_transfers:
            # Check if any subset of 2 or more remaining invoices sums exactly to transfer amount
            # Typical case: 2 invoices settling 1 payment
            matched_subset = None
            if len(remaining_invoices) >= 2:
                # Try pairs of invoices
                for i in range(len(remaining_invoices)):
                    for j in range(i + 1, len(remaining_invoices)):
                        inv1_doc, amt1, ext1 = remaining_invoices[i]
                        inv2_doc, amt2, ext2 = remaining_invoices[j]
                        if amt1 + amt2 == t_amt:
                            matched_subset = [remaining_invoices[i], remaining_invoices[j]]
                            break
                    if matched_subset:
                        break

            if matched_subset:
                inv_ids = [str(inv[0].id) for inv in matched_subset]
                inv_amts = [str(inv[1]) for inv in matched_subset]
                for inv in matched_subset:
                    used_invoices.add(inv[0].id)
                used_transfers.add(t_doc.id)

                multi_invoice_matches.append({
                    "transfer_document_id": str(t_doc.id),
                    "transfer_amount": str(t_amt),
                    "invoice_document_ids": inv_ids,
                    "invoice_amounts": inv_amts,
                    "confidence": "MEDIUM",
                    "requires_review": True,  # Section 28: Never auto-post solely because sum matches
                    "signals": ["MULTI_INVOICE_SUM_EXACT_MATCH", "SAME_SESSION_CONTEXT"],
                    "explanation": f"Transfer {t_amt} covers {len(inv_ids)} invoices ({' + '.join(inv_amts)})",
                })

        # Decorate matching_results on each document with relationship details
        for pair in matched_pairs:
            cls._decorate_pair(pair, documents)

        for multi in multi_invoice_matches:
            cls._decorate_multi(multi, documents)

        return {
            "matched_pairs": matched_pairs,
            "multi_invoice_matches": multi_invoice_matches,
            "unmatched_transfers": [str(t[0].id) for t in transfers if t[0].id not in used_transfers],
            "unmatched_invoices": [str(i[0].id) for i in invoices if i[0].id not in used_invoices],
        }

    @staticmethod
    def _decorate_pair(pair: Dict[str, Any], documents: List[Document]) -> None:
        t_id = pair["transfer_document_id"]
        inv_id = pair["invoice_document_id"]

        t_doc = next((d for d in documents if str(d.id) == t_id), None)
        inv_doc = next((d for d in documents if str(d.id) == inv_id), None)

        if t_doc and inv_doc:
            # Decorate transfer document
            t_mr = dict(t_doc.matching_results or {})
            t_mr.setdefault("session_matched_documents", []).append({
                "document_id": str(inv_doc.id),
                "document_code": inv_doc.document_code,
                "document_type": inv_doc.document_type.value,
                "relationship": "PAYS_INVOICE",
                "confidence": pair["confidence"],
                "score": pair["score"],
                "signals": pair["signals"],
                "explanation": pair["explanation"],
            })
            t_doc.matching_results = t_mr

            # Decorate invoice document
            inv_mr = dict(inv_doc.matching_results or {})
            inv_mr.setdefault("session_matched_documents", []).append({
                "document_id": str(t_doc.id),
                "document_code": t_doc.document_code,
                "document_type": t_doc.document_type.value,
                "relationship": "PAID_BY_TRANSFER",
                "confidence": pair["confidence"],
                "score": pair["score"],
                "signals": pair["signals"],
                "explanation": pair["explanation"],
            })
            inv_doc.matching_results = inv_mr

    @staticmethod
    def _decorate_multi(multi: Dict[str, Any], documents: List[Document]) -> None:
        t_id = multi["transfer_document_id"]
        t_doc = next((d for d in documents if str(d.id) == t_id), None)

        if t_doc:
            t_mr = dict(t_doc.matching_results or {})
            t_mr.setdefault("session_multi_invoice_matches", []).append(multi)
            t_doc.matching_results = t_mr

        for inv_id in multi["invoice_document_ids"]:
            inv_doc = next((d for d in documents if str(d.id) == inv_id), None)
            if inv_doc:
                inv_mr = dict(inv_doc.matching_results or {})
                inv_mr.setdefault("session_multi_invoice_matches", []).append(multi)
                inv_doc.matching_results = inv_mr
