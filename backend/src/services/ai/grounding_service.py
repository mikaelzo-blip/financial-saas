"""Copy authoritative DTO fields; do not reproduce journal/report calculations."""
import hashlib
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field
from src.schemas import reporting as reports


class GroundedPayload(BaseModel):
    organization_id: UUID
    start_date: date
    end_date: date
    insight_type: str = 'EXECUTIVE_SUMMARY'
    project_id: UUID | None = None
    factual_metrics: dict[str, Decimal | None] = Field(default_factory=dict)
    metric_sources: dict[str, str] = Field(default_factory=dict)
    source_references: list[str] = Field(default_factory=list)
    integrity_valid: bool = True
    evidence_labels: dict[str, str] = Field(default_factory=dict)

    def cache_key(self) -> str:
        # Generation timestamps and provider latency are deliberately excluded.
        content = json.dumps(self.model_dump(mode='json'), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(('insights-v1:' + content).encode()).hexdigest()


# Explicit source allowlist: ORM instances, arbitrary dicts and document text
# cannot enter the provider through this boundary.
SOURCES = {
    'pl': (reports.ProfitLossReportResponse, {'revenue': 'revenue_section.subtotal', 'gross_profit': 'gross_profit', 'gross_margin_percentage': 'gross_margin_percentage', 'operating_profit': 'operating_profit', 'net_profit': 'net_profit', 'operating_expenses': 'operating_expenses_section.subtotal'}),
    'bs': (reports.BalanceSheetReportResponse, {'total_assets': 'total_assets', 'total_liabilities': 'total_liabilities', 'total_equity': 'total_equity'}),
    'cf': (reports.CashFlowReportResponse, {'cash_balance': 'closing_cash_balance', 'net_cash_change': 'net_cash_change', 'net_operating_cash': 'net_operating_cash'}),
    'ar': (reports.ARAgingReportResponse, {'ar_total': 'summary.total', 'ar_over_90': 'summary.days_over_90', 'ar_61_90': 'summary.days_61_90'}),
    'ap': (reports.APAgingReportResponse, {'ap_total': 'summary.total', 'ap_over_90': 'summary.days_over_90'}),
    'project': (reports.ProjectProfitabilityReportResponse, {'contract_value': 'revised_contract_value', 'revenue_recognized': 'revenue_recognized', 'project_cost': 'total_project_cost', 'project_profit': 'gross_profit', 'project_margin': 'gross_margin_percentage'}),
    'project_cash': (reports.ProjectCashPositionReportResponse, {'invoiced_amount': 'invoiced_amount', 'cash_received': 'cash_received', 'cash_spent': 'cash_spent', 'project_cash_position': 'net_cash_position', 'project_ar': 'receivable_outstanding'}),
    'budget': (reports.BudgetVsActualReportResponse, {'total_budget': 'total_budget', 'budget_actual': 'total_actual', 'budget_variance': 'total_variance'}),
    'dashboard': (reports.DashboardSummaryResponse, {'review_pending': 'review_queue_pending_count', 'cash_runway_months': 'cash_runway_months'}),
    'integrity': (reports.IntegrityReportResponse, {}),
}


class GroundingService:
    @staticmethod
    def build(org: UUID, start: date, end: date, dtos: dict[str, BaseModel], insight_type='EXECUTIVE_SUMMARY', project_id=None) -> GroundedPayload:
        payload = GroundedPayload(organization_id=org, start_date=start, end_date=end, insight_type=insight_type, project_id=project_id)
        for key, dto in dtos.items():
            previous = key.startswith('previous_')
            source_key = key.removeprefix('previous_')
            if source_key not in SOURCES or type(dto) is not SOURCES[source_key][0]:
                raise ValueError('Unapproved reporting DTO')
            cls, mapping = SOURCES[source_key]
            prefix = 'previous_' if previous else ''
            source_name = cls.__name__ + (' (previous period)' if previous else '')
            payload.source_references.append(source_name)
            for name, path in mapping.items():
                value = dto
                for part in path.split('.'):
                    value = getattr(value, part)
                if source_key == 'budget' and not dto.has_budget:
                    value = None
                if value is not None and (isinstance(value, bool) or not isinstance(value, (Decimal, int))):
                    raise ValueError('Financial values must be exact')
                payload.factual_metrics[prefix + name] = Decimal(value) if value is not None else None
                payload.metric_sources[prefix + name] = source_name + '.' + path
            if getattr(dto, 'integrity_status', 'VALID') != 'VALID' or getattr(dto, 'overall_status', 'VALID') != 'VALID':
                payload.integrity_valid = False
            if source_key == 'project':
                for line in dto.cost_breakdown:
                    name = prefix + 'cost_' + line.cost_category
                    payload.factual_metrics[name] = line.amount
                    payload.metric_sources[name] = source_name + '.cost_breakdown.' + line.cost_category
            if source_key == 'ar':
                for index, invoice in enumerate(sorted(dto.invoices, key=lambda item: item.days_overdue, reverse=True)[:10]):
                    key_prefix = f'ar_invoice_{index}_'
                    payload.factual_metrics[key_prefix + 'outstanding'] = invoice.outstanding_amount
                    payload.factual_metrics[key_prefix + 'days_overdue'] = Decimal(invoice.days_overdue)
                    payload.metric_sources[key_prefix + 'outstanding'] = source_name + f'.invoices[{index}].outstanding_amount'
                    payload.metric_sources[key_prefix + 'days_overdue'] = source_name + f'.invoices[{index}].days_overdue'
                    from src.services.ai.sanitizer import sanitize_text
                    payload.evidence_labels[key_prefix + 'label'] = sanitize_text(invoice.invoice_number)
        if insight_type == 'EXECUTIVE_SUMMARY':
            for name in ('revenue', 'net_profit', 'cash_balance'):
                payload.factual_metrics.setdefault(name, None)
        payload.source_references.sort()
        return payload
