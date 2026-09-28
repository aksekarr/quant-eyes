"""Stress-window and holding-period calculations."""

import statistics

from engine.series import CoverageError, annualise, period_return, reject_fx_rate


STRESS_WINDOWS = (
    ("gfc", "2007-09", "2009-03"),
    ("covid", "2020-01", "2020-03"),
    ("rate_shock", "2021-12", "2022-10"),
)


def stress_windows(series):
    """Return total returns for the three fixed stress windows."""
    reject_fx_rate(series)

    results = []
    for window, start, end in STRESS_WINDOWS:
        covered = start in series.months and end in series.months
        results.append(
            {
                "window": window,
                "start": start,
                "end": end,
                "covered": covered,
                "return": period_return(series, start, end) if covered else None,
            }
        )
    return results


def holding_periods(series, months):
    """Summarise every covered holding period for a whole-year horizon."""
    reject_fx_rate(series)

    if isinstance(months, bool) or not isinstance(months, int):
        raise ValueError("Horizon must be a positive whole number of years in months.")
    if months <= 0 or months % 12 != 0:
        raise ValueError("Horizon must be a positive whole number of years in months.")

    period_count = len(series.values) - months
    if period_count <= 0:
        raise CoverageError("The series has no complete holding period at this horizon.")

    periods = []
    for start_index in range(period_count):
        end_index = start_index + months
        start = series.months[start_index]
        end = series.months[end_index]
        total_return = period_return(series, start, end)
        periods.append(
            {
                "start": start,
                "end": end,
                "return": total_return,
                "annualised": annualise(total_return, months),
            }
        )

    worst = min(periods, key=lambda period: period["return"])
    best = max(periods, key=lambda period: period["return"])
    total_returns = [period["return"] for period in periods]
    annualised_returns = [period["annualised"] for period in periods]
    periods_lost_money = sum(value < 0.0 for value in total_returns)

    return {
        "horizon_months": months,
        "periods": period_count,
        "non_overlapping_periods": (len(series.values) - 1) // months,
        "first_start": periods[0]["start"],
        "last_end": periods[-1]["end"],
        "worst": worst["return"],
        "worst_start": worst["start"],
        "worst_end": worst["end"],
        "median": statistics.median(total_returns),
        "best": best["return"],
        "best_start": best["start"],
        "best_end": best["end"],
        "periods_lost_money": periods_lost_money,
        "share_lost_money": periods_lost_money / period_count,
        "worst_annualised": worst["annualised"],
        "median_annualised": statistics.median(annualised_returns),
        "best_annualised": best["annualised"],
    }
