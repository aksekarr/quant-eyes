"""Pick month-end values from in-memory provider rows (methodology section 7)."""

import calendar
import datetime
import math
import re
from numbers import Real

from engine.series import CoverageError, MonthlySeries, SeriesError, _month_parts


_DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T.+)?")


class ProviderDataError(Exception):
    """Raised when provider rows contain invalid dates or month-end values."""


def last_complete_month(today):
    """Return the month before the supplied date, without consulting a clock."""
    if not isinstance(today, datetime.date) or isinstance(today, datetime.datetime):
        raise ValueError("Today must be a date without a time.")
    if today.month == 1:
        return "{:04d}-12".format(today.year - 1)
    return "{:04d}-{:02d}".format(today.year, today.month - 1)


def _row_date(date_text, row_number):
    """Validate the date as written, ignoring its time and time zone."""
    if not isinstance(date_text, str) or _DATE_PATTERN.fullmatch(date_text) is None:
        raise ProviderDataError("Row {} has an invalid date.".format(row_number))
    try:
        return datetime.date.fromisoformat(date_text[:10])
    except ValueError:
        raise ProviderDataError(
            "Row {} has an invalid calendar date.".format(row_number)
        ) from None


def _month_value(raw_value, month):
    """Convert only a selected value; never include provider values in errors."""
    if isinstance(raw_value, bool) or not isinstance(raw_value, (Real, str)):
        raise ProviderDataError("Month {} has a non-numeric value.".format(month))
    try:
        value = float(raw_value)
    except (OverflowError, TypeError, ValueError):
        raise ProviderDataError(
            "Month {} has an invalid numeric value.".format(month)
        ) from None
    if not math.isfinite(value):
        raise ProviderDataError("Month {} has a non-finite value.".format(month))
    return value


def month_end_pairs(rows, through, start=None):
    """Return the latest dated value per kept month, in ascending month order."""
    # Section 7.5: arguments, all rows, coverage, then each kept month.
    through_parts = _month_parts(through)
    if start is not None and _month_parts(start) >= through_parts:
        raise ValueError("Start month must be earlier than the as-of month.")

    seen_dates = set()
    selected = {}
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ProviderDataError(
                "Row {} must contain one date and one value.".format(row_number)
            )
        day = _row_date(row[0], row_number)
        if day in seen_dates:
            raise ProviderDataError("Duplicate date {}.".format(day.isoformat()))
        seen_dates.add(day)

        month = day.isoformat()[:7]
        if month > through or (start is not None and month < start):
            continue
        if month not in selected or day > selected[month][0]:
            # Retain the row without reading its value until checks are complete.
            selected[month] = (day, row)

    if through not in selected:
        raise CoverageError("As-of month {} has no rows.".format(through))
    if start is not None and start not in selected:
        raise CoverageError("Start month {} has no rows.".format(start))

    pairs = []
    for month in sorted(selected):
        day, row = selected[month]
        last_day = calendar.monthrange(day.year, day.month)[1]
        if day.day < last_day - 6:
            raise ProviderDataError(
                "Month {} has a stale month-end date {}.".format(month, day.isoformat())
            )
        pairs.append((month, _month_value(row[1], month)))
    return pairs


def build_monthly_series(name, currency, basis, rows, through, start=None):
    """Build a series using the engine's existing validation rules."""
    return MonthlySeries.from_pairs(
        name, currency, basis, month_end_pairs(rows, through, start)
    )
