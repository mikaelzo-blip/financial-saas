import uuid
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

from src.models.enums import DepreciationMethod, AssetStatus


class FixedAssetBase(BaseModel):
    asset_code: str = Field(..., max_length=50, description="Kode Aset unik")
    asset_name: str = Field(..., max_length=255, description="Nama Aset")
    asset_category: str = Field(..., max_length=100, description="Kategori Aset")
    purchase_date: date = Field(..., description="Tanggal Perolehan / Pembelian")
    available_for_use_date: Optional[date] = Field(None, description="Tanggal Mulai Digunakan")
    purchase_cost: Decimal = Field(..., gt=0, description="Harga Perolehan")
    salvage_value: Decimal = Field(default=Decimal("0.00"), ge=0, description="Nilai Residu")
    useful_life_months: Optional[int] = Field(None, gt=0, description="Masa Manfaat (Bulan)")
    depreciation_method: DepreciationMethod = Field(
        default=DepreciationMethod.STRAIGHT_LINE,
        description="Metode Penyusutan (Default: Garis Lurus)"
    )
    status: Optional[AssetStatus] = Field(default=AssetStatus.ACTIVE, description="Status Aset")
    vendor_id: Optional[uuid.UUID] = Field(None, description="Vendor Penjual")
    document_id: Optional[uuid.UUID] = Field(None, description="Bukti Dokumen Pendukung")

    # Fiscal Depreciation (Optional / Future-Safe)
    fiscal_asset_group: Optional[str] = Field(None, max_length=50, description="Golongan Harta Fiskal (Pajak)")
    fiscal_depreciation_method: Optional[str] = Field(None, max_length=50, description="Metode Fiskal")
    fiscal_useful_life_months: Optional[int] = Field(None, gt=0, description="Masa Manfaat Fiskal")


class FixedAssetCreate(FixedAssetBase):
    override_reason: Optional[str] = Field(None, description="Alasan jika mengubah masa manfaat standar")


class FixedAssetUpdate(BaseModel):
    asset_name: Optional[str] = None
    asset_category: Optional[str] = None
    available_for_use_date: Optional[date] = None
    salvage_value: Optional[Decimal] = None
    useful_life_months: Optional[int] = None
    status: Optional[AssetStatus] = None
    fiscal_asset_group: Optional[str] = None
    fiscal_depreciation_method: Optional[str] = None
    fiscal_useful_life_months: Optional[int] = None
    override_reason: Optional[str] = None


class DepreciationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_date: date
    depreciation_amount: Decimal
    accumulated_after: Decimal
    book_value_after: Decimal
    transaction_id: Optional[uuid.UUID] = None
    journal_entry_id: Optional[uuid.UUID] = None
    created_at: datetime


class FixedAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    asset_code: str
    asset_name: str
    asset_category: str
    purchase_date: date
    available_for_use_date: Optional[date] = None
    effective_available_date: date
    purchase_cost: Decimal
    salvage_value: Decimal
    useful_life_months: int
    depreciation_method: DepreciationMethod
    accumulated_depreciation: Decimal
    net_book_value: Decimal
    depreciable_amount: Decimal
    remaining_depreciable_amount: Decimal
    monthly_depreciation_rate: Decimal
    status: AssetStatus
    vendor_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    fiscal_asset_group: Optional[str] = None
    fiscal_depreciation_method: Optional[str] = None
    fiscal_useful_life_months: Optional[int] = None
    created_at: datetime
    depreciations: List[DepreciationRecordResponse] = []


class DepreciationRunRequest(BaseModel):
    period_date: date = Field(..., description="Tanggal Periode Penyusutan (misal: 2026-02-28)")


class DepreciationRunResult(BaseModel):
    asset_id: uuid.UUID
    asset_code: str
    asset_name: str
    period_date: date
    depreciation_amount: Decimal
    accumulated_depreciation: Decimal
    net_book_value: Decimal
    transaction_id: Optional[uuid.UUID] = None
    journal_entry_id: Optional[uuid.UUID] = None
    journal_entry_number: Optional[str] = None
    status: AssetStatus


class BatchDepreciationResponse(BaseModel):
    period_date: date
    total_assets_processed: int
    total_depreciation_amount: Decimal
    results: List[DepreciationRunResult]


class CapitalizationGuidanceResponse(BaseModel):
    amount: Decimal
    benefit_months: int
    threshold: Decimal = Decimal("5000000.00")
    qualifies_as_fixed_asset: bool
    recommendation: str
    notes: str
