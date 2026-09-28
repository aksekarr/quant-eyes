"""Assemble and check the engine's derived results."""

import math

from engine.currency import currency_split, to_gbp
from engine.portfolio import blend_comparison, correlation, rolling_correlation
from engine.risk import largest_fall, volatility
from engine.series import CoverageError, SeriesError, annualise, common_window, period_return
from engine.windows import STRESS_WINDOWS, holding_periods, stress_windows


METHOD_VERSION = "1.0"


class OutputError(Exception):
    """Raised when a result contains a forbidden shape or value."""


def check_output(value):
    """Accept named results containing only permitted values and stress windows."""
    active_groups = set()

    def check_group(group):
        if type(group) is not dict:
            raise OutputError("Output groups must be dictionaries.")
        if id(group) in active_groups:
            raise OutputError("Output groups must not contain cycles.")
        active_groups.add(id(group))

        for key, item in group.items():
            if type(key) is not str:
                raise OutputError("Output keys must be strings.")
            if item is None or type(item) in (str, bool, int):
                continue
            if type(item) is float:
                if not math.isfinite(item):
                    raise OutputError("Output numbers must be finite.")
            elif type(item) is dict:
                check_group(item)
            elif type(item) is list and key == "stress_windows" and len(item) == 3:
                for window in item:
                    check_group(window)
            else:
                raise OutputError("Output contains a forbidden value or list.")

        active_groups.remove(id(group))

    check_group(value)


def _covered(calculate, *args, **kwargs):
    """Return an empty result when a calculation lacks coverage."""
    try:
        return calculate(*args, **kwargs)
    except CoverageError:
        return None


def _profile(series):
    """Collect the measurements for one series over all its months."""
    start = series.first_month
    end = series.last_month
    months = len(series.months) - 1
    total_return = _covered(period_return, series, start, end)
    return {
        "start": start,
        "end": end,
        "months": months,
        "total_return": total_return,
        "annualised_return": (
            _covered(annualise, total_return, months)
            if months >= 12 and total_return is not None else None
        ),
        "volatility": _covered(volatility, series),
        "largest_fall": _covered(largest_fall, series),
        "stress_windows": _covered(stress_windows, series),
        "holding_periods": {
            "1_year": _covered(holding_periods, series, 12),
            "3_years": _covered(holding_periods, series, 36),
            "5_years": _covered(holding_periods, series, 60),
        },
    }


def _side_by_side(asset, tracker):
    """Collect profiles and comparisons over the common months."""
    common_asset, common_tracker = common_window(asset, tracker)
    return {
        "asset": _profile(common_asset),
        "tracker": _profile(common_tracker),
        "correlation": _covered(correlation, common_asset, common_tracker),
        "rolling_correlation_36": _covered(
            rolling_correlation, common_asset, common_tracker, 36
        ),
        "blend_90_10": _covered(
            blend_comparison, common_tracker, common_asset, asset_weight=0.1
        ),
    }


def _currency(asset, fx, pound_asset):
    """Collect currency splits over pound history and fixed stress windows."""
    full_history = None
    if pound_asset is not None:
        start = pound_asset.first_month
        end = pound_asset.last_month
        split = _covered(currency_split, asset, fx, start, end)
        if split is not None:
            full_history = {"start": start, "end": end, **split}

    windows = []
    for window, start, end in STRESS_WINDOWS:
        split = _covered(currency_split, asset, fx, start, end)
        windows.append(
            {
                "window": window,
                "start": start,
                "end": end,
                "covered": split is not None,
                **(split if split is not None else {
                    "local_return": None,
                    "currency_return": None,
                    "gbp_return": None,
                }),
            }
        )

    return {"full_history": full_history, "stress_windows": windows}


def analyse(asset, tracker, fx=None):
    """Return checked asset, tracker and currency results in pounds."""
    if tracker.currency != "GBP" or tracker.basis != "total_return":
        raise SeriesError("Tracker must have GBP currency and total_return basis.")
    if asset.basis != "total_return":
        raise SeriesError("Asset must have total_return basis.")
    if asset.currency not in ("GBP", "USD"):
        raise SeriesError("Asset must have GBP or USD currency.")

    if asset.currency == "USD":
        if fx is None:
            raise ValueError("A dollar asset requires an exchange-rate series.")
        pound_asset = _covered(to_gbp, asset, fx)
    else:
        if fx is not None:
            raise ValueError("A pound asset must not receive an exchange-rate series.")
        pound_asset = asset

    result = {
        "method_version": METHOD_VERSION,
        "asset_currency": asset.currency,
        "own": _profile(pound_asset) if pound_asset is not None else None,
        "side_by_side": (
            _covered(_side_by_side, pound_asset, tracker)
            if pound_asset is not None else None
        ),
        "currency": _currency(asset, fx, pound_asset) if asset.currency == "USD" else None,
    }
    check_output(result)
    return result
