"""Fixed card text and rounded claims for methodology section 12."""

import math

from engine.series import _month_parts
from words.cards import (
    WordsError,
    _WINDOW_NAMES,
    _formatted,
    _identifier,
    _month,
    _required,
    _rounded,
    _windows,
    month_name,
    percent_display,
)


_FIXED_TEXT = {
    "correlation": (
        "Correlation says how consistently the monthly moves lined up, not how "
        "big they were. A low figure is not protection."
    ),
    "costs": "Before fees, trading costs and tax.",
    "held": (
        "The tracker already holds these shares, so the 10% adds to a holding "
        "it already has."
    ),
    "multiply": (
        "The two parts multiply rather than add, so they never simply add up "
        "to the figure in pounds."
    ),
    "dollars_inside": (
        "It is priced in pounds, but what it holds is priced in dollars, so "
        "part of its return in pounds comes from the pound against the dollar. "
        "With only a price in pounds, that part can't be separated out."
    ),
    "pounds_only": (
        "It is priced in pounds, so there is no separate currency effect to show."
    ),
    "share": (
        "A single company's shares can fall a long way and stay down, and the "
        "company can fail."
    ),
    "etf": (
        "A fund's value moves with what it holds: bond prices, for example, "
        "fall when interest rates rise. Its market price can differ slightly "
        "from the value of its holdings, and its running charges are already "
        "inside these figures."
    ),
    "etc": (
        "This is an exchange-traded commodity: a security backed by metal held "
        "in a vault, not the metal itself. It pays no income, and you rely on "
        "the issuer and on the custodian holding the metal."
    ),
    "cryptocurrency": (
        "It is not issued or backed by a government or a company, and it pays "
        "no income. Its price can move a long way in days, it trades around "
        "the clock, and holdings can be lost to theft or lost keys. Its "
        "history here starts at the end of {own_start}, so it covers fewer "
        "market conditions than the others."
    ),
    "common": (
        "These are past results in pounds, measured at month-ends, before "
        "platform fees, trading costs and tax. Past behaviour does not "
        "predict future results."
    ),
}


def correlation_display(value):
    """Round a ratio once to two places, preserving a true minus sign."""
    rounded = _rounded(value, scale=0, exponent=-2)
    number = float(rounded)
    if not math.isfinite(number):
        raise ValueError("Correlation must be finite.")
    return {"value": number, "text": "{:.2f}".format(rounded).replace("-", "−")}


def signed_percent_display(value):
    """Use section 11 percentage rounding, adding a minus only below zero."""
    rendered = percent_display(value)
    if rendered["points"] < 0:
        rendered["text"] = "−" + rendered["text"]
    return rendered


def _sentence(text, *claims):
    return {"text": text, "claims": [claim["id"] for claim in claims]}


def _movement(claim):
    direction = claim["direction"]
    if claim["series"] == "currency":
        word = {"up": "rose", "down": "fell", "flat": "was unchanged"}[direction]
    else:
        word = "unchanged" if direction == "flat" else direction
    if direction == "flat":
        return "{} ({})".format(word, claim["display"])
    return "{} {}".format(word, claim["display"])


