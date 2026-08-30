import re
import uuid
from difflib import SequenceMatcher
from typing import Any, Dict

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.counterparty import Counterparty
from src.models.project import Project
from src.schemas.document import StructuredExtraction


def normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


async def match_entities(session: AsyncSession, organization_id: uuid.UUID,
                         data: StructuredExtraction) -> Dict[str, Any]:
    result: Dict[str, Any] = {"counterparty_id": None, "project_id": None, "alternatives": []}
    name = data.issuer_name or data.recipient_name
    parties = list((await session.scalars(select(Counterparty).where(and_(
        Counterparty.organization_id == organization_id, Counterparty.is_active.is_(True))))).all())
    exact = [p for p in parties if normalize(p.name) == normalize(name) and name]
    if len(exact) == 1:
        result.update(counterparty_id=str(exact[0].id), counterparty_method="EXACT_NAME", entity_confidence="1.00")
    elif name:
        ranked = sorted(((SequenceMatcher(None, normalize(name), normalize(p.name)).ratio(), p) for p in parties), reverse=True, key=lambda x: x[0])
        result["alternatives"] = [{"id": str(p.id), "score": f"{score:.4f}"} for score, p in ranked[:3]]
        if ranked and ranked[0][0] >= .85 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= .05):
            result.update(counterparty_id=str(ranked[0][1].id), counterparty_method="FUZZY", entity_confidence=f"{ranked[0][0]:.4f}")
    reference = normalize(data.project_reference or data.spk_number)
    projects = list((await session.scalars(select(Project).where(Project.organization_id == organization_id))).all())
    matches = [p for p in projects if reference and reference in {normalize(p.project_code), normalize(p.po_spk_no)}]
    if len(matches) == 1:
        result.update(project_id=str(matches[0].id), project_method="EXACT_ID", project_confidence="1.00")
    return result
