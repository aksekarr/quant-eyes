"""Currency conversion and return decomposition for US-dollar assets."""

from engine.series import (
    CoverageError,
    MonthlySeries,
    SeriesError,
    common_window,
    period_return,
)


def _validate_labels(asset, fx):
    """Require a non-rate USD asset and a USD exchange-rate series."""
    if asset.currency != "USD" or asset.basis == "fx_rate":
        raise SeriesError("Asset must be a USD series and must not be an exchange rate.")
    if fx.basis != "fx_rate" or fx.currency != "USD":
        raise SeriesError("Exchange rate must have fx_rate basis and USD currency.")


def to_gbp(asset, fx):
    """Divide each shared USD asset value by dollars per pound and label the result GBP."""
    _validate_labels(asset, fx)
    aligned_asset, aligned_fx = common_window(asset, fx)
    pairs = [
        (month, asset_value / fx_value)
        for month, asset_value, fx_value in zip(
            aligned_asset.months, aligned_asset.values, aligned_fx.values
        )
    ]
    return MonthlySeries.from_pairs(asset.name, "GBP", asset.basis, pairs)


def currency_split(asset, fx, start, end):
    """Return local, currency, and GBP returns between two covered month-ends."""
    _validate_labels(asset, fx)

    local_return = period_return(asset, start, end)
    period_return(fx, start, end)

    start_rate = fx.values[fx.months.index(start)]
    end_rate = fx.values[fx.months.index(end)]
    currency_return = start_rate / end_rate - 1.0

    gbp_series = to_gbp(asset, fx)
    gbp_return = period_return(gbp_series, start, end)

    return {
        "local_return": local_return,
        "currency_return": currency_return,
        "gbp_return": gbp_return,
    }