def build_cards_567(document, facts):
    """Build cards 5–7 using only the fields listed in section 12.6."""
    fact_fields = ("held_by_tracker", "priced_in_pounds_holds_dollars")
    for field in fact_fields:
        if type(_required(facts, field)) is not bool:
            raise WordsError("Invalid field: {}.".format(field))
    if set(facts) != set(fact_fields):
        raise WordsError("Unexpected field in facts.")

    instruments = {
        "asset": _identifier(document, "instrument"),
        "tracker": _identifier(document, "benchmark"),
    }
    identity = _required(_required(document, "instrument"), "identity")
    instrument_type = _required(identity, "type")
    if instrument_type not in ("share", "etf", "etc", "cryptocurrency"):
        raise WordsError("Invalid field: identity.type.")
    results = _required(document, "results")
    own_start = _month(_required(results, "own"), "start")
    side = _required(results, "side_by_side")
    asset = _required(side, "asset")
    common_start, common_end = _month(asset, "start"), _month(asset, "end")
    # Empty currency results mean a pound asset; an absent field is an error.
    if not isinstance(results, dict) or "currency" not in results:
        raise WordsError("Missing field: currency.")
    currency = results["currency"]
    if currency is not None and facts["priced_in_pounds_holds_dollars"]:
        raise WordsError("Contradictory field: priced_in_pounds_holds_dollars.")
    comparison = _required(side, "blend_90_10")
    if _required(comparison, "asset_weight") != 0.1:
        raise WordsError("Invalid field: asset_weight.")
    if _required(comparison, "rebalance") != "december":
        raise WordsError("Invalid field: rebalance.")
    mix_start, mix_end = _month(comparison, "start"), _month(comparison, "end")
    claims = []

    def claim(
        claim_id, series, metric, start, end, record, field,
        formatter=percent_display, unit="percent", claim_currency="GBP",
    ):
        rendered = _formatted(record, field, formatter)
        value = rendered["value" if unit == "ratio" else "points"]
        direction = None
        if unit == "percent" and metric != "volatility":
            direction = "down" if value < 0 else "up" if value > 0 else "flat"
        result = {
            "id": claim_id, "series": series,
            "instrument": instruments["tracker" if series == "tracker" else "asset"],
            "metric": metric, "period_start": start, "period_end": end,
            "unit": unit, "currency": claim_currency, "value": value,
            "direction": direction, "display": rendered["text"],
            "kind": "illustration" if series == "mix" else "observed",
        }
        claims.append(result)
        return result

    correlation = claim(
        "next.correlation", "asset", "correlation", common_start, common_end,
        side, "correlation", correlation_display, "ratio", None,
    )
    next_sentences = [_sentence(
        "Its correlation with the tracker was {}, measured on monthly returns "
        "in pounds from the end of {} to the end of {}: 1 would mean always "
        "moving in step, 0 no pattern, and −1 always opposite.".format(
            correlation["display"], month_name(common_start), month_name(common_end)
        ), correlation,
    )]
    rolling = _required(side, "rolling_correlation_36")
    rolling_claims = []
    for field in ("lowest", "highest"):
        end = _month(rolling, field + "_end")
        year, month = _month_parts(end)
        # A run of 36 monthly returns begins at the month-end three years earlier.
        start = "{:04d}-{:02d}".format(year - 3, month)
        rolling_claims.append(claim(
            "next.rolling_" + field, "asset", "rolling_correlation_36_" + field,
            start, end, rolling, field, correlation_display, "ratio", None,
        ))
    lowest, highest = rolling_claims
    next_sentences.append(_sentence(
        "Measured over each 36-month stretch, it ranged from {} (the 36 months "
        "to the end of {}) to {} (the 36 months to the end of {}).".format(
            lowest["display"], month_name(lowest["period_end"]),
            highest["display"], month_name(highest["period_end"]),
        ), lowest, highest,
    ))
    next_sentences.append(_sentence(_FIXED_TEXT["correlation"]))

    comparison_claims = {}
    for suffix, metric, field, formatter in (
        ("annualised", "annualised_return", "annualised_return", signed_percent_display),
        ("volatility", "volatility", "volatility", percent_display),
        ("fall", "largest_fall", "max_drawdown", percent_display),
    ):
        for series, profile_name in (("mix", "blend"), ("tracker", "tracker")):
            record = _required(comparison, profile_name)
            if metric == "largest_fall":
                record = _required(record, "largest_fall")
            name = series + "_" + suffix
            comparison_claims[name] = claim(
                "next." + name, series, metric, mix_start, mix_end,
                record, field, formatter,
            )
    mix_return = comparison_claims["mix_annualised"]
    tracker_return = comparison_claims["tracker_annualised"]
    next_sentences.append(_sentence(
        "As an illustration, not a recommendation: from the end of {} to the "
        "end of {}, a mix of 90% in the tracker and 10% in this investment, "
        "reset to 90/10 at the end of every December, returned {} a year, "
        "against {} a year for the tracker alone.".format(
            month_name(mix_start), month_name(mix_end),
            mix_return["display"], tracker_return["display"],
        ), mix_return, tracker_return,
    ))
    risk_claims = [comparison_claims[name] for name in (
        "mix_volatility", "tracker_volatility", "mix_fall", "tracker_fall"
    )]
    next_sentences.append(_sentence(
        "The mix's volatility was {} against the tracker's {}, and its largest "
        "fall at month-end was {} against {}.".format(
            *(item["display"] for item in risk_claims)
        ), *risk_claims,
    ))
    next_sentences.append(_sentence(_FIXED_TEXT["costs"]))
    if facts["held_by_tracker"]:
        next_sentences.append(_sentence(_FIXED_TEXT["held"]))

    def currency_claims(record, prefix):
        start, end = _month(record, "start"), _month(record, "end")
        return [claim(
            prefix + "." + part, series, part + "_return", start, end,
            record, part + "_return", claim_currency=claim_currency,
        ) for part, series, claim_currency in (
            ("local", "asset", "USD"),
            ("currency", "currency", None),
            ("gbp", "asset", "GBP"),
        )]

    if currency is None:
        key = "dollars_inside" if facts["priced_in_pounds_holds_dollars"] else "pounds_only"
        pound = [_sentence(_FIXED_TEXT[key])]
    else:
        full_history = _required(currency, "full_history")
        local, dollar, gbp = currency_claims(full_history, "pound")
        pound = [_sentence(
            "From the end of {} to the end of {}: {} in dollars, and the dollar "
            "{} against the pound, so in pounds it was {}.".format(
                month_name(local["period_start"]), month_name(local["period_end"]),
                _movement(local), _movement(dollar), _movement(gbp),
            ), local, dollar, gbp,
        )]
        windows = _windows(currency)
        for name, title in _WINDOW_NAMES.items():
            window = windows[name]
            try:
                covered = _required(window, "covered")
                if type(covered) is not bool:
                    raise WordsError("Invalid field: covered.")
                if not covered:
                    continue
                local, dollar, gbp = currency_claims(window, "pound." + name)
                pound.append(_sentence(
                    "{}: {} in dollars, the dollar {}, so {} in pounds.".format(
                        title, _movement(local), _movement(dollar), _movement(gbp)
                    ), local, dollar, gbp,
                ))
            except WordsError as error:
                raise WordsError("stress_windows.{}: {}".format(name, error)) from None
        pound.append(_sentence(_FIXED_TEXT["multiply"]))

    limits = [
        _sentence(_FIXED_TEXT[instrument_type].format(own_start=month_name(own_start))),
        _sentence(_FIXED_TEXT["common"]),
    ]
    return {
        "cards": [
            {"id": "next", "title": "What does it do next to the tracker?", "sentences": next_sentences},
            {"id": "pound", "title": "How much of it was the pound?", "sentences": pound},
            {"id": "limits", "title": "What these numbers don't capture", "sentences": limits},
        ],
        "claims": claims,
    }
