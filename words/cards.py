"""Fixed card text and rounded claims for methodology section 11."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import math
from numbers import Real

from engine.series import _month_parts


_MONTH_NAMES = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
_WINDOW_NAMES = {
    "gfc": "Global financial crisis",
    "covid": "Covid crash",
    "rate_shock": "2022 rate shock",
}
_FIXED_TEXT = {
    "bumpy": (
        "Volatility measures how widely returns swung around their average, up as "
        "well as down. It describes the past, not the future."
    ),
    "worst": (
        "Falls are measured from one month-end to the next, so a fall that "
        "recovered within a month doesn't show. The £10,000 figure applies only "
        "to money invested at the high."
    ),
    "panic": (
        "Each figure compares the start and end of the period. Prices may have "
        "fallen further in between and partly recovered."
    ),
}


class WordsError(Exception):
    """Raised when a document lacks a field needed by a card."""


def _decimal_value(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("Display value must be a finite number.")
    try:
        number = Decimal(repr(value))
    except (InvalidOperation, ValueError):
        raise ValueError("Display value must be a finite number.") from None
    if not number.is_finite():
        raise ValueError("Display value must be a finite number.")
    return number


def _rounded(value, scale, exponent):
    number = _decimal_value(value)
    sign, digits, power = number.as_tuple()
    # Shift the exponent exactly: Decimal multiplication could itself round
    # under the active context, before the one permitted display rounding.
    scaled = Decimal((sign, digits, power + scale))
    with localcontext() as context:
        context.prec = max(len(digits), scaled.adjusted() - exponent + 2, 1)
        rounded = scaled.quantize(
            Decimal((0, (1,), exponent)), rounding=ROUND_HALF_UP
        )
    return rounded.copy_abs() if rounded.is_zero() else rounded


def percent_display(value):
    """Return signed percentage points and unsigned text, rounded once."""
    rounded = _rounded(value, scale=2, exponent=-1)
    points = float(rounded)
    if not math.isfinite(points):
        raise ValueError("Percentage points must be finite.")
    return {"points": points, "text": "{:,.1f}%".format(rounded.copy_abs())}


def pounds_display(value):
    """Round pounds to the nearest ten, with halfway values away from zero."""
    rounded = int(_rounded(value, scale=0, exponent=1))
    return {"rounded": rounded, "text": "£{:,}".format(rounded)}


def months_display(n):
    """Display an integer month count with its singular or plural unit."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise ValueError("Months must be given as an integer.")
    return "{} {}".format(n, "month" if n == 1 else "months")


def month_name(month):
    """Display an engine month key using its three-letter English month."""
    year, number = _month_parts(month)
    return "{} {:04d}".format(_MONTH_NAMES[number - 1], year)


def _required(record, field):
    if not isinstance(record, dict) or field not in record or record[field] is None:
        raise WordsError("Missing or empty field: {}.".format(field))
    return record[field]


def _formatted(record, field, formatter):
    value = _required(record, field)
    try:
        return formatter(value)
    except ValueError:
        raise WordsError("Invalid field: {}.".format(field)) from None


def _month(record, field):
    _formatted(record, field, month_name)
    return record[field]


def _identifier(document, field):
    value = _required(_required(document, field), "id")
    if not isinstance(value, str) or not value.strip():
        raise WordsError("Missing or empty field: {}.id.".format(field))
    return value


def _windows(profile):
    windows = _required(profile, "stress_windows")
    if not isinstance(windows, list):
        raise WordsError("Invalid field: stress_windows.")
    indexed = {}
    for window in windows:
        name = _required(window, "window")
        if not isinstance(name, str):
            raise WordsError("Invalid field: stress_windows.window.")
        if name not in _WINDOW_NAMES:
            raise WordsError("Unknown stress_windows.window: {}.".format(name))
        if name in indexed:
            raise WordsError("Duplicate stress_windows.window: {}.".format(name))
        indexed[name] = window
    for name in _WINDOW_NAMES:
        if name not in indexed:
            raise WordsError("Missing stress_windows.window: {}.".format(name))
    return indexed


