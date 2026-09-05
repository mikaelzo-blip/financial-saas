import re
import uuid
from difflib import SequenceMatcher
from typing import Any, Dict

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.counterparty import Counterparty
from src.models.project import Project
from src.models.coa import PaymentAccount
from src.schemas.document import StructuredExtraction


def normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


async def match_entities(session: AsyncSession, organization_id: uuid.UUID,
                         data: StructuredExtraction) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "counterparty_id": None,
        "project_id": None,
        "payment_account_id": None,
        "alternatives": []
    }
    name = data.issuer_name or data.recipient_name
    parties = list((await session.scalars(select(Counterparty).where(and_(
        Counterparty.organization_id == organization_id, Counterparty.is_active.is_(True))))).all())
    exact = [p for p in parties if normalize(p.name) == normalize(name) and name]
    if len(exact) == 1:
        role = ("CUSTOMER" if exact[0].is_customer and not exact[0].is_vendor else
                "VENDOR" if exact[0].is_vendor and not exact[0].is_customer else None)
        result.update(counterparty_id=str(exact[0].id), counterparty_method="EXACT_NAME",
                      counterparty_role=role, entity_confidence="1.00")
    elif name:
        ranked = sorted(((SequenceMatcher(None, normalize(name), normalize(p.name)).ratio(), p) for p in parties), reverse=True, key=lambda x: x[0])
        result["alternatives"] = [{"id": str(p.id), "name": p.name, "score": f"{score:.4f}"} for score, p in ranked[:3]]
        # ponytail: 0.90 threshold prevents distinct legal entities (e.g. "PT Nusa Utama Engineering" vs "PT Nusa Engineering" at 0.87) from auto-matching. Lower only with verified alias table.
        if ranked and ranked[0][0] >= .90 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= .05):
            party = ranked[0][1]
            role = ("CUSTOMER" if party.is_customer and not party.is_vendor else
                    "VENDOR" if party.is_vendor and not party.is_customer else None)
            result.update(counterparty_id=str(party.id), counterparty_method="FUZZY",
                          counterparty_role=role, entity_confidence=f"{ranked[0][0]:.4f}")

    # Project matching
    reference = normalize(data.project_reference or data.spk_number)
    projects = list((await session.scalars(select(Project).where(Project.organization_id == organization_id))).all())
    matches = [p for p in projects if reference and reference in {normalize(p.project_code), normalize(p.po_spk_no)}]
    if len(matches) == 1:
        result.update(project_id=str(matches[0].id), project_method="EXACT_ID", project_confidence="1.00")

    # Payment account matching
    bank_hint = data.origin_bank or data.destination_bank
    acc_no_hint = data.destination_account_number
    if bank_hint or acc_no_hint:
        accounts = list((await session.scalars(select(PaymentAccount).where(
            and_(PaymentAccount.organization_id == organization_id, PaymentAccount.is_active.is_(True))
        ))).all())
        acc_matches = []
        for acc in accounts:
            if acc_no_hint and acc.account_number and normalize(acc_no_hint) == normalize(acc.account_number):
                acc_matches.append((acc, "EXACT_ACCOUNT_NO", "1.00"))
            elif bank_hint and acc.bank_name and normalize(bank_hint) in normalize(acc.bank_name):
                acc_matches.append((acc, "BANK_NAME", "0.90"))
            elif bank_hint and normalize(bank_hint) in normalize(acc.name):
                acc_matches.append((acc, "NAME_HINT", "0.85"))
        if len(acc_matches) == 1:
            acc, method, conf = acc_matches[0]
            result.update(payment_account_id=str(acc.id), payment_account_method=method, payment_account_confidence=conf)

    return result
