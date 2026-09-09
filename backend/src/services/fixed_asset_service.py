import uuid
from typing import Optional, List, Dict
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, and_, func, extract
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.fixed_asset import FixedAsset, FixedAssetDepreciation
from src.models.transaction import Transaction
from src.models.enums import (
    AssetStatus,
    DepreciationMethod,
    TransactionType,
    WorkflowStatus,
    AccountingPeriodStatus,
    UserRole
)
from src.models.accounting_period import AccountingPeriod
from src.schemas.fixed_asset import (
    FixedAssetCreate,
    FixedAssetUpdate,
    DepreciationRunResult,
    BatchDepreciationResponse,
    CapitalizationGuidanceResponse
)
from src.services.accounting_engine import AccountingEngine
from src.services.audit_service import AuditService
from src.core.exceptions import EntityNotFoundException, InvariantViolationException


# Category default useful lives in months per Owner-approved RC1 policy
CATEGORY_USEFUL_LIFE_DEFAULTS: Dict[str, int] = {
    # Computer / Laptop: 4 years
    "COMPUTER": 48,
    "LAPTOP": 48,
    "KOMPUTER": 48,
    # Office Equipment: 4 years
    "OFFICE_EQUIPMENT": 48,
    "PERALATAN_KANTOR": 48,
    # Light Project Tools: 4 years
    "LIGHT_TOOLS": 48,
    "PERALATAN_RINGAN": 48,
    "PERALATAN_PROYEK": 48,
    # Major Project Equipment: 8 years
    "MAJOR_EQUIPMENT": 96,
    "ALAT_BERAT": 96,
    "HEAVY_EQUIPMENT": 96,
    # Vehicle: 8 years
    "VEHICLE": 96,
    "KENDARAAN": 96,
    # Permanent Building: 20 years
    "BUILDING": 240,
    "BANGUNAN": 240,
}

# Company Book Capitalization Policy
CAPITALIZATION_THRESHOLD = Decimal("5000000.00")
CAPITALIZATION_MIN_BENEFIT_MONTHS = 12


