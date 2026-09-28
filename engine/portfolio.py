"""Correlation and blended-portfolio calculations."""

import math
from numbers import Real

from engine.risk import largest_fall, volatility
from engine.series import (
    CoverageError,
    MonthlySeries,
    SeriesError,
    annualise,
    common_window,
    monthly_returns,
    period_return,
    reject_fx_rate,
)


def _validate_labels(asset, tracker):
    """Require comparable investment-series labels."""
    reject_fx_rate(asset)
    reject_fx_rate(tracker)
    if asset.currency != tracker.currency:
        raise SeriesError("Series must use the same currency.")
    if asset.basis != tracker.basis:
        raise SeriesError("Series must use the same basis.")


def _pearson(asset_values, tracker_values):
    """Return Pearson correlation for two equal-length value lists."""
    if min(asset_values) == max(asset_values):
        raise SeriesError("Correlation is undefined without variation in both series.")
    if min(tracker_values) == max(tracker_values):
        raise SeriesError("Correlation is undefined without variation in both series.")

    asset_mean = sum(asset_values) / len(asset_values)
    tracker_mean = sum(tracker_values) / len(tracker_values)
    asset_deviations = [value - asset_mean for value in asset_values]
    tracker_deviations = [value - tracker_mean for value in tracker_values]
    numerator = sum(
        asset_deviation * tracker_deviation
        for asset_deviation, tracker_deviation in zip(
            asset_deviations, tracker_deviations
        )
    )
    asset_variation = sum(value * value for value in asset_deviations)
    tracker_variation = sum(value * value for value in tracker_deviations)

    if asset_variation == 0.0 or tracker_variation == 0.0:
        raise SeriesError("Correlation is undefined without variation in both series.")
    return numerator / math.sqrt(asset_variation * tracker_variation)


def correlation(asset, tracker):
    """Return Pearson correlation of common monthly returns."""
    _validate_labels(asset, tracker)
    common_asset, common_tracker = common_window(asset, tracker)
    asset_values = [value for _, value in monthly_returns(common_asset)]
    tracker_values = [value for _, value in monthly_returns(common_tracker)]

    if len(asset_values) < 3:
        raise CoverageError("At least three common monthly returns are required.")
    return _pearson(asset_values, tracker_values)


def rolling_correlation(asset, tracker, months):
    """Return the range of correlations across rolling monthly runs."""
    _validate_labels(asset, tracker)
    if isinstance(months, bool) or not isinstance(months, int) or months < 3:
        raise ValueError("Months must be a whole number of at least three.")

    common_asset, common_tracker = common_window(asset, tracker)
    asset_returns = monthly_returns(common_asset)
    tracker_returns = monthly_returns(common_tracker)
    if len(asset_returns) < months:
        raise CoverageError("There are too few common monthly returns for the run.")

    runs = []
    for start_index in range(len(asset_returns) - months + 1):
        end_index = start_index + months
        asset_values = [value for _, value in asset_returns[start_index:end_index]]
        tracker_values = [value for _, value in tracker_returns[start_index:end_index]]
        runs.append(
            {
                "value": _pearson(asset_values, tracker_values),
                "end": asset_returns[end_index - 1][0],
            }
        )

    lowest = min(runs, key=lambda run: run["value"])
    highest = max(runs, key=lambda run: run["value"])
    return {
        "windows": len(runs),
        "lowest": lowest["value"],
        "lowest_end": lowest["end"],
        "highest": highest["value"],
        "highest_end": highest["end"],
    }


def _summary(series, months):
    """Return the required performance and risk summary."""
    total_return = period_return(series, series.first_month, series.last_month)
    return {
        "total_return": total_return,
        "annualised_return": annualise(total_return, months) if months >= 12 else None,
        "volatility": volatility(series),
        "largest_fall": largest_fall(series),
    }


def blend_comparison(tracker, asset, asset_weight):
    """Compare a tracker with a December-rebalanced tracker-and-asset blend."""
    _validate_labels(asset, tracker)
    if (
        isinstance(asset_weight, bool)
        or not isinstance(asset_weight, Real)
        or not math.isfinite(asset_weight)
        or asset_weight < 0.0
        or asset_weight > 1.0
    ):
        raise ValueError("Asset weight must be a finite number from zero to one.")

    common_tracker, common_asset = common_window(tracker, asset)
    tracker_part = 1.0 - asset_weight
    asset_part = asset_weight
    blend_pairs = [(common_tracker.first_month, tracker_part + asset_part)]
    tracker_returns = monthly_returns(common_tracker)
    asset_returns = monthly_returns(common_asset)

    for (month, tracker_return), (_, asset_return) in zip(
        tracker_returns, asset_returns
    ):
        tracker_part *= 1.0 + tracker_return
        asset_part *= 1.0 + asset_return
        blend_value = tracker_part + asset_part
        blend_pairs.append((month, blend_value))
        if month.endswith("-12"):
            tracker_part = blend_value * (1.0 - asset_weight)
            asset_part = blend_value * asset_weight

    blend = MonthlySeries.from_pairs(
        "Blend",
        common_tracker.currency,
        common_tracker.basis,
        blend_pairs,
    )
    months = len(common_tracker.months) - 1
    return {
        "start": common_tracker.first_month,
        "end": common_tracker.last_month,
        "months": months,
        "asset_weight": asset_weight,
        "rebalance": "december",
        "tracker": _summary(common_tracker, months),
        "blend": _summary(blend, months),
    }
