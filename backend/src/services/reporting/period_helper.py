from datetime import date, timedelta
import calendar
from typing import Tuple
from src.schemas.reporting import ReportPeriodType


def resolve_report_dates(
    period_type: ReportPeriodType,
    start_date: date | None = None,
    end_date: date | None = None,
    as_of_date: date | None = None,
) -> Tuple[date, date]:
    """
    Resolves start_date and end_date based on period type or defaults.
    """
    today = date.today()

    if as_of_date:
        # Default start of year to as_of_date
        return date(as_of_date.year, 1, 1), as_of_date

    if start_date and end_date:
        return start_date, end_date

    if period_type == ReportPeriodType.MONTHLY:
        # Current month
        first_day = date(today.year, today.month, 1)
        last_day_num = calendar.monthrange(today.year, today.month)[1]
        last_day = date(today.year, today.month, last_day_num)
        return first_day, last_day

    elif period_type == ReportPeriodType.QUARTERLY:
        # Current quarter
        quarter = (today.month - 1) // 3 + 1
        first_month = (quarter - 1) * 3 + 1
        last_month = first_month + 2
        first_day = date(today.year, first_month, 1)
        last_day_num = calendar.monthrange(today.year, last_month)[1]
        last_day = date(today.year, last_month, last_day_num)
        return first_day, last_day

    elif period_type == ReportPeriodType.YEARLY:
        return date(today.year, 1, 1), date(today.year, 12, 31)

    return date(today.year, today.month, 1), today


def format_period_label(start_date: date, end_date: date) -> str:
    """
    Formats standard Indonesian period label.
    """
    month_names = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]
    if start_date.day == 1 and end_date.day == calendar.monthrange(end_date.year, end_date.month)[1] and start_date.month == end_date.month and start_date.year == end_date.year:
        return f"{month_names[start_date.month]} {start_date.year}"
    
    if start_date.day == 1 and start_date.month == 1 and end_date.day == 31 and end_date.month == 12 and start_date.year == end_date.year:
        return f"Tahun {start_date.year}"

    return f"{start_date.strftime('%d/%m/%Y')} — {end_date.strftime('%d/%m/%Y')}"
