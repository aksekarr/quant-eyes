"""Validated monthly series and foundational return calculations."""

import math
import re
from numbers import Real


_MONTH_PATTERN = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_BASES = frozenset(("total_return", "price", "fx_rate"))


class SeriesError(ValueError):
    """Raised when monthly series input is invalid or incomplete."""


class CoverageError(ValueError):
    """Raised when a requested calculation lacks enough covered months."""


def _month_parts(month):
    if not isinstance(month, str) or _MONTH_PATTERN.fullmatch(month) is None:
        raise ValueError("Month must use YYYY-MM with a month from 01 to 12.")
    return int(month[:4]), int(month[5:])


def _next_month(month):
    year, month_number = _month_parts(month)
    if month_number == 12:
        return "{:04d}-01".format(year + 1)
    return "{:04d}-{:02d}".format(year, month_number + 1)


class MonthlySeries:
    """An immutable, consecutive run of positive month-end values."""

    __slots__ = ("_name", "_currency", "_basis", "_months", "_values")

    def __init__(self, name, currency, basis, pairs):
        raise TypeError("Use MonthlySeries.from_pairs to build a series.")

    def __setattr__(self, name, value):
        raise AttributeError("MonthlySeries is immutable.")

    @classmethod
    def from_pairs(cls, name, currency, basis, pairs):
        """Build an immutable series, rejecting invalid, unordered, or gapped input."""
        if not isinstance(currency, str) or _CURRENCY_PATTERN.fullmatch(currency) is None:
            raise SeriesError("Currency must be a three-letter upper-case code.")
        if not isinstance(basis, str) or basis not in _BASES:
            raise SeriesError("Basis must be total_return, price, or fx_rate.")

        try:
            observations = list(pairs)
        except TypeError:
            raise SeriesError("Pairs must contain at least two observations.")

        if len(observations) < 2:
            raise SeriesError("A series must contain at least two observations.")

        months = []
        values = []
        previous_month = None

        for position, pair in enumerate(observations):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise SeriesError(
                    "Observation {} must contain one month and one value.".format(position + 1)
                )

            month, raw_value = pair
            if not isinstance(month, str) or _MONTH_PATTERN.fullmatch(month) is None:
                if isinstance(month, str):
                    raise SeriesError(
                        "Invalid month {}: expected YYYY-MM with a month from 01 to 12.".format(
                            month
                        )
                    )
                raise SeriesError(
                    "Invalid month at observation {}: expected YYYY-MM with a month from 01 to 12.".format(
                        position + 1
                    )
                )

            if previous_month is not None:
                if month == previous_month:
                    raise SeriesError("Duplicate month {}.".format(month))
                if month < previous_month:
                    raise SeriesError("Month {} is out of ascending order.".format(month))
                expected_month = _next_month(previous_month)
                if month != expected_month:
                    raise SeriesError("Missing month {}.".format(expected_month))

            if isinstance(raw_value, bool) or not isinstance(raw_value, Real):
                raise SeriesError("Month {} has a non-numeric value.".format(month))
            try:
                value = float(raw_value)
            except (OverflowError, TypeError, ValueError):
                raise SeriesError("Month {} has an invalid numeric value.".format(month))
            if not math.isfinite(value):
                raise SeriesError("Month {} has a non-finite value.".format(month))
            if value <= 0.0:
                raise SeriesError("Month {} must have a positive value.".format(month))

            months.append(month)
            values.append(value)
            previous_month = month

        series = object.__new__(cls)
        object.__setattr__(series, "_name", name)
        object.__setattr__(series, "_currency", currency)
        object.__setattr__(series, "_basis", basis)
        object.__setattr__(series, "_months", tuple(months))
        object.__setattr__(series, "_values", tuple(values))
        return series

    @property
    def name(self):
        return self._name

    @property
    def currency(self):
        return self._currency

    @property
    def basis(self):
        return self._basis

    @property
    def months(self):
        return self._months

    @property
    def values(self):
        return self._values

    @property
    def first_month(self):
        return self._months[0]

    @property
    def last_month(self):
        return self._months[-1]


def monthly_returns(series):
    """Return V(month) / V(previous month) - 1, labelled by the ending month."""
    return [
        (series.months[index], series.values[index] / series.values[index - 1] - 1.0)
        for index in range(1, len(series.months))
    ]


def period_return(series, start, end):
    """Return V(end) / V(start) - 1 between two covered month-ends."""
    try:
        start_parts = _month_parts(start)
        end_parts = _month_parts(end)
    except ValueError:
        raise ValueError("Start and end must use YYYY-MM with months from 01 to 12.")

    if start_parts >= end_parts:
        raise ValueError("Start month must be earlier than end month.")
    if start not in series.months:
        raise CoverageError("Start month {} is not covered by the series.".format(start))
    if end not in series.months:
        raise CoverageError("End month {} is not covered by the series.".format(end))

    start_index = series.months.index(start)
    end_index = series.months.index(end)
    return series.values[end_index] / series.values[start_index] - 1.0


def annualise(total_return, months):
    """Return (1 + total return) ** (12 / months) - 1 for periods of at least a year."""
    if isinstance(months, bool) or not isinstance(months, Real) or not math.isfinite(months):
        raise ValueError("Months must be a finite number.")
    if isinstance(total_return, bool) or not isinstance(total_return, Real):
        raise ValueError("Total return must be a finite number.")
    try:
        finite_return = math.isfinite(total_return)
    except (OverflowError, TypeError, ValueError):
        finite_return = False
    if not finite_return:
        raise ValueError("Total return must be a finite number.")
    if months < 12:
        raise ValueError("Periods shorter than 12 months are not annualised.")
    if total_return <= -1:
        raise ValueError("Total return must be greater than -100%.")
    return (1.0 + total_return) ** (12.0 / months) - 1.0


def common_window(a, b):
    """Cut both series to their shared months; at least two months must overlap."""
    first_month = max(a.first_month, b.first_month)
    last_month = min(a.last_month, b.last_month)

    if first_month >= last_month:
        raise CoverageError("The series share fewer than two months.")

    def cut(series):
        start_index = series.months.index(first_month)
        end_index = series.months.index(last_month) + 1
        return MonthlySeries.from_pairs(
            series.name,
            series.currency,
            series.basis,
            list(zip(series.months[start_index:end_index], series.values[start_index:end_index])),
        )

    return cut(a), cut(b)
