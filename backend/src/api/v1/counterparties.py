import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_org_id
from src.core.database import get_db
from src.models.counterparty import Counterparty
from src.schemas.counterparty import CounterpartyCreate, CounterpartyResponse


router = APIRouter(prefix="/counterparties", tags=["Counterparties"])


def response_from_model(counterparty: Counterparty) -> CounterpartyResponse:
    contact = counterparty.contact_info or {}
    return CounterpartyResponse(
        id=counterparty.id,
        organization_id=counterparty.organization_id,
        name=counterparty.name,
        is_customer=counterparty.is_customer,
        is_vendor=counterparty.is_vendor,
        phone=contact.get("phone"),
        email=contact.get("email"),
        address=contact.get("address"),
        npwp=counterparty.tax_id,
        created_at=counterparty.created_at,
    )


@router.get("", response_model=list[CounterpartyResponse])
async def list_counterparties(
    is_customer: bool | None = Query(None),
    is_vendor: bool | None = Query(None),
    organization_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    filters = [Counterparty.organization_id == organization_id, Counterparty.is_active.is_(True)]
    if is_customer is not None:
        filters.append(Counterparty.is_customer.is_(is_customer))
    if is_vendor is not None:
        filters.append(Counterparty.is_vendor.is_(is_vendor))
    result = await db.scalars(select(Counterparty).where(*filters).order_by(Counterparty.name))
    return [response_from_model(counterparty) for counterparty in result]


@router.post("", response_model=CounterpartyResponse, status_code=status.HTTP_201_CREATED)
async def create_counterparty(
    data: CounterpartyCreate,
    organization_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    counterparty = Counterparty(
        organization_id=organization_id,
        name=data.name.strip(),
        is_customer=data.is_customer,
        is_vendor=data.is_vendor,
        tax_id=data.npwp,
        contact_info={
            key: value
            for key, value in {"phone": data.phone, "email": data.email, "address": data.address}.items()
            if value
        },
    )
    db.add(counterparty)
    await db.flush()
    return response_from_model(counterparty)