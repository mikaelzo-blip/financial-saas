"""Authenticated application-side report adapter; providers see only its DTOs."""
from src.services.reporting.pl_service import ProfitLossService
from src.services.reporting.balance_sheet_service import BalanceSheetService
from src.services.reporting.cash_flow_service import CashFlowService
from src.services.reporting.ar_aging_service import ARAgingService
from src.services.reporting.ap_aging_service import APAgingService
from src.services.reporting.integrity_service import IntegrityService
from src.services.ai.grounding_service import GroundingService


async def executive_grounding(db, org, start, end):
    # AsyncSession is not safe for concurrent queries. All calculations remain
    # in existing Feature 004 services; never copied into the AI layer.
    dtos = {
        'pl': await ProfitLossService.get_profit_and_loss(db, org, start, end),
        'bs': await BalanceSheetService.get_balance_sheet(db, org, end),
        'cf': await CashFlowService.get_cash_flow(db, org, start, end),
        'ar': await ARAgingService.get_ar_aging(db, org, end),
        'ap': await APAgingService.get_ap_aging(db, org, end),
        'integrity': await IntegrityService.run_diagnostics(db, org, end),
    }
    return GroundingService.build(org, start, end, dtos)

async def executive_comparison_grounding(db, org, start, end, previous_start, previous_end):
    current = await executive_grounding(db, org, start, end)
    previous = await executive_grounding(db, org, previous_start, previous_end)
    current.factual_metrics.update({'previous_' + key: value for key, value in previous.factual_metrics.items()})
    current.metric_sources.update({'previous_' + key: value for key, value in previous.metric_sources.items()})
    current.source_references.extend('Previous ' + source for source in previous.source_references)
    current.source_references.sort()
    return current