class FixedAssetService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def get_category_default_useful_life(category: str) -> int:
        normalized = category.strip().upper().replace(" ", "_").replace("-", "_")
        return CATEGORY_USEFUL_LIFE_DEFAULTS.get(normalized, 48)

    @staticmethod
    def get_capitalization_guidance(
        amount: Decimal,
        benefit_months: int = 12
    ) -> CapitalizationGuidanceResponse:
        qualifies = (amount >= CAPITALIZATION_THRESHOLD) and (benefit_months > CAPITALIZATION_MIN_BENEFIT_MONTHS)
        if qualifies:
            rec = "FIXED_ASSET_CANDIDATE"
            notes = (
                f"Nilai perolehan (Rp {amount:,.2f}) >= ambang batas kapitalisasi (Rp {CAPITALIZATION_THRESHOLD:,.2f}) "
                f"dan masa manfaat ({benefit_months} bulan) > 12 bulan. Disarankan dicatat sebagai Aset Tetap."
            )
        elif amount < CAPITALIZATION_THRESHOLD:
            rec = "EXPENSE_DEFAULT"
            notes = (
                f"Nilai perolehan (Rp {amount:,.2f}) di bawah ambang batas kapitalisasi (Rp {CAPITALIZATION_THRESHOLD:,.2f}). "
                f"Sesuai kebijakan buku perusahaan, dibebankan langsung (Beban Proyek / Operasional)."
            )
        else:
            rec = "REVIEW_REQUIRED"
            notes = "Pembelian bernilai material namun masa manfaat <= 12 bulan atau ambigu. Perlu verifikasi manual."

        return CapitalizationGuidanceResponse(
            amount=amount,
            benefit_months=benefit_months,
            threshold=CAPITALIZATION_THRESHOLD,
            qualifies_as_fixed_asset=qualifies,
            recommendation=rec,
            notes=notes
        )

    async def list_assets(
        self,
        organization_id: uuid.UUID,
        status: Optional[AssetStatus] = None,
        category: Optional[str] = None
    ) -> List[FixedAsset]:
        stmt = (
            select(FixedAsset)
            .options(selectinload(FixedAsset.depreciations))
            .where(FixedAsset.organization_id == organization_id)
            .order_by(FixedAsset.purchase_date.desc(), FixedAsset.asset_code.asc())
        )
        if status:
            stmt = stmt.where(FixedAsset.status == status)
        if category:
            stmt = stmt.where(FixedAsset.asset_category == category)

        result = await self.session.scalars(stmt)
        return list(result.all())

    async def get_asset(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID
    ) -> FixedAsset:
        stmt = (
            select(FixedAsset)
            .options(selectinload(FixedAsset.depreciations))
            .where(
                and_(
                    FixedAsset.organization_id == organization_id,
                    FixedAsset.id == asset_id
                )
            )
        )
        asset = await self.session.scalar(stmt)
        if not asset:
            raise EntityNotFoundException("FixedAsset", asset_id)
        return asset

    async def create_asset(
        self,
        organization_id: uuid.UUID,
        data: FixedAssetCreate,
        actor_id: Optional[uuid.UUID] = None
    ) -> FixedAsset:
        # 1. Uniqueness check on asset_code
        existing_code = await self.session.scalar(
            select(FixedAsset).where(
                and_(
                    FixedAsset.organization_id == organization_id,
                    FixedAsset.asset_code == data.asset_code
                )
            )
        )
        if existing_code:
            raise InvariantViolationException(
                f"Kode aset '{data.asset_code}' sudah terdaftar dalam organisasi.",
                details={"asset_code": data.asset_code}
            )

        # 2. Resolve useful life with category defaults
        default_months = self.get_category_default_useful_life(data.asset_category)
        useful_life = data.useful_life_months or default_months

        # 3. Available for use date defaults to purchase_date if omitted
        available_date = data.available_for_use_date or data.purchase_date
        if available_date < data.purchase_date:
            raise InvariantViolationException(
                "Tanggal mulai digunakan tidak boleh sebelum tanggal pembelian.",
                details={"purchase_date": str(data.purchase_date), "available_for_use_date": str(available_date)}
            )

        if data.purchase_cost <= Decimal("0.00"):
            raise InvariantViolationException("Harga perolehan aset harus lebih besar dari 0.")

        salvage = data.salvage_value or Decimal("0.00")
        if salvage >= data.purchase_cost:
            raise InvariantViolationException("Nilai residu tidak boleh melebihi atau sama dengan harga perolehan aset.")

        asset = FixedAsset(
            id=uuid.uuid4(),
            organization_id=organization_id,
            asset_code=data.asset_code,
            asset_name=data.asset_name,
            asset_category=data.asset_category,
            purchase_date=data.purchase_date,
            available_for_use_date=available_date,
            purchase_cost=data.purchase_cost,
            salvage_value=salvage,
            useful_life_months=useful_life,
            depreciation_method=data.depreciation_method,
            accumulated_depreciation=Decimal("0.00"),
            status=data.status or AssetStatus.ACTIVE,
            vendor_id=data.vendor_id,
            document_id=data.document_id,
            fiscal_asset_group=data.fiscal_asset_group,
            fiscal_depreciation_method=data.fiscal_depreciation_method,
            fiscal_useful_life_months=data.fiscal_useful_life_months,
            depreciations=[]
        )
        self.session.add(asset)
        await self.session.flush()

        # Audit trail
        audit = AuditService(self.session)
        await audit.log_event(
            organization_id=organization_id,
            entity_name="FIXED_ASSET",
            entity_id=asset.id,
            action="CREATE",
            actor_id=actor_id,
            new_values={
                "asset_code": asset.asset_code,
                "asset_name": asset.asset_name,
                "purchase_cost": str(asset.purchase_cost),
                "useful_life_months": asset.useful_life_months,
                "default_useful_life_months": default_months,
                "override_reason": data.override_reason if useful_life != default_months else None
            }
        )

        return asset

    async def update_asset(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
        data: FixedAssetUpdate,
        actor_id: Optional[uuid.UUID] = None
    ) -> FixedAsset:
        asset = await self.get_asset(organization_id, asset_id)

        changes = {}
        if data.asset_name is not None and data.asset_name != asset.asset_name:
            changes["asset_name"] = {"old": asset.asset_name, "new": data.asset_name}
            asset.asset_name = data.asset_name
        if data.asset_category is not None and data.asset_category != asset.asset_category:
            changes["asset_category"] = {"old": asset.asset_category, "new": data.asset_category}
            asset.asset_category = data.asset_category
        if data.available_for_use_date is not None:
            if data.available_for_use_date < asset.purchase_date:
                raise InvariantViolationException("Tanggal mulai digunakan tidak boleh sebelum tanggal pembelian.")
            changes["available_for_use_date"] = {"old": str(asset.available_for_use_date), "new": str(data.available_for_use_date)}
            asset.available_for_use_date = data.available_for_use_date
        if data.salvage_value is not None:
            if data.salvage_value >= asset.purchase_cost:
                raise InvariantViolationException("Nilai residu tidak boleh melebihi atau sama dengan harga perolehan.")
            changes["salvage_value"] = {"old": str(asset.salvage_value), "new": str(data.salvage_value)}
            asset.salvage_value = data.salvage_value
        if data.useful_life_months is not None and data.useful_life_months != asset.useful_life_months:
            changes["useful_life_months"] = {"old": asset.useful_life_months, "new": data.useful_life_months}
            changes["override_reason"] = data.override_reason
            asset.useful_life_months = data.useful_life_months
        if data.status is not None and data.status != asset.status:
            changes["status"] = {"old": asset.status.value, "new": data.status.value}
            asset.status = data.status

        if data.fiscal_asset_group is not None:
            asset.fiscal_asset_group = data.fiscal_asset_group
        if data.fiscal_depreciation_method is not None:
            asset.fiscal_depreciation_method = data.fiscal_depreciation_method
        if data.fiscal_useful_life_months is not None:
            asset.fiscal_useful_life_months = data.fiscal_useful_life_months

        await self.session.flush()

        if changes:
            audit = AuditService(self.session)
            await audit.log_event(
                organization_id=organization_id,
                entity_name="FIXED_ASSET",
                entity_id=asset.id,
                action="UPDATE",
                actor_id=actor_id,
                new_values=changes,
                reason=data.override_reason
            )

        return asset

    def calculate_depreciation_amount(
        self,
        asset: FixedAsset,
        period_date: date
    ) -> Decimal:
        """
        Straight-line depreciation formula:
        depreciable_amount = purchase_cost - salvage_value
        monthly_depreciation = depreciable_amount / useful_life_months

        Guards:
        - Never depreciate before available_for_use_date
        - Never depreciate beyond remaining depreciable amount
        - Return Decimal("0.00") if already fully depreciated or inactive
        """
        if asset.status != AssetStatus.ACTIVE:
            return Decimal("0.00")

        # Never depreciate before available for use date
        if period_date < asset.effective_available_date:
            return Decimal("0.00")

        remaining = asset.remaining_depreciable_amount
        if remaining <= Decimal("0.00"):
            return Decimal("0.00")

        monthly_rate = asset.monthly_depreciation_rate
        return min(monthly_rate, remaining)

    async def _check_period_posting_guard(
        self,
        organization_id: uuid.UUID,
        tx_date: date,
        actor_role: Optional[UserRole] = None
    ) -> None:
        """Enforces accounting period closure controls for depreciation posting."""
        stmt = select(AccountingPeriod).where(
            and_(
                AccountingPeriod.organization_id == organization_id,
                AccountingPeriod.start_date <= tx_date,
                AccountingPeriod.end_date >= tx_date,
                AccountingPeriod.status.in_([AccountingPeriodStatus.CLOSED, AccountingPeriodStatus.SOFT_CLOSED])
            )
        )
        closed_period = await self.session.scalar(stmt)
        if closed_period:
            if closed_period.status == AccountingPeriodStatus.CLOSED:
                raise InvariantViolationException(
                    f"Tidak dapat memposting penyusutan: Periode akuntansi '{closed_period.period_name}' telah DITUTUP (CLOSED).",
                    details={"period_name": closed_period.period_name, "status": closed_period.status.value}
                )
            elif closed_period.status == AccountingPeriodStatus.SOFT_CLOSED:
                if actor_role not in (UserRole.ADMIN, UserRole.MANAGER):
                    raise InvariantViolationException(
                        f"Tidak dapat memposting penyusutan: Periode akuntansi '{closed_period.period_name}' dalam status SOFT_CLOSED. Diperlukan role ADMIN atau MANAGER.",
                        details={"period_name": closed_period.period_name, "status": closed_period.status.value}
                    )

    async def depreciate_asset(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
        period_date: date,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[UserRole] = None
    ) -> DepreciationRunResult:
        asset = await self.get_asset(organization_id, asset_id)

        if asset.status == AssetStatus.DRAFT:
            raise InvariantViolationException("Aset dalam status DRAFT tidak dapat disusutkan. Aktifkan aset terlebih dahulu.")
        if asset.status in (AssetStatus.DISPOSED, AssetStatus.WRITTEN_OFF):
            raise InvariantViolationException(f"Aset dalam status '{asset.status.value}' tidak dapat disusutkan.")

        # Check duplicate depreciation for the same calendar month
        dup_stmt = select(FixedAssetDepreciation).where(
            and_(
                FixedAssetDepreciation.organization_id == organization_id,
                FixedAssetDepreciation.asset_id == asset_id,
                extract("year", FixedAssetDepreciation.period_date) == period_date.year,
                extract("month", FixedAssetDepreciation.period_date) == period_date.month
            )
        )
        existing_depr = await self.session.scalar(dup_stmt)
        if existing_depr:
            raise InvariantViolationException(
                f"Aset '{asset.asset_name}' ({asset.asset_code}) sudah disusutkan untuk periode {period_date.strftime('%B %Y')}.",
                details={"asset_code": asset.asset_code, "period_date": str(period_date)}
            )

        dep_amount = self.calculate_depreciation_amount(asset, period_date)

        # If asset is already fully depreciated or 0 remaining
        if dep_amount <= Decimal("0.00"):
            if asset.remaining_depreciable_amount <= Decimal("0.00") and asset.status == AssetStatus.ACTIVE:
                asset.status = AssetStatus.FULLY_DEPRECIATED
                await self.session.flush()

            return DepreciationRunResult(
                asset_id=asset.id,
                asset_code=asset.asset_code,
                asset_name=asset.asset_name,
                period_date=period_date,
                depreciation_amount=Decimal("0.00"),
                accumulated_depreciation=asset.accumulated_depreciation,
                net_book_value=asset.net_book_value,
                status=asset.status
            )

        # Check Accounting Period guard
        await self._check_period_posting_guard(organization_id, period_date, actor_role)

        # Generate Transaction for deterministic posting
        tx = Transaction(
            id=uuid.uuid4(),
            organization_id=organization_id,
            transaction_code=f"DEP-{asset.asset_code}-{period_date.strftime('%Y%m')}",
            transaction_type=TransactionType.FIXED_ASSET_DEPRECIATION,
            transaction_date=period_date,
            amount=dep_amount,
            description=f"Beban Penyusutan {asset.asset_name} ({asset.asset_code}) - {period_date.strftime('%b %Y')}",
            workflow_status=WorkflowStatus.APPROVED,
            created_by=actor_id
        )
        self.session.add(tx)
        await self.session.flush()

        # Post via AccountingEngine -> Dr 6108, Cr 1502
        engine = AccountingEngine(self.session)
        journal = await engine.post_transaction(
            organization_id=organization_id,
            transaction_id=tx.id,
            posting_date=period_date,
            actor_id=actor_id,
            actor_role=actor_role,
        )

        # Update asset accumulated depreciation & status
        new_accumulated = asset.accumulated_depreciation + dep_amount
        asset.accumulated_depreciation = new_accumulated

        if new_accumulated >= asset.depreciable_amount:
            asset.status = AssetStatus.FULLY_DEPRECIATED

        # Insert immutable depreciation history record
        dep_record = FixedAssetDepreciation(
            id=uuid.uuid4(),
            organization_id=organization_id,
            asset_id=asset.id,
            period_date=period_date,
            depreciation_amount=dep_amount,
            accumulated_after=new_accumulated,
            book_value_after=asset.net_book_value,
            transaction_id=tx.id,
            journal_entry_id=journal.id
        )
        self.session.add(dep_record)
        await self.session.flush()

        # Audit
        audit = AuditService(self.session)
        await audit.log_event(
            organization_id=organization_id,
            entity_name="FIXED_ASSET",
            entity_id=asset.id,
            action="DEPRECIATE",
            actor_id=actor_id,
            new_values={
                "period_date": str(period_date),
                "depreciation_amount": str(dep_amount),
                "accumulated_depreciation": str(new_accumulated),
                "net_book_value": str(asset.net_book_value),
                "journal_entry_number": journal.entry_number
            }
        )

        return DepreciationRunResult(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            period_date=period_date,
            depreciation_amount=dep_amount,
            accumulated_depreciation=new_accumulated,
            net_book_value=asset.net_book_value,
            transaction_id=tx.id,
            journal_entry_id=journal.id,
            journal_entry_number=journal.entry_number,
            status=asset.status
        )

    async def depreciate_batch(
        self,
        organization_id: uuid.UUID,
        period_date: date,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[UserRole] = None
    ) -> BatchDepreciationResponse:
        # Fetch all ACTIVE assets that are available for use
        stmt = (
            select(FixedAsset)
            .where(
                and_(
                    FixedAsset.organization_id == organization_id,
                    FixedAsset.status == AssetStatus.ACTIVE,
                    func.coalesce(FixedAsset.available_for_use_date, FixedAsset.purchase_date) <= period_date,
                    FixedAsset.accumulated_depreciation < (FixedAsset.purchase_cost - FixedAsset.salvage_value)
                )
            )
            .order_by(FixedAsset.asset_code.asc())
        )
        assets = (await self.session.scalars(stmt)).all()

        results: List[DepreciationRunResult] = []
        total_dep = Decimal("0.00")

        for asset in assets:
            # Check if already depreciated for this month
            dup_stmt = select(FixedAssetDepreciation).where(
                and_(
                    FixedAssetDepreciation.organization_id == organization_id,
                    FixedAssetDepreciation.asset_id == asset.id,
                    extract("year", FixedAssetDepreciation.period_date) == period_date.year,
                    extract("month", FixedAssetDepreciation.period_date) == period_date.month
                )
            )
            if await self.session.scalar(dup_stmt):
                continue

            res = await self.depreciate_asset(
                organization_id=organization_id,
                asset_id=asset.id,
                period_date=period_date,
                actor_id=actor_id,
                actor_role=actor_role
            )
            if res.depreciation_amount > Decimal("0.00"):
                results.append(res)
                total_dep += res.depreciation_amount

        return BatchDepreciationResponse(
            period_date=period_date,
            total_assets_processed=len(results),
            total_depreciation_amount=total_dep,
            results=results
        )

    async def dispose_asset(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
        disposal_date: date,
        disposal_price: Decimal = Decimal("0.00"),
        actor_id: Optional[uuid.UUID] = None
    ) -> FixedAsset:
        asset = await self.get_asset(organization_id, asset_id)
        if asset.status == AssetStatus.DISPOSED:
            raise InvariantViolationException("Aset sudah dalam status DIJUAL / DIHAPUS (DISPOSED).")

        old_status = asset.status
        asset.status = AssetStatus.DISPOSED
        await self.session.flush()

        audit = AuditService(self.session)
        await audit.log_event(
            organization_id=organization_id,
            entity_name="FIXED_ASSET",
            entity_id=asset.id,
            action="DISPOSE",
            actor_id=actor_id,
            new_values={
                "old_status": old_status.value,
                "new_status": asset.status.value,
                "disposal_date": str(disposal_date),
                "disposal_price": str(disposal_price),
                "net_book_value_at_disposal": str(asset.net_book_value)
            }
        )

        return asset
