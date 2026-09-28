"""Historical volatility and largest-fall calculations."""

import math
import statistics

from engine.series import CoverageError, SeriesError, monthly_returns


def _reject_fx_rate(series):
    if series.basis == "fx_rate":
        raise SeriesError("Exchange-rate series cannot be used for investment risk.")


def volatility(series):
    """Return annualised sample volatility of monthly returns."""
    _reject_fx_rate(series)
    returns = [value for _, value in monthly_returns(series)]
    if len(returns) < 2:
        raise CoverageError("At least two monthly returns are required.")
    return statistics.stdev(returns) * math.sqrt(12.0)


def largest_fall(series):
    """Return details of the largest month-end fall."""
    _reject_fx_rate(series)

    highest_value = series.values[0]
    highest_index = 0
    max_drawdown = 0.0
    peak_index = None
    trough_index = None

    for index, value in enumerate(series.values):
        if value >= highest_value:
            highest_value = value
            highest_index = index

        drawdown = value / highest_value - 1.0
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            peak_index = highest_index
            trough_index = index

    drawdown_at_end = series.values[-1] / highest_value - 1.0

    if trough_index is None:
        return {
            "max_drawdown": 0.0,
            "peak_month": None,
            "trough_month": None,
            "recovery_month": None,
            "recovered": None,
            "months_peak_to_trough": None,
            "months_trough_to_recovery": None,
            "months_underwater": None,
            "ten_thousand_at_trough": 10000.0,
            "ten_thousand_lost": 0.0,
            "drawdown_at_end": drawdown_at_end,
        }

    peak_value = series.values[peak_index]
    recovery_index = None
    for index in range(trough_index + 1, len(series.values)):
        if series.values[index] >= peak_value:
            recovery_index = index
            break

    recovered = recovery_index is not None
    if recovered:
        recovery_month = series.months[recovery_index]
        months_trough_to_recovery = recovery_index - trough_index
        months_underwater = recovery_index - peak_index
    else:
        recovery_month = None
        months_trough_to_recovery = None
        months_underwater = len(series.values) - 1 - peak_index

    return {
        "max_drawdown": max_drawdown,
        "peak_month": series.months[peak_index],
        "trough_month": series.months[trough_index],
        "recovery_month": recovery_month,
        "recovered": recovered,
        "months_peak_to_trough": trough_index - peak_index,
        "months_trough_to_recovery": months_trough_to_recovery,
        "months_underwater": months_underwater,
        "ten_thousand_at_trough": 10000.0 * (1.0 + max_drawdown),
        "ten_thousand_lost": 10000.0 * -max_drawdown,
        "drawdown_at_end": drawdown_at_end,
    }