def build_cards(document):
    """Build cards 1–3 using only the fields listed in section 11.6."""
    instruments = {
        "asset": _identifier(document, "instrument"),
        "tracker": _identifier(document, "benchmark"),
    }
    results = _required(document, "results")
    own = _required(results, "own")
    side = _required(results, "side_by_side")
    asset = _required(side, "asset")
    tracker = _required(side, "tracker")
    own_start, own_end = _month(own, "start"), _month(own, "end")
    common_start = _month(asset, "start")
    tracker_start, tracker_end = _month(tracker, "start"), _month(tracker, "end")
    claims = []

    def claim(claim_id, series, metric, start, end, unit, value, display):
        direction = None
        if unit == "percent" and metric != "volatility":
            direction = "down" if value < 0 else "up" if value > 0 else "flat"
        result = {
            "id": claim_id, "series": series, "instrument": instruments[series],
            "metric": metric, "period_start": start, "period_end": end,
            "unit": unit, "currency": None if unit == "months" else "GBP",
            "value": value, "direction": direction, "display": display,
            "kind": "observed",
        }
        claims.append(result)
        return result

    def percent_claim(claim_id, series, metric, start, end, record, field):
        rendered = _formatted(record, field, percent_display)
        return claim(
            claim_id, series, metric, start, end, "percent",
            rendered["points"], rendered["text"],
        )

    def months_claim(claim_id, metric, start, end, record):
        display = _formatted(record, metric, months_display)
        return claim(
            claim_id, "asset", metric, start, end, "months", record[metric], display
        )

    def sentence(text, *used_claims):
        return {"text": text, "claims": [item["id"] for item in used_claims]}

    own_volatility = percent_claim(
        "bumpy.volatility", "asset", "volatility", own_start, own_end,
        own, "volatility",
    )
    bumpy = [sentence(
        "Its volatility was {} a year, measured on monthly returns in pounds "
        "from the end of {} to the end of {}.".format(
            own_volatility["display"], month_name(own_start), month_name(own_end)
        ), own_volatility,
    )]
    longer_history = own_start < common_start
    if longer_history:
        common_end = _month(asset, "end")
        common_volatility = percent_claim(
            "bumpy.volatility_common", "asset", "volatility", common_start,
            common_end, asset, "volatility",
        )
    tracker_volatility = percent_claim(
        "bumpy.tracker_volatility", "tracker", "volatility", tracker_start,
        tracker_end, tracker, "volatility",
    )
    if longer_history:
        bumpy.append(sentence(
            "Over the same months as the tracker, from the end of {} to the end "
            "of {}, it was {} against the tracker's {}.".format(
                month_name(common_start), month_name(common_end),
                common_volatility["display"], tracker_volatility["display"],
            ), common_volatility, tracker_volatility,
        ))
    else:
        bumpy.append(sentence(
            "Over the same months, the tracker's was {}.".format(
                tracker_volatility["display"]
            ), tracker_volatility,
        ))
    bumpy.append(sentence(_FIXED_TEXT["bumpy"]))

    fall = _required(own, "largest_fall")
    raw_drawdown = _formatted(fall, "max_drawdown", _decimal_value)
    if raw_drawdown == 0:
        worst = [sentence(
            "Since the end of {}, it has not been below a previous high at any "
            "month-end.".format(month_name(own_start))
        )]
    else:
        peak, trough = _month(fall, "peak_month"), _month(fall, "trough_month")
        drawdown = percent_claim(
            "worst.fall", "asset", "largest_fall", peak, trough, fall, "max_drawdown"
        )
        to_low = months_claim(
            "worst.months_to_low", "months_peak_to_trough", peak, trough, fall
        )
        worst = [sentence(
            "Since the end of {}, its largest fall, measured at month-end, was "
            "{}: from its high at the end of {} to its low at the end of {}, "
            "{} later.".format(
                month_name(own_start), drawdown["display"], month_name(peak),
                month_name(trough), to_low["display"],
            ), drawdown, to_low,
        )]
        left = _formatted(fall, "ten_thousand_at_trough", pounds_display)
        left_claim = claim(
            "worst.ten_thousand_left", "asset", "ten_thousand_at_trough",
            peak, trough, "gbp", left["rounded"], left["text"],
        )
        # The complement is already in whole tens: do not round the loss again.
        lost = 10000 - left["rounded"]
        lost_claim = claim(
            "worst.ten_thousand_lost", "asset", "ten_thousand_lost",
            peak, trough, "gbp", lost, "£{:,}".format(lost),
        )
        worst.append(sentence(
            "£10,000 invested at that high would have been worth {} at the low, "
            "{} less.".format(left_claim["display"], lost_claim["display"]),
            left_claim, lost_claim,
        ))
        recovered = _required(fall, "recovered")
        if type(recovered) is not bool:
            raise WordsError("Invalid field: recovered.")
        if recovered:
            recovery = _month(fall, "recovery_month")
            to_recover = months_claim(
                "worst.months_to_recover", "months_trough_to_recovery",
                trough, recovery, fall,
            )
            underwater = months_claim(
                "worst.months_underwater", "months_underwater", peak, recovery, fall
            )
            worst.append(sentence(
                "It was back at that high by the end of {}, {} after the low "
                "and {} after the high.".format(
                    month_name(recovery), to_recover["display"], underwater["display"]
                ), to_recover, underwater,
            ))
        else:
            below_high = percent_claim(
                "worst.below_high_at_end", "asset", "drawdown_at_end",
                peak, own_end, fall, "drawdown_at_end",
            )
            underwater = months_claim(
                "worst.months_underwater", "months_underwater", peak, own_end, fall
            )
            worst.append(sentence(
                "It had not recovered by the end of {}: it was still {} below "
                "its high, {} after it.".format(
                    month_name(own_end), below_high["display"], underwater["display"]
                ), below_high, underwater,
            ))
        worst.append(sentence(_FIXED_TEXT["worst"]))

    own_windows, tracker_windows = _windows(own), _windows(tracker)
    panic = []
    for name, title in _WINDOW_NAMES.items():
        for series, windows in (("asset", own_windows), ("tracker", tracker_windows)):
            window = windows[name]
            try:
                start, end = _month(window, "start"), _month(window, "end")
                covered = _required(window, "covered")
                if type(covered) is not bool:
                    raise WordsError("Invalid field: covered.")
                heading = "{} (end of {} to end of {})".format(
                    title, month_name(start), month_name(end)
                ) if series == "asset" else "The tracker"
                if not covered:
                    text = (
                        "{}: not covered; its history in pounds starts at the end "
                        "of {}.".format(heading, month_name(own_start))
                        if series == "asset" else "The tracker: not covered."
                    )
                    panic.append(sentence(text))
                    continue
                window_claim = percent_claim(
                    "panic." + name + (".tracker" if series == "tracker" else ""),
                    series, "stress_window", start, end, window, "return",
                )
                movement = (
                    "unchanged ({})".format(window_claim["display"])
                    if window_claim["direction"] == "flat"
                    else "{} {}".format(window_claim["direction"], window_claim["display"])
                )
                panic.append(sentence(
                    "{}: {} over the {}period.".format(
                        heading, movement, "same " if series == "tracker" else ""
                    ), window_claim,
                ))
            except WordsError as error:
                raise WordsError("stress_windows.{}: {}".format(name, error)) from None
    panic.append(sentence(_FIXED_TEXT["panic"]))

    return {
        "cards": [
            {"id": "bumpy", "title": "How bumpy is the ride?", "sentences": bumpy},
            {"id": "worst", "title": "What's the worst it's been?", "sentences": worst},
            {"id": "panic", "title": "What happened when markets panicked?", "sentences": panic},
        ],
        "claims": claims,
    }
