"""Golden tests for volatility and largest month-end fall."""

import unittest

from engine.risk import largest_fall, volatility
from engine.series import CoverageError, SeriesError
from golden_support import (
    assert_exact_error,
    assert_exact_value,
    assert_numeric_equal,
    build_series,
    generate_golden_tests,
    load_golden,
)


_GOLDEN = load_golden("risk.json")
_TOLERANCE = _GOLDEN["tolerance_abs"]
_POUNDS_TOLERANCE = _GOLDEN["tolerance_abs_pounds"]
_ERRORS = {
    "SeriesError": SeriesError,
    "CoverageError": CoverageError,
}
_LARGEST_FALL_KEYS = {
    "max_drawdown",
    "peak_month",
    "trough_month",
    "recovery_month",
    "recovered",
    "months_peak_to_trough",
    "months_trough_to_recovery",
    "months_underwater",
    "ten_thousand_at_trough",
    "ten_thousand_lost",
    "drawdown_at_end",
}
_POUNDS_KEYS = {"ten_thousand_at_trough", "ten_thousand_lost"}
_NUMERIC_KEYS = _POUNDS_KEYS | {"max_drawdown", "drawdown_at_end"}


class RiskGoldenTests(unittest.TestCase):
    def assert_largest_fall_equal(self, actual, expected):
        self.assertEqual(set(actual), _LARGEST_FALL_KEYS)
        self.assertEqual(set(expected), _LARGEST_FALL_KEYS)
        for key, expected_value in expected.items():
            actual_value = actual[key]
            if key in _NUMERIC_KEYS:
                tolerance = _POUNDS_TOLERANCE if key in _POUNDS_KEYS else _TOLERANCE
                assert_numeric_equal(self, actual_value, expected_value, tolerance)
            else:
                assert_exact_value(self, actual_value, expected_value)

    def exercise_case(self, case):
        series = build_series(_GOLDEN["series"][case["series"]])
        check = case["check"]

        if check == "volatility":
            calculate = lambda: volatility(series)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                assert_numeric_equal(self, calculate(), case["expected"], _TOLERANCE)
            return

        if check == "largest_fall":
            calculate = lambda: largest_fall(series)
            if "expected_error" in case:
                assert_exact_error(self, case, calculate, _ERRORS)
            else:
                self.assert_largest_fall_equal(calculate(), case["expected"])
            return

        self.fail("Unsupported golden check type: {}".format(check))


generate_golden_tests(
    RiskGoldenTests,
    _GOLDEN["cases"],
    {"volatility", "largest_fall"},
)


if __name__ == "__main__":
    unittest.main()
